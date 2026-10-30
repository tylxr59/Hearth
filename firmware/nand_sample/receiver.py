"""Bounded, private two-pass raw sample collector. Never log received payloads."""

import hashlib
import json
import os
import re
import select
import stat
import struct
import time
import zlib
from pathlib import Path

MAGIC = b"HRTHSMP1"
FAILED = b"HEARTH_RAW_SAMPLE_FAILED_V1\n"
HEADER = struct.Struct("<8s6I")
PAGES, RECORD, PASSES = 64, 2112, 2
PRIVATE_ROOT = Path(__file__).resolve().parents[2] / "private"


def validate_output(output, private_root=None):
    root = PRIVATE_ROOT if private_root is None else Path(private_root)
    output = Path(output).absolute()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("private root must be a regular directory")
    if output.parent != root.absolute() or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{1,79}", output.name
    ):
        raise ValueError("fresh direct child of the private directory required")
    if output.exists() or output.is_symlink():
        raise ValueError("refusing an existing output path")
    if output.parent.resolve() != root.absolute():
        raise ValueError("private root path must not contain symlinks")
    return output


def header_fields(data):
    if len(data) != HEADER.size:
        raise ValueError("invalid sample header length")
    magic, version, pass_id, page, length, crc, header_crc = HEADER.unpack(data)
    if (
        magic != MAGIC
        or version != 1
        or pass_id >= PASSES
        or page >= PAGES
        or length != RECORD
        or zlib.crc32(data[:-4]) != header_crc
    ):
        raise ValueError("invalid sample header")
    return pass_id, page, crc


def frames(fd, deadline):
    """Synchronize once, then strictly require all 128 ordered, checked records."""
    data = bytearray()
    expected = 0
    discarded = 0
    while expected < PAGES * PASSES:
        if time.monotonic() >= deadline:
            raise TimeoutError("sample stream incomplete")
        if len(data) < HEADER.size + RECORD:
            remaining = deadline - time.monotonic()
            if not select.select([fd], [], [], max(0, min(remaining, 0.5)))[0]:
                continue
            chunk = os.read(fd, 4096)
            if not chunk:
                raise OSError("sample serial stream disconnected")
            data.extend(chunk)
        if expected == 0:
            start = data.find(MAGIC)
            if start < 0:
                if FAILED in data:
                    raise ValueError("device sample acquisition failed")
                discarded += max(0, len(data) - 31)
                del data[:-31]
                if discarded > 1024 * 1024:
                    raise ValueError("sample synchronization limit exceeded")
                continue
            discarded += start
            del data[:start]
            if discarded > 1024 * 1024:
                raise ValueError("sample synchronization limit exceeded")
        if len(data) < HEADER.size + RECORD:
            continue
        try:
            pass_id, page, crc = header_fields(bytes(data[: HEADER.size]))
            payload = bytes(data[HEADER.size : HEADER.size + RECORD])
            if pass_id * PAGES + page != expected:
                raise ValueError("sample record out of order")
            if zlib.crc32(payload) != crc:
                raise ValueError("sample payload CRC mismatch")
        except ValueError:
            if expected:
                raise
            del data[:1]
            discarded += 1
            continue
        del data[: HEADER.size + RECORD]
        yield pass_id, page, payload
        expected += 1


def exclusive(path):
    return os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    )


def collect(fd, deadline, output, private_root=None):
    output = validate_output(output, private_root)
    output.parent.mkdir(mode=0o700, exist_ok=True)
    output.mkdir(mode=0o700)
    if not stat.S_ISDIR(output.lstat().st_mode):
        raise ValueError("regular private output directory required")
    record = {
        "status": "incomplete",
        "raw_nand_offset": 0,
        "pages_per_pass": PAGES,
        "page_data_bytes": 2048,
        "oob_bytes": 64,
        "ecc": "raw; uncorrected",
        "bad_blocks": "not skipped or classified",
        "full_backup": False,
        "restoration": "unverified",
        "records_received": 0,
    }
    streams = []
    digests = [hashlib.sha256() for _ in range(PASSES)]
    try:
        for pass_id in range(PASSES):
            streams.append(exclusive(output / f"pass-{pass_id}.raw"))
        for pass_id, _, payload in frames(fd, deadline):
            streams[pass_id].write(payload)
            digests[pass_id].update(payload)
            record["records_received"] += 1
        hashes = [d.hexdigest() for d in digests]
        record["sha256"] = hashes
        record["passes_match"] = hashes[0] == hashes[1]
        record["status"] = "raw-sample-matched" if hashes[0] == hashes[1] else "raw-sample-mismatch"
        if hashes[0] != hashes[1]:
            raise ValueError("raw sample passes differ; retained privately for review")
    finally:
        storage_error = None
        try:
            for stream in streams:
                try:
                    stream.flush()
                    os.fsync(stream.fileno())
                except OSError as exc:
                    storage_error = exc
                    record["status"] = "storage-failed"
                finally:
                    try:
                        stream.close()
                    except OSError as exc:
                        storage_error = exc
                        record["status"] = "storage-failed"
        finally:
            with exclusive(output / "capture.json") as stream:
                stream.write((json.dumps(record, sort_keys=True, indent=2) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
        directory = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        if storage_error:
            raise OSError("private sample storage did not sync") from storage_error
    return {
        "status": "raw-sample-matched",
        "passes": PASSES,
        "pages_per_pass": PAGES,
        "bytes_per_pass": PAGES * RECORD,
        "storage": "private directory; not logged",
        "firmware_backup": False,
        "restoration": "unverified",
    }
