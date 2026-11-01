"""Bind the fixed private replacement plan to verified snapshot custody.

Produces an offline data header, not an installer, executable or device command.
Host callers must supply the separately observed native partition/version and
the expected snapshot session. No remote input or device access exists here.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from firmware.file_snapshot.run import decode
from provisioning import file_backup as custody


@dataclass(frozen=True)
class Replacement:
    target: int
    mode: int
    data: bytes


def _validate(records, replacements):
    if len(replacements) != 9:
        raise ValueError("exact nine-file replacement scope required")
    for index, (old, new) in enumerate(zip(records, replacements, strict=True)):
        expected_mode = {1: 0o644, 2: 0o644, 4: 0o444, 5: 0o750, 7: 0o600, 8: 0o600}.get(
            index, old.mode
        )
        if (
            not isinstance(new, Replacement)
            or type(new.target) is not int
            or new.target != index
            or type(new.mode) is not int
            or new.mode != expected_mode
            or type(new.data) is not bytes
            or not 0 < len(new.data) <= custody.LIMIT
            or old.existed != (index not in (4, 5))
        ):
            raise ValueError("replacement scope or metadata changed")


def _layout(value):
    if type(value) is not int or value not in (0, 1):
        raise ValueError("reviewed legacy or plan-derived archive layout required")
    return value


def _header(records, replacements, plan, archive_layout=0):
    lines = ["/* Private original/replacement DATA only; never commit. */", '#include "posix.h"']
    if _layout(archive_layout):
        lines.append("#define HEARTH_CAPSULE_ARCHIVE_LAYOUT 1")

    def array(name, data):
        lines.append("static const unsigned char " + name + "[]={")
        for at in range(0, len(data), 24):
            lines.append(",".join(f"0x{value:02x}" for value in data[at : at + 24]) + ",")
        lines.append("};")

    for index, (old, new) in enumerate(zip(records, replacements, strict=True)):
        if old.data:
            array(f"hearth_original_{index}", old.data)
        array(f"hearth_replacement_{index}", new.data)
    array("hearth_capsule_plan_id", plan)
    lines.append("static const struct hearth_file_change hearth_capsule_changes[9]={")
    for index, (old, new) in enumerate(zip(records, replacements, strict=True)):
        pointer = f"hearth_original_{index}" if old.data else "0"
        lines.append(
            "{"
            + f"{index},{int(old.existed)},{{{pointer},{len(old.data)}}},"
            + f"{{hearth_replacement_{index},{len(new.data)}}},{old.mode},{new.mode}"
            + "},"
        )
    lines.append("};\nstatic const unsigned int hearth_capsule_count=9;\n")
    return "\n".join(lines).encode("ascii")


def _manifest(records, replacements, session, frame, archive_layout=0):
    result = {
        "format": "hearth-file-plan-v1",
        "profile": "Display-2.6/5.9.4-5",
        "native_partition_observation": "primary",
        "source_root": "root0",
        "snapshot_session": session.hex(),
        "snapshot_sha256": hashlib.sha256(frame).hexdigest(),
        "files": [
            {
                "target": i,
                "path": custody.TARGETS[i],
                "owner": old.owner,
                "group": old.group,
                "original_exists": old.existed,
                "original_mode": old.mode,
                "original_bytes": len(old.data),
                "original_sha256": hashlib.sha256(old.data).hexdigest(),
                "replacement_mode": new.mode,
                "replacement_bytes": len(new.data),
                "replacement_sha256": hashlib.sha256(new.data).hexdigest(),
            }
            for i, (old, new) in enumerate(zip(records, replacements, strict=True))
        ],
    }
    if _layout(archive_layout):
        result["archive_layout"] = "plan-id-directory-v1"
    return result


def prepare(
    snapshot, replacements, output, *, session, native_partition, software_version, archive_layout=0
):
    """Verify source custody, then fsync/read back a plan-bound private capsule.

    Callers still review replacement *contents*. This enforces custody, fixed
    scope, metadata and byte binding, not TLS/settings/startup correctness.
    No device-writer acknowledgment or permission follows from this artifact.
    """
    _layout(archive_layout)
    if native_partition != "primary" or software_version != "5.9.4-5":
        raise ValueError("separately observed primary/5.9.4-5 profile required")
    if type(session) is not bytes or len(session) != 32:
        raise ValueError("expected snapshot session required")
    snapshot = Path(snapshot)
    directory = custody._open_directory(snapshot)
    try:
        frame = custody._read(directory, "capture.bin", 9 * (custody.LIMIT + 24) + 64)
    finally:
        os.close(directory)
    records, replacements = decode(frame, session), tuple(replacements)
    _validate(records, replacements)
    collection_plan = hashlib.sha256(
        b"read-only-root0-snapshot-v1\n" + "\n".join(custody.TARGETS).encode()
    ).digest()
    custody.verify(
        snapshot / "backup", records, session=session, plan=collection_plan, native_root="root0"
    )
    manifest = custody._canonical(_manifest(records, replacements, session, frame, archive_layout))
    plan = hashlib.sha256(manifest).digest()
    output = Path(output)
    if output.name in ("", ".", ".."):
        raise ValueError("fresh capsule output required")
    parent = custody._open_directory(output.parent)
    destination = -1
    try:
        os.mkdir(output.name, 0o700, dir_fd=parent)
        destination = os.open(
            output.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
        )
        os.fchmod(destination, 0o700)
        os.fsync(parent)
        # This second custody record binds the actual replacement plan, rather
        # than promoting the earlier read-only collection receipt to a writer.
        custody.preserve(
            output / "backup", records, session=session, plan=plan, native_root="root0"
        )
        for item in replacements:
            custody._write(destination, f"{item.target}.replacement", item.data)
        custody._write(destination, "capture.bin", frame)
        custody._write(destination, "plan.json", manifest)
        custody._write(
            destination, "capsule.h", _header(records, replacements, plan, archive_layout)
        )
        os.fsync(destination)
        os.fsync(parent)
    finally:
        if destination >= 0:
            os.close(destination)
        os.close(parent)
    check(output, expected_plan=plan)
    return plan


def check(output, *, expected_plan):
    """Revalidate every byte against an externally pinned plan before packaging.

    The exact expected plan must come from a separate reviewed profile; these
    are unsigned local development artifacts, not authenticated deployments.
    """
    if type(expected_plan) is not bytes or len(expected_plan) != 32:
        raise ValueError("externally pinned plan required")
    output = Path(output)
    directory = custody._open_directory(output)
    try:
        names = {f"{i}.replacement" for i in range(9)} | {
            "backup",
            "capture.bin",
            "plan.json",
            "capsule.h",
        }
        if set(os.listdir(directory)) != names:
            raise ValueError("unexpected capsule inventory")
        data = custody._read(directory, "plan.json", 32768)
        if hashlib.sha256(data).digest() != expected_plan:
            raise ValueError("capsule plan mismatch")
        # Canonical reserialization below rejects extra fields and noncanonical
        # JSON. Reading only fixed fields cannot authorize additional paths.
        manifest = json.loads(data)
        layout_value = manifest.get("archive_layout")
        if layout_value not in (None, "plan-id-directory-v1"):
            raise ValueError("unsupported archive layout")
        archive_layout = int(layout_value is not None)
        session = bytes.fromhex(manifest["snapshot_session"])
        frame = custody._read(directory, "capture.bin", 9 * (custody.LIMIT + 24) + 64)
        records = decode(frame, session)
        replacements = tuple(
            Replacement(
                i,
                manifest["files"][i]["replacement_mode"],
                custody._read(directory, f"{i}.replacement", custody.LIMIT),
            )
            for i in range(9)
        )
        _validate(records, replacements)
        expected = custody._canonical(
            _manifest(records, replacements, session, frame, archive_layout)
        )
        if data != expected:
            raise ValueError("capsule contents differ from pinned plan")
        custody.verify(
            output / "backup", records, session=session, plan=expected_plan, native_root="root0"
        )
        header = _header(records, replacements, expected_plan, archive_layout)
        if custody._read(directory, "capsule.h", 96 * custody.LIMIT) != header:
            raise ValueError("capsule data header changed")
        return {
            "status": "offline-plan-bound-not-installable",
            "targets": 9,
            "installed": False,
            "target_receipt_enforced": False,
            "archive_layout": archive_layout,
        }
    finally:
        os.close(directory)
