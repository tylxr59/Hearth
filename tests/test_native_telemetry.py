import asyncio
import base64
import copy
import json
import secrets

import pytest
from aiohttp.test_utils import TestClient, TestServer

from backend.api import NATIVE, NATIVE_ACTIVE, create_app
from backend.native import NativeTelemetry
from backend.validation import Invalid
from tests.conftest import OTHER, SERIAL
from tests.test_security import auth


def batch():
    # Sanitized source-derived shapes, not a captured thermostat request.
    return {
        "session": "fixture+/=",
        "objects": [
            {
                "object_key": f"device.{SERIAL}",
                "base_object_revision": 0,
                "value": {
                    "current_temperature": 21.5,
                    "current_humidity": 45,
                    "software_version": "5.9.4-5",
                    "unprojected": {"value": 1},
                },
            },
            {
                "object_key": f"shared.{SERIAL}",
                "if_object_revision": 0,
                "value": {
                    "current_temperature": 0,
                    "target_temperature": 22,
                    "target_temperature_type": "heat",
                },
            },
        ],
    }


@pytest.fixture
async def native_client(rig):
    app = create_app(rig[0], native_telemetry=True, native_hold_seconds=0.03)
    async with TestClient(TestServer(app)) as client:
        yield client


async def test_native_rejection_reason_is_manager_only_and_payload_free(native_client, rig, caplog):
    core, token, admin, _ = rig
    marker = secrets.token_hex(32)
    endpoint = "/v1/manage/devices"
    manager = {"Authorization": "Bearer " + admin}
    assert (await native_client.get(endpoint)).status == 401
    assert (await native_client.get(endpoint, headers=auth(token))).status == 401
    response = await native_client.post("/nest/transport/put", json={marker: marker})
    assert response.status == 401
    assert native_client.app[NATIVE].diagnostics()["rejections"] == {}
    response = await native_client.post(
        "/nest/transport/put", headers=auth(token), json={"objects": marker}
    )
    assert response.status == 400
    assert not core.available(SERIAL) and core.states == {}
    response = await native_client.get(endpoint, headers=manager)
    result = await response.json()
    assert result["native_diagnostics"] == {
        "rejections": {"envelope_shape": 1},
        "last_rejection": "envelope_shape",
    }
    assert marker not in json.dumps(result) and marker not in caplog.text
    assert marker not in repr(native_client.app[NATIVE].__dict__)
    assert marker not in core.registry.path.read_text()
    assert (
        await native_client.post("/nest/transport/put", headers=auth(token), json=batch())
    ).status == 200
    assert core.available(SERIAL) and core.command_delivery_enabled is False


def test_rejection_diagnostics_have_finite_keys_saturating_counts_and_restart_reset(rig):
    native = NativeTelemetry(rig[0])
    for _ in range(1000):
        native.reject(Invalid(secrets.token_hex(32)))
    assert native.diagnostics() == {"rejections": {"other": 1000}, "last_rejection": "other"}
    native._rejections["other"] = 2147483647
    native.reject(Invalid("unknown payload text"))
    assert native.diagnostics()["rejections"]["other"] == 2147483647
    copy = native.diagnostics()
    copy["rejections"]["other"] = 0
    assert native.diagnostics()["rejections"]["other"] == 2147483647
    assert NativeTelemetry(rig[0]).diagnostics() == {"rejections": {}, "last_rejection": None}


async def test_normal_runtime_does_not_expose_native_diagnostics(rig):
    core, _, admin, _ = rig
    async with TestClient(TestServer(create_app(core))) as client:
        response = await client.get(
            "/v1/manage/devices", headers={"Authorization": "Bearer " + admin}
        )
        assert set(await response.json()) == {"devices"}


async def test_authenticated_native_entry_put_listing_and_read_only_controls(native_client, rig):
    core, token, admin, _ = rig
    response = await native_client.post(
        "/nest/entry", headers=auth(token), data={"reset": "true", "model": "Display-2.6"}
    )
    assert response.status == 200
    assert await response.json() == {"transport_url": "https://127.0.0.1:8443/nest/transport"}
    response = await native_client.post("/nest/transport/v7/put", headers=auth(token), json=batch())
    assert response.status == 200
    ack = await response.json()
    assert len(ack["objects"]) == 2
    for obj in ack["objects"]:
        assert list(obj) == ["object_revision", "object_timestamp", "object_key"]
        assert obj["object_revision"] == 1 and obj["object_timestamp"] > 0
        assert "value" not in obj
    assert core.view(SERIAL)["state"] == {
        "temperature": 0,
        "humidity": 45,
        "firmware": "5.9.4-5",
        "target_temperature": 22,
    }
    assert core.available(SERIAL)
    response = await native_client.get(
        f"/nest/transport/v7/device/device.{SERIAL}", headers=auth(token)
    )
    assert await response.json() == ack
    assert (
        await native_client.get(f"/nest/transport/v7/device/device.{OTHER}", headers=auth(token))
    ).status == 403
    response = await native_client.post(
        f"/v1/manage/devices/{SERIAL}/commands",
        headers={"Authorization": "Bearer " + admin},
        json={"operation": "temperature", "value": 24},
    )
    assert response.status == 409
    with pytest.raises(Invalid, match="no command delivery"):
        core.enqueue(SERIAL, {"operation": "temperature", "value": 24})
    assert (await native_client.get("/v1/device/commands", headers=auth(token))).status == 409
    assert core.poll(SERIAL) == []


