"""One supervised RAM boot; a separate local decision permits persistent work.

There is no automatic retry or commit. Unknown post-write state requires review
with USB power retained, rather than a generic instruction to boot native code.
"""

import argparse
import hashlib
import json
import os
import select
import subprocess  # nosec B404
import time
from pathlib import Path

from firmware.file_writer import profile, protocol
from firmware.file_writer.session import Session
from firmware.probe.observe import require_native
from firmware.settings_compat_probe.observe import observe
from firmware.tls_probe.package import private_read
from provisioning import file_backup
from tools.elf_review import private_path


def save(root, name, data):
    """Exclusive, durable private evidence. Names are repository constants."""
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def checked_pair(root, recovery):
    root, recovery = private_path(root), private_path(recovery)
    profile.check(root)
    profile.check(recovery)
    record = json.loads(private_read(root / "file-action-profile.json", 1024 * 1024))
    restore = json.loads(private_read(recovery / "file-action-profile.json", 1024 * 1024))
    if restore["action"] != 2 or any(
        record[key] != restore[key]
        for key in ("plan", "capsule", "pin", "kernel_files", "helpers_files", "recipes")
    ):
        raise ValueError("matching checked restoration image required before a boot")
    receipt = json.loads(private_read(Path(record["capsule"]) / "backup/receipt.json", 65536))
    binding = protocol.Binding(
        bytes.fromhex(record["plan"]), bytes.fromhex(receipt["manifest_sha256"]), record["action"]
    )
    return record, binding


def write_token(fd, token):
    """Continue short writes of one fixed token; never repeat the logical command."""
    deadline, at = time.monotonic() + 5, 0
    while at < len(token) and time.monotonic() < deadline:
        if not select.select([], [fd], [], 0.1)[1]:
            continue
        try:
            count = os.write(fd, token[at:])
        except (BlockingIOError, InterruptedError):
            continue
        if count <= 0:
            raise OSError("USB token transfer disconnected")
        at += count
    if at != len(token):
        raise TimeoutError("fixed scoped token incomplete; no logical retry")


def require_entry(binding, recover_from=None, *, sysfs=Path("/sys/bus/usb/devices")):
    if recover_from is None:
        return require_native("1-1", sysfs=sysfs)
    # Avoid starting potentially partial native files after an interrupted write.
    # Accept only known RAM mode and a matching exited persistent attempt.
    if binding.action != 2:
        raise ValueError("RAM recovery entry is restricted to the restore image")
    previous = private_path(recover_from)
    execution = json.loads(private_read(previous / "execution.json", 65536))
    ended = json.loads(private_read(previous / "finished.json", 65536))
    sending = json.loads(private_read(previous / "decision-sending.json", 65536))
    if (
        ended != {"host_command_exited": True}
        or sending != {"execution": execution, "commit": True}
        or execution["plan"] != binding.plan.hex()
    ):
        raise ValueError("matching exited persistent attempt required for recovery entry")
    _, prior = checked_pair(execution["profile"], execution["recovery"])
    if (prior.plan, prior.receipt) != (binding.plan, binding.receipt):
        raise ValueError("recovery custody differs from interrupted attempt")
    usb = sysfs / "1-1"
    identity = ((usb / "idVendor").read_text().strip(), (usb / "idProduct").read_text().strip())
    if identity not in (("0525", "a4a7"), ("0525", "a4a6")):
        raise ValueError("known failed-session RAM mode required; no stale ROM or automatic retry")
    return {"status": "reviewed-interrupted-session-ram-entry", "native_startup_required": False}


