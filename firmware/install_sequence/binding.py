"""Bind three one-use kernel slots to the two disjoint checked plans."""

import json
from pathlib import Path

from firmware.file_writer.prepare import pin_read
from firmware.network_probe.profile import pinned_plan
from firmware.tls_probe.package import private_read
from provisioning import file_capsule
from tools.elf_review import private_path


def header(path, capsule, pin):
    row = json.loads(private_read(private_path(path), 4096))
    if (
        set(row) != {"format", "cleanup", "backup", "pin"}
        or row["format"] != "hearth-install-sequence-binding-v1"
    ):
        raise ValueError("fixed cleanup sequence binding required")
    bound = pinned_plan(row["cleanup"], row["backup"], row["pin"])
    if bound["target_count"] != 3:
        raise ValueError("disjoint cleanup3 sequence required")
    plan = pin_read(pin)
    file_capsule.check(capsule, expected_plan=plan)
    receipt = json.loads(private_read(Path(capsule) / "backup/receipt.json", 65536))
    core_receipt = bytes.fromhex(receipt["manifest_sha256"])
    array = lambda values: "{" + ",".join("{" + ",".join(map(str, v)) + "}" for v in values) + "}"
    return (
        "#define HEARTH_INSTALL_SEQUENCE 1\n"
        "static const unsigned char hearth_sequence_plans[3][32]="
        + array((bound["plan"], plan, bound["plan"]))
        + ";\n"
        "static const unsigned char hearth_sequence_receipts[3][32]="
        + array((bound["receipt"], core_receipt, bound["receipt"]))
        + ";\n"
    )
