"""Offline installer inputs from a checked NAND archive. No mounts or device I/O.

Frames are host encodings for existing consumers, never evidence of a live read.
The provenance receipt and independent re-extraction distinguish them from USB
acquisition. Live free space is deliberately unknown (zero), not estimated here.
"""

import hashlib
import json
import secrets
import stat
import struct
import zlib

from firmware.acquisition import codec
from firmware.acquisition.run import preserve_inputs
from firmware.file_snapshot.run import END, MAGIC
from firmware.file_writer.run import encode, save
from firmware.network_snapshot import protocol
from installer.archive_discovery import View, crc
from provisioning import file_backup, network_backup
from tools.elf_review import private_path

FORMAT = "hearth-nand-installer-inputs-v1"
NAMES = (
    "capture.bin",
    "network-capture.bin",
    *(f"group-{i}.bin" for i in range(4)),
    "completion.bin",
)


class Filesystem(View):
    """Fixed-range JFFS2 reader; refuse ambiguous, incomplete or unsupported data."""

    def __init__(self, data):
        self.metadata, self.damaged, self.xattrs = {}, set(), set()
        super().__init__(data)
        at = 0
        while at + 12 <= len(data):
            if data[at : at + 2] != b"\x85\x19":
                at += 4
                continue
            _, kind, size, checksum = struct.unpack_from("<HHII", data, at)
            if (
                not 12 <= size <= 131072
                or at + size > len(data)
                or crc(data[at : at + 8]) != checksum
            ):
                at += 4
                continue
            if kind == 0xE009 and size >= 28:
                self.xattrs.add(struct.unpack_from("<I", data, at + 12)[0])
            at += (size + 3) & ~3

    def inode(self, raw):
        ino, version, mode, uid, gid, size = struct.unpack_from("<IIIHHI", raw, 12)
        offset, compressed, count = struct.unpack_from("<III", raw, 44)
        data_crc, node_crc = struct.unpack_from("<II", raw, 60)
        if (
            len(raw) != 68 + compressed
            or crc(raw[:60]) != node_crc
            or crc(raw[68:]) != data_crc
            or size > codec.FILE_LIMIT
            or offset + count > codec.FILE_LIMIT
        ):
            self.damaged.add(ino)
            return
        row = version, mode, size, offset, count, raw[56], raw[68:]
        versions = self.inodes.setdefault(ino, {})
        metadata = mode, uid, gid
        if version in versions and (
            versions[version] != row or self.metadata[ino, version] != metadata
        ):
            raise ValueError("ambiguous equal-version inode")
        versions[version] = row
        self.metadata[ino, version] = metadata

    def meta(self, ino, kind):
        # JFFS2 synthesizes inode 1 when the image has no explicit root node.
        # No other missing inode receives invented metadata or contents.
        if ino == 1 and ino not in self.inodes and kind == stat.S_IFDIR:
            return stat.S_IFDIR | 0o755, 0, 0
        if ino in self.damaged or ino in self.xattrs or not self.inodes.get(ino):
            raise ValueError("complete inode without extended attributes required")
        version = max(self.inodes[ino])
        mode, uid, gid = self.metadata[ino, version]
        if stat.S_IFMT(mode) != kind or (kind == stat.S_IFDIR and (uid or gid or mode & 0o7022)):
            raise ValueError("root-owned safe inode type and permissions required")
        return mode, uid, gid

    def lookup(self, name, *, absent=False):
        parts = name.split("/")
        if not parts or any(p in ("", ".", "..") or "\\" in p for p in parts):
            raise ValueError("literal relative input path required")
        ino = 1
        for i, part in enumerate(parts):
            self.meta(ino, stat.S_IFDIR)
            child = self.children(ino).get(part.encode("ascii"))
            if child is None:
                if absent and i == len(parts) - 1:
                    return None
                raise ValueError("required original path absent from NAND")
            ino = child
        return ino

    def contents(self, ino, maximum):
        mode, uid, gid = self.meta(ino, stat.S_IFREG)
        content, covered = bytearray(), bytearray()
        for _, _, size, offset, count, compression, raw in sorted(self.inodes[ino].values()):
            if size > maximum or offset + count > maximum:
                raise ValueError("bounded original input required")
            if compression in (0, 4):
                block = raw
            elif compression == 1 and not raw:
                block = bytes(count)
            elif compression == 6:
                decoder = zlib.decompressobj()
                block = decoder.decompress(raw, count + 1)
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise ValueError("complete bounded zlib input required")
            elif compression == 2:
                block = rtime(raw, count)
            else:
                raise ValueError("unsupported NAND input compression; no fallback read")
            if len(block) != count:
                raise ValueError("exact original fragment length required")
            del content[size:]
            del covered[size:]
            if len(content) < size:
                content.extend(bytes(size - len(content)))
                covered.extend(bytes(size - len(covered)))
            end = min(size, offset + count)
            if offset < end:
                content[offset:end] = block[: end - offset]
                covered[offset:end] = b"\1" * (end - offset)
        if not all(covered):
            raise ValueError("original has missing fragments; implicit zero fill refused")
        return bytes(content), mode & 0o7777, uid, gid

    def original(self, path, index, maximum, *, absent=False):
        ino = self.lookup(path, absent=absent)
        if ino is None:
            return file_backup.CapturedFile(index, False, 0, 0, 0, b"")
        data, mode, uid, gid = self.contents(ino, maximum)
        if uid or gid or mode & ~0o777 or mode & 0o022:
            raise ValueError("root-owned safe fixed original required")
        return file_backup.CapturedFile(index, True, mode, uid, gid, data)