def require_snapshot_handoff(record, binding, previous, *, sysfs=Path("/sys/bus/usb/devices")):
    """One owner-timed RAM handoff from a verified zero-write changed-file run.

    Native startup can rewrite identical settings values in a new byte order.
    Keep exact byte checks, and bind the new plan to the preceding captured bytes
    instead of requiring another native boot that invalidates its own snapshot.
    """
    if binding.action != 1:
        raise ValueError("snapshot handoff is restricted to fresh install preflight")
    previous = private_path(previous)
    execution = json.loads(private_read(previous / "execution.json", 65536))
    ended = json.loads(private_read(previous / "finished.json", 65536))
    result = protocol.validate_result(private_read(previous / "result.json", 16384), 1)
    observed = json.loads(private_read(previous / "observed.json", 65536))
    protocol.validate_selftest(private_read(previous / "selftest.jsonl", 16384))
    if (
        ended != {"host_command_exited": True}
        or observed != {"execution": execution, "result": result}
        or execution["action"] != 1
        or any(
            (previous / name).exists()
            for name in ("decision.json", "decision-sending.json", "decision-sent.json")
        )
        or any(
            result[key] != value
            for key, value in {
                "initial_error": 2,
                "snapshot_available": 1,
                "commit_received": 0,
                "window_opened": 0,
                "rw_attempted": 0,
                "transaction_called": 0,
                "program": 0,
                "erase": 0,
                "marker": 0,
                "failed": 0,
                "phase": 2,
                "protected": 1,
                "safe_to_restart": 1,
            }.items()
        )
    ):
        raise ValueError("verified completed zero-write snapshot attempt required")
    capsule = private_path(record["capsule"])
    source = private_read(previous / "changed-files.bin", protocol.MAX_SNAPSHOT + 56)
    if source != private_read(capsule / "capture.bin", protocol.MAX_SNAPSHOT + 56):
        raise ValueError("fresh capsule is not bound to this exact RAM capture")
    from firmware.file_snapshot.run import decode

    records = decode(source, bytes.fromhex(execution["plan"]))
    scope = {
        "session": bytes.fromhex(execution["plan"]),
        "plan": hashlib.sha256(
            b"read-only-root0-snapshot-v1\n" + "\n".join(file_backup.TARGETS).encode()
        ).digest(),
        "native_root": "root0",
    }
    file_backup.verify(previous / "changed-files-backup", records, **scope)
    usb = sysfs / "1-1"
    identity = ((usb / "idVendor").read_text().strip(), (usb / "idProduct").read_text().strip())
    if identity not in (("0525", "a4a7"), ("0525", "a4a6")):
        raise ValueError("known snapshot RAM mode required; no native restart or stale ROM")
    return {"status": "reviewed-zero-write-snapshot-handoff", "native_startup_required": False}


def receive(fd, output, binding, execution, recheck):
    session = Session(binding, lambda name, data: save(output, name, data))
    decoder = protocol.Decoder(binding)
    deadline, ready_saved = time.monotonic() + 240, False
    while time.monotonic() < deadline:
        if session.ready and not ready_saved:
            save(output, "preflight.json", encode(execution))
            ready_saved = True
            deadline = time.monotonic() + 540  # Below target's 600-second bound.
            print(
                "RAM selftests and real-file read-only preflight passed. Waiting for a separate local commit or abort; no writes authorized yet.",
                flush=True,
            )
        decision = output / "decision.json"
        if ready_saved and not session.committed and not session.aborted and decision.exists():
            value = json.loads(private_read(decision, 65536))
            if (
                set(value) != {"execution", "commit"}
                or value["execution"] != execution
                or type(value["commit"]) is not bool
            ):
                raise ValueError("decision does not match this live execution")
            recheck()  # Exact original/capsule/backup/image bytes before sending.
            token = session.decide(value["commit"])
            # Durable evidence BEFORE the first byte of a potentially dangerous
            # token. Any later transport failure is treated as uncertain.
            save(output, "decision-sending.json", encode(value))
            write_token(fd, token)
            save(output, "decision-sent.json", encode(value))
            deadline = time.monotonic() + 300
        if not select.select([fd], [], [], 0.2)[0]:
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            raise OSError("USB report interface disconnected")
        for kind, payload in decoder.feed(chunk):
            reply = session.event(kind, payload)
            if reply is not None:
                write_token(fd, reply)
            if session.result is not None:
                if session.snapshot is not None:
                    scope = {
                        "session": binding.plan,
                        "plan": hashlib.sha256(
                            b"read-only-root0-snapshot-v1\n"
                            + "\n".join(file_backup.TARGETS).encode()
                        ).digest(),
                        "native_root": "root0",
                    }
                    file_backup.preserve(output / "changed-files-backup", session.snapshot, **scope)
                    file_backup.verify(output / "changed-files-backup", session.snapshot, **scope)
                save(
                    output,
                    "observed.json",
                    encode({"execution": execution, "result": session.result}),
                )
                return session.result
    raise TimeoutError("RAM session expired; no automatic retry or commit")


