"""One explicit owner-timed four-file protected snapshot. No retry or installer."""

import argparse
import hashlib
import json
import os
import select
import struct
import subprocess  # nosec B404
import time

from firmware.network_snapshot.profile import check
from firmware.network_snapshot.protocol import FAILURE, MAGIC, MAX_PAYLOAD, decode
from firmware.probe.observe import require_native
from firmware.settings_compat_probe.observe import observe
from firmware.startup_diagnostic.run import save
from firmware.tls_probe.package import private_read
from provisioning.network_backup import preserve, verify
from tools.elf_review import private_path


def receive_frame(fd, deadline, session, capture):
    data = bytearray()
    try:
        return _receive_frame(fd, deadline, session, capture, data)
    except (OSError, ValueError, TimeoutError):
        if not capture.exists():
            save(capture.parent, capture.name + ".partial", bytes(data))
        raise


def _receive_frame(fd, deadline, session, capture, data):
    while (remaining := deadline - time.monotonic()) > 0:
        if not select.select([fd], [], [], min(0.5, remaining))[0]:
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            raise OSError("network snapshot USB disconnected")
        data.extend(chunk)
        # A fixed failure marker is meaningful only before a binary frame.
        if FAILURE in data and MAGIC not in data:
            raise ValueError("protected network snapshot acquisition failed")
        start = data.find(MAGIC + session)
        if start < 0:
            del data[:-47]
            continue
        if start:
            del data[:start]
        if len(data) >= 48:
            size = struct.unpack_from("<I", data, 40)[0]
            if size > MAX_PAYLOAD:
                raise ValueError("network snapshot frame exceeds bound")
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
            raise ValueError("network snapshot receive bound exceeded")
    raise TimeoutError("network snapshot report incomplete; no backup receipt")


def run(root, output=None, *, execute=False):
    root = private_path(root)
    result = check(root)
    if not execute:
        return result
    if output is None:
        raise ValueError("fresh private output required")
    output = private_path(output)
    if output.exists() or output.is_symlink() or output.parent.stat().st_mode & 0o077:
        raise ValueError("fresh owner-only output required")
    require_native("1-1")
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
                "session": session.hex(),
                "profile_sha256": hashlib.sha256(
                    private_read(root / "profile.json", 65536)
                ).hexdigest(),
                "native_active_partition": "not measured by RAM reader",
            }
        ).encode(),
    )
    print(
        "PROTECTED READ-ONLY NETWORK SNAPSHOT: four fixed root0 files and filesystem space metadata. No installer, native app execution or flash writes. Keep USB connected and base detached.",
        flush=True,
    )
    print("Waiting up to 90 seconds for the reviewed manual ROM restart.", flush=True)
    artifacts = root / "artifacts"
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
        check=True,
        timeout=90,
    )

    def collect(fd, deadline, _capture):
        return receive_frame(fd, deadline, session, output / "capture.bin")

    snapshot = observe("1-1", 300, receive_fn=collect)
    preserve(output / "backup", snapshot)
    verify(output / "backup", snapshot)
    summary = {
        "status": "protected-network-snapshot-preserved",
        "targets": 4,
        "source": "custom RAM kernel root0; native selection separately confirmed",
        "flash_writes": False,
        "native_execution": False,
        "restoration": "unverified",
    }
    save(output, "observed.json", (json.dumps(summary, indent=2) + "\n").encode())
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--execute-read-only-network-snapshot", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                run(args.profile, args.output, execute=args.execute_read_only_network_snapshot),
                indent=2,
            )
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(
            1,
            "Network snapshot incomplete ("
            + type(exc).__name__
            + "). Preserve private output; no automatic retry.\n",
        )
