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
    elif count == 3:
        from firmware.network_writer.session import selftest as validate_selftest

        validate_selftest(selftest)
    else:
        raise ValueError("only the disjoint commissioning9 and cleanup3 phases may chain")
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