def test_revisions_merge_cas_numeric_equivalence_and_duplicate_timestamps(rig):
    core = rig[0]
    clock = [1234.5]
    native = NativeTelemetry(core, clock=lambda: clock[0])
    data = {"objects": [batch()["objects"][0]]}
    first = native.apply(SERIAL, data)
    data["objects"][0]["value"] = {"current_temperature": 21.5}
    clock[0] += 100
    assert native.apply(SERIAL, data) == first
    data["objects"][0]["value"] = {"unprojected": {"value": 1.0}}
    assert native.apply(SERIAL, data) == first
    data["objects"][0]["value"] = {"current_temperature": 24}
    data["objects"][0]["if_object_revision"] = 0
    assert native.apply(SERIAL, data) == first
    assert core.states[SERIAL]["temperature"] == 21.5
    data["objects"][0]["if_object_revision"] = 1
    clock[0] = 1  # wall-clock rollback must not regress an object's timestamp
    second = native.apply(SERIAL, data)
    assert second["objects"][0]["object_revision"] == 2
    assert second["objects"][0]["object_timestamp"] == first["objects"][0]["object_timestamp"] + 1


def test_bucket_keyed_put_is_supported_but_outer_inner_mismatch_rejected(rig):
    native = NativeTelemetry(rig[0])
    key = f"device.{SERIAL}"
    body = {
        "session": "abc",
        key: {"object_key": key, "base_object_revision": 0, "current_humidity": 0},
    }
    assert native.apply(SERIAL, body)["objects"][0]["object_revision"] == 1
    assert rig[0].states[SERIAL]["humidity"] == 0
    body[key]["object_key"] = f"device.{OTHER}"
    with pytest.raises(Invalid, match="identity mismatch"):
        native.apply(SERIAL, body)


def test_unbound_account_objects_are_not_acknowledged_stored_or_used_for_identity(rig):
    native = NativeTelemetry(rig[0])
    data = batch()
    data["objects"].append(
        {
            "object_key": "structure.fixture-house",
            "value": {"devices": [OTHER], "private_fixture": "discard-this-value"},
        }
    )
    response = native.apply(SERIAL, data)
    assert len(response["objects"]) == 2
    assert "structure.fixture-house" not in repr(native._records)
    assert "discard-this-value" not in repr(native._records)
    assert set(rig[0].states) == {SERIAL}


async def test_unknown_fields_are_not_stored_echoed_or_logged(native_client, rig, caplog):
    marker = secrets.token_hex(32)
    body = batch()
    body["objects"][0]["value"]["private_fixture"] = marker
    response = await native_client.post("/nest/transport/put", headers=auth(rig[1]), json=body)
    assert response.status == 200
    assert marker not in await response.text()
    assert marker not in repr(native_client.app[NATIVE]._records)
    assert marker not in rig[0].registry.path.read_text() and marker not in caplog.text
    assert "private_fixture" not in rig[0].states[SERIAL]


@pytest.mark.parametrize(
    "mutation",
    [
        "foreign",
        "duplicate",
        "bad-temperature",
        "bool-revision",
        "negative-revision",
        "huge-revision",
        "mixed-envelope",
        "deep",
        "nonfinite",
        "too-many-fields",
    ],
)
async def test_invalid_batch_is_atomic(native_client, rig, mutation):
    data = batch()
    if mutation == "foreign":
        data["objects"][1]["object_key"] = f"shared.{OTHER}"
    elif mutation == "duplicate":
        data["objects"].append(copy.deepcopy(data["objects"][0]))
    elif mutation == "bad-temperature":
        data["objects"][1]["value"]["current_temperature"] = True
    elif mutation in ("bool-revision", "negative-revision", "huge-revision"):
        data["objects"][1]["if_object_revision"] = {
            "bool-revision": True,
            "negative-revision": -1,
            "huge-revision": 2**53,
        }[mutation]
    elif mutation == "mixed-envelope":
        data[f"device.{SERIAL}"] = data["objects"][0]
    elif mutation == "deep":
        value = 0
        for _ in range(18):
            value = [value]
        data["objects"][1]["value"]["deep"] = value
    elif mutation == "nonfinite":
        data["objects"][1]["value"]["unknown"] = float("inf")
    else:
        data["objects"][1]["value"] = {f"field_{i}": i for i in range(257)}
    response = await native_client.post("/nest/transport/put", headers=auth(rig[1]), json=data)
    assert response.status == 400
    assert rig[0].states == {} and rig[0].seen == {}
    assert native_client.app[NATIVE].listing(SERIAL) == {"objects": []}