def rtime(raw, count):
    positions, output, at = [0] * 256, bytearray(), 0
    while len(output) < count:
        if at + 2 > len(raw):
            raise ValueError("truncated RTIME fragment")
        value, repeat = raw[at : at + 2]
        at += 2
        output.append(value)
        back = positions[value]
        positions[value] = len(output)
        if len(output) + repeat > count:
            raise ValueError("RTIME expansion exceeds bound")
        for _ in range(repeat):
            if back >= len(output):
                raise ValueError("invalid RTIME back reference")
            output.append(output[back])
            back += 1
    if at != len(raw):
        raise ValueError("trailing RTIME bytes")
    return bytes(output)


def frame(magic, session, payload, end):
    return magic + session + struct.pack("<II", len(payload), zlib.crc32(payload)) + payload + end


def records_payload(records):
    return b"".join(
        struct.pack("<6I", r.target, r.existed, r.mode, r.owner, r.group, len(r.data)) + r.data
        for r in records
    )


def frames(root, user, session):
    rows = tuple(
        (user if i == 7 else root).original(path, i, file_backup.LIMIT, absent=i in (4, 5))
        for i, path in enumerate(file_backup.TARGETS)
    )
    network = tuple(
        root.original(path, i, limit)
        for i, (path, limit) in enumerate(
            zip(network_backup.TARGETS, network_backup.LIMITS, strict=True)
        )
    )
    result = {
        "capture.bin": frame(MAGIC, session, struct.pack("<II", 0, 9) + records_payload(rows), END),
        "network-capture.bin": frame(
            protocol.MAGIC,
            session,
            struct.pack("<8I", 0, 4, 4096, 46 * 256, 0, 0, 0x72B6, 0) + records_payload(network),
            protocol.END,
        ),
    }
    for i, prefix in enumerate(codec.GROUPS):
        parent = root.lookup(prefix)
        root.meta(parent, stat.S_IFDIR)
        children = root.children(parent)
        if len(children) > 512:
            raise ValueError("bounded input directory required")
        selected = []
        for name, ino in sorted(children.items()):
            nodes = root.inodes.get(ino)
            if not nodes:
                raise ValueError("missing directory child inode")
            if not stat.S_ISREG(nodes[max(nodes)][1]):
                continue  # Never follow links or create special nodes.
            data, mode, uid, gid = root.contents(ino, codec.FILE_LIMIT)
            selected.append(
                struct.pack("<6I", len(name), stat.S_IFREG | mode, uid, gid, len(data), len(data))
                + name
                + data
            )
        payload = struct.pack("<4I", 0, len(selected), len(children), 0) + b"".join(selected)
        if not 0 < len(selected) <= 256 or len(payload) > codec.LIMIT:
            raise ValueError("bounded complete library group required")
        result[f"group-{i}.bin"] = (
            codec.MAGIC
            + session
            + struct.pack("<3I", i, len(payload), zlib.crc32(payload))
            + payload
            + codec.END
        )
    result["completion.bin"] = codec.DONE
    return result


def from_archive(session, token):
    from installer.nand_backup import check

    check(session)
    with (session / "nand/analysis/pass-0-data.bin").open("rb") as source:
        views = []
        for offset, size in ((12, 46), (116, 8)):
            source.seek(offset * 1048576)
            data = source.read(size * 1048576)
            if len(data) != size * 1048576:
                raise ValueError("complete checked filesystem range required")
            views.append(Filesystem(data))
    return frames(*views, token)


def verify(root):
    from firmware.acquisition.custody import read

    root = private_path(root)
    receipt = json.loads(read(root / "nand-inputs.json", 4096))
    if (
        set(receipt) != {"format", "session", "quality_sha256", "live_filesystem_statistics"}
        or receipt["format"] != FORMAT
        or receipt["live_filesystem_statistics"] is not False
    ):
        raise ValueError("explicit offline NAND input provenance required")
    token = bytes.fromhex(receipt["session"])
    if (
        len(token) != 32
        or receipt["quality_sha256"]
        != hashlib.sha256(read(root.parent / "nand/analysis/quality.json", 1048576)).hexdigest()
    ):
        raise ValueError("same checked archive required")
    expected = from_archive(root.parent, token)
    for name in NAMES:
        if read(root / name, codec.LIMIT + 60) != expected[name]:
            raise ValueError("reconstructed input differs from checked NAND archive")
    return receipt


def extract(session):
    session = private_path(session)
    output = session / "acquisition"
    if output.exists():
        raise ValueError("fresh NAND input output required; no retry")
    token = secrets.token_bytes(32)
    result = from_archive(session, token)
    output.mkdir(mode=0o700)
    decoder = codec.Decoder(token, lambda name, data: save(output, name, data))
    for name in NAMES:
        data = result[name]
        for at in range(0, len(data), 65536):
            decoder.feed(data[at : at + 65536])
    preserve_inputs(output, decoder, from_nand=True)
    save(
        output,
        "nand-inputs.json",
        encode(
            {
                "format": FORMAT,
                "session": token.hex(),
                "quality_sha256": hashlib.sha256(
                    (session / "nand/analysis/quality.json").read_bytes()
                ).hexdigest(),
                "live_filesystem_statistics": False,
            }
        ),
    )
    save(output, "finished.json", encode({"host_command_exited": True}))
    return {
        "status": "nand-installer-inputs-preserved",
        "flash_writes": False,
        "device_executed": False,
    }
