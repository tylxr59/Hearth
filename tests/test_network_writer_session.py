import json

import pytest

from firmware.file_writer import protocol as p
from firmware.network_writer.session import NetworkSession, result
from tests.test_file_writer_protocol import BINDING
from tests.test_file_writer_protocol import result as legacy_result


def evidence(**changes):
    row = {
        "type": "network_ram_preflight",
        "stream_cases": 41,
        "transaction_cases": 20,
        "child_status": 0,
        "child_output_bytes": 0,
        "real_files_checked": 0,
        "phase": 0,
        "real_preflight": False,
        "flash_writes": False,
        "diagnostic_hex": "",
    }
    row.update(changes)
    return json.dumps(row).encode()


def info(**changes):
    row = {
        "targets": 4,
        "originals_verified": 4,
        "memory_free": 32 * 1048576,
        "space_available": 21 * 1048576,
        "space_required": 19 * 1048576,
    }
    row.update(changes)
    return json.dumps(row).encode()


def session(action=1):
    saved = {}
    return NetworkSession(
        p.Binding(BINDING.plan, BINDING.receipt, action), lambda n, d: saved.setdefault(n, d)
    ), saved


@pytest.mark.parametrize("action", [1, 2])
def test_four_target_end_to_end_ordered_evidence_and_separate_commit(action):
    s, saved = session(action)
    assert s.event(p.SELFTEST, evidence()) == s.binding.prefix(b"HFW_ACK1")
    assert not s.committed
    with pytest.raises(ValueError):
        s.event(p.READY, b"")
    s.event(p.PREFLIGHT_INFO, info())
    s.event(p.READY, b"")
    assert not s.committed
    assert s.decide(True) == s.binding.prefix(b"HFW_RUN1")
    with pytest.raises(ValueError):
        s.decide(True)
    s.event(
        p.RESULT,
        legacy_result(action, attempted=15, restored=0 if action == 1 else 15, program=300),
    )
    assert s.result["complete"] == 1 and set(saved) == {
        "selftest.jsonl",
        "preflight-info.json",
        "result.json",
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"stream_cases": 40},
        {"transaction_cases": 19},
        {"child_status": 11},
        {"child_output_bytes": 1, "diagnostic_hex": "41"},
        {"phase": 1},
        {"real_preflight": True},
        {"real_files_checked": 4},
        {"flash_writes": True},
    ],
)
def test_incomplete_or_wrong_ram_workload_cannot_ack_or_commit(changes):
    s, _ = session()
    with pytest.raises(ValueError):
        s.event(p.SELFTEST, evidence(**changes))
    assert not s.selftest
    with pytest.raises(ValueError):
        s.decide(True)


@pytest.mark.parametrize(
    "changes",
    [
        {"targets": 9},
        {"originals_verified": 3},
        {"memory_free": 24 * 1048576 - 1},
        {"space_available": 10 * 1048576},
        {"space_required": True},
        {"space_available": 1 << 32},
    ],
)
def test_resources_checked_before_ready(changes):
    s, _ = session()
    s.event(p.SELFTEST, evidence())
    with pytest.raises(ValueError):
        s.event(p.PREFLIGHT_INFO, info(**changes))
    assert s.info is None and not s.ready


@pytest.mark.parametrize("kind", [p.SNAPSHOT, p.KERNEL_LOG, b"rejected", b"unknown"])
def test_scope_has_no_old_nine_file_snapshot_or_logs(kind):
    s, _ = session()
    with pytest.raises(ValueError):
        s.event(kind, b"")


def test_four_target_result_refuses_legacy_scope_and_false_program_evidence():
    with pytest.raises(ValueError):
        result(legacy_result(), 1)
    with pytest.raises(ValueError):
        result(legacy_result(attempted=15), 1)
    with pytest.raises(ValueError):
        p.validate_result(legacy_result(attempted=15), 1)
    with pytest.raises(ValueError):
        p.validate_result(legacy_result(3), 3, target_count=4)


def test_resource_repetition_is_exact_and_cannot_reopen_after_result():
    s, _ = session()
    s.event(p.SELFTEST, evidence())
    s.event(p.PREFLIGHT_INFO, info())
    assert s.event(p.PREFLIGHT_INFO, info()) is None
    with pytest.raises(ValueError):
        s.event(p.PREFLIGHT_INFO, info(memory_free=33 * 1048576))
