"""Offline exact-span plans bound to verified four-file custody. No device API."""

import hashlib
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from backend.validation import loads
from provisioning import file_backup as custody
from provisioning import network_backup
from provisioning.native_network import (
    FixedSpan,
    connman_time_candidate,
    connman_time_config,
    probe_candidate,
    registration_candidate,
)
from provisioning.time_server import DEFAULT, time_server


@dataclass(frozen=True)
class Plan:
    target: int
    size: int
    span: FixedSpan
    original_hash: bytes
    replacement_hash: bytes

    def binary(self):
        return struct.pack(
            "<4I64s64s32s32s",
            self.target,
            self.size,
            self.span.offset,
            len(self.span.original),
            self.span.original,
            self.span.replacement,
            self.original_hash,
            self.replacement_hash,
        )


def make_plan(target, original, span):
    if (
        type(target) is not int
        or not 0 <= target < 4
        or type(original) is not bytes
        or not 0 < len(original) <= network_backup.LIMITS[target]
        or not isinstance(span, FixedSpan)
    ):
        raise ValueError("fixed bounded network target required")
    replacement = span.apply(original)
    if replacement == original:
        raise ValueError("a concrete reviewed change required")
    return Plan(
        target,
        len(original),
        span,
        hashlib.sha256(original).digest(),
        hashlib.sha256(replacement).digest(),
    )


def _array(data):
    return "{" + ",".join(str(b) for b in data) + "}"


def header(plans, modes, plan_id, receipt_id, *, custom_time=None):
    count = len(plans) + (1 if custom_time else 0)
    if count not in (3, 4) or len(modes) != count or (custom_time and len(plans) != 2):
        raise ValueError("fixed three- or four-file network scope required")
    lines = ["/* PRIVATE generated fixed DATA, not an executable or authorization. */"]
    lines += [f"static const struct hn_plan hn_plans[{len(plans)}]={{"]
    for item in plans:
        lines.append(
            "{"
            + ",".join(
                (
                    str(item.target),
                    str(item.size),
                    str(item.span.offset),
                    str(len(item.span.original)),
                    _array(item.span.original),
                    _array(item.span.replacement),
                    _array(item.original_hash),
                    _array(item.replacement_hash),
                )
            )
            + "},"
        )
    lines += ["};", f"static const unsigned int hn_modes[{count}]=" + _array(modes) + ";"]
    if custom_time:
        original, replacement = custom_time
        lines += [
            "#define HN_CUSTOM_TIME 1",
            f"static const unsigned int hn_time_original_size={len(original)};",
            f"static const unsigned int hn_time_config_size={len(replacement)};",
            "static const unsigned char hn_time_config[]=" + _array(replacement) + ";",
            "static const unsigned char hn_time_original_hash[32]="
            + _array(hashlib.sha256(original).digest())
            + ";",
            "static const unsigned char hn_time_config_hash[32]="
            + _array(hashlib.sha256(replacement).digest())
            + ";",
        ]
    lines += ["static const unsigned char hn_plan_id[32]=" + _array(plan_id) + ";"]
    lines += ["static const unsigned char hn_receipt_id[32]=" + _array(receipt_id) + ";"]
    return ("\n".join(lines) + "\n").encode("ascii")


def _files(
    snapshot, backup, old_origin, new_origin, probe_port, *, target_count=4, ntp_server=DEFAULT
):
    if type(target_count) is not int or target_count not in (3, 4):
        raise ValueError("fixed network target count required")
    if target_count == 3 and old_origin is not None:
        raise ValueError("cleanup scope cannot change registration configuration")
    ntp_server = time_server(ntp_server)
    custom_time = ntp_server != DEFAULT
    if custom_time and target_count != 3:
        raise ValueError("custom time server requires the disjoint three-file plan")
    receipt = network_backup.verify(backup, snapshot)
    original = [row.data for row in snapshot.records]
    # Registration validation also validates both literal private HTTPS origins.
    address = urlsplit(new_origin).hostname
    spans = (
        probe_candidate(original[0], address, probe_port),
        probe_candidate(original[1], address, probe_port),
    )
    if not custom_time:
        spans += (connman_time_candidate(original[2]),)
    if target_count == 4:
        spans += (registration_candidate(original[3], old_origin, new_origin),)
    plans = tuple(make_plan(i, data, span) for i, (data, span) in enumerate(zip(original, spans)))
    receipt_id = hashlib.sha256(receipt).digest()
    record = {
        "format": "hearth-network-offline-plan-v1"
        if target_count == 4
        else "hearth-network-cleanup-time-plan-v1"
        if custom_time
        else "hearth-network-cleanup-plan-v1",
        "session": snapshot.session.hex(),
        "receipt_sha256": receipt_id.hex(),
        "installed": False,
        "previous_origin": old_origin,
        "origin": new_origin,
        "probe_port": probe_port,
        "files": [
            {
                "target": i,
                "path": network_backup.TARGETS[i],
                "bytes": p.size,
                "mode": snapshot.records[i].mode,
                "original_sha256": p.original_hash.hex(),
                "replacement_sha256": p.replacement_hash.hex(),
                "offset": p.span.offset,
                "original_span": p.span.original.hex(),
                "replacement_span": p.span.replacement.hex(),
            }
            for i, p in enumerate(plans)
        ],
    }
    changed_time = connman_time_config(original[2], ntp_server) if custom_time else None
    if custom_time:
        record["ntp_server"] = ntp_server
        record["files"].append(
            {
                "target": 2,
                "path": network_backup.TARGETS[2],
                "bytes": len(original[2]),
                "replacement_bytes": len(changed_time),
                "mode": snapshot.records[2].mode,
                "original_sha256": hashlib.sha256(original[2]).hexdigest(),
                "replacement_sha256": hashlib.sha256(changed_time).hexdigest(),
                "update": "bounded-time-server-text",
            }
        )
    canonical = custody._canonical(record)
    plan_id = hashlib.sha256(record["format"].encode() + b"\n" + canonical).digest()
    files = {
        "plan.json": canonical,
        "plan.h": header(
            plans,
            [r.mode for r in snapshot.records[:target_count]],
            plan_id,
            receipt_id,
            custom_time=(original[2], changed_time) if custom_time else None,
        ),
    }
    if custom_time:
        files["2.replacement"] = changed_time
    files |= {
        f"{i}.replacement": span.apply(data) for i, (data, span) in enumerate(zip(original, spans))
    }
    return files, plan_id, receipt_id


