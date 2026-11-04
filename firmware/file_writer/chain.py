"""Narrow evidence-bound RAM handoffs. Never starts a loader or sends a decision."""

import hashlib
import json
from pathlib import Path

from firmware.acquisition import custody
from firmware.acquisition.profile import check as check_acquisition
from firmware.file_writer import protocol
from firmware.tls_probe.package import private_read
from provisioning import file_backup, network_backup
from tools.elf_review import private_path


def ram(sysfs):
    usb = sysfs / "1-1"
    identity = tuple((usb / name).read_text().strip() for name in ("idVendor", "idProduct"))
    if identity not in (("0525", "a4a7"), ("0525", "a4a6")):
        raise ValueError("known exited RAM session required; no native startup or stale ROM")


def acquisition_install(record, binding, previous, *, sysfs=Path("/sys/bus/usb/devices")):
    if binding.action != 1:
        raise ValueError("acquisition handoff is install-only")
    previous = private_path(previous)
    if (previous / "nand-inputs.json").exists():
        from installer.nand_backup import require_handoff

        decoder, _ = custody.verify(previous)
        if private_read(previous / "capture.bin", protocol.MAX_SNAPSHOT + 56) != private_read(
            private_path(record["capsule"]) / "capture.bin", protocol.MAX_SNAPSHOT + 56
        ) or decoder.session != bytes.fromhex(
            json.loads(private_read(previous / "nand-inputs.json", 4096))["session"]
        ):
            raise ValueError("commissioning capsule differs from checked NAND originals")
        require_handoff(previous.parent / "nand", previous.parent)
        ram(sysfs)
        return {"status": "verified-nand-inputs-install-handoff", "native_startup_required": False}
    execution = json.loads(private_read(previous / "execution.json", 65536))
    source = private_path(execution["profile"])
    check_acquisition(source)
    creation = private_read(source / "profile.json", 65536)
    profile = json.loads(creation)
    started = json.loads(private_read(source / "execution-started.json", 65536))
    ended = json.loads(private_read(previous / "finished.json", 65536))
    observed = json.loads(private_read(previous / "observed.json", 65536))
    decoder, _ = custody.verify(previous)
    if (
        execution.get("profile_sha256") != hashlib.sha256(creation).hexdigest()
        or execution.get("session") != profile["session"]
        or decoder.session.hex() != execution["session"]
        or execution.get("flash_writes") is not False
        or started
        != {"output": str(previous), "once": True, "operation": "read-only-installer-acquisition"}
        or ended != {"host_command_exited": True}
        or observed.get("status") != "protected-installer-inputs-preserved"
        or observed.get("fixed_snapshots") != 2
        or observed.get("library_groups") != 4
        or observed.get("flash_writes") is not False
        or observed.get("native_execution") is not False
    ):
        raise ValueError("complete checked read-only acquisition required before handoff")
    if private_read(previous / "capture.bin", protocol.MAX_SNAPSHOT + 56) != private_read(
        private_path(record["capsule"]) / "capture.bin", protocol.MAX_SNAPSHOT + 56
    ):
        raise ValueError("commissioning capsule differs from acquisition")
    ram(sysfs)
    return {"status": "verified-acquisition-install-handoff", "native_startup_required": False}


def completed(previous, engine, action, count):
    previous = private_path(previous)
    execution = json.loads(private_read(previous / "execution.json", 65536))
    ended = json.loads(private_read(previous / "finished.json", 65536))
    observed = json.loads(private_read(previous / "observed.json", 65536))
    record, binding = engine.checked_pair(execution["profile"], execution["recovery"])
    started = json.loads(
        private_read(private_path(execution["profile"]) / "execution-started.json", 65536)
    )
    preflight = json.loads(private_read(previous / "preflight.json", 65536))
    sending = json.loads(private_read(previous / "decision-sending.json", 65536))
    sent = json.loads(private_read(previous / "decision-sent.json", 65536))
    selftest = private_read(previous / "selftest.jsonl", 32768)
    if count == 9:
        protocol.validate_selftest(selftest)
    elif count in (3, 4):
        from firmware.network_writer.session import selftest as validate_selftest

        validate_selftest(
            selftest, **({"shared_originals": True} if record.get("shared_archive") else {})
        )
    else:
        raise ValueError(
            "only the reviewed commissioning9, cleanup3 and legacy network4 phases may chain"
        )
    result = protocol.validate_result(
        private_read(previous / "result.json", 16384), action, target_count=count
    )
    if (
        ended != {"host_command_exited": True}
        or started != execution
        or preflight != execution
        or sending != {"execution": execution, "commit": True}
        or sent != sending
        or execution["action"] != action
        or binding.action != action
        or execution["plan"] != binding.plan.hex()
        or observed != {"execution": execution, "result": result}
        or not result["complete"]
        or not result["safe_to_restart"]
        or not result["encoding_verified"]
        or not result["program"]
    ):
        raise ValueError("complete sealed and verified prior phase required")
    return record


