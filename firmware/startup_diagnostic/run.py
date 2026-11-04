"""One explicit protected RAM log/snapshot acquisition, with no serial commands."""

import argparse
import hashlib
import json
import os
import select
import stat
import struct
import subprocess  # nosec B404
import time
import zlib

from firmware.file_snapshot.run import END, MAGIC, MAX_PAYLOAD, decode
from firmware.probe import port as usb_port
from firmware.probe.observe import require_native
from firmware.settings_compat_probe.observe import observe
from firmware.startup_diagnostic.profile import check
from firmware.tls_probe.package import private_read
from provisioning import file_backup
from tools.elf_review import private_path

LOG_MAGIC, LOG_END = b"HFLOGS1\n", b"HFENDL1\n"
LOG_LIMIT = 16 + 64 * (65536 + 264)


def save(root, name, data):
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def parse_logs(payload):
    if not 16 <= len(payload) <= LOG_LIMIT:
        raise ValueError("bounded diagnostic log payload required")
    status, count, scanned, limit = struct.unpack_from("<4I", payload)
    if status not in (0, 1, 2) or count > 64 or scanned > 513 or limit != int(status == 2):
        raise ValueError("log completion fields invalid")
    rows, seen, at = [], set(), 16
    for _ in range(count):
        if len(payload) - at < 24:
            raise ValueError("truncated log metadata")
        length, mode, owner, group, total, captured = struct.unpack_from("<6I", payload, at)
        at += 24
        if (
            not 0 < length < 240
            or total > 0x7FFFFFFF
            or captured != min(total, 65536)
            or stat.S_IFMT(mode) != stat.S_IFREG
            or length + captured > len(payload) - at
        ):
            raise ValueError("log entry bound/type invalid")
        path = payload[at : at + length]
        at += length
        if (
            any(byte < 32 or byte > 126 for byte in path)
            or path.startswith(b"/")
            or any(part in (b"", b".", b"..") for part in path.split(b"/"))
            or path in seen
        ):
            raise ValueError("log entry path invalid")
        seen.add(path)
        rows.append(
            {
                "path": path.decode("ascii"),
                "mode": mode,
                "owner": owner,
                "group": group,
                "original_bytes": total,
                "data": payload[at : at + captured],
            }
        )
        at += captured
    if at != len(payload):
        raise ValueError("trailing log data")
    return {"status": status, "scanned": scanned, "limit": bool(limit), "files": rows}


def receive(fd, deadline, session, output):
    buffer, found = bytearray(), {}
    formats = {
        MAGIC: (MAX_PAYLOAD, END, "snapshot.bin"),
        LOG_MAGIC: (LOG_LIMIT, LOG_END, "logs.bin"),
    }
    while (remaining := deadline - time.monotonic()) > 0:
        if not select.select([fd], [], [], min(remaining, 0.5))[0]:
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            raise OSError("diagnostic USB disconnected")
        buffer.extend(chunk)
        while True:
            candidates = [(buffer.find(magic + session), magic) for magic in formats]
            candidates = [(at, magic) for at, magic in candidates if at >= 0]
            if not candidates:
                if b"HEARTH_SNAPSHOT_FAILED_V1\n" in buffer:
                    raise ValueError("protected snapshot failed")
                buffer = buffer[-47:]
                break
            start, magic = min(candidates)
            del buffer[:start]
            if len(buffer) < 48:
                break
            length, crc = struct.unpack_from("<II", buffer, 40)
            bound, footer, name = formats[magic]
            if length > bound:
                raise ValueError("diagnostic frame exceeds bound")
            if len(buffer) < length + 56:
                break
            frame = bytes(buffer[: length + 56])
            del buffer[: length + 56]
            if magic in found:
                if found[magic] != frame:
                    raise ValueError("cached diagnostic changed")
                continue
            save(output, name, frame)
            if frame[-8:] != footer or zlib.crc32(frame[48:-8]) != crc:
                raise ValueError("diagnostic integrity failure")
            found[magic] = frame
            if len(found) == 2:
                return decode(found[MAGIC], session), parse_logs(found[LOG_MAGIC][48:-8])
        if len(buffer) > MAX_PAYLOAD + 56:
            raise ValueError("diagnostic synchronization bound exceeded")
    raise TimeoutError("snapshot/log diagnostic incomplete; preserve private evidence")


