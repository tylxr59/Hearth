"""Bounded non-identifying controller contract; no data acquisition or writes."""

import os
import re
import select
import time

if __package__:
    from firmware.nand_metadata import report as geometry
else:
    import geometry_report as geometry

START = b"HEARTH_NAND_CONTRACT_V1\n"
END = b"END_HEARTH_NAND_CONTRACT\n"
NUMERIC = {
    "protected",
    "bus_width",
    "badblock_position",
    "scan_second_page",
    "scan_last_page",
    "scan_byte1_and6",
    "pattern_present",
    "pattern_offset",
    "pattern_length",
    "pattern_options",
    "ecc_mode",
    "ecc_size",
    "ecc_bytes",
    "ecc_steps",
    "ecc_total",
    "oob_free_offset",
    "oob_free_length",
}


def parse(data):
    if len(data) > 1536 or not data.startswith(START) or not data.endswith(END):
        raise ValueError("invalid controller metadata frame")
    try:
        rows = data[len(START) : -len(END)].decode("ascii").splitlines()
    except UnicodeError as exc:
        raise ValueError("invalid controller metadata encoding") from exc
    fields = {}
    for row in rows:
        key, sep, value = row.partition("=")
        if sep != "=" or key in fields or not 0 < len(value) <= 200:
            raise ValueError("invalid/duplicate controller metadata")
        fields[key] = value
    if set(fields) != geometry.FIELDS | NUMERIC | {"ecc_positions"}:
        raise ValueError("missing/unexpected controller metadata")
    old = (
        geometry.START
        + "".join(f"{k}={fields[k]}\n" for k in sorted(geometry.FIELDS)).encode()
        + geometry.END
    )
    result = geometry.parse(old)
    if tuple(result[k] for k in ("size", "erasesize", "writesize", "oobsize")) != (
        268435456,
        131072,
        2048,
        64,
    ):
        raise ValueError("previously measured unit geometry differs")
    numbers = {}
    for key in NUMERIC:
        if not re.fullmatch(r"[0-9]{1,10}", fields[key]):
            raise ValueError("invalid controller numeric metadata")
        numbers[key] = int(fields[key])
    expected = {
        "protected": 1,
        "badblock_position": 0,
        "ecc_mode": 2,
        "ecc_size": 2048,
        "ecc_bytes": 28,
        "ecc_steps": 1,
        "ecc_total": 28,
        "oob_free_offset": 2 if numbers["bus_width"] == 16 else 1,
        "oob_free_length": 34 if numbers["bus_width"] == 16 else 35,
        "pattern_present": 0 if numbers["bus_width"] == 16 else 1,
        "pattern_offset": 0,
        "pattern_length": 0 if numbers["bus_width"] == 16 else 1,
        "pattern_options": 0 if numbers["bus_width"] == 16 else 0xC00,
    }
    if (
        any(numbers[k] != v for k, v in expected.items())
        or numbers["bus_width"] not in (8, 16)
        or any(
            numbers[k] not in (0, 1)
            for k in ("scan_second_page", "scan_last_page", "scan_byte1_and6")
        )
    ):
        raise ValueError("controller contract differs from reviewed BCH4 layout")
    if fields["ecc_positions"] != ",".join(str(n) for n in range(36, 64)):
        raise ValueError("unexpected OOB ECC layout")
    return result | {
        "status": "nand-readonly-contract-observed",
        **numbers,
        "ecc_positions": list(range(36, 64)),
        "write_path_verified": False,
    }


def receive(fd, deadline):
    data = b""
    while (remaining := deadline - time.monotonic()) > 0:
        if not select.select([fd], [], [], min(remaining, 0.5))[0]:
            continue
        chunk = os.read(fd, 1536)
        if not chunk:
            raise OSError("serial device disconnected")
        data = (data + chunk)[-8192:]
        normalized = data.replace(b"\r\n", b"\n")
        start = normalized.rfind(START)
        if start >= 0 and (end := normalized.find(END, start)) >= 0:
            return parse(normalized[start : end + len(END)])
    raise TimeoutError("controller metadata not observed")
