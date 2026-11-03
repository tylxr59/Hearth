"""A failed readback permits only a separately checked protected RAM diagnostic."""

import json
from types import SimpleNamespace

import pytest

from firmware.file_writer import run as writer
from firmware.file_writer.run import encode, save
from firmware.startup_diagnostic.run import sealed_restore_entry
from tests.test_file_writer_protocol import result as result_frame


@pytest.fixture
def sealed(tmp_path, monkeypatch):
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    tmp_path.chmod(0o700)
    execution = {
        "profile": str(tmp_path / "profile"),
        "recovery": str(tmp_path / "profile"),
        "action": 2,
    }
    row = json.loads(
        result_frame(
            2, restored=511, complete=0, safe_to_restart=0, verified=0, encoding_verified=0
        )
    )
    for name, value in (
        ("execution.json", execution),
        ("result.json", row),
        ("observed.json", {"execution": execution, "result": row}),
        ("finished.json", {"host_command_exited": True}),
    ):
        save(tmp_path, name, encode(value))
    calls = []
    monkeypatch.setattr(writer, "checked_pair", lambda *a: ({}, SimpleNamespace(action=2)))
    monkeypatch.setattr(writer, "require_entry", lambda *a: calls.append(a))
    return tmp_path, calls


def test_known_exited_sealed_failure_can_enter_read_only_diagnostic(sealed):
    root, calls = sealed
    assert sealed_restore_entry(root)["flash_writes"] is False
    assert len(calls) == 1


@pytest.mark.parametrize(
    "fault",
    (
        "protected",
        "seal_error",
        "unmount_errors",
        "restored",
        "complete",
        "finished",
        "observation",
    ),
)
def test_unknown_unsealed_or_incomplete_state_cannot_use_diagnostic_entry(sealed, fault):
    root, calls = sealed
    if fault == "finished":
        (root / "finished.json").unlink()
    elif fault == "observation":
        (root / "observed.json").write_bytes(encode({"execution": {}, "result": {}}))
    else:
        row = json.loads((root / "result.json").read_bytes())
        row[fault] = 0 if fault in ("protected", "restored") else 1
        (root / "result.json").write_bytes(encode(row))
        execution = json.loads((root / "execution.json").read_bytes())
        (root / "observed.json").write_bytes(encode({"execution": execution, "result": row}))
    with pytest.raises((ValueError, OSError)):
        sealed_restore_entry(root)
    assert not calls
