"""One protected read-only encoding audit; no commit, retry or native startup."""

import hashlib
import json
import os
import select
import struct
import subprocess  # nosec B404
import time
import zlib
from pathlib import Path

from firmware.encoding_audit import profile
from firmware.file_snapshot.run import END, MAGIC, MAX_PAYLOAD, decode
from firmware.file_writer.run import encode, save
from firmware.probe import port as usb_port
from firmware.settings_compat_probe.observe import observe
from firmware.startup_diagnostic.profile import check as check_diagnostic
from firmware.tls_probe.package import private_read
from provisioning import file_capsule
from tools.elf_review import private_path

AUDIT_MAGIC, AUDIT_END = b"HFEAUD1\n", b"HFEEND1\n"
BACKUP_MAGIC = b"HFEAHSH1"


def restored_archive_plan(manifest, plan):
    layout = manifest.get("archive_layout")
    if layout not in (None, "plan-id-directory-v1"):
        raise ValueError("known restored archive layout required")
    return plan.hex() if layout is not None else None


def original_records(capsule, pin):
    capsule, pin = private_path(capsule), private_path(pin)
    from firmware.file_writer.prepare import pin_read

    file_capsule.check(capsule, expected_plan=pin_read(pin))
    manifest = json.loads(private_read(capsule / "plan.json", 32768))
    return decode(
        private_read(capsule / "capture.bin", MAX_PAYLOAD + 56),
        bytes.fromhex(manifest["snapshot_session"]),
    )


def same(originals, records):
    return originals == records


def audit_report(raw, originals):
    if len(raw) != 84:
        raise ValueError("fixed nineteen-inode encoding report required")
    version, count, *codes = struct.unpack("<II19i", raw)
    if (
        version not in (1, 2)
        or count != 19
        or any(n < -10000 or n > (0 if version == 1 else 65535) for n in codes)
    ):
        raise ValueError("encoding version/count/status invalid")
    masks = {}
    if version == 2:
        masks = {"selected_codec_masks": codes[:9], "archive_codec_masks": codes[9:]}
        # Preserve the original strict NONE/ZERO decision; codec inventory is
        # diagnostic evidence, never permission to accept another compressor.
        codes = [n if n < 0 else (0 if not n & ~3 else -95) for n in codes]
    expected = [0 if row.existed else -2 for row in originals]
    return {
        "selected_codes": codes[:9],
        "archive_codes": codes[9:],
        "selected_encoding_verified": codes[:9] == expected,
        "archive_encoding_verified": codes[9:] == expected + [0],
        "flash_writes": False,
    } | masks


def backup_report(raw, originals, plan):
    if len(raw) != 532 or len(plan) != 32 or len(originals) != 9:
        raise ValueError("fixed backup fingerprint report required")
    version, count, inventory = struct.unpack_from("<IIi", raw)
    if (version, count) != (1, 10) or inventory not in (0, -1):
        raise ValueError("backup fingerprint header invalid")
    journal = b"HFI1" + struct.pack("<3I", 6, 511, 9) + plan
    expected = [row.data if row.existed else None for row in originals] + [journal]
    matches, statuses = [], []
    for index, data in enumerate(expected):
        row = struct.unpack_from("<i4I32s", raw, 12 + 52 * index)
        if not -10000 <= row[0] <= 0:
            raise ValueError("backup fingerprint status invalid")
        wanted = (
            (-2, 0, 0, 0, 0, bytes(32))
            if data is None
            else (0, 0o100600, 0, 0, len(data), hashlib.sha256(data).digest())
        )
        matches.append(row == wanted)
        statuses.append(row[0])
    return {
        "archive_inventory_valid": inventory == 0,
        "backup_hashes_match": inventory == 0 and all(matches),
        "archive_file_statuses": statuses,
    }


def receive(fd, deadline, session, output, *, require_backups=False):
    buffer, frames = bytearray(), {}
    formats = {
        MAGIC: (MAX_PAYLOAD, END, "snapshot.bin"),
        AUDIT_MAGIC: (84, AUDIT_END, "encoding.bin"),
        BACKUP_MAGIC: (532, AUDIT_END, "backup-fingerprints.bin"),
    }
    wanted = {MAGIC, AUDIT_MAGIC} | ({BACKUP_MAGIC} if require_backups else set())
    while (remaining := deadline - time.monotonic()) > 0:
        if not select.select([fd], [], [], min(remaining, 0.5))[0]:
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            raise OSError("audit USB disconnected")
        buffer.extend(chunk)
        while True:
            candidates = [(buffer.find(m + session), m) for m in formats]
            candidates = [(at, m) for at, m in candidates if at >= 0]
            if not candidates:
                if b"HEARTH_SNAPSHOT_FAILED_V1\n" in buffer:
                    raise ValueError("protected encoding snapshot failed")
                buffer = buffer[-47:]
                break
            at, magic = min(candidates)
            del buffer[:at]
            if len(buffer) < 48:
                break
            length, crc = struct.unpack_from("<II", buffer, 40)
            bound, footer, name = formats[magic]
            if length > bound:
                raise ValueError("bounded encoding frame required")
            if len(buffer) < length + 56:
                break
            frame = bytes(buffer[: length + 56])
            del buffer[: length + 56]
            if frame[-8:] != footer or zlib.crc32(frame[48:-8]) != crc:
                raise ValueError("encoding frame integrity failed")
            if magic in frames:
                if frames[magic] != frame:
                    raise ValueError("immutable cached audit required")
                continue
            save(output, name, frame)
            frames[magic] = frame
            if wanted <= frames.keys():
                result = decode(frames[MAGIC], session), frames[AUDIT_MAGIC][48:-8]
                return result + (frames[BACKUP_MAGIC][48:-8],) if require_backups else result
        if len(buffer) > MAX_PAYLOAD + 56:
            raise ValueError("audit synchronization bound exceeded")
    raise TimeoutError("protected audit incomplete")


