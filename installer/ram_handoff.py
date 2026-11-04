"""Evidence-bound, one-shot backup-to-successor boot. Never retries or commits."""

import contextlib
import json
import os
import pty
import select
import subprocess  # nosec B404
import time
from pathlib import Path

from firmware.file_writer.run import encode, save, write_token
from firmware.nand_handoff import profile
from firmware.probe import port as usb_port
from firmware.settings_compat_probe.observe import observe
from firmware.tls_probe.package import MAX_IMAGE, private_read, sha
from installer import ui
from tools.elf_review import private_path

SCANNING = b"scanning for USB device matching 0451:d00e"
MAX_LOG = 1048576


def loader_args(artifacts):
    artifacts = Path(artifacts)
    return [
        str(artifacts / "omap_loader"),
        "-P",
        usb_port.current(),
        "-f",
        str(artifacts / "x-load-gen2.bin"),
        "-f",
        str(artifacts / "u-boot.bin"),
        "-a",
        "0x80100000",
        "-f",
        str(artifacts / "uImage"),
        "-a",
        "0x80a00000",
        "-j",
        "0x80100000",
    ]


def transfer(fd, nonce, artifacts, output, source):
    """Wait for a live loader's flushed PTY message before the one restart."""
    master, slave = pty.openpty()
    process = None
    log_fd = -1
    pending = bytearray()
    sent = False
    restart_attempted = False
    deadline = time.monotonic() + 90
    try:
        log_fd = os.open(
            output / "handoff-loader.log",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        process = subprocess.Popen(
            loader_args(artifacts),
            stdin=subprocess.DEVNULL,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
        )  # nosec B603
        os.close(slave)
        slave = -1
        save(output, "handoff-loader-started.json", encode({"pid": process.pid, "once": True}))
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    chunk = os.read(master, 8192)
                except OSError as exc:
                    if exc.errno != 5:
                        raise
                    chunk = b""
                if chunk:
                    if len(pending) + len(chunk) > MAX_LOG:
                        raise ValueError("bounded successor loader log required")
                    pending.extend(chunk)
                    at = 0
                    while at < len(chunk):
                        n = os.write(log_fd, chunk[at:])
                        if n <= 0:
                            raise OSError("successor log write failed")
                        at += n
                    os.fsync(log_fd)
                    # Forward only progress from the already checked loader.
                    print(chunk.decode(errors="replace"), end="", flush=True)
            if not sent and SCANNING in pending:
                if process.poll() is not None:
                    raise ValueError("successor loader exited before restart")
                intent = {
                    "source_profile": str(source),
                    "successor_artifacts": str(artifacts),
                    "successor_image_sha256": sha(private_read(artifacts / "uImage", MAX_IMAGE)),
                    "once": True,
                }
                save(
                    output,
                    "handoff-loader-ready.json",
                    encode({"pid": process.pid, "scanning_observed": True}),
                )
                # Consumes the old reader even if this token's delivery fails.
                save(output, "restart-sending.json", encode(intent))
                save(source.parent / "nand", "restart-sending.json", encode(intent))
                restart_attempted = True
                write_token(fd, b"HNBRST1\n" + nonce)
                sent = True
                save(output, "restart-sent.json", encode(intent))
                ui.say("Software restart requested. Leave the ring untouched.")
            code = process.poll()
            if code is not None:
                if not sent or code != 0:
                    raise ValueError("successor transfer failed; preserve evidence, no retry")
                save(
                    output,
                    "handoff-transfer-finished.json",
                    encode(
                        {"loader_exited": True, "returncode": 0, "second_image_ready": "pending"}
                    ),
                )
                return {"restart_sent": True, "loader_transfer_complete": True}
            if not sent and time.monotonic() > deadline - 80:
                raise TimeoutError("successor loader did not become ready; no restart sent")
        raise TimeoutError("successor transfer timed out; no retry")
    finally:
        if process is not None and process.poll() is None:
            if restart_attempted:
                # A failed/partial token or interrupted host is uncertain.
                # Allow this one bounded boot to finish and drain its PTY;
                # never interrupt it early or start a replacement loader.
                while process.poll() is None and time.monotonic() < deadline:
                    if select.select([master], [], [], 0.2)[0]:
                        with contextlib.suppress(OSError):
                            os.read(master, 8192)
            # Same bound as the ordinary loader subprocess. Never start another.
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        if slave >= 0:
            os.close(slave)
        os.close(master)
        if log_fd >= 0:
            os.close(log_fd)


def _source(previous):
    """The checked, never-restarted reader endpoint of this exact backup."""
    from installer.nand_backup import require_handoff

    previous = private_path(previous)
    session = previous.parent
    require_handoff(previous, session)
    execution = json.loads(private_read(previous / "execution.json", 65536))
    source = private_path(execution["handoff_profile"])
    if source != session / "nand-handoff-reader" or (previous / "restart-sending.json").exists():
        raise ValueError("fresh, same-session restartable reader required; no second restart")
    profile.check(source)
    row = json.loads(private_read(source / "profile.json", 65536))
    return source, bytes.fromhex(row["session"])


def _wait_nonce(fd, deadline, nonce):
    buffer = b""
    while time.monotonic() < deadline:
        if not select.select([fd], [], [], 0.1)[0]:
            continue
        chunk = os.read(fd, 4096)
        if not chunk:
            raise OSError("backup restart interface disconnected")
        buffer = (buffer + chunk)[-8192:]
        if b"HNBRDY1\n" + nonce in buffer:
            return
    raise TimeoutError("exact backup restart readiness not received; no token sent")


def await_ready(previous, *, seconds=20):
    """Read-only: confirm the backup reader still answers. Sends nothing, writes nothing.

    The reader repeats its readiness line and ignores a closed host tty, so this
    check leaves it waiting exactly as before. Callers use it before consuming
    one-use profiles, so a disconnected or reset Nest never uses up a kit.
    """
    _, nonce = _source(previous)
    observe(
        usb_port.current(),
        seconds,
        receive_fn=lambda fd, deadline, _c: _wait_nonce(fd, deadline, nonce),
    )
    return {"backup_reader_ready": True, "restart_sent": False}


def load(artifacts, output, previous, *, recheck):
    """Called only inside an owner-approved install after all kit/backup checks."""
    artifacts, output, previous = map(private_path, (artifacts, output, previous))
    source, nonce = _source(previous)
    recheck()

    def ready(fd, deadline, _capture):
        _wait_nonce(fd, deadline, nonce)
        save(
            output,
            "backup-restart-ready.json",
            encode({"nonce_verified": True, "source_profile": str(source)}),
        )
        return transfer(fd, nonce, artifacts, output, source)

    return observe(usb_port.current(), 20, receive_fn=ready)
