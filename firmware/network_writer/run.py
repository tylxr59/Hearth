"""Explicit owner-timed network update boot and separate one-shot decision.

No auto retry/commit. An incomplete persistent action requires review with USB
power maintained; it is never silently treated as permission to boot native code.
"""

import argparse
import json
import os
import subprocess  # nosec B404
import time
from pathlib import Path

from firmware.file_writer import protocol
from firmware.file_writer import run as shared
from firmware.network_writer.profile import check
from firmware.network_writer.session import NetworkSession
from firmware.probe.observe import require_native
from firmware.settings_compat_probe.observe import observe
from firmware.tls_probe.package import private_read
from tools.elf_review import private_path


def checked_pair(root, recovery):
    root, recovery = private_path(root), private_path(recovery)
    check(root)
    check(recovery)
    record = json.loads(private_read(root / "profile.json", 65536))
    restore = json.loads(private_read(recovery / "profile.json", 65536))
    if restore["action"] != 2 or any(
        record[k] != restore[k]
        for k in ("kernel", "libraries", "plan_path", "backup", "pin", "plan", "receipt", "recipes")
    ):
        raise ValueError("matching fully checked four-file restore profile required")
    return record, protocol.Binding(
        bytes.fromhex(record["plan"]), bytes.fromhex(record["receipt"]), record["action"]
    )


def require_entry(binding, previous=None, *, sysfs=Path("/sys/bus/usb/devices")):
    if previous is None:
        return require_native("1-1", sysfs=sysfs)
    if binding.action != 2:
        raise ValueError("direct RAM recovery is restore-only")
    previous = private_path(previous)
    execution = json.loads(private_read(previous / "execution.json", 65536))
    ended = json.loads(private_read(previous / "finished.json", 65536))
    sending = json.loads(private_read(previous / "decision-sending.json", 65536))
    if (
        ended != {"host_command_exited": True}
        or sending != {"execution": execution, "commit": True}
        or execution["plan"] != binding.plan.hex()
    ):
        raise ValueError("matching exited persistent network attempt required")
    _, prior = checked_pair(execution["profile"], execution["recovery"])
    if (prior.plan, prior.receipt) != (binding.plan, binding.receipt):
        raise ValueError("recovery plan/receipt differs")
    usb = sysfs / "1-1"
    if ((usb / "idVendor").read_text().strip(), (usb / "idProduct").read_text().strip()) not in (
        ("0525", "a4a7"),
        ("0525", "a4a6"),
    ):
        raise ValueError("known exited RAM session required; no automatic retry")
    return {"status": "reviewed-network-ram-recovery-entry"}


def boot(root, recovery, output=None, *, execute=False, recover_from=None):
    root, recovery = private_path(root), private_path(recovery)
    record, binding = checked_pair(root, recovery)
    if not execute:
        return {
            "status": "network-install-restore-pair-checked",
            "action": binding.action,
            "device_executed": False,
            "targets": 4,
        }
    if output is None:
        raise ValueError("fresh private execution output required")
    output = private_path(output)
    if (
        output.exists()
        or output.is_symlink()
        or output.parent.stat().st_mode & 0o077
        or (root / "execution-started.json").exists()
    ):
        raise ValueError("fresh one-use private profile and output required")
    require_entry(binding, recover_from)
    output.mkdir(mode=0o700)
    execution = {
        "profile": str(root),
        "recovery": str(recovery),
        "action": binding.action,
        "plan": binding.plan.hex(),
        "pid": os.getpid(),
        "started_monotonic": time.monotonic(),
        "nonce": os.urandom(32).hex(),
        "recover_from": str(private_path(recover_from)) if recover_from is not None else None,
    }
    shared.save(root, "execution-started.json", shared.encode(execution))
    shared.save(output, "execution.json", shared.encode(execution))
    print(
        "EXPERIMENTAL FOUR-FILE NETWORK UPDATE: root0-only write-capable kernel, initially protected.61 RAM checks then real-file/space/memory preflight; separate scoped commit required. Keep USB connected and base detached. Whole-firmware recovery remains unverified.",
        flush=True,
    )
    print("Waiting up to90 seconds for the reviewed manual ROM restart.", flush=True)
    a = root / "artifacts"
    try:
        subprocess.run(
            [
                str(a / "omap_loader"),
                "-f",
                str(a / "x-load-gen2.bin"),
                "-f",
                str(a / "u-boot.bin"),
                "-a",
                "0x80100000",
                "-f",
                str(a / "uImage"),
                "-a",
                "0x80a00000",
                "-j",
                "0x80100000",
            ],
            check=True,
            timeout=90,
        )  # nosec B603

        def collect(fd, _deadline, _capture):
            return shared.receive(
                fd,
                output,
                binding,
                execution,
                lambda: checked_pair(root, recovery),
                session_factory=NetworkSession,
                ready_message="All61 RAM checks and four real-file/resource preflights passed. Paused before writes; waiting for separate local commit/abort.",
            )

        row = observe("1-1", 120, receive_fn=collect)
        return {
            "status": "network-file-action-observed",
            "action": record["action"],
            "complete": bool(row["complete"]),
            "safe_to_restart": bool(row["safe_to_restart"]),
            "encoding_verified": bool(row["encoding_verified"]),
            "recovery": "whole-firmware-unverified",
        }
    finally:
        shared.save(output, "finished.json", shared.encode({"host_command_exited": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("boot")
    p.add_argument("profile")
    p.add_argument("recovery")
    p.add_argument("output", nargs="?")
    p.add_argument("--execute-supervised-network-update", action="store_true")
    p.add_argument("--recover-from")
    for name in ("commit", "abort"):
        p = sub.add_parser(name)
        p.add_argument("output")
        p.add_argument("--action", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    try:
        value = (
            boot(
                args.profile,
                args.recovery,
                args.output,
                execute=args.execute_supervised_network_update,
                recover_from=args.recover_from,
            )
            if args.command == "boot"
            else shared.decide(
                args.output,
                commit=args.command == "commit",
                expected_action=args.action,
                checker=checked_pair,
            )
        )
        print(json.dumps(value, indent=2))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(
            1,
            "Network action incomplete ("
            + type(exc).__name__
            + "). Keep USB connected; review private evidence before restart. No automatic retry.\n",
        )