def run(root, output, previous, capsule, pin, *, execute=False, from_restore=False):
    root, output, previous, capsule, pin = map(private_path, (root, output, previous, capsule, pin))
    status = profile.check(root)
    if not execute:
        return status
    if type(from_restore) is not bool:
        raise ValueError("explicit read-only entry required")
    execution = json.loads(private_read(previous / "execution.json", 65536))
    originals = original_records(capsule, pin)
    if from_restore:
        from firmware.startup_diagnostic.run import sealed_restore_entry

        sealed_restore_entry(previous)
        prior_execution = execution
    else:
        check_diagnostic(execution["profile"])
        if (
            json.loads(private_read(previous / "host-exit-confirmed.json", 4096))
            != {"host_command_exited": True}
            or json.loads(private_read(previous / "observed.json", 4096)).get("flash_writes")
            is not False
        ):
            raise ValueError("exited protected read-only diagnostic required")
        records = decode(
            private_read(previous / "snapshot.bin", MAX_PAYLOAD + 56),
            bytes.fromhex(execution["session"]),
        )
        if not same(originals, records):
            raise ValueError("verified original stock snapshot required before audit")
        prior_execution = json.loads(
            private_read(Path(execution["recover_from"]) / "execution.json", 65536)
        )
    from firmware.file_writer.run import checked_pair

    prior, binding = checked_pair(prior_execution["profile"], prior_execution["recovery"])
    if prior["capsule"] != str(capsule) or prior["pin"] != str(pin):
        raise ValueError("same restored originals required")
    usb = usb_port.SYSFS / usb_port.current()
    if tuple((usb / n).read_text().strip() for n in ("idVendor", "idProduct")) not in (
        ("0525", "a4a7"),
        ("0525", "a4a6"),
    ):
        raise ValueError("known protected RAM mode required")
    if output.exists() or output.parent.stat().st_mode & 0o077:
        raise ValueError("fresh owner-only output required")
    creation = json.loads(private_read(root / "profile.json", 65536))
    manifest = json.loads(private_read(capsule / "plan.json", 32768))
    expected_archive = restored_archive_plan(manifest, binding.plan)
    if creation.get("archive_plan") != expected_archive:
        raise ValueError("audit must inspect the exact restored plan's archive")
    session = bytes.fromhex(creation["session"])
    output.mkdir(mode=0o700)
    save(
        root,
        "execution-started.json",
        encode({"output": str(output), "operation": "protected-readonly-encoding-audit"}),
    )
    save(
        output,
        "execution.json",
        encode(
            {
                "profile": str(root),
                "session": session.hex(),
                "previous": str(previous),
                "capsule": str(capsule),
                "pin": str(pin),
                **({"previous_kind": "sealed-restore"} if from_restore else {}),
            }
        ),
    )
    print(
        "PROTECTED READ-ONLY ENCODING AUDIT: write callbacks disabled. No native execution or writer. Keep USB connected and HVAC base detached.",
        flush=True,
    )
    print("Waiting up to 90 seconds for the reviewed manual ROM restart.", flush=True)
    artifacts = root / "artifacts"
    subprocess.run(  # nosec B603
        [
            str(artifacts / "omap_loader"),
            "-P",
            usb_port.current(),
            "-f",
            str(artifacts / "x-load-gen2.bin"),
            "-f",
            str(artifacts / "u-boot.bin"),
            "-a",
            "0x80100000",
            "-f",
            str(artifacts / "uImage"),
            "-a",
            "0x80a00000",
            "-j",
            "0x80100000",
        ],
        check=True,
        timeout=90,
    )
    result = observe(
        usb_port.current(),
        180,
        receive_fn=lambda fd, deadline, _: receive(
            fd, deadline, session, output, require_backups=True
        ),
    )
    records, raw, hashes = result
    report = (
        audit_report(raw, originals)
        | backup_report(hashes, originals, binding.plan)
        | {
            "stock_files_match": same(originals, records),
            "native_execution": False,
        }
    )
    save(output, "observed.json", encode(report))
    save(output, "finished.json", encode({"host_command_exited": True}))
    return report
