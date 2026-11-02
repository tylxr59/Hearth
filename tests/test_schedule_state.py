import copy
import json

import pytest

from backend import reported_store, schedule_state
from backend.native_controls import NativeControls
from backend.validation import Invalid
from tests.conftest import SERIAL
from tests.test_native_controls import baseline, sub
from tests.test_native_features import week


@pytest.fixture
def scheduled(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    n.apply(SERIAL, {"objects": [{"object_key": f"schedule.{SERIAL}", "value": week()}]})
    return n


def queue(n):
    changed = week()
    changed["days"]["0"] = []
    version = n.schedules.view(SERIAL)["revision"]
    n.enqueue(
        SERIAL,
        {"operation": "schedule", "value": changed, "expected_revision": version},
        schedule_backed_up=True,
    )
    return changed


def frame(n):
    return n.updates(SERIAL, sub(n))


def acknowledge(n, response):
    return n.apply(
        SERIAL,
        {
            "objects": [
                {k: v for k, v in row.items() if k != "value"} for row in response["objects"]
            ]
        },
        subscription=True,
    )


def test_pending_week_and_revision_are_paired_without_fabricating_native_report(scheduled):
    n = scheduled
    original = n.schedules.view(SERIAL)
    queue(n)
    current = n.schedules.view(SERIAL)
    assert current["revision"] == original["revision"] + 1 and current["source"] == "pending"
    assert current["schedule"]["days"]["0"] == {}
    assert n.reported[SERIAL]["schedule"]["values"]["days"]["0"]
    assert n.schedules.snapshot()["devices"][SERIAL]["source"] == "device"
    with pytest.raises(Invalid):
        n.advanced_plan(
            SERIAL,
            {"operation": "schedule", "value": week(), "expected_revision": current["revision"]},
            True,
        )


def test_only_post_write_matching_subscription_acknowledges_and_stops_resend(scheduled):
    n = scheduled
    queue(n)
    response = frame(n)
    acknowledge(n, response)
    assert n.schedules.view(SERIAL)["source"] == "pending"
    n.note_stream_write(SERIAL, response)
    stale = copy.deepcopy(response)
    stale["objects"][0]["object_timestamp"] -= 1
    acknowledge(n, stale)
    assert n.schedules.view(SERIAL)["source"] == "pending"
    acknowledge(n, response)
    current = n.schedules.view(SERIAL)
    assert current["source"] == "acknowledged" and current["schedule"]["days"]["0"] == {}
    assert n.command_status(SERIAL)["schedule"] == "acknowledged"
    assert frame(n) == {"objects": []}
    assert not n.intents[SERIAL]
    assert (
        n.control_view(SERIAL)["delivery_receipts"]["schedule"]["matching_reported_field_count"]
        == 0
    )
    assert len(n.schedules.snapshot()["devices"]) == 1
    n.advanced_plan(
        SERIAL,
        {"operation": "schedule", "value": week(), "expected_revision": current["revision"]},
        True,
    )


def test_invalid_packet_cannot_partially_acknowledge(scheduled):
    n = scheduled
    queue(n)
    response = frame(n)
    n.note_stream_write(SERIAL, response)
    metadata = {k: v for k, v in response["objects"][0].items() if k != "value"}
    with pytest.raises(Invalid):
        n.apply(
            SERIAL,
            {
                "objects": [
                    metadata,
                    {"object_key": f"device.{SERIAL}", "value": {"current_temperature": None}},
                ]
            },
            subscription=True,
        )
    assert n.schedules.view(SERIAL)["source"] == "pending"
    assert n.schedules.snapshot()["devices"][SERIAL]["source"] == "device"


def test_expired_write_is_unconfirmed_and_not_replayed_or_persisted(scheduled, rig):
    n = scheduled
    queue(n)
    response = frame(n)
    n.note_stream_write(SERIAL, response)
    rig[3][0] += 31
    acknowledge(n, response)
    assert n.command_status(SERIAL)["schedule"] == "expired"
    assert n.schedules.view(SERIAL)["source"] == "unconfirmed"
    assert n.schedules.snapshot()["devices"][SERIAL]["source"] == "device"
    assert frame(n) == {"objects": []}


def test_native_complete_week_wins_over_assignment(scheduled):
    n = scheduled
    queue(n)
    response = frame(n)
    n.note_stream_write(SERIAL, response)
    acknowledge(n, response)
    actual = week()
    actual["days"]["1"] = []
    n.apply(
        SERIAL,
        {"objects": [{"object_key": f"schedule.{SERIAL}", "op": "OVERWRITE", "value": actual}]},
    )
    current = n.schedules.view(SERIAL)
    assert current["source"] == "device" and current["schedule"]["days"]["1"] == {}
    assert n.schedules.snapshot()["devices"][SERIAL]["source"] == "device"
    assert n.command_status(SERIAL)["schedule"] == "acknowledged"


def test_partial_native_delta_cannot_merge_an_old_week_over_new_assignment(scheduled):
    n = scheduled
    queue(n)
    response = frame(n)
    n.note_stream_write(SERIAL, response)
    acknowledge(n, response)
    n.apply(
        SERIAL, {"objects": [{"object_key": f"schedule.{SERIAL}", "value": {"name": "Changed"}}]}
    )
    with pytest.raises(Invalid):
        n.schedules.view(SERIAL)
    assert n.command_status(SERIAL)["schedule"] == "acknowledged"


def test_pending_replacement_does_not_erase_last_acknowledged_configuration(scheduled):
    n = scheduled
    queue(n)
    response = frame(n)
    n.note_stream_write(SERIAL, response)
    acknowledge(n, response)
    committed = n.schedules.snapshot()
    n.enqueue(
        SERIAL,
        {
            "operation": "schedule",
            "value": week(),
            "expected_revision": n.schedules.view(SERIAL)["revision"],
        },
        schedule_backed_up=True,
    )
    assert n.schedules.snapshot() == committed
    assert n.schedules.view(SERIAL)["source"] == "pending"


def test_restore_is_cache_only_until_fresh_matching_metadata_and_never_replays(scheduled, rig):
    n = scheduled
    reported = n.snapshot_reported()
    queue(n)
    response = frame(n)
    n.note_stream_write(SERIAL, response)
    acknowledge(n, response)
    saved = n.schedules.snapshot()
    rig[0].states.clear()
    rig[0].seen.clear()
    restored = NativeControls(rig[0], clock=lambda: 1000)
    restored.restore_reported(reported)
    restored.schedules.restore(saved)
    assert restored.schedules.view(SERIAL)["source"] == "cache"
    assert restored.schedules.view(SERIAL)["schedule"]["days"]["0"] == {}
    assert not restored.intents and frame(restored) == {"objects": []}
    acknowledge(restored, response)
    assert restored.schedules.view(SERIAL)["source"] == "acknowledged"
    assert not restored.intents and frame(restored) == {"objects": []}


def test_newer_native_snapshot_wins_over_older_acknowledged_file(scheduled, rig):
    n = scheduled
    queue(n)
    response = frame(n)
    n.note_stream_write(SERIAL, response)
    acknowledge(n, response)
    saved = n.schedules.snapshot()
    n.apply(SERIAL, {"objects": [{"object_key": f"schedule.{SERIAL}", "value": week()}]})
    reported = n.snapshot_reported()
    rig[0].states.clear()
    rig[0].seen.clear()
    restored = NativeControls(rig[0], clock=lambda: 1000)
    restored.restore_reported(reported)
    restored.schedules.restore(saved)
    assert restored.schedules.view(SERIAL)["schedule"]["days"]["0"]
    assert not restored.schedules.committed


def test_reenrollment_drops_known_schedule_assignment(scheduled):
    n = scheduled
    queue(n)
    response = frame(n)
    n.note_stream_write(SERIAL, response)
    acknowledge(n, response)
    n.core.registry.data["devices"][SERIAL]["hash"] = "c" * 64
    with pytest.raises(Invalid):
        n.schedules.view(SERIAL)
    assert not n.schedules.snapshot()["devices"]


def test_schedule_configuration_private_store_and_strict_codec(scheduled, tmp_path):
    n = scheduled
    queue(n)
    response = frame(n)
    n.note_stream_write(SERIAL, response)
    acknowledge(n, response)
    saved = n.schedules.snapshot()
    tmp_path.chmod(0o700)
    reported_store.save(
        tmp_path, saved, schedule_state.NAME, schedule_state.encode, schedule_state.decode
    )
    assert reported_store.load(tmp_path, schedule_state.NAME, schedule_state.decode) == saved
    path = tmp_path / schedule_state.NAME
    assert path.stat().st_mode & 0o777 == 0o600
    bad = copy.deepcopy(saved)
    bad["devices"][SERIAL]["pending"] = True
    with pytest.raises(Invalid):
        schedule_state.encode(bad)
    bad = copy.deepcopy(saved)
    bad["devices"][SERIAL]["revision"] = True
    with pytest.raises(Invalid):
        schedule_state.encode(bad)
    with pytest.raises(Invalid):
        schedule_state.decode(json.dumps(saved).encode() + b"{}")
    path.chmod(0o644)
    with pytest.raises(Invalid):
        reported_store.load(tmp_path, schedule_state.NAME, schedule_state.decode)


def test_complete_native_week_proof_survives_restart_without_replaying(scheduled, rig):
    n = scheduled
    saved = n.schedules.snapshot()
    assert saved["devices"][SERIAL]["source"] == "device"
    reported = n.snapshot_reported()
    response = {
        "objects": [n._records_for(SERIAL)[f"schedule.{SERIAL}"].metadata(f"schedule.{SERIAL}")]
    }
    rig[0].states.clear()
    rig[0].seen.clear()
    restored = NativeControls(rig[0], clock=lambda: 1000)
    restored.restore_reported(reported)
    restored.schedules.restore(saved)
    assert restored.schedules.view(SERIAL)["source"] == "cache"
    acknowledge(restored, response)
    assert restored.schedules.view(SERIAL)["source"] == "acknowledged"
    assert not restored.intents and frame(restored) == {"objects": []}


def test_unproven_reported_cache_cannot_be_promoted_by_metadata(scheduled, rig):
    n = scheduled
    reported = n.snapshot_reported()
    response = {
        "objects": [n._records_for(SERIAL)[f"schedule.{SERIAL}"].metadata(f"schedule.{SERIAL}")]
    }
    rig[0].states.clear()
    rig[0].seen.clear()
    restored = NativeControls(rig[0], clock=lambda: 1000)
    restored.restore_reported(reported)
    acknowledge(restored, response)
    assert restored.schedules.view(SERIAL)["source"] == "cache"
    assert not restored.schedules.committed


def test_same_metadata_different_week_does_not_restore_known_proof(scheduled, rig):
    n = scheduled
    saved = n.schedules.snapshot()
    saved["devices"][SERIAL]["value"]["days"]["0"] = {}
    reported = n.snapshot_reported()
    rig[0].states.clear()
    rig[0].seen.clear()
    restored = NativeControls(rig[0], clock=lambda: 1000)
    restored.restore_reported(reported)
    restored.schedules.restore(saved)
    assert not restored.schedules.committed
    assert restored.schedules.view(SERIAL)["source"] == "cache"


def test_known_schedule_rejects_unconfirmed_source(scheduled):
    saved = scheduled.schedules.snapshot()
    saved["devices"][SERIAL]["source"] = "pending"
    with pytest.raises(Invalid):
        schedule_state.encode(saved)
