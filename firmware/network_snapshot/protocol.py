"""Strict four-file read-only frame decoder. Bytes/hashes are never logged."""

import struct
import zlib

from provisioning.file_backup import CapturedFile
from provisioning.network_backup import LIMITS, Snapshot, validate

MAGIC, END = b"HNSNAP1\n", b"HNSEND1\n"
FAILURE = b"HEARTH_NETWORK_SNAPSHOT_FAILED_V1\n"
MAX_PAYLOAD = 32 + 4 * 24 + sum(LIMITS)


def decode(frame, session):
    if type(session) is not bytes or len(session) != 32:
        raise ValueError("32-byte snapshot session required")
    if len(frame) < 56 or frame[:8] != MAGIC or frame[8:40] != session:
        raise ValueError("network snapshot frame/session mismatch")
    length, checksum = struct.unpack_from("<II", frame, 40)
    if not 128 <= length <= MAX_PAYLOAD or len(frame) != length + 56 or frame[-8:] != END:
        raise ValueError("network snapshot frame bound/completion mismatch")
    payload = frame[48:-8]
    if zlib.crc32(payload) != checksum:
        raise ValueError("network snapshot transport integrity mismatch")
    root, count, *filesystem = struct.unpack_from("<8I", payload)
    if root != 0 or count != 4:
        raise ValueError("fixed root0/four-target snapshot required")
    records, at = [], 32
    for index, limit in enumerate(LIMITS):
        if len(payload) - at < 24:
            raise ValueError("network snapshot metadata truncated")
        target, existed, mode, owner, group, size = struct.unpack_from("<6I", payload, at)
        at += 24
        if target != index or existed != 1 or not 0 < size <= limit or size > len(payload) - at:
            raise ValueError("network snapshot target/length invalid")
        records.append(CapturedFile(target, True, mode, owner, group, payload[at : at + size]))
        at += size
    if at != len(payload):
        raise ValueError("network snapshot trailing data")
    snapshot = Snapshot(session, tuple(filesystem), tuple(records))
    validate(snapshot)
    return snapshot
