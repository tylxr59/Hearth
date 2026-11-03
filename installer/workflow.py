"""Explicit owner-supervised kit phases. No automatic retry, decision or restart."""

import json
from pathlib import Path
from types import SimpleNamespace

from firmware.acquisition.custody import read
from firmware.file_writer import chain
from firmware.file_writer import run as core
from firmware.file_writer.run import encode, save
from firmware.network_writer import run as cleanup
from installer import kit, ui
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
        "capacity-preflight": "capacity-outcome.json",
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


def inspect_native(disk, bundle, *, sudo_read=False):
    from installer.cli import inspect_disk

    device_info(inspect_disk(disk, sudo_read=sudo_read), bundle)


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


def install(root, disk, *, ask=input, runner=None):
    from installer.cli import execute

    runner = execute if runner is None else runner
    root, session, bundle = checked(root)
    from installer.nand_backup import check as check_backup

    check_backup(session)
    mode = identity()
    if mode == "native":
        inspect_native(disk, bundle)
    first, second = root / "install-commissioning", root / "install-cleanup"
    fresh(root, "cleanup-install", second)
    fresh(root, "cleanup-restore", root / "restore-cleanup")
    fresh(root, "commissioning-restore", root / "restore-commissioning")
    fresh(root, "commissioning-install", first)
    record, binding = core.checked_pair(
        root / "commissioning-install", root / "commissioning-restore"
    )
    entry = {}
    if mode == "ram":
        chain.acquisition_install(record, binding, session / "acquisition")
        entry = {"handoff_from_acquisition": session / "acquisition"}
    capacity = root / "check-capacity"
    fresh(root, "capacity-preflight", capacity)
    ui.section("Part 1 of 3: check free space (read-only)")
    row = runner(
        root / "capacity-preflight",
        root / "cleanup-restore",
        capacity,
        ask=ask,
        engine=network_engine(),
        entry={"handoff_from_acquisition": session / "acquisition"} if mode == "ram" else {},
        restart_after=False,
        backup_session=session,
    )
    if not row.get("cancelled"):
        save(root, "capacity-outcome.json", encode(row))
    if row.get("preflight_passed") is not True or row.get("safe_to_restart") is not True:
        return {
            "complete": False,
            "completed_phases": [],
            "automatic_retry": False,
            "capacity_passed": False,
        }
    chain.capacity_to_commissioning(record, binding, capacity)
    entry = {"handoff_from_capacity": capacity}
    ui.section("Part 2 of 3: Home Assistant settings, trust and startup (nine files)")
    row = runner(
        root / "commissioning-install",
        root / "commissioning-restore",
        first,
        ask=ask,
        entry=entry,
        restart_after=False,
        backup_session=session,
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
    check_backup(session)
    ui.section("Part 3 of 3: local connectivity check and time server (three files)")
    row = runner(
        root / "cleanup-install",
        root / "cleanup-restore",
        second,
        ask=ask,
        engine=network_engine(),
        entry=entry,
        restart_after=True,
        backup_session=session,
    )
    if not row.get("cancelled"):
        save(root, "cleanup-outcome.json", encode(row))
    return {
        "complete": complete(row),
        "completed_phases": ["commissioning", "cleanup"] if complete(row) else ["commissioning"],
        "automatic_retry": False,
        "whole_firmware_recovery": "unverified",
    }


def restore(root, disk, *, phase="all", ask=input, runner=None, sudo_read=False):
    from installer.cli import execute

    if phase not in ("all", "cleanup", "commissioning"):
        raise ValueError("explicit checked restoration scope required")
    runner = execute if runner is None else runner
    root, _, bundle = checked(root, for_restore=True)
    mode = identity()
    if mode == "native":
        inspect_native(disk, bundle, **({"sudo_read": True} if sudo_read else {}))
    if phase in ("all", "cleanup"):
        fresh(root, "cleanup-restore", root / "restore-cleanup")
    if phase in ("all", "commissioning"):
        fresh(root, "commissioning-restore", root / "restore-commissioning")
    completed = []
    if phase in ("all", "cleanup"):
        output = root / "restore-cleanup"
        fresh(root, "cleanup-restore", output)
        entry = {"recover_from": root / "install-cleanup"} if mode == "ram" else {}
        ui.section("Restore part 1 of 2: original network files (three files)")
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
        ui.section("Restore part 2 of 2: original settings, trust and startup files (nine files)")
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
