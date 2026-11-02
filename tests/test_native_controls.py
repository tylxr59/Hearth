import copy
import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from backend.api import create_app
from backend.native_controls import NativeControls
from backend.validation import Invalid
from tests.conftest import SERIAL
from tests.test_native_telemetry import batch
from tests.test_security import auth


def baseline(native):
    data = batch()
    data["objects"][0]["value"].update(
        can_heat=True, can_cool=True, has_fan=True, fan_timer_timeout=0
    )
    native.apply(SERIAL, data)


def sub(native):
    return {"objects": [{**r} for r in native.listing(SERIAL)["objects"]], "chunked": True}


@pytest.fixture
def native(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    return n


def test_delivery_does_not_optimistically_update_state_and_only_put_confirms(native, rig):
    request = sub(native)
    before = copy.deepcopy(rig[0].states[SERIAL])
    item = native.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    assert item["status"] == "pending" and rig[0].states[SERIAL] == before
    reply = native.updates(SERIAL, request)
    shared = next(r for r in reply["objects"] if r["object_key"].startswith("shared."))
    assert list(shared) == ["object_revision", "object_timestamp", "object_key", "value"]
    assert shared["value"] == {"target_temperature": 23}
    assert rig[0].states[SERIAL] == before
    ack = {
        "objects": [
            {
                "object_key": shared["object_key"],
                "if_object_revision": shared["object_revision"],
                "value": {"target_temperature": 23},
            }
        ]
    }
    native.apply(SERIAL, ack)
    assert rig[0].states[SERIAL]["target_temperature"] == 23
    assert native.command_status(SERIAL)["temperature"] == "confirmed"
    assert not native.intents[SERIAL]


@pytest.mark.parametrize(
    "operation,value",
    [
        ("temperature", True),
        ("temperature", float("nan")),
        ("temperature", 31),
        ("mode", "range"),
        ("fan", "forever"),
        ("shell", "reboot"),
    ],
)
def test_only_bounded_allowlisted_controls(native, operation, value):
    before = copy.deepcopy(native._records)
    with pytest.raises(Invalid):
        native.enqueue(SERIAL, {"operation": operation, "value": value})
    assert native._records == before and not native.intents


def test_missing_capabilities_do_not_default_to_heat_or_cool(rig):
    n = NativeControls(rig[0])
    n.apply(SERIAL, batch())
    assert n.capabilities(SERIAL) == {"modes": ["off"], "fan": False}
    with pytest.raises(Invalid):
        n.enqueue(SERIAL, {"operation": "mode", "value": "heat"})
    with pytest.raises(Invalid):
        n.enqueue(SERIAL, {"operation": "fan", "value": "on"})


def test_expiry_and_backend_restart_do_not_replay(native, rig):
    request = sub(native)
    native.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    rig[3][0] += 31
    assert all("value" not in r for r in native.updates(SERIAL, request)["objects"])
    assert native.command_status(SERIAL)["temperature"] == "expired"
    assert not NativeControls(rig[0]).intents


def test_local_changed_value_wins_over_queued_intent(native, rig):
    native.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    native.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"target_temperature": 20}}]},
    )
    assert rig[0].states[SERIAL]["target_temperature"] == 20
    assert native.command_status(SERIAL)["temperature"] == "superseded_by_device"
    assert not native.intents[SERIAL]


def test_unrelated_telemetry_rebases_without_extending_deadline(native, rig):
    request = sub(native)
    native.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    original = native.intents[SERIAL]["temperature"].expires
    native.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"current_temperature": 21}}]},
    )
    values = [r.get("value") for r in native.updates(SERIAL, request)["objects"]]
    assert {"target_temperature": 23} in values
    assert native.intents[SERIAL]["temperature"].expires == original


def test_disjoint_commands_share_revision_and_supersession_is_bounded(native):
    request = sub(native)
    native.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    native.enqueue(SERIAL, {"operation": "mode", "value": "cool"})
    native.enqueue(SERIAL, {"operation": "temperature", "value": 24})
    assert len(native.intents[SERIAL]) == 2
    rows = native.updates(SERIAL, request)["objects"]
    assert rows[0]["value"] == {"target_temperature": 24, "target_temperature_type": "cool"}


