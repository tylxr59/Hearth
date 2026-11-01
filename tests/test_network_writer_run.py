import json
import os
import time
from pathlib import Path

import pytest

from firmware.file_writer import run as shared
from firmware.file_writer.protocol import Binding
from firmware.network_writer import run


@pytest.fixture(autouse=True)
def private_fixture(tmp_path, monkeypatch):
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)


B = Binding(b"p" * 32, b"r" * 32, 1)


def test_offline_pair_never_opens_usb_and_requires_same_restore_custody(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    a = tmp_path / "install"
    b = tmp_path / "restore"
    a.mkdir()
    b.mkdir()
    row = {
        "action": 1,
        "plan": B.plan.hex(),
        "receipt": B.receipt.hex(),
        **{k: k for k in ("kernel", "libraries", "plan_path", "backup", "pin", "recipes")},
    }
    (a / "profile.json").write_text(json.dumps(row))
    row["action"] = 2
    (b / "profile.json").write_text(json.dumps(row))
    monkeypatch.setattr(run, "check", lambda *_: None)
    monkeypatch.setattr(run, "require_entry", lambda *_: pytest.fail("offline pair opened USB"))
    assert run.boot(a, b)["device_executed"] is False
    row["receipt"] = (b"x" * 32).hex()
    (b / "profile.json").write_text(json.dumps(row))
    with pytest.raises(ValueError):
        run.checked_pair(a, b)


@pytest.mark.parametrize(
    "fault",
    ["none", "wrong-action", "expired", "no-live-pid", "wrong-plan", "already-sending", "finished"],
)
def test_network_commit_requires_live_exact_preflight_single_use(tmp_path, monkeypatch, fault):
    tmp_path.chmod(0o700)
    row = {
        "pid": os.getpid(),
        "started_monotonic": time.monotonic(),
        "profile": str(tmp_path),
        "recovery": str(tmp_path),
        "action": 1,
        "plan": B.plan.hex(),
    }
    if fault == "expired":
        row["started_monotonic"] -= 1000
    if fault == "wrong-plan":
        row["plan"] = (b"q" * 32).hex()
    shared.save(tmp_path, "execution.json", shared.encode(row))
    shared.save(tmp_path, "preflight.json", shared.encode(row))
    if fault == "already-sending":
        shared.save(tmp_path, "decision-sending.json", b"{}")
    if fault == "finished":
        shared.save(tmp_path, "finished.json", b"{}")
    if fault == "no-live-pid":
        monkeypatch.setattr(
            shared.os, "kill", lambda *_: (_ for _ in ()).throw(ProcessLookupError())
        )
    checker = lambda *_: ({}, B)
    if fault == "none":
        assert (
            shared.decide(tmp_path, commit=True, expected_action=1, checker=checker)[
                "device_result"
            ]
            == "pending"
        )
        with pytest.raises(ValueError):
            shared.decide(tmp_path, commit=True, expected_action=1, checker=checker)
    else:
        with pytest.raises((ValueError, ProcessLookupError)):
            shared.decide(
                tmp_path,
                commit=True,
                expected_action=2 if fault == "wrong-action" else 1,
                checker=checker,
            )
        assert not (tmp_path / "decision.json").exists()


def test_restore_entry_refuses_install_profile_before_any_device_read(tmp_path):
    with pytest.raises(ValueError):
        run.require_entry(B, tmp_path, sysfs=Path("/nonexistent"))
