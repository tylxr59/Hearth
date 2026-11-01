import hashlib
import json
import os
import socket
import threading
import time

import pytest

from firmware.file_snapshot.run import decode
from firmware.file_writer import protocol as p
from firmware.file_writer import run
from provisioning import file_backup
from tests.test_file_snapshot_profile import frame as snapshot_frame
from tests.test_file_writer_protocol import BINDING, frame, result, selftests


@pytest.fixture
def output(tmp_path, monkeypatch):
    from tools import elf_review

    tmp_path.chmod(0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    return tmp_path


def test_real_socket_handshake_waits_for_explicit_local_decision(output):
    host, target = socket.socketpair()
    target.settimeout(3)
    execution = {
        "pid": os.getpid(),
        "plan": BINDING.plan.hex(),
        "action": 1,
        "profile": str(output),
        "recovery": str(output),
        "started_monotonic": time.monotonic(),
    }
    rechecked, errors = [], []

    def device():
        try:
            target.sendall(frame(p.SELFTEST, selftests()))
            assert target.recv(76) == BINDING.prefix(b"HFW_ACK1")
            target.sendall(frame(p.READY))
            until = time.monotonic() + 3
            while not (output / "preflight.json").exists() and time.monotonic() < until:
                time.sleep(0.01)
            assert not rechecked
            run.save(output, "decision.json", run.encode({"execution": execution, "commit": True}))
            assert target.recv(76) == BINDING.prefix(b"HFW_RUN1")
            assert len(rechecked) == 1
            assert (output / "decision-sending.json").exists()
            target.sendall(frame(p.RESULT, result()))
        except (AssertionError, OSError) as exc:
            errors.append(exc)
        finally:
            target.close()

    thread = threading.Thread(target=device)
    thread.start()
    try:
        observed = run.receive(
            host.fileno(), output, BINDING, execution, lambda: rechecked.append(True)
        )
        assert observed["complete"] == 1
        assert (output / "decision-sent.json").exists()
        assert json.loads((output / "observed.json").read_bytes())["result"] == observed
    finally:
        host.close()
        thread.join(4)
    assert not thread.is_alive() and not errors


def test_bad_selftest_is_preserved_without_ack_or_decision(output):
    host, target = socket.socketpair()
    target.sendall(frame(p.SELFTEST, b"{}\n"))
    try:
        with pytest.raises(ValueError):
            run.receive(host.fileno(), output, BINDING, {}, lambda: pytest.fail("recheck"))
        target.setblocking(False)
        with pytest.raises(BlockingIOError):
            target.recv(76)
        assert (output / "selftest.jsonl").read_bytes() == b"{}\n"
        assert not (output / "decision-sending.json").exists()
    finally:
        host.close()
        target.close()


def test_private_decision_is_bound_to_live_preflight_and_single_use(output, monkeypatch):
    execution = {
        "pid": os.getpid(),
        "started_monotonic": time.monotonic(),
        "profile": str(output),
        "recovery": str(output),
        "action": 1,
        "plan": BINDING.plan.hex(),
    }
    run.save(output, "execution.json", run.encode(execution))
    with pytest.raises(ValueError):
        run.decide(output, commit=True, expected_action=1)
    run.save(output, "preflight.json", run.encode(execution))
    monkeypatch.setattr(run, "checked_pair", lambda *_: ({}, BINDING))
    with pytest.raises(ValueError):
        run.decide(output, commit=True, expected_action=2)
    assert run.decide(output, commit=True, expected_action=1)["device_result"] == "pending"
    with pytest.raises(ValueError):
        run.decide(output, commit=True, expected_action=1)


def test_restore_entry_requires_matching_exited_persistent_attempt_and_ram(output, monkeypatch):
    restore = p.Binding(BINDING.plan, BINDING.receipt, 2)
    execution = {"plan": BINDING.plan.hex(), "profile": str(output), "recovery": str(output)}
    run.save(output, "execution.json", run.encode(execution))
    with pytest.raises(ValueError):
        run.require_entry(restore, output, sysfs=output)
    run.save(output, "finished.json", run.encode({"host_command_exited": True}))
    run.save(output, "decision-sending.json", run.encode({"execution": execution, "commit": True}))
    usb = output / "1-1"
    usb.mkdir()
    (usb / "idVendor").write_text("0451")
    (usb / "idProduct").write_text("d00e")
    monkeypatch.setattr(run, "checked_pair", lambda *_: ({}, BINDING))
    with pytest.raises(ValueError):
        run.require_entry(restore, output, sysfs=output)
    (usb / "idVendor").write_text("0525")
    (usb / "idProduct").write_text("a4a7")
    assert run.require_entry(restore, output, sysfs=output)["native_startup_required"] is False
    with pytest.raises(ValueError):
        run.require_entry(BINDING, output, sysfs=output)
    monkeypatch.setattr(
        run, "checked_pair", lambda *_: ({}, p.Binding(b"x" * 32, BINDING.receipt, 1))
    )
    with pytest.raises(ValueError):
        run.require_entry(restore, output, sysfs=output)


def test_custody_recheck_failure_prevents_commit_token(output):
    host, target = socket.socketpair()
    execution = {"test": "bound session"}
    run.save(output, "decision.json", run.encode({"execution": execution, "commit": True}))
    target.sendall(frame(p.SELFTEST, selftests()) + frame(p.READY))

    def changed():
        raise ValueError("custody changed")

    try:
        with pytest.raises(ValueError):
            run.receive(host.fileno(), output, BINDING, execution, changed)
        target.settimeout(1)
        assert target.recv(76) == BINDING.prefix(b"HFW_ACK1")
        target.setblocking(False)
        with pytest.raises(BlockingIOError):
            target.recv(76)
        assert not (output / "decision-sending.json").exists()
    finally:
        host.close()
        target.close()


@pytest.fixture
def handoff(output):
    previous, capsule = output / "previous", output / "capsule"
    previous.mkdir(mode=0o700)
    capsule.mkdir(mode=0o700)
    execution = {"action": 1, "plan": (b"s" * 32).hex()}
    row = dict.fromkeys(p.FIELDS, 0)
    row.update(
        type="file_action",
        action=1,
        initial_error=2,
        preflight_target=7,
        snapshot_available=1,
        safe_to_restart=1,
        protected=1,
        phase=2,
        error=-2,
    )
    for name, data in {
        "execution.json": run.encode(execution),
        "finished.json": run.encode({"host_command_exited": True}),
        "result.json": run.encode(row),
        "observed.json": run.encode({"execution": execution, "result": row}),
        "selftest.jsonl": selftests(),
        "changed-files.bin": snapshot_frame(),
    }.items():
        run.save(previous, name, data)
    run.save(capsule, "capture.bin", snapshot_frame())
    scope = {
        "session": b"s" * 32,
        "plan": hashlib.sha256(
            b"read-only-root0-snapshot-v1\n" + "\n".join(file_backup.TARGETS).encode()
        ).digest(),
        "native_root": "root0",
    }
    file_backup.preserve(
        previous / "changed-files-backup", decode(snapshot_frame(), b"s" * 32), **scope
    )
    usb = output / "1-1"
    usb.mkdir()
    (usb / "idVendor").write_text("0525")
    (usb / "idProduct").write_text("a4a7")
    return previous, {"capsule": str(capsule)}, output


def test_exact_zero_write_snapshot_allows_supervised_ram_handoff(handoff):
    previous, record, sysfs = handoff
    assert (
        run.require_snapshot_handoff(record, BINDING, previous, sysfs=sysfs)[
            "native_startup_required"
        ]
        is False
    )


@pytest.fixture
def protected_handoff(handoff, monkeypatch):
    from firmware.startup_diagnostic import profile as reader

    previous, record, sysfs = handoff
    source = sysfs / "protected-reader"
    source.mkdir(mode=0o700)
    creation = run.encode({"session": (b"s" * 32).hex()})
    run.save(source, "profile.json", creation)
    run.save(source, "execution-started.json", run.encode({"output": str(previous)}))
    (previous / "execution.json").write_bytes(
        run.encode(
            {
                "profile": str(source),
                "session": (b"s" * 32).hex(),
                "profile_sha256": hashlib.sha256(creation).hexdigest(),
            }
        )
    )
    (previous / "observed.json").write_bytes(
        run.encode(
            {
                "status": "protected-startup-diagnostic-preserved",
                "targets": 9,
                "installed": False,
                "flash_writes": False,
            }
        )
    )
    run.save(previous, "snapshot.bin", snapshot_frame())
    (previous / "changed-files-backup").rename(previous / "backup")
    checked = []
    monkeypatch.setattr(reader, "check", lambda path: checked.append(path))
    return previous, record, sysfs, source, checked


def test_protected_capture_handoff_checks_reader_and_exact_backup(protected_handoff):
    previous, record, sysfs, source, checked = protected_handoff
    assert run.require_snapshot_source(record, BINDING, previous, sysfs=sysfs) == {
        "status": "verified-protected-snapshot-install-handoff",
        "native_startup_required": False,
    }
    assert checked == [source]


@pytest.mark.parametrize(
    "fault",
    (
        "profile",
        "session",
        "output",
        "status",
        "writes",
        "capture",
        "custody",
        "native",
        "rom",
        "action",
        "checker",
    ),
)
def test_protected_capture_handoff_refuses_unbound_or_unsafe_state(
    protected_handoff, fault, monkeypatch
):
    previous, record, sysfs, source, _checked = protected_handoff
    binding = BINDING
    if fault == "profile":
        (source / "profile.json").write_bytes(b"{}")
    elif fault == "session":
        value = json.loads((previous / "execution.json").read_bytes())
        value["session"] = (b"x" * 32).hex()
        (previous / "execution.json").write_bytes(run.encode(value))
    elif fault == "output":
        (source / "execution-started.json").write_bytes(run.encode({"output": str(sysfs)}))
    elif fault in ("status", "writes"):
        value = json.loads((previous / "observed.json").read_bytes())
        value["status" if fault == "status" else "flash_writes"] = "unconfirmed"
        (previous / "observed.json").write_bytes(run.encode(value))
    elif fault == "capture":
        (previous / "snapshot.bin").write_bytes(snapshot_frame(session=b"x" * 32))
    elif fault == "custody":
        (previous / "backup/0.original").write_bytes(b"changed")
    elif fault in ("native", "rom"):
        (sysfs / "1-1/idVendor").write_text("2464" if fault == "native" else "0451")
        (sysfs / "1-1/idProduct").write_text("0002" if fault == "native" else "d00e")
    elif fault == "action":
        binding = p.Binding(BINDING.plan, BINDING.receipt, 2)
    else:
        from firmware.startup_diagnostic import profile as reader

        def reject(_path):
            raise ValueError("reader artifact changed")

        monkeypatch.setattr(reader, "check", reject)
    with pytest.raises(ValueError):
        run.require_snapshot_source(record, binding, previous, sysfs=sysfs)


@pytest.mark.parametrize(
    "fault", ("native", "rom", "decision", "capture", "custody", "result", "selftest")
)
def test_snapshot_handoff_rejects_nonmatching_or_uncertain_prior_state(handoff, fault):
    previous, record, sysfs = handoff
    if fault == "native":
        (sysfs / "1-1/idVendor").write_text("2464")
        (sysfs / "1-1/idProduct").write_text("0002")
    elif fault == "rom":
        (sysfs / "1-1/idVendor").write_text("0451")
        (sysfs / "1-1/idProduct").write_text("d00e")
    elif fault == "decision":
        run.save(previous, "decision-sending.json", b"{}")
    elif fault == "capture":
        (previous / "changed-files.bin").write_bytes(snapshot_frame(session=b"x" * 32))
    elif fault == "custody":
        (previous / "changed-files-backup/0.original").write_bytes(b"tampered")
    elif fault == "result":
        row = json.loads((previous / "result.json").read_bytes())
        row["program"] = 1
        (previous / "result.json").write_bytes(run.encode(row))
    else:
        (previous / "selftest.jsonl").write_bytes(b"{}\n")
    with pytest.raises(ValueError):
        run.require_snapshot_handoff(record, BINDING, previous, sysfs=sysfs)


@pytest.fixture
def readonly_repair(output):
    old = output / "old-profile"
    old.mkdir(mode=0o700)
    record = {
        "status": run.profile.STATUS,
        "action": 3,
        "device_executed": False,
        "selftest_cases": 72,
        "plan": BINDING.plan.hex(),
        "capsule": "fixed private capsule",
        "pin": "fixed private pin",
        "kernel_files": {"kernel": "same frozen kernel"},
    }
    run.save(old, "file-action-profile.json", run.encode(record))
    previous = output / "previous"
    previous.mkdir(mode=0o700)
    execution = {"action": 3, "plan": BINDING.plan.hex(), "profile": str(old)}
    row = dict.fromkeys(p.FIELDS, 0)
    row.update(
        type="file_action",
        action=3,
        initial_error=2,
        preflight_target=-1,
        safe_to_restart=1,
        phase=2,
        protected=1,
        error=-2,
    )
    for name, data in {
        "execution.json": run.encode(execution),
        "result.json": run.encode(row),
        "observed.json": run.encode({"execution": execution, "result": row}),
        "finished.json": run.encode({"host_command_exited": True}),
        "selftest.jsonl": selftests(),
    }.items():
        run.save(previous, name, data)
    usb = output / "1-1"
    usb.mkdir()
    (usb / "idVendor").write_text("0525")
    (usb / "idProduct").write_text("a4a7")
    return previous, record, output


def test_zero_write_repair_resume_keeps_exact_kernel_and_plan(readonly_repair):
    previous, record, sysfs = readonly_repair
    binding = p.Binding(BINDING.plan, BINDING.receipt, 3)
    assert (
        run.require_readonly_resume(record, binding, previous, sysfs=sysfs)[
            "native_startup_required"
        ]
        is False
    )


@pytest.mark.parametrize(
    "fault", ("kernel", "plan", "decision", "native", "rom", "result", "selftest")
)
def test_repair_resume_refuses_changed_or_potentially_written_state(readonly_repair, fault):
    previous, record, sysfs = readonly_repair
    binding = p.Binding(BINDING.plan, BINDING.receipt, 3)
    if fault == "kernel":
        record = dict(record, kernel_files={})
    elif fault == "plan":
        record = dict(record, plan=(b"x" * 32).hex())
    elif fault == "decision":
        run.save(previous, "decision.json", b"{}")
    elif fault in ("native", "rom"):
        (sysfs / "1-1/idVendor").write_text("2464" if fault == "native" else "0451")
        (sysfs / "1-1/idProduct").write_text("0002" if fault == "native" else "d00e")
    elif fault == "selftest":
        (previous / "selftest.jsonl").write_bytes(b"{}\n")
    else:
        row = json.loads((previous / "result.json").read_bytes())
        row["program"] = 1
        (previous / "result.json").write_bytes(run.encode(row))
    with pytest.raises(ValueError):
        run.require_readonly_resume(record, binding, previous, sysfs=sysfs)
