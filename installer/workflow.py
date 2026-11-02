"""Explicit owner-supervised kit phases. No automatic retry, decision or restart."""

import json
from pathlib import Path
from types import SimpleNamespace

from firmware.acquisition.custody import read
from firmware.file_writer import chain
from firmware.file_writer import run as core
from firmware.file_writer.run import encode, save
from firmware.network_writer import run as cleanup
from installer import kit
from installer.bundle import device_info, read_bundle
from tools.elf_review import private_path


def identity(sysfs=Path("/sys/bus/usb/devices")):
    usb = sysfs / "1-1"
    result = tuple((usb / name).read_text().strip() for name in ("idVendor", "idProduct"))
    if result == ("2464", "0002"):
        return "native"
    if result in (("0525", "a4a7"), ("0525", "a4a6")):
        return "ram"
    raise ValueError("known native or exited RAM USB mode required; no stale ROM")


def network_engine():
    def decide(output, *, commit, expected_action):
        return core.decide(
            output, commit=commit, expected_action=expected_action, checker=cleanup.checked_pair
        )

    return SimpleNamespace(run=cleanup.boot, checked_pair=cleanup.checked_pair, decide=decide)


def fresh(root, role, output):
    outcomes = {
        "commissioning-install": "commissioning-outcome.json",
        "cleanup-install": "cleanup-outcome.json",
        "commissioning-restore": "commissioning-restore-outcome.json",
        "cleanup-restore": "cleanup-restore-outcome.json",
    }
    if role not in outcomes:
        raise ValueError("fixed kit phase required")
    if (
        output.exists()
        or (root / role / "execution-started.json").exists()
        or (root / outcomes[role]).exists()
    ):
        raise ValueError(
            "one-use phase already attempted; preserve it and prepare fresh reviewed images"
        )


def inspect_native(disk, bundle):
    from installer.cli import inspect_disk

    device_info(inspect_disk(disk), bundle)


def checked(root, *, for_restore=False):
    root = private_path(root)
    status = kit.check(root, for_restore=for_restore)
    if status["review_only"]:
        raise ValueError("review-only kit cannot open USB or write a thermostat")
    record = json.loads(read(root / "kit.json", 65536))
    session = private_path(record["session"])
    bundle, _, _ = read_bundle(read(session / "commissioning.zip", 65536), for_restore=for_restore)
    return root, session, bundle


def complete(row):
    return all(
        row.get(name) is True for name in ("complete", "safe_to_restart", "encoding_verified")
    )


def install(root, disk, *, ask=input, runner=None, continue_cleanup=False):
    from installer.cli import execute

    runner = execute if runner is None else runner
    root, session, bundle = checked(root)
    mode = identity()
    if mode == "native":
        inspect_native(disk, bundle)
    first, second = root / "install-commissioning", root / "install-cleanup"
    fresh(root, "cleanup-install", second)
    fresh(root, "cleanup-restore", root / "restore-cleanup")
    fresh(root, "commissioning-restore", root / "restore-commissioning")
    if continue_cleanup:
        chain.completed(first, core, 1, 9)
    else:
        fresh(root, "commissioning-install", first)
        record, binding = core.checked_pair(
            root / "commissioning-install", root / "commissioning-restore"
        )
        entry = {}
        if mode == "ram":
            chain.acquisition_install(record, binding, session / "acquisition")
            entry = {"handoff_from_acquisition": session / "acquisition"}
        print("Step1/2: install local HA settings, trust and startup (nine files).")
        row = runner(
            root / "commissioning-install",
            root / "commissioning-restore",
            first,
            ask=ask,
            entry=entry,
            restart_after=False,
        )
        if not row.get("cancelled"):
            save(root, "commissioning-outcome.json", encode(row))
        if not complete(row):
            return {"complete": False, "completed_phases": [], "automatic_retry": False}
        mode = "ram"
    entry = {}
    if mode == "ram":
        record, binding = cleanup.checked_pair(root / "cleanup-install", root / "cleanup-restore")
        chain.commissioning_to_cleanup(record, binding, first)
        entry = {"handoff_from_commissioning": first}
    print("Step2/2: redirect connectivity checks and time locally (three disjoint files).")
    row = runner(
        root / "cleanup-install",
        root / "cleanup-restore",
        second,
        ask=ask,
        engine=network_engine(),
        entry=entry,
        restart_after=True,
    )
    if not row.get("cancelled"):
        save(root, "cleanup-outcome.json", encode(row))
    return {
        "complete": complete(row),
        "completed_phases": ["commissioning", "cleanup"] if complete(row) else ["commissioning"],
        "automatic_retry": False,
        "whole_firmware_recovery": "unverified",
    }


def restore(root, disk, *, phase="all", ask=input, runner=None):
    from installer.cli import execute

    if phase not in ("all", "cleanup", "commissioning"):
        raise ValueError("explicit checked restoration scope required")
    runner = execute if runner is None else runner
    root, _, bundle = checked(root, for_restore=True)
    mode = identity()
    if mode == "native":
        inspect_native(disk, bundle)
    if phase in ("all", "cleanup"):
        fresh(root, "cleanup-restore", root / "restore-cleanup")
    if phase in ("all", "commissioning"):
        fresh(root, "commissioning-restore", root / "restore-commissioning")
    completed = []
    if phase in ("all", "cleanup"):
        output = root / "restore-cleanup"
        fresh(root, "cleanup-restore", output)
        entry = {"recover_from": root / "install-cleanup"} if mode == "ram" else {}
        print(
            "Restore step: original three network files; real journal preflight remains required."
        )
        row = runner(
            root / "cleanup-restore",
            root / "cleanup-restore",
            output,
            restore=True,
            ask=ask,
            engine=network_engine(),
            entry=entry,
            restart_after=phase == "cleanup",
        )
        if not row.get("cancelled"):
            save(root, "cleanup-restore-outcome.json", encode(row))
        if not complete(row):
            return {"complete": False, "restored_phases": [], "automatic_retry": False}
        completed.append("cleanup")
        mode = "ram"
    if phase in ("all", "commissioning"):
        output = root / "restore-commissioning"
        fresh(root, "commissioning-restore", output)
        entry = {}
        if mode == "ram":
            if completed:
                record, binding = core.checked_pair(
                    root / "commissioning-restore", root / "commissioning-restore"
                )
                chain.cleanup_restore_to_commissioning(record, binding, root / "restore-cleanup")
                entry = {"handoff_from_cleanup_restore": root / "restore-cleanup"}
            else:
                entry = {"recover_from": root / "install-commissioning"}
        print(
            "Restore step: original nine commissioning files; exact backup and journal checks remain required."
        )
        row = runner(
            root / "commissioning-restore",
            root / "commissioning-restore",
            output,
            restore=True,
            ask=ask,
            entry=entry,
            restart_after=True,
        )
        if not row.get("cancelled"):
            save(root, "commissioning-restore-outcome.json", encode(row))
        if not complete(row):
            return {"complete": False, "restored_phases": completed, "automatic_retry": False}
        completed.append("commissioning")
    return {
        "complete": True,
        "restored_phases": completed,
        "automatic_retry": False,
        "whole_firmware_recovery": "unverified",
    }
