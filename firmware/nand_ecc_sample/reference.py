"""Read a bounded owner-private comparison reference; never execute its bytes."""

import hashlib
import json
import os
import stat
from pathlib import Path

PRIVATE_ROOT = Path(__file__).resolve().parents[2] / "private"
REFERENCE_BYTES = 64 * 2112


def private_bytes(path, limit, root):
    path = Path(path).absolute()
    root = Path(root).absolute()
    if root.is_symlink() or not path.is_relative_to(root) or path.resolve() != path:
        raise ValueError("reference must be an owner-private file without symlinks")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_mode & 0o077
            or info.st_uid != os.geteuid()
            or info.st_size > limit
        ):
            raise ValueError("bounded owner-only reference file required")
        return stream.read(limit + 1)


def read_reference(path, private_root=None):
    root = PRIVATE_ROOT if private_root is None else Path(private_root)
    path = Path(path).absolute()
    data = private_bytes(path, REFERENCE_BYTES, root)
    record = json.loads(private_bytes(path.parent / "reference.json", 16384, root))
    expected = {
        "status": "preserved-bch4-data-and-raw-oob-reference",
        "file": path.name,
        "flash_data_offset": 190 * 131072,
        "pages": 64,
        "record_bytes": 2112,
    }
    if (
        len(data) != REFERENCE_BYTES
        or not isinstance(record, dict)
        or any(type(record.get(k)) is not type(v) or record[k] != v for k, v in expected.items())
        or record.get("sha256") != hashlib.sha256(data).hexdigest()
    ):
        raise ValueError("private reference identity/scope mismatch")
    return data, record
