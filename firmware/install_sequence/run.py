"""One owner-timed loader, three ordered sessions and two separate write decisions."""

import json
import os
import subprocess  # nosec B404
import time
from pathlib import Path

from firmware.file_writer import protocol
from firmware.file_writer import run as shared
from firmware.file_writer.session import Session
from firmware.install_sequence import profile
from firmware.network_writer.session import NetworkSession
from firmware.settings_compat_probe.observe import observe
from firmware.tls_probe.package import private_read
from installer.capacity import passed
from tools.elf_review import private_path


def checked_pair(root, recovery):
    root, recovery = private_path(root), private_path(recovery)
    profile.check(root)
    row = json.loads(private_read(root / "profile.json", 65536))
    if recovery != Path(row["kit"]):
        raise ValueError("same-kit standalone recovery images required")
    return row, protocol.Binding(
        bytes.fromhex(
            json.loads(
                private_read(recovery / "sequence-commissioning/file-action-profile.json", 1048576)
            )["plan"]
        ),
        bytes.fromhex(
            json.loads(
                private_read(recovery / "replacements/commissioning/backup/receipt.json", 65536)
            )["manifest_sha256"]
        ),
        1,
    )


def bindings(records):
    receipt = json.loads(private_read(Path(records[1]["capsule"]) / "backup/receipt.json", 65536))
    return tuple(
        protocol.Binding(
            bytes.fromhex(r["plan"]),
            bytes.fromhex(receipt["manifest_sha256"] if i == 1 else r["receipt"]),
            1,
        )
        for i, r in enumerate(records)
    )


def pending_stage(output):
    output = private_path(output)
    pending = [
        name
        for name in ("commissioning", "cleanup")
        if (output / name / "preflight.json").exists()
        and not (output / name / "decision.json").exists()
        and not (output / name / "finished.json").exists()
    ]
    return pending[0] if len(pending) == 1 else None


def decide(output, *, commit, expected_action):
    output = private_path(output)
    stage = pending_stage(output)
    if stage is None:
        raise ValueError("one fixed live write stage required")
    return shared.decide(
        output / stage,
        commit=commit,
        expected_action=expected_action,
        checker=lambda root, recovery: stage_checker(
            root, recovery, 1 if stage == "commissioning" else 2
        ),
    )


def stage_checker(root, recovery, stage):
    row, _ = checked_pair(root, recovery)
    _, records = profile.constituents(row["kit"])
    return row, bindings(records)[stage]


