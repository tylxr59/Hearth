"""Private custody for the fixed network snapshot. No device or install API."""

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from provisioning import file_backup as custody

TARGETS = (
    "nestlabs/sbin/nlclient",
    "usr/sbin/connmand",
    "etc/connman/main.conf",
    "etc/nestlabs/client.config",
)
LIMITS = (6 * 1048576, 1048576, 65536, 65536)


@dataclass(frozen=True)
class Snapshot:
    session: bytes
    filesystem: tuple
    records: tuple


def validate(snapshot):
    if (
        not isinstance(snapshot, Snapshot)
        or type(snapshot.session) is not bytes
        or len(snapshot.session) != 32
        or type(snapshot.filesystem) is not tuple
        or len(snapshot.filesystem) != 6
        or any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF for v in snapshot.filesystem)
        or type(snapshot.records) is not tuple
        or len(snapshot.records) != 4
    ):
        raise ValueError("fixed network snapshot scope required")
    block, total, free, available, magic, _ = snapshot.filesystem
    if (
        not 512 <= block <= 65536
        or block & (block - 1)
        or block * total != 46 * 1048576
        or available > free
        or free > total
        or magic != 0x72B6
    ):
        raise ValueError("read-only root0 filesystem geometry required")
    for index, item in enumerate(snapshot.records):
        if (
            not isinstance(item, custody.CapturedFile)
            or type(item.target) is not int
            or item.target != index
            or item.existed is not True
            or type(item.mode) is not int
            or not 0 < item.mode <= 0o777
            or item.mode & 0o022
            or type(item.owner) is not int
            or type(item.group) is not int
            or item.owner != 0
            or item.group != 0
            or type(item.data) is not bytes
            or not 0 < len(item.data) <= LIMITS[index]
        ):
            raise ValueError("fixed existing network file required")


def _manifest(snapshot):
    validate(snapshot)
    return custody._canonical(
        {
            "format": "hearth-network-backup-v1",
            "session": snapshot.session.hex(),
            "source": "custom-kernel-root0; native-active-selection-unverified-by-this-reader",
            "filesystem": snapshot.filesystem,
            "files": [
                {
                    "target": item.target,
                    "path": TARGETS[item.target],
                    "mode": item.mode,
                    "owner": item.owner,
                    "group": item.group,
                    "bytes": len(item.data),
                    "sha256": hashlib.sha256(item.data).hexdigest(),
                }
                for item in snapshot.records
            ],
        }
    )


def _receipt(snapshot, manifest):
    return custody._canonical(
        {
            "format": "hearth-network-backup-receipt-v1",
            "session": snapshot.session.hex(),
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
            "restoration_verified": False,
        }
    )


def preserve(output, snapshot):
    manifest = _manifest(snapshot)
    output = Path(output)
    if output.name in ("", ".", ".."):
        raise ValueError("fresh backup destination required")
    parent = custody._open_directory(output.parent)
    directory = -1
    try:
        os.mkdir(output.name, 0o700, dir_fd=parent)
        directory = os.open(
            output.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
        )
        os.fchmod(directory, 0o700)
        os.fsync(parent)
        for item in snapshot.records:
            custody._write(directory, f"{item.target}.original", item.data)
        custody._write(directory, "manifest.json", manifest)
        os.fsync(directory)
        for item in snapshot.records:
            if (
                custody._read(directory, f"{item.target}.original", LIMITS[item.target])
                != item.data
            ):
                raise ValueError("network backup readback mismatch")
        if custody._read(directory, "manifest.json", 16384) != manifest:
            raise ValueError("network manifest readback mismatch")
        receipt = _receipt(snapshot, manifest)
        custody._write(directory, "receipt.json", receipt)
        os.fsync(directory)
        os.fsync(parent)
        return receipt
    finally:
        if directory >= 0:
            os.close(directory)
        os.close(parent)


def verify(output, snapshot):
    manifest = _manifest(snapshot)
    directory = custody._open_directory(output)
    try:
        if set(os.listdir(directory)) != {"manifest.json", "receipt.json"} | {
            f"{i}.original" for i in range(4)
        }:
            raise ValueError("network backup inventory mismatch")
        if custody._read(directory, "manifest.json", 16384) != manifest:
            raise ValueError("network backup manifest mismatch")
        for item in snapshot.records:
            if (
                custody._read(directory, f"{item.target}.original", LIMITS[item.target])
                != item.data
            ):
                raise ValueError("network original mismatch")
        receipt = _receipt(snapshot, manifest)
        if custody._read(directory, "receipt.json", 4096) != receipt:
            raise ValueError("network backup receipt mismatch")
        return receipt
    finally:
        os.close(directory)
