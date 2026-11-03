"""Whole-install capacity refuses uncertainty before either persistent phase."""

import json

import pytest

from installer import capacity
from tests.test_network_writer_session import refused_resource_result


def successful_capacity():
    return json.loads(
        refused_resource_result(
            initial_error=0,
            diagnostic=0,
            space_available=24 * 1048576,
            snapshot_target=-1,
            settings_state=5,
        )
    )


def test_successful_no_write_capacity_does_not_claim_an_install():
    from firmware.network_writer.session import result

    row = successful_capacity()
    assert capacity.passed(result(json.dumps(row).encode(), 1, target_count=3, preflight_only=True))
    assert row["complete"] == row["commit_received"] == 0


@pytest.mark.parametrize(
    "field,value",
    (
        ("initial_error", 2),
        ("diagnostic", 42),
        ("safe_to_restart", 0),
        ("program", 1),
        ("erase", 1),
        ("marker", 1),
        ("rw_attempted", 1),
        ("transaction_called", 1),
        ("phase", 0),
        ("protected", 0),
        ("preflight_only", 0),
        ("space_available", 1),
        ("memory_free", 1),
        ("space_required", 0),
        ("release_error", 1),
        ("seal_error", 1),
        ("commit_received", 1),
        ("complete", 1),
        ("error", 0),
        ("program", False),
        ("safe_to_restart", True),
    ),
)
def test_capacity_never_credits_refused_unsealed_or_mutating_results(field, value):
    assert not capacity.passed(successful_capacity() | {field: value})


@pytest.mark.parametrize("reserve", (-1, True, 8 * 1048576 + 1, "100", None))
def test_reservation_must_be_bounded_integer(reserve):
    with pytest.raises(ValueError):
        capacity.checked_reserve(reserve, True)


def test_reservation_cannot_sneak_into_a_commit_capable_image():
    with pytest.raises(ValueError, match="no-commit"):
        capacity.checked_reserve(1, False)
    assert capacity.checked_reserve(4096, True) == 4096


def test_commissioning_reserve_counts_all_new_root_data_without_reclaim_credit(
    monkeypatch, tmp_path
):
    from firmware.file_writer import prepare
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    monkeypatch.setattr(capacity.file_capsule, "check", lambda *a, **kw: None)
    monkeypatch.setattr(prepare, "pin_read", lambda _: b"p" * 32)
    rows = [{"target": i, "original_bytes": 100, "replacement_bytes": 200} for i in range(9)]
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"files": rows}))
    path.chmod(0o600)
    assert capacity.root_reserve(tmp_path, tmp_path / "pin") == 8 * 200 + 128 * 1024
