import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from firmware.file_writer import chain
from firmware.file_writer.run import encode, save
from tests import test_installer_replacements as stock_module
from tests.test_file_writer_protocol import BINDING, result, selftests
from tests.test_network_writer_session import evidence

stock_inputs = stock_module.stock


@pytest.fixture
def ram_usb(tmp_path):
    root = tmp_path / "sysfs"
    (root / "1-1").mkdir(parents=True)
    (root / "1-1/idVendor").write_text("0525")
    (root / "1-1/idProduct").write_text("a4a7")
    return root


@pytest.fixture
def acquisition(stock_inputs, ram_usb, monkeypatch):
    session, _, output, _ = stock_inputs
    acquired = session / "acquisition"
    source = session / "reader-profile"
    source.mkdir(mode=0o700)
    creation = encode({"session": "73" * 32})
    save(source, "profile.json", creation)
    save(
        source,
        "execution-started.json",
        encode(
            {"output": str(acquired), "once": True, "operation": "read-only-installer-acquisition"}
        ),
    )
    save(
        acquired,
        "execution.json",
        encode(
            {
                "profile": str(source),
                "profile_sha256": hashlib.sha256(creation).hexdigest(),
                "session": "73" * 32,
                "flash_writes": False,
            }
        ),
    )
    save(acquired, "finished.json", encode({"host_command_exited": True}))
    save(
        acquired,
        "observed.json",
        encode(
            {
                "status": "protected-installer-inputs-preserved",
                "fixed_snapshots": 2,
                "library_groups": 4,
                "flash_writes": False,
                "native_execution": False,
            }
        ),
    )
    output.mkdir(mode=0o700)
    save(output, "capture.bin", (acquired / "capture.bin").read_bytes())
    monkeypatch.setattr(chain, "check_acquisition", lambda _: {"checked": True})
    return acquired, {"capsule": str(output)}, ram_usb


def test_protected_acquisition_handoff_requires_completed_bound_custody(acquisition):
    acquired, record, sysfs = acquisition
    assert (
        chain.acquisition_install(record, BINDING, acquired, sysfs=sysfs)["native_startup_required"]
        is False
    )


@pytest.mark.parametrize(
    "fault", ("profile", "nonce", "native_execution", "incomplete", "capsule", "rom", "restore")
)
def test_acquisition_handoff_refuses_stale_or_unrelated_capture(acquisition, fault):
    acquired, record, sysfs = acquisition
    binding = BINDING
    if fault in ("profile", "nonce"):
        path = acquired / "execution.json"
        row = json.loads(path.read_bytes())
        row["profile_sha256" if fault == "profile" else "session"] = "00" * 32
        path.write_bytes(encode(row))
    elif fault == "native_execution":
        path = acquired / "observed.json"
        row = json.loads(path.read_bytes())
        row["native_execution"] = True
        path.write_bytes(encode(row))
    elif fault == "incomplete":
        (acquired / "completion.bin").unlink()
    elif fault == "capsule":
        from pathlib import Path

        (Path(record["capsule"]) / "capture.bin").write_bytes(b"different")
    elif fault == "rom":
        (sysfs / "1-1/idVendor").write_text("0451")
        (sysfs / "1-1/idProduct").write_text("d00e")
    else:
        binding = replace(binding, action=2)
    with pytest.raises((ValueError, OSError)):
        chain.acquisition_install(record, binding, acquired, sysfs=sysfs)


@pytest.fixture(params=(9, 3, 4))
def finished_phase(tmp_path, monkeypatch, request):
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    previous = tmp_path / "phase"
    previous.mkdir(mode=0o700)
    profile = tmp_path / "profile"
    profile.mkdir(mode=0o700)
    count = request.param
    action = 1 if count == 9 else 2
    binding = replace(BINDING, action=action)
    execution = {
        "profile": str(profile),
        "recovery": str(profile),
        "action": action,
        "plan": binding.plan.hex(),
    }
    row = result(
        action,
        attempted=(1 << count) - 1,
        restored=0 if action == 1 else (1 << count) - 1,
        program=10,
    )
    save(profile, "execution-started.json", encode(execution))
    for name, data in {
        "execution.json": encode(execution),
        "preflight.json": encode(execution),
        "decision-sending.json": encode({"execution": execution, "commit": True}),
        "decision-sent.json": encode({"execution": execution, "commit": True}),
        "finished.json": encode({"host_command_exited": True}),
        "result.json": row,
        "selftest.jsonl": selftests() if count == 9 else evidence(),
        "observed.json": encode({"execution": execution, "result": json.loads(row)}),
    }.items():
        save(previous, name, data)
    engine = SimpleNamespace(checked_pair=lambda *_: ({"base": "fixture"}, binding))
    return previous, engine, action, count


def test_completed_phase_needs_real_owner_decision_selftests_and_sealed_result(finished_phase):
    previous, engine, action, count = finished_phase
    assert chain.completed(previous, engine, action, count) == {"base": "fixture"}


@pytest.mark.parametrize(
    "fault",
    ("uncommitted", "not_sent", "still_running", "selftest", "unsafe", "different_execution"),
)
def test_partial_or_contradictory_prior_phase_cannot_arm_next_loader(finished_phase, fault):
    previous, engine, action, count = finished_phase
    if fault == "uncommitted":
        path = previous / "decision-sending.json"
        row = json.loads(path.read_bytes())
        row["commit"] = False
        path.write_bytes(encode(row))
    elif fault == "not_sent":
        (previous / "decision-sent.json").unlink()
    elif fault == "still_running":
        (previous / "finished.json").unlink()
    elif fault == "selftest":
        (previous / "selftest.jsonl").write_bytes(b"incomplete")
    elif fault == "unsafe":
        path = previous / "result.json"
        row = json.loads(path.read_bytes())
        row["safe_to_restart"] = 0
        path.write_bytes(encode(row))
    else:
        path = previous / "observed.json"
        row = json.loads(path.read_bytes())
        row["execution"]["plan"] = "00" * 32
        path.write_bytes(encode(row))
    with pytest.raises((ValueError, OSError)):
        chain.completed(previous, engine, action, count)
