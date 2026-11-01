import pytest

from backend import reported_cache as cache
from backend.validation import Invalid
from tests.conftest import SERIAL


def fixture():
    return {
        "format": cache.FORMAT,
        "saved_at": 1000,
        "devices": {
            SERIAL: {
                "generation": "a" * 64,
                "records": {
                    "shared": {
                        "revision": 3,
                        "timestamp": 1000,
                        "values": {
                            "target_temperature": 22,
                            "target_temperature_type": "heat",
                            "can_heat": True,
                        },
                    },
                    "device": {
                        "revision": 2,
                        "timestamp": 999,
                        "values": {
                            "current_humidity": 42,
                            "current_temperature": 20,
                            "software_version": "5.9.4-5",
                            "fan_timer_timeout": 0,
                        },
                    },
                },
            }
        },
    }


def test_reported_cache_deterministic_and_copies_input():
    data = fixture()
    raw = cache.encode(data)
    assert cache.decode(raw) == data and cache.encode(cache.decode(raw)) == raw
    result = cache.validate(data)
    result["devices"][SERIAL]["records"]["shared"]["values"]["target_temperature"] = 23
    assert data["devices"][SERIAL]["records"]["shared"]["values"]["target_temperature"] == 22


@pytest.mark.parametrize(
    "field",
    [
        "assigned_cred_secret",
        "wifi_password",
        "platform_key",
        "unknown_value",
        "operation",
        "desired_target",
        "pending",
    ],
)
def test_reported_cache_never_accepts_credentials_unknown_values_or_intent_fields(field):
    data = fixture()
    data["devices"][SERIAL]["records"]["shared"]["values"][field] = "must-not-persist"
    with pytest.raises(Invalid):
        cache.encode(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_temperature", True),
        ("target_temperature", float("nan")),
        ("target_temperature", float("inf")),
        ("target_temperature", 36),
        ("target_temperature_type", "script"),
        ("can_heat", 1),
    ],
)
def test_reported_cache_scalars_are_typed_and_bounded(field, value):
    data = fixture()
    data["devices"][SERIAL]["records"]["shared"]["values"][field] = value
    with pytest.raises(Invalid):
        cache.encode(data)


def test_cache_rejects_unknown_envelope_bucket_metadata_and_oversize():
    for mutate in (
        lambda d: d.update(pending={}),
        lambda d: d["devices"][SERIAL]["records"].update(schedule={}),
        lambda d: d["devices"][SERIAL]["records"]["shared"].update(fingerprints={}),
        lambda d: d["devices"][SERIAL].update(generation="not-a-hash"),
    ):
        data = fixture()
        mutate(data)
        with pytest.raises(Invalid):
            cache.encode(data)
    with pytest.raises(Invalid):
        cache.decode(b" " * (cache.LIMIT + 1))
    with pytest.raises(Invalid):
        cache.decode(b'{"format":1,"format":2}')


def test_pending_desired_values_are_not_saved_and_restore_is_not_fresh(rig):
    from backend.core import Core
    from backend.native_controls import NativeControls
    from tests.test_native_controls import baseline

    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    n.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    saved = n.snapshot_reported()
    shared = saved["devices"][SERIAL]["records"]["shared"]["values"]
    assert shared["target_temperature"] == 22 and "pending" not in saved
    fresh = NativeControls(Core(rig[0].registry), clock=lambda: 1000)
    assert fresh.restore_reported(saved) == 1
    assert fresh.core.states[SERIAL]["target_temperature"] == 22
    assert fresh.core.available(SERIAL) is False and fresh.intents == {}
    assert fresh.capabilities(SERIAL) == {"modes": ["off", "heat", "cool"], "fan": True}
    assert all("value" not in r for r in fresh.listing(SERIAL)["objects"])


def test_reported_restore_drops_unknown_fields_and_old_credential_generation(rig):
    from backend.core import Core
    from backend.native_controls import NativeControls
    from tests.test_native_controls import baseline

    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    n.apply(
        SERIAL,
        {
            "objects": [
                {"object_key": f"device.{SERIAL}", "value": {"private_field": "do-not-save"}}
            ]
        },
    )
    raw = cache.encode(n.snapshot_reported())
    assert b"private_field" not in raw and b"do-not-save" not in raw and b"fingerprints" not in raw
    rig[0].registry.register(SERIAL, "e" * 64, rig[0].caps(SERIAL), rotate=True)
    fresh = NativeControls(Core(rig[0].registry))
    assert fresh.restore_reported(cache.decode(raw)) == 0
    assert fresh.core.states == {} and fresh.intents == {}


def test_reported_cache_does_not_replace_a_live_process_and_is_detached(rig):
    from backend.native_controls import NativeControls
    from tests.test_native_controls import baseline

    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    saved = n.snapshot_reported()
    saved["devices"][SERIAL]["records"]["shared"]["values"]["target_temperature"] = 30
    assert n.reported[SERIAL]["shared"]["values"]["target_temperature"] == 22
    with pytest.raises(Invalid):
        n.restore_reported(saved)


def test_restored_sources_clear_per_reported_field_without_fake_freshness(rig):
    from backend.core import Core
    from backend.native_controls import NativeControls
    from tests.test_native_controls import baseline

    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    fresh = NativeControls(Core(rig[0].registry), clock=lambda: 1000)
    fresh.restore_reported(n.snapshot_reported())
    assert fresh.state_source(SERIAL, "target_temperature") == "cache"
    assert fresh.state_source(SERIAL, "humidity") == "cache"
    assert not fresh.core.available(SERIAL)
    fresh.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"target_temperature": 22}}]},
    )
    assert fresh.state_source(SERIAL, "target_temperature") == "device"
    assert fresh.state_source(SERIAL, "humidity") == "cache"
    assert fresh.core.available(SERIAL)


def test_invalid_observed_capability_cannot_restore_old_positive_permission(rig):
    from backend.core import Core
    from backend.native_controls import NativeControls
    from tests.test_native_controls import baseline

    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    n.apply(SERIAL, {"objects": [{"object_key": f"device.{SERIAL}", "value": {"can_heat": 1}}]})
    fresh = NativeControls(Core(rig[0].registry))
    fresh.restore_reported(n.snapshot_reported())
    assert "heat" not in fresh.capabilities(SERIAL)["modes"]