def prepare(
    output,
    snapshot,
    backup,
    old_origin,
    new_origin,
    *,
    probe_port=8123,
    target_count=4,
    ntp_server=DEFAULT,
):
    """Produce fresh private candidate DATA only after complete backup verification."""
    files, _, _ = _files(
        snapshot,
        backup,
        old_origin,
        new_origin,
        probe_port,
        target_count=target_count,
        ntp_server=ntp_server,
    )
    output = Path(output)
    parent = custody._open_directory(output.parent)
    directory = -1
    try:
        os.mkdir(output.name, 0o700, dir_fd=parent)
        directory = os.open(
            output.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
        )
        os.fchmod(directory, 0o700)
        os.fsync(parent)
        for name, data in files.items():
            custody._write(directory, name, data)
        os.fsync(directory)
        for name, data in files.items():
            limit = (
                network_backup.LIMITS[int(name[0])]
                if name.endswith(".replacement")
                else 512 * 1024
                if name == "plan.h"
                else 16384
            )
            if custody._read(directory, name, limit) != data:
                raise ValueError("private network plan readback mismatch")
        os.fsync(parent)
    finally:
        if directory >= 0:
            os.close(directory)
        os.close(parent)
    return {"status": "offline-network-plan-prepared", "targets": target_count, "installed": False}


def check(root, backup, expected_plan):
    if type(expected_plan) is not bytes or len(expected_plan) != 32:
        raise ValueError("separate reviewed plan pin required")
    directory = custody._open_directory(root)
    try:
        record = loads(custody._read(directory, "plan.json", 16384))
        custom_time = (
            isinstance(record, dict)
            and record.get("format") == "hearth-network-cleanup-time-plan-v1"
        )
        if not isinstance(record, dict) or set(record) != {
            "format",
            "session",
            "receipt_sha256",
            "installed",
            "previous_origin",
            "origin",
            "probe_port",
            "files",
        } | ({"ntp_server"} if custom_time else set()):
            raise ValueError("fixed network plan fields required")
        snapshot = network_backup.load(backup)
        formats = {
            "hearth-network-offline-plan-v1": 4,
            "hearth-network-cleanup-plan-v1": 3,
            "hearth-network-cleanup-time-plan-v1": 3,
        }
        if record["format"] not in formats:
            raise ValueError("reviewed network plan format required")
        files, plan_id, receipt_id = _files(
            snapshot,
            backup,
            record["previous_origin"],
            record["origin"],
            record["probe_port"],
            target_count=formats[record["format"]],
            ntp_server=record["ntp_server"] if custom_time else DEFAULT,
        )
        if plan_id != expected_plan or set(os.listdir(directory)) != set(files):
            raise ValueError("network plan pin/inventory mismatch")
        for name, data in files.items():
            limit = (
                network_backup.LIMITS[int(name[0])]
                if name.endswith(".replacement")
                else 512 * 1024
                if name == "plan.h"
                else 16384
            )
            if custody._read(directory, name, limit) != data:
                raise ValueError("network plan/candidate differs from reviewed span")
        return {
            "plan": plan_id,
            "receipt": receipt_id,
            "header": files["plan.h"],
            "snapshot": snapshot,
            "target_count": formats[record["format"]],
            "custom_time": custom_time,
        }
    finally:
        os.close(directory)