def test_stale_conditional_put_does_not_confirm(native):
    revision = native._records_for(SERIAL)[f"shared.{SERIAL}"].revision
    native.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    native.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"shared.{SERIAL}",
                    "if_object_revision": revision,
                    "value": {"target_temperature": 23},
                }
            ]
        },
    )
    assert native.command_status(SERIAL)["temperature"] == "pending"


def test_rotation_clears_intents_and_capabilities(native, rig):
    native.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    rig[0].registry.register(SERIAL, "c" * 64, rig[0].caps(SERIAL), rotate=True)
    assert native.command_status(SERIAL) == {}
    assert native.capabilities(SERIAL) == {"modes": ["off"], "fan": False}


def test_fan_on_is_bounded_native_timer(native):
    request = sub(native)
    native.enqueue(SERIAL, {"operation": "fan", "value": "on"})
    row = next(
        r
        for r in native.updates(SERIAL, request)["objects"]
        if r["object_key"].startswith("device.")
    )
    assert row["value"] == {"fan_timer_timeout": 1600}


async def test_http_manager_command_and_native_subscription_delivery(rig):
    core, token, admin, _ = rig
    app = create_app(core, native_telemetry=True, native_controls=True, native_hold_seconds=1)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/nest/transport/put", headers=auth(token), json=batch())
        assert response.status == 200
        rows = (await response.json())["objects"]
        # Start the real chunked subscription before enqueueing the command.
        response = await client.post(
            "/nest/transport/v7/subscribe",
            headers=auth(token),
            json={"objects": rows, "chunked": True},
        )
        command_response = await client.post(
            f"/v1/manage/devices/{SERIAL}/commands",
            headers={"Authorization": "Bearer " + admin},
            json={"operation": "temperature", "value": 23},
        )
        assert command_response.status == 202
        data = json.loads(await response.read())
        assert data["objects"][0]["value"] == {"target_temperature": 23}
        assert core.states[SERIAL]["target_temperature"] == 22
        assert (await client.get("/v1/device/commands", headers=auth(token))).status == 409


def test_unknown_manager_target_is_refused_without_keyerror(native):
    with pytest.raises(Invalid):
        native.enqueue("HEARTHLABUNKNOWN", {"operation": "temperature", "value": 20})


def test_unknown_values_remain_fingerprints_and_never_enter_control_responses(native):
    marker = "do-not-reflect-fixture"
    native.apply(
        SERIAL,
        {"objects": [{"object_key": f"shared.{SERIAL}", "value": {"private_unknown": marker}}]},
    )
    request = sub(native)
    native.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    assert marker not in repr(native.__dict__)
    assert marker not in json.dumps(native.updates(SERIAL, request))


@pytest.mark.parametrize(
    "flags,expected",
    [
        ({"hvac_heater_state": True}, "heating"),
        ({"hvac_ac_state": True}, "cooling"),
        ({"hvac_heater_state": True, "hvac_ac_state": True}, None),
        ({"hvac_fan_state": True}, "fan"),
        ({"hvac_heater_state": "true"}, None),
    ],
)
def test_action_uses_reported_booleans_not_target_temperature(native, flags, expected):
    native.apply(SERIAL, {"objects": [{"object_key": f"shared.{SERIAL}", "value": flags}]})
    assert native.action(SERIAL) == expected


async def test_auth_rotation_mid_subscription_stops_control_delivery(rig):
    core, token, _admin, _ = rig
    app = create_app(core, native_telemetry=True, native_controls=True, native_hold_seconds=1)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/nest/transport/put", headers=auth(token), json=batch())
        rows = (await response.json())["objects"]
        response = await client.post(
            "/nest/transport/v7/subscribe",
            headers=auth(token),
            json={"objects": rows, "chunked": True},
        )
        core.registry.register(SERIAL, "d" * 64, core.caps(SERIAL), rotate=True)
        assert await response.read() == b""


def test_put_ack_never_piggybacks_pending_controls_even_on_cas_conflict(native):
    request = sub(native)
    revision = native._records_for(SERIAL)[f"shared.{SERIAL}"].revision
    native.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    for conditional in (revision, None):
        obj = {"object_key": f"shared.{SERIAL}", "value": {"current_temperature": 19}}
        if conditional is not None:
            obj["if_object_revision"] = conditional
        response = native.apply(SERIAL, {"objects": [obj]})
        assert all("value" not in r for r in response["objects"])
    assert any(
        r.get("value") == {"target_temperature": 23}
        for r in native.updates(SERIAL, request)["objects"]
    )


