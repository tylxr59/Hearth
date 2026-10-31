"""Durable private snapshot gate; contains no USB or device write operation."""

import hashlib
import json
import os
import stat
from pathlib import Path

if __package__:
    from firmware.nand_sample.receiver import exclusive, validate_output
else:
    from raw_receiver import exclusive, validate_output

BLOCK = 1312
OFFSET = 164 * 1024 * 1024
PAGE, OOB, PAGES = 2048, 64, 64
RECORD = PAGE + OOB
SIZE = PAGES * RECORD
MARKER = bytes.fromhex("8519032008000000")
ACK_PREFIX = b"HSACK001"


def canonical(data):
    """No other contents, even an all-FF first-page OOB, are authorized."""
    if len(data) != SIZE:
        return False
    expected = bytearray(b"\xff" * SIZE)
    expected[PAGE + 2 : PAGE + 10] = MARKER
    return data == expected


def durable_snapshot(output, data, target_digest, private_root):
    """Return a digest-bound token only after saved bytes and directory sync.

    The future caller must send the returned bytes, never reconstruct a token
    on failure. Partial outputs are retained, existing outputs never reused.
    This does not cryptographically prove storage durability to the device;
    the owner-controlled host implementation enforces the ordering.
    """
    if not canonical(data) or len(target_digest) != 32:
        raise ValueError("fixed canonical scratch snapshot required")
    digest = hashlib.sha256(data).digest()
    if digest != target_digest:
        raise ValueError("snapshot does not match target digest")
    root = Path(private_root).absolute()
    output = validate_output(output, root)
    info = root.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError("owner-only private root required")
    output.mkdir(mode=0o700)
    snapshot = output / "original.raw-oob"
    with exclusive(snapshot) as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    # Independent readback before acknowledging preservation.
    with snapshot.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").digest() != digest:
            raise ValueError("saved snapshot readback mismatch")
    record = {
        "status": "scratch-original-durable-readback-verified",
        "block": BLOCK,
        "data_offset": OFFSET,
        "pages": PAGES,
        "record_bytes": RECORD,
        "bytes": SIZE,
        "sha256": digest.hex(),
        "device_written": False,
        "restoration": "unverified",
    }
    with exclusive(output / "original.json") as stream:
        stream.write((json.dumps(record, sort_keys=True, indent=2) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())
    for directory in (output, root):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    for path in (snapshot, output / "original.json"):
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError("snapshot storage permissions changed")
    return ACK_PREFIX + digest
