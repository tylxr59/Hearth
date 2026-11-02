import pytest

from backend.device_settings import SETTINGS, validate
from backend.native_controls import NativeControls
from backend.validation import Invalid
from tests.conftest import SERIAL
from tests.test_native_controls import baseline, sub


@pytest.fixture
def settings(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"device.{SERIAL}",
                    "value": {
                        "learning_mode": False,
                        "preconditioning_enabled": False,
                        "temperature_scale": "F",
                        "lower_safety_temp": 4.5,
                        "upper_safety_temp": 35,
                        "heat_pump_aux_threshold": 0,
                        "heatpump_ready": False,
                    },
                }
            ]
        },
    )
    return n


def enqueue(n, values, confirmed=False):
    return n.enqueue(
        SERIAL,
        {
            "operation": "device_settings",
            "value": {"settings": values, "confirm_equipment_changes": confirmed},
        },
    )


def test_learning_and_preconditioning_deliver_and_confirm_only_fresh_values(settings):
    n = settings
    enqueue(n, {"learning_mode": True, "preconditioning_enabled": True})
    assert n.reported[SERIAL]["device"]["values"]["learning_mode"] is False
    frame = n.updates(SERIAL, sub(n))
    values = next(
        row["value"] for row in frame["objects"] if row["object_key"].startswith("device.")
    )
    assert values == {"learning_mode": True, "preconditioning_enabled": True}
    n.note_stream_write(SERIAL, frame)
    n.apply(SERIAL, {"objects": [{"object_key": f"device.{SERIAL}", "value": values}]})
    assert n.command_status(SERIAL)["settings:learning_mode,preconditioning_enabled"] == "confirmed"


@pytest.mark.parametrize(
    "values",
    [
        {"unknown": True},
        {"learning_mode": "true"},
        {"temperature_scale": "K"},
        {"target_humidity": 101},
        {"postal_code": "bad\nvalue"},
    ],
)
def test_invalid_settings_never_queue(settings, values):
    with pytest.raises(Invalid):
        enqueue(settings, values, True)
    assert not settings.intents.get(SERIAL)


def test_safety_settings_require_confirmation_and_preserve_order(settings):
    with pytest.raises(Invalid):
        enqueue(settings, {"lower_safety_temp": 5})
    with pytest.raises(Invalid):
        enqueue(settings, {"lower_safety_temp": 35, "upper_safety_temp": 24}, True)
    enqueue(settings, {"lower_safety_temp": 5}, True)


def test_missing_capability_and_baseline_refuse(settings):
    with pytest.raises(Invalid):
        enqueue(settings, {"heat_pump_aux_threshold": 2}, True)
    with pytest.raises(Invalid):
        enqueue(settings, {"filter_reminder_enabled": True})


def test_cached_setting_cannot_authorize_write(settings, rig):
    saved = settings.snapshot_reported()
    rig[0].states.clear()
    rig[0].seen.clear()
    n = NativeControls(rig[0], clock=lambda: 1000)
    n.restore_reported(saved)
    baseline(n)
    with pytest.raises(Invalid):
        enqueue(n, {"learning_mode": True})


def test_sensitive_pin_is_not_in_reported_cache(settings):
    settings.apply(
        SERIAL,
        {
            "objects": [
                {"object_key": f"device.{SERIAL}", "value": {"temp_lock_pin_hash": "a" * 64}}
            ]
        },
    )
    assert (
        "temp_lock_pin_hash"
        not in settings.snapshot_reported()["devices"][SERIAL]["records"]["device"]["values"]
    )


@pytest.mark.parametrize("name,spec", SETTINGS.items())
def test_catalog_values_have_bounded_type_validation(name, spec):
    value = (
        True
        if spec.kind == "boolean"
        else spec.low
        if spec.kind == "number"
        else spec.options[0]
        if spec.kind == "select"
        else "US"
        if name == "country_code"
        else "a" * 64
        if spec.sensitive
        else "example"
    )
    assert validate(name, value) == value
    with pytest.raises(Invalid):
        validate(name, None)


def test_disjoint_setting_controls_do_not_drop_each_other(settings):
    enqueue(settings, {"learning_mode": True})
    enqueue(settings, {"preconditioning_enabled": True})
    response = settings.updates(SERIAL, sub(settings))
    values = next(
        row["value"] for row in response["objects"] if row["object_key"].startswith("device.")
    )
    assert values == {"learning_mode": True, "preconditioning_enabled": True}
    assert len(settings.intents[SERIAL]) == 2


def test_reported_diagnostics_keep_zero_and_do_not_enter_command_state(settings):
    values = {
        "battery_level": 3.8,
        "rssi": 60,
        "outside_temperature": 0,
        "filter_runtime_sec": 86400,
        "filter_replacement_needed": False,
        "sunlight_correction_active": True,
        "time_to_target": 2000000000,
    }
    settings.apply(SERIAL, {"objects": [{"object_key": f"device.{SERIAL}", "value": values}]})
    saved = settings.snapshot_reported()["devices"][SERIAL]["records"]["device"]["values"]
    assert all(saved[k] == v for k, v in values.items())
    assert not settings.intents.get(SERIAL)


def test_invalid_diagnostics_refuse_codec():
    from backend.device_reports import validate

    for name, value in (
        ("battery_level", 100),
        ("rssi", float("inf")),
        ("filter_replacement_needed", "yes"),
    ):
        with pytest.raises(Invalid):
            validate(name, value)