def test_manager_control_diagnostics_are_bounded_and_value_free(native):
    native.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    row = native.control_view(SERIAL)
    assert row["command_status"] == {"temperature": "pending"}
    assert row["pending"]["temperature"] == {"offered": False, "seconds_remaining": 30}
    assert row["baseline_fields"] == {"temperature": True, "mode": True, "fan": True}
    assert row["requests"] == {"put": 1}
    assert set(row) == {
        "capabilities",
        "command_status",
        "pending",
        "requests",
        "last_request_age",
        "baseline_fields",
        "feature_baselines",
        "local_pairing",
    }
    assert row["feature_baselines"]["observed_bucket_kinds"] == ["device", "shared"]
    assert row["feature_baselines"]["home_reference_observed"] is False
    assert row["feature_baselines"]["schedule_schema_validated"] is False
    assert SERIAL not in json.dumps(row)


async def test_native_subscription_renews_availability_without_faking_a_reading(rig):
    core, token, _admin, now = rig
    app = create_app(core, native_telemetry=True, native_controls=True, native_hold_seconds=0.02)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/nest/transport/put", headers=auth(token), json=batch())
        objects = (await response.json())["objects"]
        before = copy.deepcopy(core.states[SERIAL])
        now[0] += 91
        assert not core.available(SERIAL)
        response = await client.post(
            "/nest/transport/v7/subscribe",
            headers=auth(token),
            json={"objects": objects, "chunked": True},
        )
        assert response.status == 200
        await response.read()
        assert core.available(SERIAL) and core.states[SERIAL] == before
        assert response.headers["X-nl-defer-device-window"] == "15"
        assert int(response.headers["X-nl-suspend-time-max"]) > 0.02
        now[0] += 91
        response = await client.post(
            "/nest/transport/v7/subscribe",
            headers=auth(token),
            json={"objects": "invalid", "chunked": True},
        )
        assert response.status == 400 and not core.available(SERIAL)


async def test_subscription_push_sets_native_confirmation_timing_headers(rig):
    core, token, admin, _ = rig
    app = create_app(core, native_telemetry=True, native_controls=True, native_hold_seconds=290)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/nest/transport/put", headers=auth(token), json=batch())
        objects = (await response.json())["objects"]
        response = await client.post(
            f"/v1/manage/devices/{SERIAL}/commands",
            headers={"Authorization": "Bearer " + admin},
            json={"operation": "temperature", "value": 23},
        )
        assert response.status == 202
        response = await client.post(
            "/nest/transport/v7/subscribe",
            headers=auth(token),
            json={"objects": objects, "chunked": True},
        )
        assert response.headers["X-nl-suspend-time-max"] == "300"
        assert response.headers["X-nl-disable-defer-window"] == "60"
        assert (await response.json(content_type=None))["objects"][0]["value"] == {
            "target_temperature": 23
        }
        response = await client.get(
            "/v1/manage/devices", headers={"Authorization": "Bearer " + admin}
        )
        diagnostics = (await response.json())["devices"][0]["native_controls"]
        assert diagnostics["pending"]["temperature"]["offered"] is True


def test_emergency_mode_requires_explicit_permission_and_positive_device_capability(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    with pytest.raises(Invalid):
        n.enqueue(SERIAL, {"operation": "mode", "value": "emergency"})
    rig[0].registry.data["devices"][SERIAL]["capabilities"]["modes"].append("emergency")
    with pytest.raises(Invalid):
        n.enqueue(SERIAL, {"operation": "mode", "value": "emergency"})
    n.apply(
        SERIAL, {"objects": [{"object_key": f"device.{SERIAL}", "value": {"has_emer_heat": True}}]}
    )
    request = sub(n)
    n.enqueue(SERIAL, {"operation": "mode", "value": "emergency"})
    assert n.updates(SERIAL, request)["objects"][0]["value"] == {
        "target_temperature_type": "emergency"
    }
    n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"shared.{SERIAL}",
                    "value": {"target_temperature_type": "emergency"},
                }
            ]
        },
    )
    assert rig[0].states[SERIAL]["mode"] == "heat"
    assert n.command_status(SERIAL)["mode"] == "confirmed"
