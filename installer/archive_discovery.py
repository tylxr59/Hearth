"""Nominate exact restored archives from the checked NAND view, never authorize reuse.

Only the measured source root0 range is inspected. Native namespace, complete
fingerprints, inode identity, links, permissions and encoding are all checked
again by the RAM preflight before any write. Nothing is mounted or executed.
"""

import hashlib
import json
import re
import stat
import struct
import zlib

from provisioning.network_backup import load

LIMIT = 6 * 1048576


def crc(data):
    return zlib.crc32(data, 0xFFFFFFFF) ^ 0xFFFFFFFF


class View:
    def __init__(self, data):
        if len(data) > 46 * 1048576:
            raise ValueError("bounded source root0 view required")
        data = bytes(data)
        self.data, self.inodes, self.names = data, {}, {}
        at = 0
        while at + 12 <= len(data):
            if data[at : at + 2] != b"\x85\x19":
                at += 4
                continue
            _, kind, size, checksum = struct.unpack_from("<HHII", data, at)
            if (
                not 12 <= size <= 131072
                or at + size > len(data)
                or (at % 131072) + size > 131072
                or crc(data[at : at + 8]) != checksum
            ):
                at += 4
                continue
            raw = data[at : at + size]
            if kind == 0xE001 and size >= 40:
                self.dirent(raw)
            elif kind == 0xE002 and size >= 68:
                self.inode(raw)
            at += (size + 3) & ~3

    def dirent(self, raw):
        parent, version, ino = struct.unpack_from("<III", raw, 12)
        count = raw[28]
        node_crc, name_crc = struct.unpack_from("<II", raw, 32)
        name = raw[40:]
        if (
            len(name) != count
            or not count
            or b"/" in name
            or b"\0" in name
            or name in (b".", b"..")
            or crc(raw[:32]) != node_crc
            or crc(name) != name_crc
        ):
            return
        key = parent, name
        previous = self.names.get(key)
        value = version, ino
        if previous and previous[0] == version and previous != value:
            raise ValueError("ambiguous equal-version directory entry")
        if previous is None or version > previous[0]:
            self.names[key] = value

    def inode(self, raw):
        ino, version, mode = struct.unpack_from("<III", raw, 12)
        size = struct.unpack_from("<I", raw, 28)[0]
        position, compressed, expanded = struct.unpack_from("<III", raw, 44)
        data_crc, node_crc = struct.unpack_from("<II", raw, 60)
        if (
            size > LIMIT
            or expanded > LIMIT
            or position > LIMIT
            or len(raw) != 68 + compressed
            or crc(raw[:60]) != node_crc
            or crc(raw[68:]) != data_crc
        ):
            return
        row = version, mode, size, position, expanded, raw[56], raw[68:]
        versions = self.inodes.setdefault(ino, {})
        if version in versions and versions[version] != row:
            raise ValueError("ambiguous equal-version inode fragment")
        versions[version] = row

    def children(self, parent):
        return {name: ino for (p, name), (_, ino) in self.names.items() if p == parent and ino}

    def file(self, ino, maximum):
        nodes = self.inodes.get(ino, {})
        if not nodes or len(nodes) > 8192:
            raise ValueError("bounded present archive inode required")
        content = bytearray()
        for _, mode, size, offset, count, codec, raw in sorted(nodes.values()):
            if not stat.S_ISREG(mode) or size > maximum or offset + count > maximum:
                raise ValueError("bounded regular archive data required")
            if codec == 0:
                block = raw
            elif codec == 1 and not raw:
                block = bytes(count)
            elif codec == 6:
                decoder = zlib.decompressobj()
                block = decoder.decompress(raw, count + 1)
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise ValueError("bounded complete zlib fragment required")
            else:
                raise ValueError("archive nomination supports NONE/ZERO/ZLIB only")
            if len(block) != count:
                raise ValueError("exact archive fragment length required")
            del content[size:]
            if len(content) < size:
                content.extend(bytes(size - len(content)))
            if offset < size:
                content[offset : min(size, offset + count)] = block[: min(count, size - offset)]
        return bytes(content)


def nominate(data, originals):
    """Return one exact candidate or None. Ambiguity and damage refuse sharing."""
    view = View(data)
    found = []
    for name, ino in view.children(1).items():
        if not re.fullmatch(rb"\.hearth-rollback-[0-9a-f]{64}", name):
            continue
        children = view.children(ino)
        expected = {b"journal", *(f"{i}.original".encode() for i in range(4))}
        if set(children) != expected or len(set(children.values())) != 5:
            continue
        try:
            journal = view.file(children[b"journal"], 48)
            if (
                len(journal) != 48
                or struct.unpack_from("<4s3I", journal) != (b"HFI1", 6, 15, 4)
                or name != b".hearth-rollback-" + journal[16:].hex().encode()
                or journal[16:] == bytes(32)
            ):
                continue
            files = [
                view.file(children[f"{i}.original".encode()], limit)
                for i, limit in enumerate((LIMIT, 1048576, 65536, 65536))
            ]
            if any(not data for data in files) or any(
                not record.existed or record.data != files[i]
                for i, record in enumerate(originals[:3])
            ):
                continue
        except (ValueError, zlib.error):
            continue
        found.append(
            {
                "format": "hearth-restored-network-originals-v1",
                "directory": name.decode("ascii"),
                "journal": journal.hex(),
                "files": [
                    {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                    for data in files
                ],
            }
        )
    if len(found) > 1:
        raise ValueError("multiple matching rollback archives require review")
    return found[0] if found else None


def discover(session):
    from installer.nand_backup import check

    check(session)
    originals = load(session / "acquisition/network-backup").records
    with (session / "nand/analysis/pass-0-data.bin").open("rb") as source:
        source.seek(12 * 1048576)
        data = source.read(46 * 1048576)
    if len(data) != 46 * 1048576:
        raise ValueError("complete checked source root0 range required")
    row = nominate(data, originals)
    return None if row is None else (json.dumps(row, sort_keys=True) + "\n").encode()
