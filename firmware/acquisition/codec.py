"""Bounded, ordered, private acquisition frames. Data only; no executable loading."""

import struct
import zlib
from dataclasses import dataclass
from pathlib import PurePosixPath

from firmware.file_snapshot.run import MAGIC as SNAP_MAGIC
from firmware.file_snapshot.run import MAX_PAYLOAD
from firmware.file_snapshot.run import decode as decode_snapshot
from firmware.network_snapshot import protocol as network

MAGIC = b"HACQLIB1"
END = b"HACQEND1"
DONE = b"HACQDONE"
FAILURE = b"HEARTH_ACQUISITION_FAILED_V1\n"
GROUPS = ("lib", "usr/lib", "nestlabs/lib", "nestlabs/sbin")
LIMIT = 16 * 1024 * 1024
FILE_LIMIT = 8 * 1024 * 1024


@dataclass(frozen=True)
class AcquiredFile:
    path: str
    mode: int
    owner: int
    group: int
    data: bytes


def decode_group(payload, prefix):
    if prefix not in GROUPS or not isinstance(payload, bytes) or not 16 <= len(payload) <= LIMIT:
        raise ValueError("bounded acquisition group required")
    status, count, scanned, limited = struct.unpack_from("<4I", payload)
    if status or limited or not 0 < count <= 256 or not count <= scanned <= 512:
        raise ValueError("complete bounded acquisition required")
    files, paths, at = [], set(), 16
    for _ in range(count):
        if len(payload) - at < 24:
            raise ValueError("truncated acquisition metadata")
        length, mode, owner, group, size, captured = struct.unpack_from("<6I", payload, at)
        at += 24
        if (
            not 0 < length < 240
            or mode & 0o170000 != 0o100000
            or size != captured
            or not 0 <= size <= FILE_LIMIT
            or length + size > len(payload) - at
        ):
            raise ValueError("regular complete acquisition file required")
        raw = payload[at : at + length]
        at += length
        if any(c < 32 or c > 126 for c in raw) or b"\\" in raw:
            raise ValueError("bounded acquisition path required")
        name = raw.decode("ascii")
        if (
            any(part in ("", ".", "..") for part in name.split("/"))
            or str(PurePosixPath(name)) != name
        ):
            raise ValueError("relative canonical acquisition path required")
        path = prefix + "/" + name
        if path in paths:
            raise ValueError("duplicate acquisition path")
        paths.add(path)
        files.append(AcquiredFile(path, mode, owner, group, payload[at : at + size]))
        at += size
    if at != len(payload):
        raise ValueError("trailing acquisition data")
    return tuple(files)


class Decoder:
    """Consume each frame once; persist bounded raw evidence before decoding it."""

    def __init__(self, session, preserve):
        if type(session) is not bytes or len(session) != 32:
            raise ValueError("fresh acquisition session required")
        self.session, self.preserve = session, preserve
        self.buffer = bytearray()
        self.snapshot, self.files = None, []
        self.network = None
        self.group, self.complete = 0, False

    def feed(self, chunk):
        if not isinstance(chunk, bytes) or len(chunk) > 65536 or self.complete:
            raise ValueError("bounded acquisition chunk required before completion")
        self.buffer.extend(chunk)
        if len(self.buffer) > LIMIT + 65600:
            raise ValueError("acquisition buffer limit")
        while True:
            if self.snapshot is None:
                if self.buffer.startswith(FAILURE):
                    raise ValueError("device acquisition failed")
                if len(self.buffer) < 48:
                    return
                if self.buffer[:8] != SNAP_MAGIC or self.buffer[8:40] != self.session:
                    raise ValueError("snapshot session mismatch")
                length = struct.unpack_from("<I", self.buffer, 40)[0]
                if length > MAX_PAYLOAD:
                    raise ValueError("snapshot frame bound")
                total = 56 + length
                if len(self.buffer) < total:
                    return
                frame = bytes(self.buffer[:total])
                del self.buffer[:total]
                self.preserve("capture.bin", frame)
                self.snapshot = decode_snapshot(frame, self.session)
            elif self.network is None:
                if self.buffer.startswith(FAILURE):
                    raise ValueError("device acquisition failed")
                if len(self.buffer) < 48:
                    return
                if self.buffer[:8] != network.MAGIC or self.buffer[8:40] != self.session:
                    raise ValueError("network snapshot session mismatch")
                length = struct.unpack_from("<I", self.buffer, 40)[0]
                if not 128 <= length <= network.MAX_PAYLOAD:
                    raise ValueError("network snapshot bound")
                total = 56 + length
                if len(self.buffer) < total:
                    return
                frame = bytes(self.buffer[:total])
                del self.buffer[:total]
                self.preserve("network-capture.bin", frame)
                self.network = network.decode(frame, self.session)
                if self.network.records[3] != type(self.network.records[3])(
                    3,
                    self.snapshot[8].existed,
                    self.snapshot[8].mode,
                    self.snapshot[8].owner,
                    self.snapshot[8].group,
                    self.snapshot[8].data,
                ):
                    raise ValueError("overlapping client configuration differs within acquisition")
            elif self.group < len(GROUPS):
                if self.buffer.startswith(FAILURE):
                    raise ValueError("device acquisition failed")
                if len(self.buffer) < 52:
                    return
                if self.buffer[:8] != MAGIC or self.buffer[8:40] != self.session:
                    raise ValueError("acquisition session mismatch")
                group, length, crc = struct.unpack_from("<3I", self.buffer, 40)
                if group != self.group or not 16 <= length <= LIMIT:
                    raise ValueError("ordered bounded acquisition group required")
                total = 60 + length
                if len(self.buffer) < total:
                    return
                frame = bytes(self.buffer[:total])
                del self.buffer[:total]
                self.preserve(f"group-{group}.bin", frame)
                payload = frame[52:-8]
                if frame[-8:] != END or zlib.crc32(payload) != crc:
                    raise ValueError("acquisition frame integrity failure")
                self.files.extend(decode_group(payload, GROUPS[group]))
                self.group += 1
            else:
                if len(self.buffer) < 8:
                    return
                if bytes(self.buffer) != DONE:
                    raise ValueError("exact acquisition completion required")
                self.preserve("completion.bin", bytes(self.buffer))
                self.buffer.clear()
                self.complete = True
                return
