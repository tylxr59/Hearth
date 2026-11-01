import json

import pytest

from firmware.file_writer import protocol as p
from firmware.file_writer.session import Session
from tests.test_file_writer_protocol import BINDING, result, selftests


def session():
    saved = {}
    return Session(BINDING, lambda name, data: saved.setdefault(name, data)), saved


def test_selftest_ack_once_and_explicit_commit_after_ready():
    s, saved = session()
    assert s.event(p.SELFTEST, selftests()) == BINDING.prefix(b"HFW_ACK1")
    assert s.event(p.SELFTEST, selftests()) is None
    assert not s.committed
    s.event(p.READY, b"")
    assert not s.committed
    assert s.decide(True) == BINDING.prefix(b"HFW_RUN1")
    with pytest.raises(ValueError):
        s.decide(True)
    s.event(p.RESULT, result())
    assert s.result["complete"] == 1
    assert set(saved) == {"selftest.jsonl", "result.json"}
    assert s.event(p.RESULT, result()) is None


def test_no_commit_before_ready_or_after_abort():
    s, _ = session()
    with pytest.raises(ValueError):
        s.decide(True)
    with pytest.raises(ValueError):
        s.event(p.READY, b"")
    s.event(p.SELFTEST, selftests())
    s.event(p.READY, b"")
    assert s.decide(False) == BINDING.prefix(b"HFW_STOP")
    with pytest.raises(ValueError):
        s.decide(True)


def test_invalid_or_changing_selftest_never_acknowledged():
    s, saved = session()
    with pytest.raises(ValueError):
        s.event(p.SELFTEST, b"{}\n")
    assert not s.selftest and saved["selftest.jsonl"] == b"{}\n"
    s, _ = session()
    s.event(p.SELFTEST, selftests())
    with pytest.raises(ValueError):
        s.event(p.SELFTEST, selftests() + b"\n")


def test_result_cannot_invent_host_commit():
    s, saved = session()
    s.event(p.SELFTEST, selftests())
    s.event(p.READY, b"")
    with pytest.raises(ValueError):
        s.event(p.RESULT, result())
    assert "result.json" in saved and s.result is None


def test_failed_initial_preflight_finishes_without_decision():
    s, _ = session()
    s.event(p.SELFTEST, selftests())
    row = dict.fromkeys(p.FIELDS, 0)
    row.update(
        type="file_action",
        action=1,
        preflight_target=7,
        initial_error=2,
        error=-1,
        safe_to_restart=1,
        protected=1,
        phase=2,
    )
    s.event(p.RESULT, json.dumps(row).encode())
    assert not s.ready and s.result["safe_to_restart"] == 1


def test_result_requiring_snapshot_cannot_pass_without_it():
    s, _ = session()
    s.event(p.SELFTEST, selftests())
    row = dict.fromkeys(p.FIELDS, 0)
    row.update(
        type="file_action",
        action=1,
        preflight_target=7,
        initial_error=2,
        error=-1,
        safe_to_restart=1,
        protected=1,
        phase=2,
        snapshot_available=1,
    )
    with pytest.raises(ValueError):
        s.event(p.RESULT, json.dumps(row).encode())


def test_kernel_evidence_is_private_and_never_authorizes_commit():
    s, saved = session()
    s.event(p.SELFTEST, selftests())
    assert s.event(p.KERNEL_LOG, b"synthetic kernel evidence") is None
    assert saved["kernel-log.bin"] == b"synthetic kernel evidence"
    assert not s.ready and not s.committed
    with pytest.raises(ValueError):
        s.decide(True)
