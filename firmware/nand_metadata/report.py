"""Bounded, non-identifying geometry report parser; no firmware data transport."""

import os
import re
import select
import time

START = b"HEARTH_NAND_METADATA_V1\n"
END = b"END_HEARTH_NAND_METADATA\n"
FIELDS = {"source", "name", "type", "flags", "size", "erasesize", "writesize", "oobsize"}


def parse(data):
    if len(data) > 1024 or not data.startswith(START) or not data.endswith(END):
        raise ValueError("invalid geometry frame")
    try:
        rows = data[len(START) : -len(END)].decode("ascii").splitlines()
    except UnicodeError as exc:
        raise ValueError("invalid geometry encoding") from exc
    fields = {}
    for row in rows:
        key, separator, value = row.partition("=")
        if separator != "=" or key in fields or key not in FIELDS or not 0 < len(value) <= 80:
            raise ValueError("invalid or duplicate geometry field")
        fields[key] = value
    if set(fields) != FIELDS or fields["source"] != "custom-ram-kernel":
        raise ValueError("unexpected geometry source/fields")
    if fields["type"] != "nand" or not re.fullmatch(r"[A-Za-z0-9 ._()+/-]{1,80}", fields["name"]):
        raise ValueError("NAND master was not registered; geometry unavailable")
    if not re.fullmatch(r"0x[0-9a-fA-F]{1,8}", fields["flags"]) or int(fields["flags"], 16) != 0:
        raise ValueError("read-only NAND capability flags were not observed")
    values = {}
    for key in ("size", "erasesize", "writesize", "oobsize"):
        if not re.fullmatch(r"[0-9]{1,12}", fields[key]):
            raise ValueError("invalid numeric geometry field")
        values[key] = int(fields[key])
    total, erase, page, oob = (values[k] for k in ("size", "erasesize", "writesize", "oobsize"))
    if not (
        0 < total <= 2**34
        and 256 <= page <= 16384
        and page <= erase <= 2**24
        and 0 < oob <= 4096
        and total % erase == 0
        and erase % page == 0
        and page & (page - 1) == 0
        and erase & (erase - 1) == 0
    ):
        raise ValueError("inconsistent NAND geometry")
    return {
        "status": "nand-geometry-observed",
        "source": "custom RAM kernel master, not stock partition map",
        "name": fields["name"],
        "flags": 0,
        **values,
        "registration_guard": "required protected NAND status",
        "firmware_acquired": False,
        "restoration": "unverified",
    }


def receive(fd, deadline):
    data = b""
    while (remaining := deadline - time.monotonic()) > 0:
        if not select.select([fd], [], [], min(remaining, 0.5))[0]:
            continue
        chunk = os.read(fd, 1024)
        if not chunk:
            raise OSError("serial device disconnected")
        data = (data + chunk)[-8192:]
        normalized = data.replace(b"\r\n", b"\n")
        start = normalized.rfind(START)
        if start >= 0 and (end := normalized.find(END, start)) >= 0:
            return parse(normalized[start : end + len(END)])
    raise TimeoutError("geometry report not observed")
