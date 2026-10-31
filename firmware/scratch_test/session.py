"""Bounded draft duplex protocol; host-only synthetic testing, not an installer."""

import hashlib
import json
import os
import select
import struct
import time
import zlib

if __package__:
    from firmware.nand_sample.receiver import exclusive
    from firmware.scratch_test import backup, ecc
else:
    import backup_helper as backup
    import ecc_helper as ecc
    from raw_receiver import exclusive

MAGIC = b"HRTHSWR1"
HEADER = struct.Struct("<8s6I")
META = struct.Struct("<8s14I32s32s")
WIRE_BYTES = 128 + 2 * backup.SIZE + 2 * backup.RECORD


def read_exact(fd, count, deadline):
    data = bytearray()
    while len(data) < count:
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("scratch protocol incomplete")
        if not select.select([fd], [], [], min(left, 0.5))[0]:
            continue
        try:
            chunk = os.read(fd, count - len(data))
        except BlockingIOError:
            continue
        if not chunk:
            raise OSError("scratch serial disconnected")
        data.extend(chunk)
    return bytes(data)


def send_exact(fd, data, deadline):
    done = 0
    while done < len(data):
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("scratch control transfer incomplete")
        if not select.select([], [fd], [], min(left, 0.5))[1]:
            continue
        try:
            count = os.write(fd, data[done:])
        except BlockingIOError:
            continue
        if count <= 0:
            raise OSError("scratch control transfer stopped")
        done += count


def receive(fd, stage, deadline):
    prefix = read_exact(fd, 8, deadline)
    discarded = 0
    while prefix != MAGIC and stage == 1 and discarded < 4096:
        prefix = prefix[1:] + read_exact(fd, 1, deadline)
        discarded += 1
    header = prefix + read_exact(fd, HEADER.size - 8, deadline)
    magic, version, received_stage, length, crc, reserved, header_crc = HEADER.unpack(header)
    if (
        magic != MAGIC
        or version != 1
        or received_stage != stage
        or length != WIRE_BYTES
        or reserved != 0
        or zlib.crc32(header[:-4]) != header_crc
    ):
        raise ValueError("invalid scratch frame header")
    data = read_exact(fd, WIRE_BYTES, deadline)
    if zlib.crc32(data) != crc:
        raise ValueError("scratch frame payload CRC mismatch")
    return data


def split(data):
    if len(data) != WIRE_BYTES:
        raise ValueError("invalid fixed scratch snapshot length")
    meta = META.unpack(data[: META.size])
    if meta[0] != b"HRTHSCR1" or meta[1] != 1 or meta[13:15] != (backup.BLOCK, backup.SIZE):
        raise ValueError("invalid scratch identity or scope")
    original_end = META.size + backup.SIZE
    raw_end = original_end + backup.RECORD
    normal_end = raw_end + backup.RECORD
    return (
        meta,
        data[META.size : original_end],
        data[original_end:raw_end],
        data[raw_end:normal_end],
        data[normal_end:],
    )


def transact(fd, deadline, output, private_root, mask):
    """The only post-start control message is the durable digest token.

    No target instruction follows the ACK: cleanup is synchronous on target and
    must not depend on the host staying connected. Any ambiguity remains failure.
    """
    output = backup.validate_output(output, private_root)
    record = {"status": "incomplete", "write_may_have_executed": False, "restoration": "unverified"}
    try:
        if len(mask) != 7:
            raise ValueError("private BCH4 storage mask required")
        send_exact(fd, b"HSBEGIN1", deadline)
        prepared = receive(fd, 1, deadline)
        meta, original, raw, normal, final = split(prepared)
        if meta[2:13] != (2, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0):
            raise ValueError("target did not prepare a protected unused transaction")
        if any(raw) or any(normal) or any(final) or any(meta[16]):
            raise ValueError("prepared transaction already contains execution results")
        ack = backup.durable_snapshot(output, original, meta[15], private_root)
        # Mark uncertainty BEFORE attempting the first ACK byte. Never retry.
        record["write_may_have_executed"] = True
        send_exact(fd, ack, deadline)
        completed = receive(fd, 2, deadline)
        with exclusive(output / "result.bin") as stream:
            stream.write(completed)
            stream.flush()
            os.fsync(stream.fileno())
        done, saved, raw, normal, restored = split(completed)
        if done[2:13] != (5, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0):
            raise ValueError("scratch target did not report complete protected restoration")
        if (
            saved != original
            or restored != original
            or done[15] != meta[15]
            or done[16] != meta[15]
            or hashlib.sha256(restored).digest() != meta[15]
        ):
            raise ValueError("scratch restoration differs from preserved original")
        record.update(ecc.validate_programmed(raw, normal, mask))
        record.update(status="scratch-transaction-validated", restoration="exact fixed block only")
    finally:
        if output.exists():
            with exclusive(output / "attempt.json") as stream:
                stream.write((json.dumps(record, sort_keys=True, indent=2) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
            fd_dir = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(fd_dir)
            finally:
                os.close(fd_dir)
    return record