def sealed_restore_entry(previous):
    """Read-only RAM handoff from an exited, sealed restore readback failure."""
    from firmware.file_writer import protocol
    from firmware.file_writer import run as writer

    previous = private_path(previous)
    execution = json.loads(private_read(previous / "execution.json", 65536))
    result = protocol.validate_result(private_read(previous / "result.json", 16384), 2)
    observed = json.loads(private_read(previous / "observed.json", 65536))
    if (
        json.loads(private_read(previous / "finished.json", 65536)) != {"host_command_exited": True}
        or observed != {"execution": execution, "result": result}
        or any(
            result.get(k) != v
            for k, v in {
                "action": 2,
                "initial_error": 0,
                "commit_received": 1,
                "stage_error": 0,
                "window_opened": 1,
                "rw_attempted": 3,
                "transaction_called": 1,
                "error": 0,
                "rollback_error": 0,
                "journal_error": 0,
                "cleanup_error": 0,
                "attempted": 511,
                "restored": 511,
                "committed": 0,
                "release_error": 0,
                "unmount_errors": 0,
                "seal_error": 0,
                "verified": 0,
                "safe_to_restart": 0,
                "complete": 0,
                "phase": 2,
                "protected": 1,
                "failed": 0,
                "marker": 0,
            }.items()
        )
    ):
        raise ValueError("exact exited sealed restore readback failure required")
    _, binding = writer.checked_pair(execution["profile"], execution["recovery"])
    writer.require_entry(binding, previous)
    return {"status": "sealed-restore-to-protected-readonly-diagnostic", "flash_writes": False}


def run(root, output=None, *, execute=False, recover_from=None):
    root = private_path(root)
    result = check(root)
    if not execute:
        return result
    if output is None:
        raise ValueError("fresh private output required")
    output = private_path(output)
    if output.exists() or output.is_symlink() or output.parent.stat().st_mode & 0o077:
        raise ValueError("fresh owner-only diagnostic output required")
    if recover_from is None:
        require_native(usb_port.current())
    else:
        sealed_restore_entry(recover_from)
    record = json.loads(private_read(root / "profile.json", 65536))
    session = bytes.fromhex(record["session"])
    output.mkdir(mode=0o700)
    save(
        root,
        "execution-started.json",
        json.dumps({"output": str(output), "started": time.time()}).encode(),
    )
    save(
        output,
        "execution.json",
        json.dumps(
            {
                "profile": str(root),
                "recover_from": str(private_path(recover_from))
                if recover_from is not None
                else None,
                "session": session.hex(),
                "profile_sha256": hashlib.sha256(
                    private_read(root / "profile.json", 65536)
                ).hexdigest(),
            }
        ).encode(),
    )
    print(
        "PROTECTED READ-ONLY STARTUP DIAGNOSTIC: current nine files and bounded log tails. No native execution, installer or write-capable kernel. Keep USB connected and base detached.",
        flush=True,
    )
    print("Waiting up to 90 seconds for the reviewed manual ROM restart.", flush=True)
    artifacts = root / "artifacts"
    subprocess.run(  # nosec B603
        [
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
        ],
        check=True,
        timeout=90,
    )

    def collect(fd, deadline, _capture):
        return receive(fd, deadline, session, output)

    records, logs = observe(usb_port.current(), 300, receive_fn=collect)
    scope = {
        "session": session,
        "plan": hashlib.sha256(
            b"read-only-root0-snapshot-v1\n" + "\n".join(file_backup.TARGETS).encode()
        ).digest(),
        "native_root": "root0",
    }
    file_backup.preserve(output / "backup", records, **scope)
    file_backup.verify(output / "backup", records, **scope)
    summary = {
        "status": "protected-startup-diagnostic-preserved",
        "targets": 9,
        "log_files": len(logs["files"]),
        "log_status": logs["status"],
        "log_limit_reached": logs["limit"],
        "installed": False,
        "flash_writes": False,
    }
    save(output, "observed.json", (json.dumps(summary, indent=2) + "\n").encode())
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--execute-read-only-startup-diagnostic", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                run(args.profile, args.output, execute=args.execute_read_only_startup_diagnostic),
                indent=2,
            )
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(
            1,
            "Read-only diagnostic incomplete ("
            + type(exc).__name__
            + "). Preserve private output; no automatic retry.\n",
        )