def decide(output, *, commit, expected_action):
    output = private_path(output)
    execution = json.loads(private_read(output / "execution.json", 65536))
    if execution != json.loads(private_read(output / "preflight.json", 65536)):
        raise ValueError("exact live preflight required")
    if any((output / name).exists() for name in ("finished.json", "result.json", "decision.json")):
        raise ValueError("execution is no longer awaiting its first decision")
    if type(expected_action) is not int or expected_action != execution["action"]:
        raise ValueError("explicit install/restore action must match live profile")
    if not 0 <= time.monotonic() - execution["started_monotonic"] < 780:
        raise ValueError("execution decision has expired")
    os.kill(execution["pid"], 0)  # Fail closed when the waiting host process exited.
    _, binding = checked_pair(execution["profile"], execution["recovery"])
    if binding.action != expected_action or binding.plan.hex() != execution["plan"]:
        raise ValueError("live execution plan changed")
    save(output, "decision.json", encode({"execution": execution, "commit": commit}))
    return {"status": "local-decision-recorded", "commit": commit, "device_result": "pending"}


def run(root, recovery, output=None, *, execute=False, recover_from=None, handoff_from=None):
    root, recovery = private_path(root), private_path(recovery)
    record, binding = checked_pair(root, recovery)
    if not execute:
        return {"status": "paired-install-restore-offline-checked", "device_executed": False}
    if output is None:
        raise ValueError("fresh private output required")
    output = private_path(output)
    if output.exists() or output.is_symlink() or output.parent.stat().st_mode & 0o077:
        raise ValueError("fresh owner-only output required")
    if handoff_from is not None:
        if recover_from is not None:
            raise ValueError("one explicit RAM entry reason required")
        require_snapshot_handoff(record, binding, handoff_from)
    else:
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
        "handoff_from": str(private_path(handoff_from)) if handoff_from is not None else None,
    }
    save(root, "execution-started.json", encode(execution))
    save(output, "execution.json", encode(execution))
    print(
        "EXPERIMENTAL FILE-ACTION RAM BOOT: write-capable kernel, initially protected. Real files remain read-only until a separate scoped commit. Whole-firmware recovery remains unverified.",
        flush=True,
    )
    print(
        "Keep USB connected and the unwired base detached. Waiting up to 90 seconds for the reviewed ROM restart.",
        flush=True,
    )
    artifacts = root / "artifacts"
    try:
        subprocess.run(  # nosec B603
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
        )

        def capture(fd, _deadline, _capture):
            return receive(fd, output, binding, execution, lambda: checked_pair(root, recovery))

        result = observe("1-1", 120, receive_fn=capture)
        return {
            "status": "file-action-observed",
            "action": record["action"],
            "complete": bool(result["complete"]),
            "safe_to_restart": bool(result["safe_to_restart"]),
            "changed_files_preserved": bool(result["snapshot_available"]),
            "recovery": "whole-firmware-unverified",
        }
    finally:
        save(output, "finished.json", encode({"host_command_exited": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    boot = sub.add_parser("boot")
    boot.add_argument("profile")
    boot.add_argument("recovery")
    boot.add_argument("output", nargs="?")
    boot.add_argument("--execute-writer-preflight", action="store_true")
    entry = boot.add_mutually_exclusive_group()
    entry.add_argument("--recover-from", help="reviewed exited private write attempt; restore only")
    entry.add_argument("--handoff-from", help="verified zero-write snapshot attempt; install only")
    decision = sub.add_parser("decide")
    decision.add_argument("output")
    flags = decision.add_mutually_exclusive_group(required=True)
    flags.add_argument("--execute-persistent-file-install", action="store_true")
    flags.add_argument("--execute-persistent-file-restore", action="store_true")
    flags.add_argument("--abort", type=int, choices=(1, 2))
    args = parser.parse_args()
    try:
        if args.command == "boot":
            result = run(
                args.profile,
                args.recovery,
                args.output,
                execute=args.execute_writer_preflight,
                recover_from=args.recover_from,
                handoff_from=args.handoff_from,
            )
        else:
            action = args.abort or (1 if args.execute_persistent_file_install else 2)
            result = decide(args.output, commit=args.abort is None, expected_action=action)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(
            1,
            "File action not confirmed ("
            + type(exc).__name__
            + "). Keep USB power connected and base detached. Review private evidence before any restart; no automatic retry.\n",
        )
