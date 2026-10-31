import json
import os
import socket
import threading
import time

import pytest

from firmware.file_writer import protocol as p
from firmware.file_writer import run
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
