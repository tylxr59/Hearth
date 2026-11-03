"""Synthetic original NAND records; no firmware, mount or hardware."""

import struct
import zlib
from types import SimpleNamespace

import pytest

from installer.archive_discovery import View, crc, nominate

PLAN = b"p" * 32
NAME = b".hearth-rollback-" + PLAN.hex().encode()
FILES = [b"binary fixture", b"network fixture", b"clock fixture", b"legacy fourth"]
ORIGINALS = [SimpleNamespace(existed=True, data=data) for data in FILES[:3]]


def node(kind, body):
    header = struct.pack("<HHI", 0x1985, kind, 12 + len(body))
    raw = header + struct.pack("<I", crc(header)) + body
    return raw + bytes((-len(raw)) % 4)


def dirent(parent, name, ino, version=1):
    raw = bytearray(node(0xE001, bytes(28 + len(name))))
    struct.pack_into("<4I", raw, 12, parent, version, ino, 0)
    raw[28] = len(name)
    raw[40 : 40 + len(name)] = name
    struct.pack_into("<2I", raw, 32, crc(raw[:32]), crc(name))
    return bytes(raw)


def inode(ino, data, *, codec=0, version=1):
    encoded = zlib.compress(data) if codec == 6 else data
    raw = bytearray(node(0xE002, bytes(56 + len(encoded))))
    struct.pack_into("<IIIHH4I", raw, 12, ino, version, 0o100600, 0, 0, len(data), 0, 0, 0)
    struct.pack_into("<III", raw, 44, 0, len(encoded), len(data))
    raw[56] = codec
    raw[68 : 68 + len(encoded)] = encoded
    struct.pack_into("<2I", raw, 60, crc(encoded), crc(raw[:60]))
    return bytes(raw)


def archive(*, codec=0, files=None, journal=None):
    files = FILES if files is None else files
    journal = b"HFI1" + struct.pack("<3I", 6, 15, 4) + PLAN if journal is None else journal
    rows = [dirent(1, NAME, 2), dirent(2, b"journal", 3), inode(3, journal)]
    for i, data in enumerate(files):
        rows += [dirent(2, f"{i}.original".encode(), 4 + i), inode(4 + i, data, codec=codec)]
    return b"".join(rows)


@pytest.mark.parametrize("codec", (0, 6))
def test_only_exact_restored_archive_is_nominated(codec):
    row = nominate(archive(codec=codec), ORIGINALS)
    assert row["directory"] == NAME.decode()
    assert [f["bytes"] for f in row["files"]] == list(map(len, FILES))


@pytest.mark.parametrize(
    "fault", ("bytes", "missing", "unknown", "deleted", "journal", "crc", "codec")
)
def test_partial_damaged_or_mismatching_archive_is_not_reused(fault):
    data = archive()
    if fault == "bytes":
        data = archive(files=[b"wrong"] + FILES[1:])
    if fault == "missing":
        data = archive(files=FILES[:3])
    if fault == "unknown":
        data += dirent(2, b"unknown", 40)
    if fault == "deleted":
        data += dirent(2, b"0.original", 0, version=2)
    if fault == "journal":
        data = archive(journal=b"HFI1" + struct.pack("<3I", 4, 15, 4) + PLAN)
    if fault == "crc":
        data = bytearray(data)
        data[-8] ^= 1
    if fault == "codec":
        data = archive(codec=9)
    assert nominate(data, ORIGINALS) is None


def test_conflicting_equal_versions_and_out_of_bound_views_are_refused():
    with pytest.raises(ValueError, match="ambiguous"):
        View(dirent(1, NAME, 2) + dirent(1, NAME, 3))
    with pytest.raises(ValueError, match="bounded"):
        View(bytes(46 * 1048576 + 1))


def test_later_version_wins_and_older_fragments_do_not_replace_newer():
    data = archive() + inode(4, b"wrong", version=2)
    assert nominate(data, ORIGINALS) is None
