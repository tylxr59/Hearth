import json
import struct
import zlib

import pytest

from firmware.file_writer import protocol as p

BINDING = p.Binding(b"p" * 32, b"r" * 32, 1)


def frame(kind, payload=b"", binding=BINDING):
    prefix = binding.prefix(kind)
    return (
        prefix
        if kind == p.READY
        else prefix + struct.pack("<II", len(payload), zlib.crc32(payload)) + payload + p.END
    )


def selftests():
    rows = [
        {"type": kind, "case": case, "passed": True}
        for kind, cases in (("file_case", p.FILE_CASES), ("recovery_case", p.RECOVERY_CASES))
        for case in sorted(cases)
    ]
    data = b"".join(json.dumps(row).encode() + b"\n" for row in rows)
    return (
        data
        + json.dumps(
            {
                "type": "file_selftest_process",
                "wait_status": 0,
                "stderr_bytes": 0,
                "stderr_dropped": 0,
                "stdout_bytes": len(data),
            }
        ).encode()
        + b"\n"
    )


def result(action=1, **changes):
    row = dict.fromkeys(p.FIELDS, 0)
    row.update(
        type="file_action",
        action=action,
        preflight_target=-1,
        commit_received=1,
        window_opened=1,
        rw_attempted=3,
        transaction_called=1,
        attempted=511,
        committed=int(action == 1),
        restored=511 if action == 2 else 0,
        verified=1,
        safe_to_restart=1,
        complete=1,
        phase=2,
        protected=1,
    )
    row.update(changes)
    return json.dumps(row).encode()


def test_fragmented_frames_bind_exact_plan_receipt_and_action():
    decoder = p.Decoder(BINDING)
    data = (
        b"startup noise"
        + frame(p.SELFTEST, selftests())
        + frame(p.READY)
        + frame(p.RESULT, result())
    )
    events = []
    for byte in data:
        events.extend(decoder.feed(bytes([byte])))
    assert [kind for kind, _ in events] == [p.SELFTEST, p.READY, p.RESULT]
    assert p.validate_selftest(events[0][1])["cases"] == 56
    assert p.validate_result(events[2][1], 1)["complete"] == 1
    wrong = p.Binding(b"q" * 32, BINDING.receipt, 1)
    assert p.Decoder(BINDING).feed(frame(p.READY, binding=wrong)) == []


def test_bad_crc_preserved_and_rejection_bounded():
    data = bytearray(frame(p.RESULT, result()))
    data[-9] ^= 1
    decoder = p.Decoder(BINDING)
    for _ in range(4):
        assert decoder.feed(data)[0][0] == b"rejected"
    with pytest.raises(ValueError):
        decoder.feed(data)


@pytest.mark.parametrize("kind", (p.SELFTEST, p.RESULT, p.SNAPSHOT))
def test_declared_frame_size_checked_before_allocation(kind):
    limit = p.MAX_SNAPSHOT if kind == p.SNAPSHOT else p.MAX_PAYLOAD
    with pytest.raises(ValueError):
        p.Decoder(BINDING).feed(BINDING.prefix(kind) + struct.pack("<II", limit + 1, 0))


@pytest.mark.parametrize(
    "change",
    (
        {"wait_status": 11},
        {"stderr_bytes": 1},
        {"stderr_dropped": 1},
        {"stdout_bytes": 1},
    ),
)
def test_selftest_process_failure_cannot_authorize_action(change):
    lines = selftests().splitlines()
    row = json.loads(lines[-1])
    row.update(change)
    lines[-1] = json.dumps(row).encode()
    with pytest.raises(ValueError):
        p.validate_selftest(b"\n".join(lines) + b"\n")


def test_selftest_duplicate_or_missing_cases_rejected():
    data = selftests()
    with pytest.raises(ValueError):
        p.validate_selftest(data.split(b"\n", 1)[1])
    with pytest.raises(ValueError):
        p.validate_selftest(data.splitlines(keepends=True)[0] + data)


@pytest.mark.parametrize("action", (1, 2))
def test_complete_result_requires_exact_transaction_and_readback(action):
    assert p.validate_result(result(action), action)["complete"] == 1
    for name, value in (
        ("verified", 0),
        ("protected", 0),
        ("phase", 1),
        ("unmount_errors", 1),
        ("attempted", 255),
        ("commit_received", 0),
        ("failed", 1),
    ):
        with pytest.raises(ValueError):
            p.validate_result(result(action, **{name: value}), action)


@pytest.mark.parametrize(
    "changes",
    (
        {"complete": 0, "initial_error": 2},
        {"complete": 0, "window_opened": 0},
        {"complete": 0, "transaction_called": 0},
        {"complete": 0, "rw_attempted": 0},
        {"complete": 0, "snapshot_available": 1},
        {"complete": 0, "error": -1},
        {"complete": 0, "restored": 1},
        {"complete": True},
    ),
)
def test_inconsistent_or_noninteger_results_rejected(changes):
    with pytest.raises(ValueError):
        p.validate_result(result(**changes), 1)


def test_clean_abort_can_report_restart_without_claiming_install():
    row = dict.fromkeys(p.FIELDS, 0)
    row.update(
        type="file_action",
        action=1,
        preflight_target=-1,
        error=-1,
        safe_to_restart=1,
        phase=2,
        protected=1,
    )
    assert p.validate_result(json.dumps(row).encode(), 1)["complete"] == 0


def test_snapshot_reuses_strict_nine_file_scope():
    payload = struct.pack("<II", 0, 9)
    for target in range(9):
        absent = target in (4, 5)
        payload += struct.pack("<6I", target, int(not absent), 0 if absent else 0o644, 0, 0, 0)
    saved, records = p.snapshot_frame(payload, BINDING)
    assert len(records) == 9 and saved.startswith(b"HFSNAP1\n" + BINDING.plan)
    with pytest.raises(ValueError):
        p.snapshot_frame(payload + b"trailing", BINDING)
