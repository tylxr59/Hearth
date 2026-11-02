"""Private pre-change weekly schedule archive; never a replay queue."""

import json
import os
import secrets

from backend.native import integer
from backend.native_features import schedule
from backend.registry import token_valid
from backend.reported_store import directory
from backend.validation import Invalid, serial


def archive(path, ident, generation, revision, previous):
    serial(ident)
    if not token_valid(generation):
        raise Invalid("schedule credential generation required")
    raw = json.dumps(
        {
            "format": "hearth-schedule-backup-v1",
            "serial": ident,
            "generation": generation,
            "revision": integer(revision),
            "schedule": schedule(previous),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    root = directory(path)
    name = "schedule-backup-" + secrets.token_hex(16) + ".json"
    try:
        if len([n for n in os.listdir(root) if n.startswith("schedule-backup-")]) >= 64:
            raise Invalid("archive limit reached; preserve and clear old schedule backups")
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=root,
        )
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(root)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=root)
        with os.fdopen(fd, "rb") as stream:
            if stream.read(len(raw) + 1) != raw:
                raise Invalid("schedule backup readback failed")
        return name
    finally:
        os.close(root)
