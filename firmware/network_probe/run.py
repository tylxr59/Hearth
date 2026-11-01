"""Explicit protected RAM matrix/preflight; no commit or automatic retry."""

import argparse
import hashlib
import json
import os
import re
import select
import struct
import subprocess  # nosec B404
import time
import zlib

from backend.validation import loads
from firmware.network_probe.profile import check
from firmware.probe.observe import require_native
from firmware.settings_compat_probe.observe import observe
from firmware.startup_diagnostic.run import save
from firmware.tls_probe.package import private_read
from tools.elf_review import private_path

MAGIC, END = b"HNPREP1\n", b"HNPEND1\n"
LIMIT = 4096


def decode(frame, session):
    if (
        type(session) is not bytes
        or len(session) != 32
        or len(frame) < 56
        or frame[:8] != MAGIC
        or frame[8:40] != session
    ):
        raise ValueError("exact network preflight frame/session required")
    length, checksum = struct.unpack_from("<II", frame, 40)
    if (
        length > LIMIT
        or len(frame) != length + 56
        or frame[-8:] != END
        or zlib.crc32(frame[48:-8]) != checksum
    ):
        raise ValueError("network preflight transport failure")
    row = loads(frame[48:-8])
    integers = {
        "stream_cases",
        "transaction_cases",
        "child_status",
        "child_output_bytes",
        "real_files_checked",
        "phase",
    }
    if (
        not isinstance(row, dict)
        or set(row) != {"type", *integers, "real_preflight", "flash_writes", "diagnostic_hex"}
        or row["type"] != "network_ram_preflight"
        or any(type(row[k]) is not int for k in integers)
    ):
        raise ValueError("network preflight report schema differs")
    if (
        type(row["real_preflight"]) is not bool
        or row["flash_writes"] is not False
        or not 0 <= row["stream_cases"] <= 41
        or not 0 <= row["transaction_cases"] <= 20
        or not -1 <= row["child_status"] <= 65535
        or not 0 <= row["child_output_bytes"] <= 1024
        or not 0 <= row["real_files_checked"] <= 4
        or row["phase"] not in {0, 1, 2, 50, 51, 52, 53, *range(10, 30), *range(60, 64)}
        or not isinstance(row["diagnostic_hex"], str)
        or len(row["diagnostic_hex"]) != 2 * row["child_output_bytes"]
        or re.fullmatch("[0-9a-f]*", row["diagnostic_hex"]) is None
    ):
        raise ValueError("network preflight report bounds differ")
    return row


def successful(row):
    return (
        row["real_preflight"] is True
        and row["phase"] == 0
        and row["stream_cases"] == 41
        and row["transaction_cases"] == 20
        and row["child_status"] == 0
        and row["child_output_bytes"] == 0
        and row["real_files_checked"] == 4
        and row["flash_writes"] is False
    )


def receive(fd, deadline, session, output):
    data = bytearray()
    try:
        while (remaining := deadline - time.monotonic()) > 0:
            if not select.select([fd], [], [], min(remaining, 0.5))[0]:
                continue
            chunk = os.read(fd, 65536)
            if not chunk:
                raise OSError("network preflight USB disconnected")
            data.extend(chunk)
            start = data.find(MAGIC + session)
            if start < 0:
                del data[:-47]
                continue
            del data[:start]
            if len(data) < 48:
                continue
            length = struct.unpack_from("<I", data, 40)[0]
            if length > LIMIT:
                raise ValueError("network preflight frame exceeds limit")
            if len(data) >= length + 56:
                frame = bytes(data[: length + 56])
                save(output, "report.bin", frame)
                return decode(frame, session)
        raise TimeoutError("network RAM report incomplete")
    except (OSError, ValueError, TimeoutError):
        if not (output / "report.bin").exists():
            save(output, "report.partial", bytes(data[: LIMIT + 56]))
        raise


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
                "profile_sha256": hashlib.sha256(
                    private_read(root / "profile.json", 65536)
                ).hexdigest(),
                "session": session.hex(),
            }
        ).encode(),
    )
    print(
        "PROTECTED NETWORK RAM MATRIX/PREFLIGHT:61 synthetic checks then four real files read-only. No installer or flash-write kernel. Keep USB connected and base detached.",
        flush=True,
    )
    print("Waiting up to90 seconds for the reviewed manual ROM restart.", flush=True)
    a = root / "artifacts"
    subprocess.run(
        [
            str(a / "omap_loader"),
            "-f",
            str(a / "x-load-gen2.bin"),
            "-f",
            str(a / "u-boot.bin"),
            "-a",
            "0x80100000",
            "-f",
            str(a / "uImage"),
            "-a",
            "0x80a00000",
            "-j",
            "0x80100000",
        ],
        check=True,
        timeout=90,
    )  # nosec B603

    def collect(fd, deadline, _capture):
        return receive(fd, deadline, session, output)

    row = observe("1-1", 240, receive_fn=collect)
    save(output, "report.json", (json.dumps(row, indent=2) + "\n").encode())
    if not successful(row):
        raise ValueError("network RAM checks or real-file preflight refused")
    summary = {
        "status": "protected-network-ram-preflight-observed",
        "stream_cases": 41,
        "transaction_cases": 20,
        "real_files_checked": 4,
        "flash_writes": False,
        "installed": False,
        "restoration": "unverified",
    }
    save(output, "observed.json", (json.dumps(summary, indent=2) + "\n").encode())
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--execute-read-only-network-preflight", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                run(args.profile, args.output, execute=args.execute_read_only_network_preflight),
                indent=2,
            )
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(
            1,
            "Network RAM preflight incomplete ("
            + type(exc).__name__
            + "). Preserve private output; no automatic retry.\n",
        )
