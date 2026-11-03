"""Explicit reviewed reuse of a restored, exact four-file on-device archive."""

import hashlib
import json
import re
import struct

from firmware.tls_probe.package import private_read
from provisioning.network_backup import load
from tools.elf_review import private_path


def checked(path, backup, plan):
    path = private_path(path)
    raw = private_read(path, 65536)
    row = json.loads(raw)
    if not isinstance(row, dict) or set(row) != {"format", "directory", "journal", "files"}:
        raise ValueError("exact shared-original archive schema required")
    if row["format"] != "hearth-restored-network-originals-v1":
        raise ValueError("reviewed shared-original archive required")
    name = row["directory"]
    if not isinstance(name, str) or not re.fullmatch(r"\.hearth-rollback-[0-9a-f]{64}", name):
        raise ValueError("one plan-named rollback directory required")
    if not isinstance(row["journal"], str) or not re.fullmatch("[0-9a-f]{96}", row["journal"]):
        raise ValueError("exact restored journal bytes required")
    journal = bytes.fromhex(row["journal"])
    if (
        len(journal) != 48
        or struct.unpack_from("<4s3I", journal) != (b"HFI1", 6, 15, 4)
        or name != ".hearth-rollback-" + journal[16:].hex()
        or journal[16:] == bytes(32)
        or journal[16:] == plan
    ):
        raise ValueError("distinct, fully restored four-file journal required")
    files = row["files"]
    if not isinstance(files, list) or len(files) != 4:
        raise ValueError("four exact older originals required")
    snapshot = load(backup)
    for i, (entry, limit) in enumerate(
        zip(files, (6 * 1048576, 1048576, 65536, 65536), strict=True)
    ):
        if (
            not isinstance(entry, dict)
            or set(entry) != {"bytes", "sha256"}
            or type(entry["bytes"]) is not int
            or not 0 < entry["bytes"] <= limit
            or not isinstance(entry["sha256"], str)
            or not re.fullmatch("[0-9a-f]{64}", entry["sha256"])
        ):
            raise ValueError("bounded full original fingerprints required")
        if i < 3 and (
            not snapshot.records[i].existed
            or len(snapshot.records[i].data) != entry["bytes"]
            or hashlib.sha256(snapshot.records[i].data).hexdigest() != entry["sha256"]
        ):
            raise ValueError("existing archive must match all acquired cleanup originals")
    packed = name.encode().ljust(96, b"\0") + journal
    packed += struct.pack("<4I", *(f["bytes"] for f in files))
    packed += b"".join(bytes.fromhex(f["sha256"]) for f in files)
    array = lambda b: "{" + ",".join(map(str, b)) + "}"
    header = (
        "/* Private exact restored-original reference binding. */\n"
        "static const struct hn_shared_archive hearth_shared_spec={"
        + array(name.encode().ljust(96, b"\0"))
        + ","
        + array(journal)
        + ","
        + "{"
        + ",".join(str(f["bytes"]) for f in files)
        + "},"
        + "{"
        + ",".join(array(bytes.fromhex(f["sha256"])) for f in files)
        + "}};\n"
    ).encode()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "packed": packed, "header": header}
