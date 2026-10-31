"""Bounded, private two-pass normal-ECC sample collector. Never log received payloads."""

import hashlib
import json
import os
import re
import select
import stat
import struct
import time
import zlib
from pathlib import Path

if __package__:
    from .reference import read_reference
else:
    from reference_helper import read_reference

MAGIC = b"HRTHCOR1"
FIRST_PAGE = 12160
FAILED = b"HRTHFAL1"
HEADER = struct.Struct("<8s6I")
PAGES, RECORD, PASSES = 64, 2112, 2
PRIVATE_ROOT = Path(__file__).resolve().parents[2] / "private"


class AcquisitionFailed(ValueError):
    def __init__(self, observation):
        super().__init__("device normal-ECC sample acquisition failed")
        self.observation = observation


def failure_fields(data):
    if len(data) != HEADER.size:
        raise ValueError("invalid acquisition failure length")
    magic, version, stage, pass_id, page, code, crc = HEADER.unpack(data)
    code = code if code < 2**31 else code - 2**32
    if (
        magic != FAILED
        or version != 1
        or stage not in (1, 2)
        or pass_id >= PASSES
        or not FIRST_PAGE <= page < FIRST_PAGE + PAGES
        or not -4095 <= code < RECORD
        or (stage == 1 and (page != FIRST_PAGE or code >= 0))
        or zlib.crc32(data[:-4]) != crc
    ):
        raise ValueError("invalid acquisition failure metadata")
    return {
        "stage": "open" if stage == 1 else "read",
        "pass": pass_id,
        "page": page,
        "result": code,
    }


def validate_output(output, private_root=None):
    root = PRIVATE_ROOT if private_root is None else Path(private_root)
    output = Path(output).absolute()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("private root must be a regular directory")
    if output.parent != root.absolute() or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{1,79}", output.name
    ):
        raise ValueError("fresh direct child of the private directory required")
    if output.exists() or output.is_symlink():
        raise ValueError("refusing an existing output path")
    if output.parent.resolve() != root.absolute():
        raise ValueError("private root path must not contain symlinks")
    return output


def header_fields(data):
    if len(data) != HEADER.size:
        raise ValueError("invalid sample header length")
    magic, version, pass_id, page, length, crc, header_crc = HEADER.unpack(data)
    if (
        magic != MAGIC
        or version != 1
        or pass_id >= PASSES
        or not FIRST_PAGE <= page < FIRST_PAGE + PAGES
        or length != RECORD
        or zlib.crc32(data[:-4]) != header_crc
    ):
        raise ValueError("invalid sample header")
    return pass_id, page - FIRST_PAGE, crc


def frames(fd, deadline):
    """Synchronize once, then strictly require all 128 ordered, checked records."""
    data = bytearray()
    expected = 0
    discarded = 0
    while expected < PAGES * PASSES:
        if time.monotonic() >= deadline:
            raise TimeoutError("sample stream incomplete")
        if len(data) < HEADER.size + RECORD:
            remaining = deadline - time.monotonic()
            if not select.select([fd], [], [], max(0, min(remaining, 0.5)))[0]:
                continue
            chunk = os.read(fd, 4096)
            if not chunk:
                raise OSError("sample serial stream disconnected")
            data.extend(chunk)
        if expected == 0:
            start = data.find(MAGIC)
            if start < 0:
                failed = data.find(FAILED)
                if failed >= 0 and len(data) >= failed + HEADER.size:
                    raise AcquisitionFailed(
                        failure_fields(bytes(data[failed : failed + HEADER.size]))
                    )
                discarded += max(0, len(data) - 31)
                del data[:-31]
                if discarded > 1024 * 1024:
                    raise ValueError("sample synchronization limit exceeded")
                continue
            discarded += start
            del data[:start]
            if discarded > 1024 * 1024:
                raise ValueError("sample synchronization limit exceeded")
        if len(data) < HEADER.size + RECORD:
            continue
        try:
            pass_id, page, crc = header_fields(bytes(data[: HEADER.size]))
            payload = bytes(data[HEADER.size : HEADER.size + RECORD])
            if pass_id * PAGES + page != expected:
                raise ValueError("sample record out of order")
            if zlib.crc32(payload) != crc:
                raise ValueError("sample payload CRC mismatch")
        except ValueError:
            if expected:
                raise
            del data[:1]
            discarded += 1
            continue
        del data[: HEADER.size + RECORD]
        yield pass_id, page, payload
        expected += 1


def exclusive(path):
    return os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    )


def collect(fd, deadline, output, reference, private_root=None):
    _, metadata = read_reference(reference, private_root)
    output = validate_output(output, private_root)
    output.parent.mkdir(mode=0o700, exist_ok=True)
    output.mkdir(mode=0o700)
    if not stat.S_ISDIR(output.lstat().st_mode):
        raise ValueError("regular private output directory required")
    record = {
        "status": "incomplete",
        "flash_data_offset": FIRST_PAGE * 2048,
        "pages_per_pass": PAGES,
        "page_data_bytes": 2048,
        "oob_bytes": 64,
        "ecc": "normal HW ECC read; physical OOB",
        "reference_sha256": metadata["sha256"],
        "ecc_fault_injection_tested": False,
        "driver_ecc_status_reliable": False,
        "bad_blocks": "not skipped or classified",
        "full_backup": False,
        "restoration": "unverified",
        "records_received": 0,
    }
    streams = []
    digests = [hashlib.sha256() for _ in range(PASSES)]
    try:
        for pass_id in range(PASSES):
            streams.append(exclusive(output / f"pass-{pass_id}.ecc-oob"))
        for pass_id, _, payload in frames(fd, deadline):
            streams[pass_id].write(payload)
            digests[pass_id].update(payload)
            record["records_received"] += 1
        hashes = [d.hexdigest() for d in digests]
        record["sha256"] = hashes
        record["passes_match"] = hashes[0] == hashes[1]
        record["status"] = (
            "normal-ecc-sample-matched" if hashes[0] == hashes[1] else "normal-ecc-sample-mismatch"
        )
        if hashes[0] != hashes[1]:
            raise ValueError("normal ECC sample passes differ; retained privately for review")
        record["reference_matches"] = all(h == metadata["sha256"] for h in hashes)
        if not record["reference_matches"]:
            record["status"] = "normal-ecc-reference-mismatch"
            raise ValueError(
                "normal ECC data/OOB differs from preserved reference; retained privately"
            )
        record["status"] = "normal-ecc-reference-matched"
    except AcquisitionFailed as exc:
        record["status"] = "normal-ecc-device-failed"
        record["device_failure"] = exc.observation
        raise
    finally:
        storage_error = None
        try:
            for stream in streams:
                try:
                    stream.flush()
                    os.fsync(stream.fileno())
                except OSError as exc:
                    storage_error = exc
                    record["status"] = "storage-failed"
                finally:
                    try:
                        stream.close()
                    except OSError as exc:
                        storage_error = exc
                        record["status"] = "storage-failed"
        finally:
            with exclusive(output / "capture.json") as stream:
                stream.write((json.dumps(record, sort_keys=True, indent=2) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
        directory = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        if storage_error:
            raise OSError("private sample storage did not sync") from storage_error
    return {
        "status": "normal-ecc-reference-matched",
        "reference_matched": True,
        "write_path_verified": False,
        "ecc_fault_injection_tested": False,
        "driver_ecc_status_reliable": False,
        "passes": PASSES,
        "pages_per_pass": PAGES,
        "bytes_per_pass": PAGES * RECORD,
        "storage": "private directory; not logged",
        "firmware_backup": False,
        "restoration": "unverified",
    }
