"""Native notification acknowledgements remain distinct from value reports."""

import pytest

from backend.native_controls import NativeControls
from tests.conftest import SERIAL
from tests.test_native_controls import baseline, sub


@pytest.fixture
def target(rig):
    native = NativeControls(rig[0], clock=lambda: 1000)
    baseline(native)
    native.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    return native


def clear(native, **metadata):
    return native.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"shared.{SERIAL}",
                    "value": {"target_change_pending": False},
                    **metadata,
                }
            ]
        },
    )


def written(native):
    frame = native.updates(SERIAL, sub(native))
    native.note_stream_write(SERIAL, frame)
    return frame


def test_clear_after_write_stops_resend_without_fabricating_report(target, rig):
    written(target)
    clear(target)
    assert target.core.states[SERIAL]["target_temperature"] == 22
    assert target.target_value(SERIAL) == 23
    assert target.state_source(SERIAL, "target_temperature") == "acknowledged"
    assert target.state_source(SERIAL, "temperature") != "acknowledged"
    assert target.intents[SERIAL]["temperature"].observed_fields == set()
    assert target.updates(SERIAL, sub(target)) == {"objects": []}
    rig[3][0] += 31
    assert target.command_status(SERIAL)["temperature"] == "acknowledged"
    receipt = target.control_view(SERIAL)["delivery_receipts"]["temperature"]
    assert receipt["notification_acknowledged"] and receipt["matching_reported_field_count"] == 0
    assert target.target_value(SERIAL) == 23
    assert target.updates(SERIAL, sub(target)) == {"objects": []}


def test_notification_before_actual_write_is_not_acknowledgement(target):
    target.updates(SERIAL, sub(target))
    clear(target)
    assert target.target_value(SERIAL) == 22
    assert not target.intents[SERIAL]["temperature"].notification_acknowledged
    assert target.updates(SERIAL, sub(target))["objects"]


def test_stale_conditional_clear_is_not_acknowledgement(target):
    written(target)
    clear(target, if_object_revision=0)
    assert not target.intents[SERIAL]["temperature"].notification_acknowledged
    assert target.target_value(SERIAL) == 22


def test_expired_notification_cannot_create_assumed_target(target, rig):
    written(target)
    rig[3][0] += 31
    clear(target)
    assert target.command_status(SERIAL)["temperature"] == "expired"
    assert target.target_value(SERIAL) == 22


def test_native_target_report_replaces_assumption_and_confirms(target):
    written(target)
    clear(target)
    target.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"target_temperature": 23}}]},
    )
    assert target.state_source(SERIAL, "target_temperature") == "device"
    assert target.command_status(SERIAL)["temperature"] == "confirmed"


def test_conflicting_native_target_wins_over_assumption(target):
    written(target)
    clear(target)
    target.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"target_temperature": 21}}]},
    )
    assert target.target_value(SERIAL) == 21
    assert target.command_status(SERIAL)["temperature"] == "superseded_by_device"
    assert target.state_source(SERIAL, "target_temperature") == "device"


def test_assumption_is_not_persisted_or_restored(target):
    written(target)
    clear(target)
    snapshot = target.snapshot_reported()
    values = snapshot["devices"][SERIAL]["records"]["shared"]["values"]
    assert values["target_temperature"] == 22
    assert "target_change_pending" not in values
    assert not NativeControls(target.core).acknowledged_targets


def test_reenrollment_drops_assumption(target):
    written(target)
    clear(target)
    target.core.registry.data["devices"][SERIAL]["hash"] = "c" * 64
    assert target.state_source(SERIAL, "target_temperature") != "acknowledged"
    assert SERIAL not in target.acknowledged_targets


def test_range_assumptions_clear_together_when_device_disagrees(rig):
    rig[0].registry.data["devices"][SERIAL]["capabilities"]["modes"].append("heat_cool")
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"shared.{SERIAL}",
                    "value": {
                        "target_temperature_type": "range",
                        "target_temperature_low": 20,
                        "target_temperature_high": 26,
                    },
                }
            ]
        },
    )
    n.enqueue(SERIAL, {"operation": "temperature_range", "value": {"low": 21, "high": 25}})
    written(n)
    clear(n)
    assert n.target_value(SERIAL, "target_temperature_high") == 25
    n.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"target_temperature_low": 19}}]},
    )
    assert not n.acknowledged_targets[SERIAL]
    assert n.target_value(SERIAL, "target_temperature_high") == 26


def test_partial_range_report_keeps_its_device_source_after_notification(rig):
    rig[0].registry.data["devices"][SERIAL]["capabilities"]["modes"].append("heat_cool")
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"shared.{SERIAL}",
                    "value": {
                        "target_temperature_type": "range",
                        "target_temperature_low": 20,
                        "target_temperature_high": 26,
                    },
                }
            ]
        },
    )
    n.enqueue(SERIAL, {"operation": "temperature_range", "value": {"low": 21, "high": 25}})
    written(n)
    n.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"target_temperature_low": 21}}]},
    )
    clear(n)
    assert n.state_source(SERIAL, "target_temperature_low") == "device"
    assert n.state_source(SERIAL, "target_temperature_high") == "acknowledged"


def test_late_value_report_updates_state_without_confirming_expired_intent(target, rig):
    written(target)
    rig[3][0] += 31
    target.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"target_temperature": 23}}]},
    )
    assert target.command_status(SERIAL)["temperature"] == "expired"
    assert target.target_value(SERIAL) == 23
    assert target.state_source(SERIAL, "target_temperature") == "device"
