import copy

import pytest

from backend.native_controls import NativeControls
from backend.validation import Invalid
from tests.conftest import SERIAL
from tests.test_native_controls import baseline, sub


@pytest.fixture
def ranged(rig):
    record = rig[0].registry.data["devices"][SERIAL]
    record["capabilities"]["modes"].append("heat_cool")
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
    return n


def test_range_is_one_intent_and_only_confirmed_when_both_reported(ranged):
    before = sub(ranged)
    ranged.enqueue(SERIAL, {"operation": "temperature_range", "value": {"low": 21, "high": 25}})
    reply = ranged.updates(SERIAL, before)
    assert reply["objects"][0]["value"] == {
        "target_temperature_low": 21,
        "target_temperature_high": 25,
    }
    ranged.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"target_temperature_low": 21}}]},
    )
    assert ranged.command_status(SERIAL)["temperature_range"] == "pending"
    ranged.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"target_temperature_high": 25}}]},
    )
    assert ranged.command_status(SERIAL)["temperature_range"] == "confirmed"


@pytest.mark.parametrize(
    "value",
    [
        {"low": 25, "high": 21},
        {"low": 20, "high": 20},
        {"low": 20},
        {"high": 25},
        {"low": True, "high": 25},
        {"low": 9, "high": 25},
        {"low": 20, "high": 31},
        {"low": 20, "high": 25, "extra": 0},
    ],
)
def test_range_rejection_is_atomic(ranged, value):
    before = copy.deepcopy(ranged._records)
    with pytest.raises(Invalid):
        ranged.enqueue(SERIAL, {"operation": "temperature_range", "value": value})
    assert ranged._records == before and not ranged.intents


def test_range_requires_native_and_configured_capabilities_and_active_mode(ranged, rig):
    ranged.apply(
        SERIAL,
        {
            "objects": [
                {"object_key": f"shared.{SERIAL}", "value": {"target_temperature_type": "heat"}}
            ]
        },
    )
    with pytest.raises(Invalid):
        ranged.enqueue(SERIAL, {"operation": "temperature_range", "value": {"low": 20, "high": 25}})
    ranged.apply(
        SERIAL, {"objects": [{"object_key": f"device.{SERIAL}", "value": {"can_cool": False}}]}
    )
    assert "heat_cool" not in ranged.capabilities(SERIAL)["modes"]
    with pytest.raises(Invalid):
        ranged.enqueue(SERIAL, {"operation": "mode", "value": "heat_cool"})


def test_single_target_disallowed_in_range_and_mode_change_cancels_range(ranged):
    with pytest.raises(Invalid):
        ranged.enqueue(SERIAL, {"operation": "temperature", "value": 22})
    ranged.enqueue(SERIAL, {"operation": "temperature_range", "value": {"low": 21, "high": 25}})
    ranged.enqueue(SERIAL, {"operation": "mode", "value": "off"})
    assert "temperature_range" not in ranged.intents[SERIAL]
    assert ranged.command_status(SERIAL)["temperature_range"] == "superseded"


def test_range_mode_uses_native_enum_without_optimistic_state(ranged, rig):
    ranged.apply(
        SERIAL,
        {
            "objects": [
                {"object_key": f"shared.{SERIAL}", "value": {"target_temperature_type": "heat"}}
            ]
        },
    )
    before = sub(ranged)
    ranged.enqueue(SERIAL, {"operation": "mode", "value": "heat_cool"})
    assert rig[0].states[SERIAL]["mode"] == "heat"
    assert ranged.updates(SERIAL, before)["objects"][0]["value"] == {
        "target_temperature_type": "range"
    }


def test_partial_local_range_change_supersedes_entire_pending_pair(ranged):
    ranged.enqueue(SERIAL, {"operation": "temperature_range", "value": {"low": 21, "high": 25}})
    ranged.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"target_temperature_high": 27}}]},
    )
    assert ranged.command_status(SERIAL)["temperature_range"] == "superseded_by_device"
    assert not ranged.intents[SERIAL]
