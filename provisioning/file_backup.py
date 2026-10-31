"""Durable, private custody of the fixed commissioning file snapshot.

No device access, target-root selection, installer or transport acknowledgment.
A future USB supervisor must bind this receipt to its own fresh snapshot/session.
"""

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

LIMIT = 1024 * 1024
TARGETS = (
    "nestlabs/lib/libnlwebservice.so",
    "etc/ssl/certs/ca-bundle.pem",
    "etc/ssl/certs/nest-crl-bundle.pem",
    "etc/ntp.conf",
    "nestlabs/lib/libhearth-settings-compat.so",
    "nestlabs/sbin/hearth-nlclient",
    "etc/init.d/nestlabs",
    "settings.config",
    "etc/nestlabs/client.config",
)


@dataclass(frozen=True)
class CapturedFile:
    target: int
    existed: bool
    mode: int
    owner: int
    group: int
    data: bytes


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _validate(records, session, plan, root):
    if (
        type(session) is not bytes
        or len(session) != 32
        or type(plan) is not bytes
        or len(plan) != 32
        or root not in ("root0", "root1")
        or len(records) != len(TARGETS)
    ):
        raise ValueError("invalid fixed snapshot scope")
    for index, item in enumerate(records):
        if (
            not isinstance(item, CapturedFile)
            or type(item.target) is not int
            or item.target != index
            or type(item.existed) is not bool
            or type(item.mode) is not int
            or not 0 <= item.mode <= 0o777
            or type(item.owner) is not int
            or type(item.group) is not int
            or item.owner != 0
            or item.group != 0
            or type(item.data) is not bytes
            or len(item.data) > LIMIT
            or (not item.existed and (index not in (4, 5) or item.mode or item.data))
        ):
            raise ValueError("invalid fixed snapshot record")


def _open_directory(path):
    """Walk every component without following links; never create ancestors."""
    path = Path(path).absolute()
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            if part in (".", ".."):
                raise ValueError("literal directory path required")
            next_fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd
            )
            os.close(fd)
            fd = next_fd
        meta = os.fstat(fd)
        if meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o700:
            raise ValueError("owner-only directory required")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _write(directory, name, data):
    fd = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
        dir_fd=directory,
    )
    try:
        os.fchmod(fd, 0o600)
        at = 0
        while at < len(data):
            count = os.write(fd, data[at:])
            if count <= 0:
                raise OSError("backup write incomplete")
            at += count
        os.fsync(fd)
    finally:
        os.close(fd)


def _read(directory, name, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
    try:
        meta = os.fstat(fd)
        if (
            not stat.S_ISREG(meta.st_mode)
            or meta.st_nlink != 1
            or meta.st_uid != os.getuid()
            or stat.S_IMODE(meta.st_mode) != 0o600
            or meta.st_size > limit
        ):
            raise ValueError("private bounded backup file required")
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, min(65536, limit + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise ValueError("backup file exceeded bound")
            chunks.append(chunk)
        if size != meta.st_size:
            raise ValueError("backup file changed during readback")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _manifest(records, session, plan, root):
    return {
        "format": "hearth-file-backup-v1",
        "session": session.hex(),
        "plan": plan.hex(),
        "native_root": root,
        "files": [
            {
                "target": item.target,
                "path": TARGETS[item.target],
                "existed": item.existed,
                "mode": item.mode,
                "owner": item.owner,
                "group": item.group,
                "bytes": len(item.data),
                "sha256": hashlib.sha256(item.data).hexdigest(),
            }
            for item in records
        ],
    }


def preserve(output, records, *, session, plan, native_root):
    """Create a fresh backup and receipt only after file/directory fsync/readback.

    Returns the private receipt, never logs snapshot data. Failed partial output
    stays intact for diagnosis and cannot be reused as a fresh destination.
    This attests host custody only, not device identity or flash restoration.
    """
    records = tuple(records)
    _validate(records, session, plan, native_root)
    output = Path(output)
    if output.name in ("", ".", ".."):
        raise ValueError("fresh output name required")
    parent = _open_directory(output.parent)
    directory = -1
    try:
        os.mkdir(output.name, 0o700, dir_fd=parent)
        directory = os.open(
            output.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
        )
        os.fchmod(directory, 0o700)
        os.fsync(parent)
        manifest = _canonical(_manifest(records, session, plan, native_root))
        for item in records:
            _write(directory, f"{item.target}.original", item.data)
        _write(directory, "manifest.json", manifest)
        os.fsync(directory)
        # Reopen every stored byte before producing a receipt.
        for item in records:
            if _read(directory, f"{item.target}.original", LIMIT) != item.data:
                raise ValueError("backup readback mismatch")
        if _read(directory, "manifest.json", 16384) != manifest:
            raise ValueError("manifest readback mismatch")
        receipt = {
            "format": "hearth-file-backup-receipt-v1",
            "session": session.hex(),
            "plan": plan.hex(),
            "native_root": native_root,
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        }
        _write(directory, "receipt.json", _canonical(receipt))
        os.fsync(directory)
        os.fsync(parent)
        return receipt
    finally:
        if directory >= 0:
            os.close(directory)
        os.close(parent)


def verify(output, records, *, session, plan, native_root):
    """Verify the whole exact private backup, not just a copied receipt token."""
    records = tuple(records)
    _validate(records, session, plan, native_root)
    directory = _open_directory(output)
    try:
        manifest = _canonical(_manifest(records, session, plan, native_root))
        expected_names = {f"{i}.original" for i in range(len(TARGETS))} | {
            "manifest.json",
            "receipt.json",
        }
        if set(os.listdir(directory)) != expected_names:
            raise ValueError("unexpected backup inventory")
        if _read(directory, "manifest.json", 16384) != manifest:
            raise ValueError("backup manifest mismatch")
        for item in records:
            if _read(directory, f"{item.target}.original", LIMIT) != item.data:
                raise ValueError("backup original mismatch")
        receipt = {
            "format": "hearth-file-backup-receipt-v1",
            "session": session.hex(),
            "plan": plan.hex(),
            "native_root": native_root,
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        }
        if _read(directory, "receipt.json", 4096) != _canonical(receipt):
            raise ValueError("backup receipt mismatch")
        return receipt
    finally:
        os.close(directory)