def commissioning_to_cleanup(record, binding, previous, *, sysfs=Path("/sys/bus/usb/devices")):
    from firmware.file_writer import run

    if binding.action != 1 or record.get("targets", 4) != 3:
        raise ValueError("disjoint cleanup3 install-only handoff required")
    prior = completed(previous, run, 1, 9)
    source = private_path(prior["base"])
    custody.verify(source)
    if (
        record["libraries"] != str(source)
        or record["backup"] != str(source / "network-backup")
        or set(file_backup.TARGETS) & set(network_backup.TARGETS[:3])
    ):
        raise ValueError("cleanup and commissioning must share custody and disjoint targets")
    ram(sysfs)
    return {"status": "verified-commissioning-to-cleanup-handoff", "native_startup_required": False}


def acquisition_to_capacity(record, binding, previous, *, sysfs=Path("/sys/bus/usb/devices")):
    previous = private_path(previous)
    if (
        binding.action != 1
        or record.get("preflight_only") is not True
        or record.get("targets") != 3
        or not record.get("capacity_reserve")
        or record["libraries"] != str(previous)
        or record["backup"] != str(previous / "network-backup")
    ):
        raise ValueError("same-acquisition no-commit combined capacity profile required")
    # Reuse complete protected-reader custody, not just a USB identity or flag.
    acquisition_install({"capsule": str(previous)}, binding, previous, sysfs=sysfs)
    return {"status": "verified-acquisition-capacity-handoff", "native_startup_required": False}


def capacity_to_commissioning(record, binding, previous, *, sysfs=Path("/sys/bus/usb/devices")):
    from firmware.network_writer import run
    from firmware.network_writer.session import result, selftest
    from installer.capacity import passed, root_reserve

    previous = private_path(previous)
    execution = json.loads(private_read(previous / "execution.json", 65536))
    prior, prior_binding = run.checked_pair(execution["profile"], execution["recovery"])
    creation = private_path(execution["profile"])
    observed = json.loads(private_read(previous / "observed.json", 65536))
    row = result(
        private_read(previous / "result.json", 16384), 1, target_count=3, preflight_only=True
    )
    selftest(
        private_read(previous / "selftest.jsonl", 32768), shared_originals="shared_archive" in prior
    )
    if (
        binding.action != 1
        or prior_binding.action != 1
        or prior.get("targets") != 3
        or prior.get("preflight_only") is not True
        or prior.get("capacity_reserve")
        != root_reserve(Path(record["capsule"]), Path(record["pin"]))
        or prior["libraries"] != record["base"]
        or prior["backup"] != str(Path(record["base"]) / "network-backup")
        or execution["plan"] != prior_binding.plan.hex()
        or json.loads(private_read(creation / "execution-started.json", 65536)) != execution
        or json.loads(private_read(previous / "finished.json", 4096))
        != {"host_command_exited": True}
        or observed != {"execution": execution, "result": row}
        or not passed(row)
        or any(
            (previous / name).exists()
            for name in ("decision-sending.json", "decision-sent.json", "preflight.json")
        )
    ):
        raise ValueError(
            "complete no-write combined capacity evidence required before commissioning"
        )
    custody.verify(private_path(record["base"]))
    ram(sysfs)
    return {"status": "verified-capacity-commissioning-handoff", "native_startup_required": False}


def cleanup_restore_to_commissioning(
    record, binding, previous, *, sysfs=Path("/sys/bus/usb/devices")
):
    from firmware.network_writer import run

    if binding.action != 2:
        raise ValueError("original commissioning restoration only")
    prior = completed(previous, run, 2, 3)
    source = private_path(record["base"])
    custody.verify(source)
    if (
        prior.get("targets", 4) != 3
        or prior["libraries"] != str(source)
        or prior["backup"] != str(source / "network-backup")
        or set(file_backup.TARGETS) & set(network_backup.TARGETS[:3])
    ):
        raise ValueError("matching cleanup3 custody required before original restoration")
    ram(sysfs)
    return {
        "status": "verified-cleanup-to-original-restoration-handoff",
        "native_startup_required": False,
    }


def legacy_network_restore_to_stock(
    record, binding, previous, *, sysfs=Path("/sys/bus/usb/devices")
):
    """Owner legacy4 overlap: network original3 must be core installed8 exactly."""
    from firmware.file_writer.restore_settings import check
    from firmware.network_writer import run

    admission = record.get("restore_observation")
    if binding.action != 2 or admission is None:
        raise ValueError("explicit observed-settings original restoration required")
    check(admission, record["capsule"], record["pin"])
    prior = completed(previous, run, 2, 4)
    if (
        prior.get("targets", 4) != 4
        or prior["libraries"] != record["base"]
        or prior["plan_path"] != admission["network"]
        or prior["backup"] != admission["network_backup"]
        or prior["pin"] != admission["network_pin"]
    ):
        raise ValueError("exact observed legacy network restoration required")
    # check() verifies independently preserved acquisition, every installed file,
    # both plans/custody and the exact restored overlap before admitting settings.
    ram(sysfs)
    return {"status": "verified-legacy-network-to-stock-handoff", "native_startup_required": False}