async def test_native_limit_does_not_expand_canonical_limit(native_client, rig):
    response = await native_client.post(
        "/v1/device/state",
        headers={**auth(rig[1]), "Content-Type": "application/json"},
        data=b" " * 17000 + b"{}",
    )
    assert response.status == 413
    data = batch()
    data["objects"][0]["value"]["unprojected"] = "x" * 17000
    assert (
        await native_client.post("/nest/transport/put", headers=auth(rig[1]), json=data)
    ).status == 200
    data["objects"][0]["value"]["unprojected"] = "x" * 65536
    assert (
        await native_client.post("/nest/transport/put", headers=auth(rig[1]), json=data)
    ).status == 413


async def test_native_authentication_remains_explicit_and_generation_bound(native_client, rig):
    core, token, _, _ = rig
    for headers in (
        {},
        auth("bad"),
        auth(token, OTHER),
        {"X-NL-Device-Serial": SERIAL},
        {
            "Authorization": "Basic "
            + base64.b64encode(f"d.{SERIAL}.fixture:{token}".encode()).decode()
        },
    ):
        assert (
            await native_client.post("/nest/transport/put", headers=headers, json=batch())
        ).status == 401
    assert (
        await native_client.post("/nest/transport/put", headers=auth(token), json=batch())
    ).status == 200
    replacement = secrets.token_hex(32)
    core.registry.register(SERIAL, replacement, core.caps(SERIAL), rotate=True)
    core.forget(SERIAL)
    assert (
        await native_client.get(f"/nest/transport/device/{SERIAL}", headers=auth(token))
    ).status == 401
    response = await native_client.get(
        f"/nest/transport/device/{SERIAL}", headers=auth(replacement)
    )
    assert await response.json() == {"objects": []}


async def test_named_inline_subscribe_reports_state_without_echoing_values(native_client, rig):
    data = {
        "chunked": True,
        "session": "fixture",
        "shared": {
            "object_key": f"shared.{SERIAL}",
            "object_revision": 0,
            "object_timestamp": 0,
            "value": {"current_temperature": 19},
        },
    }
    response = await native_client.post(
        "/nest/transport/v7/subscribe", headers=auth(rig[1]), json=data
    )
    assert response.status == 200 and response.headers["Transfer-Encoding"] == "chunked"
    first = await response.json()
    assert first["objects"][0]["object_revision"] == 1
    assert "value" not in first["objects"][0] and rig[0].states[SERIAL]["temperature"] == 19
    metadata = first["objects"][0]
    response = await native_client.post(
        "/nest/transport", headers=auth(rig[1]), json={"chunked": True, "objects": [metadata]}
    )
    assert response.status == 200 and await response.read() == b""
    assert not native_client.app[NATIVE_ACTIVE]


@pytest.mark.parametrize("native", [False, True])
async def test_rotation_during_a_slow_body_cannot_update_new_credential_generation(rig, native):
    core, token, _, _ = rig
    started, release = asyncio.Event(), asyncio.Event()

    async def chunks():
        yield b'{"objects":[' if native else b'{"temperature":'
        started.set()
        await release.wait()
        yield json.dumps(batch()["objects"]).encode()[1:-1] + b"]}" if native else b"20}"

    app = create_app(core, native_telemetry=native)
    async with TestClient(TestServer(app)) as client:
        path = "/nest/transport/put" if native else "/v1/device/state"
        task = asyncio.create_task(
            client.post(
                path, headers={**auth(token), "Content-Type": "application/json"}, data=chunks()
            )
        )
        await started.wait()
        await asyncio.sleep(0.01)
        core.registry.register(SERIAL, secrets.token_hex(32), core.caps(SERIAL), rotate=True)
        core.forget(SERIAL)
        release.set()
        response = await task
        assert response.status == 401 and core.states == {} and core.seen == {}
