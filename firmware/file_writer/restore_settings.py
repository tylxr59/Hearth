"""Explicit original restore admission of one exact custody-verified settings file.

No new original/plan, unknown bytes, paths, writes or device execution. The old
journal and all original backups remain mandatory. This is not a general uninstall.
"""

import json
from pathlib import Path

from firmware.acquisition.custody import read, verify
from firmware.file_writer.prepare import pin_read
from firmware.tls_probe.package import sha
from provisioning import file_capsule, network_plan
from tools.elf_review import private_path


def observed(acquisition, capsule, pin, network, network_backup, network_pin):
    acquisition, capsule, pin, network, network_backup, network_pin = map(
        private_path, (acquisition, capsule, pin, network, network_backup, network_pin)
    )
    file_capsule.check(capsule, expected_plan=pin_read(pin))
    decoder, _ = verify(acquisition)
    net_pin = json.loads(read(network_pin, 4096))
    if set(net_pin) != {"format", "plan"} or net_pin["format"] != "hearth-network-reviewed-pin-v1":
        raise ValueError("separate reviewed legacy network pin required")
    bound = network_plan.check(network, network_backup, bytes.fromhex(net_pin["plan"]))
    if bound["target_count"] != 4:
        raise ValueError("legacy four-file owner restoration only")
    plan = json.loads(read(capsule / "plan.json", 32768))
    for i, row in enumerate(decoder.snapshot):
        if (
            not row.existed
            or row.owner
            or row.group
            or row.mode != plan["files"][i]["replacement_mode"]
        ):
            raise ValueError("exact installed target metadata required")
        expected = (
            read(network / "3.replacement", 65536)
            if i == 8
            else read(capsule / f"{i}.replacement", 1048576)
        )
        if i != 7 and row.data != expected:
            raise ValueError("unexpected native file outside observed settings")
    for i, row in enumerate(decoder.network.records):
        expected = read(network / f"{i}.replacement", 6 * 1048576)
        if (
            row.data != expected
            or row.mode != bound["snapshot"].records[i].mode
            or row.owner
            or row.group
        ):
            raise ValueError("network observation differs from reviewed installed plan")
    if read(network_backup / "3.original", 65536) != read(capsule / "8.replacement", 1048576):
        raise ValueError("legacy overlap must restore the commissioning client candidate")
    data = decoder.snapshot[7].data
    if not 0 < len(data) <= 1048576:
        raise ValueError("bounded exact native settings required")
    header = b"/* PRIVATE exact observed settings; original restoration only. */\nstatic const unsigned char hearth_observed_settings[]={\n"
    header += b"\n".join(
        b",".join(str(x).encode() for x in data[i : i + 24]) + b"," for i in range(0, len(data), 24)
    )
    header += b"\n};\n"
    record = {
        "format": "hearth-exact-settings-stock-return-v1",
        "acquisition": str(acquisition),
        "capsule": str(capsule),
        "pin": str(pin),
        "network": str(network),
        "network_backup": str(network_backup),
        "network_pin": str(network_pin),
        "capture_sha256": sha(read(acquisition / "capture.bin", 12 * 1048576)),
        "settings_sha256": sha(data),
        "header_sha256": sha(header),
    }
    return record, header


def check(record, capsule, pin):
    if (
        not isinstance(record, dict)
        or record.get("capsule") != str(Path(capsule).absolute())
        or record.get("pin") != str(Path(pin).absolute())
    ):
        raise ValueError("observed settings must match the original restore capsule")
    expected, header = observed(
        *(
            record[k]
            for k in ("acquisition", "capsule", "pin", "network", "network_backup", "network_pin")
        )
    )
    if record != expected:
        raise ValueError("observed settings custody or admission changed")
    return header


def check_helpers(compiled, helpers, capsule, pin, action):
    from firmware.file_writer.profile import read_build

    record = compiled.get("restore_observation")
    if record is None:
        if (Path(helpers) / "restore-settings.h").exists():
            raise ValueError("observed header requires explicit restore admission")
        return None
    if action != 2:
        raise ValueError("settings observation cannot authorize installation or reencoding")
    header = check(record, capsule, pin)
    if read_build(Path(helpers) / "restore-settings.h", 8 * 1048576) != header:
        raise ValueError("compiled observed-settings header differs")
    return record