def boot(
    root,
    recovery,
    output=None,
    *,
    execute=False,
    handoff_from_acquisition=None,
    handoff_from_backup=None,
):
    root, recovery = private_path(root), private_path(recovery)
    record, binding = checked_pair(root, recovery)
    if not execute:
        return profile.check(root)
    from installer.kit import check as check_kit

    if check_kit(recovery)["review_only"]:
        raise ValueError("review-only kit cannot open USB or write a thermostat")
    if output is None or handoff_from_acquisition is None:
        raise ValueError("fresh output and checked same-session RAM handoff required")
    output = private_path(output)
    if (
        output.exists()
        or output.parent.stat().st_mode & 0o077
        or (root / "execution-started.json").exists()
    ):
        raise ValueError("fresh private sequence output required")
    roots, records = profile.constituents(record["kit"])
    if any((source / "execution-started.json").exists() for source in roots):
        raise ValueError("fresh one-use constituent profiles required")
    from firmware.file_writer.chain import acquisition_install
    from installer.nand_backup import check as check_backup

    acquisition_install(records[1], binding, handoff_from_acquisition)
    session = private_path(handoff_from_acquisition).parent
    if handoff_from_backup is not None and private_path(handoff_from_backup) != session / "nand":
        raise ValueError("same acquisition/backup restart source required")
    check_backup(session)
    if handoff_from_backup is not None:
        from installer.ram_handoff import await_ready

        # Read-only and before any one-use marker: an unreachable or reset
        # backup reader leaves the kit unused, with nothing sent or written.
        await_ready(handoff_from_backup)
    all_bindings = bindings(records)
    execution = {
        "profile": str(root),
        "recovery": str(recovery),
        "pid": os.getpid(),
        "nonce": os.urandom(32).hex(),
        "started_monotonic": time.monotonic(),
        "action": 1,
        "plan": binding.plan.hex(),
    }
    output.mkdir(mode=0o700)
    shared.save(root, "execution-started.json", shared.encode(execution))
    shared.save(output, "execution.json", shared.encode(execution))
    # Every constituent becomes attempted at this boot, even if an earlier
    # stage refuses. No later standalone reuse or continuation is permitted.
    for source in roots:
        shared.save(source, "execution-started.json", shared.encode(execution))
    artifacts = root / "artifacts"
    try:
        if handoff_from_backup is not None:
            from installer.ram_handoff import load

            load(
                artifacts, output, handoff_from_backup, recheck=lambda: checked_pair(root, recovery)
            )
        else:
            subprocess.run(
                [
                    str(artifacts / "omap_loader"),
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
            )  # nosec B603

        def collect(fd, _deadline, _capture):
            from installer.ui import stage

            completed = []
            for index, (name, scoped, child) in enumerate(
                zip(("capacity", "commissioning", "cleanup"), all_bindings, records, strict=True)
            ):
                stage(
                    index + 1,
                    3,
                    (
                        "Checking space for the whole install",
                        "Installing Home Assistant settings",
                        "Installing local connectivity and time server",
                    )[index],
                )
                dest = output / name
                dest.mkdir(mode=0o700)
                live = execution | {
                    "stage": name,
                    "plan": scoped.plan.hex(),
                    "started_monotonic": time.monotonic(),
                }
                shared.save(dest, "execution.json", shared.encode(live))
                # An exclusive marker per stage allows the wizard to offer its
                # next write prompt without replacing earlier evidence.
                if index:
                    shared.save(output, name + "-active.json", shared.encode({"stage": name}))
                factory = (
                    Session
                    if index == 1
                    else lambda b, s, index=index, child=child: NetworkSession(
                        b,
                        s,
                        target_count=3,
                        preflight_only=index == 0,
                        shared_originals="shared_archive" in child,
                    )
                )
                row = shared.receive(
                    fd,
                    dest,
                    scoped,
                    live,
                    lambda: checked_pair(root, recovery),
                    session_factory=factory,
                )
                shared.save(dest, "finished.json", shared.encode({"host_command_exited": True}))
                accepted = (
                    passed(row)
                    if index == 0
                    else bool(
                        row["complete"] and row["safe_to_restart"] and row["encoding_verified"]
                    )
                )
                if not accepted:
                    return {
                        "complete": False,
                        "completed_phases": completed,
                        "capacity_passed": index > 0,
                        "safe_to_restart": bool(row["safe_to_restart"]),
                        "failed_stage": name,
                        "automatic_retry": False,
                    }
                # Persist acknowledgement intent before sending it. An uncertain
                # transfer never authorizes a replay or a second boot.
                shared.save(
                    dest, "terminal-ack-sending.json", shared.encode({"plan": scoped.plan.hex()})
                )
                shared.write_token(fd, scoped.prefix(b"HFW_DONE"))
                shared.save(
                    dest, "terminal-ack-sent.json", shared.encode({"plan": scoped.plan.hex()})
                )
                if index:
                    completed.append(name)
            return {
                "complete": True,
                "completed_phases": completed,
                "safe_to_restart": True,
                "encoding_verified": True,
                "automatic_retry": False,
                "whole_firmware_recovery": "unverified",
            }

        result = observe("1-1", 120, receive_fn=collect)
        shared.save(output, "observed.json", shared.encode(result))
        return result
    finally:
        shared.save(output, "finished.json", shared.encode({"host_command_exited": True}))


# Common installer engine interface; boot still requires explicit execute=True.
run = boot


def attempted_stages(kit):
    """Persistent intent, including a transfer that may have been interrupted."""
    kit = private_path(kit)
    output = kit / "install-combined"
    if json.loads(private_read(output / "finished.json", 4096)) != {"host_command_exited": True}:
        raise ValueError("exited combined host process required before restoration")
    execution = json.loads(private_read(output / "execution.json", 65536))
    if execution != json.loads(
        private_read(kit / "install-sequence/execution-started.json", 65536)
    ):
        raise ValueError("same one-use combined execution required")
    attempted = []
    for name in ("commissioning", "cleanup"):
        sending = output / name / "decision-sending.json"
        if sending.exists():
            value = json.loads(private_read(sending, 65536))
            live = json.loads(private_read(output / name / "execution.json", 65536))
            if value != {"execution": live, "commit": True}:
                if value != {"execution": live, "commit": False}:
                    raise ValueError("exact combined write intent required")
                continue
            if live.get("stage") != name or any(
                live.get(k) != v
                for k, v in execution.items()
                if k not in ("plan", "started_monotonic")
            ):
                raise ValueError("same combined write session required")
            attempted.append(name)
    return attempted


def require_recovery(binding, previous, *, sysfs=Path("/sys/bus/usb/devices")):
    """Admit fresh standalone restoration from a matching exited sequence attempt."""
    previous = private_path(previous)
    if (
        binding.action != 2
        or previous.name not in ("commissioning", "cleanup")
        or previous.parent.name != "install-combined"
    ):
        raise ValueError("fixed sequence stage and original-file restore required")
    kit = previous.parent.parent
    if previous.name not in attempted_stages(kit):
        raise ValueError("matching persistent intent required for RAM recovery")
    record, _ = checked_pair(kit / "install-sequence", kit)
    _, records = profile.constituents(record["kit"])
    expected = bindings(records)[1 if previous.name == "commissioning" else 2]
    live = json.loads(private_read(previous / "execution.json", 65536))
    if (binding.plan, binding.receipt) != (expected.plan, expected.receipt) or live[
        "plan"
    ] != expected.plan.hex():
        raise ValueError("same exact sequence plan and original custody required")
    from firmware.file_writer.chain import ram

    ram(sysfs)
    return {
        "status": "verified-sequence-to-standalone-restore-handoff",
        "native_startup_required": False,
    }
