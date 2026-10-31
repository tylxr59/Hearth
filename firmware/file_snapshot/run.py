"""Explicit one-shot protected snapshot execution; never installs or retries."""

import argparse
import hashlib
import json
import os
import select
import struct
import subprocess  # nosec B404
import sys
import time
import zlib
from pathlib import Path

from firmware.file_snapshot.prepare import RECIPES, ROOT, digest
from firmware.probe.observe import require_native
from firmware.settings_compat_probe.observe import observe
from provisioning import file_backup
from tools.elf_review import private_path

MAGIC = b"HFSNAP1\n"
END = b"HFSEND1\n"
FAILURE = b"HEARTH_SNAPSHOT_FAILED_V1\n"
MAX_PAYLOAD = 8 + 9 * (24 + file_backup.LIMIT)


def decode(frame, session):
    if len(frame) < 56 or frame[:8] != MAGIC or frame[8:40] != session:
        raise ValueError("snapshot frame/session mismatch")
    length, crc = struct.unpack_from("<II", frame, 40)
    if length > MAX_PAYLOAD or len(frame) != 48 + length + 8 or frame[-8:] != END:
        raise ValueError("snapshot frame bound/completion mismatch")
    payload = frame[48:-8]
    if zlib.crc32(payload) != crc or len(payload) < 8:
        raise ValueError("snapshot transport integrity mismatch")
    root, count = struct.unpack_from("<II", payload)
    if root != 0 or count != 9:
        raise ValueError("unexpected snapshot source/scope")
    records, at = [], 8
    for index in range(count):
        if len(payload) - at < 24:
            raise ValueError("snapshot metadata truncated")
        target, existed, mode, owner, group, size = struct.unpack_from("<6I", payload, at)
        at += 24
        if (
            target != index
            or existed not in (0, 1)
            or size > file_backup.LIMIT
            or size > len(payload) - at
        ):
            raise ValueError("snapshot record invalid")
        records.append(
            file_backup.CapturedFile(
                target, bool(existed), mode, owner, group, payload[at : at + size]
            )
        )
        at += size
    if at != len(payload):
        raise ValueError("snapshot has trailing data")
    # Reuse full host custody validation before accepting any record set.
    file_backup._validate(records, session, b"\0" * 32, "root0")
    return tuple(records)


def receive_frame(fd, deadline, session, capture):
    data = bytearray()
    while (remaining := deadline - time.monotonic()) > 0:
        if not select.select([fd], [], [], min(0.5, remaining))[0]:
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            raise OSError("snapshot USB disconnected")
        data.extend(chunk)
        # A fixed failure marker is meaningful only before a binary frame.
        if FAILURE in data and MAGIC not in data:
            raise ValueError("protected snapshot acquisition failed")
        start = data.find(MAGIC + session)
        if start < 0:
            data = data[-47:]
            continue
        if start:
            del data[:start]
        if len(data) >= 48:
            size = struct.unpack_from("<I", data, 40)[0]
            if size > MAX_PAYLOAD:
                raise ValueError("snapshot frame exceeds bound")
            total = 48 + size + 8
            if len(data) >= total:
                frame = bytes(data[:total])
                # Preserve the first complete bounded frame, including failed
                # CRC evidence. Do not relabel a later retransmission as a run.
                fd_out = os.open(
                    capture, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                with os.fdopen(fd_out, "wb") as stream:
                    stream.write(frame)
                    stream.flush()
                    os.fsync(stream.fileno())
                return decode(frame, session)
        if len(data) > MAX_PAYLOAD + 56:
            raise ValueError("snapshot receive bound exceeded")
    raise TimeoutError("snapshot report incomplete; no backup receipt")


def run(build, output=None, *, execute=False):
    build = Path(build).resolve()
    prepared = json.loads((build / "snapshot-preparation.json").read_text())
    for name in RECIPES:
        if digest(ROOT / name) != prepared["recipes"][name]:
            raise ValueError("source changed since snapshot preparation")
    # Fixed, generated checker validates config/image/bootstrap/helper bytes.
    subprocess.run([sys.executable, str(build / "check.py"), str(build)], check=True)  # nosec B603
    if not execute:
        return {"status": "offline-only", "device_executed": False}
    if output is None:
        raise ValueError("fresh private output required")
    output = private_path(output)
    if output.exists() or output.is_symlink() or output.parent.stat().st_mode & 0o077:
        raise ValueError("fresh owner-only private output required")
    require_native("1-1")
    output.mkdir(mode=0o700)
    marker = build / "execution-started"
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(b"one-shot-readonly-snapshot\n")
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(build, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    print(
        "EXPERIMENTAL READ-ONLY JFFS2 RAM SNAPSHOT: no installer or writable flash mount.",
        flush=True,
    )
    print(
        "Keep USB connected and the unwired base detached. Waiting up to 90 seconds for ROM.",
        flush=True,
    )
    artifacts = build / "artifacts"
    subprocess.run(  # nosec B603
        [
            str(artifacts / "omap_loader"),
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
        ],
        timeout=90,
        check=True,
    )
    session = bytes.fromhex(prepared["session"])

    def receive(fd_in, deadline, _capture):
        return receive_frame(fd_in, deadline, session, output / "capture.bin")

    records = observe("1-1", 300, receive_fn=receive)
    scope = {
        "session": session,
        "plan": hashlib.sha256(
            b"read-only-root0-snapshot-v1\n" + "\n".join(file_backup.TARGETS).encode()
        ).digest(),
        "native_root": "root0",
    }
    file_backup.preserve(output / "backup", records, **scope)
    file_backup.verify(output / "backup", records, **scope)
    return {
        "status": "readonly-file-snapshot-preserved",
        "targets": 9,
        "source": "custom kernel root0 view; native active root unverified",
        "installed": False,
        "restoration": "unverified",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--execute-read-only-file-snapshot", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                run(args.build, args.output, execute=args.execute_read_only_file_snapshot), indent=2
            )
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Avoid paths, raw child output, device data or credentials in errors.
        parser.exit(
            1,
            "Snapshot not confirmed ("
            + type(exc).__name__
            + "). Preserve private output; manually restart after exit. No retry.\n",
        )
