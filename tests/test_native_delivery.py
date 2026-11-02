import asyncio
import copy
import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from backend.api import NATIVE_STOP, create_app
from backend.native_controls import NativeControls
from tests.conftest import SERIAL
from tests.test_native_controls import baseline, sub
from tests.test_native_telemetry import batch
from tests.test_security import auth


@pytest.fixture
def eco_native(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"device.{SERIAL}",
                    "value": {"structure_id": "structure.DELIVERYLAB"},
                },
                {
                    "object_key": "structure.DELIVERYLAB",
                    "value": {"manual_eco_all": False, "manual_eco_timestamp": 900},
                },
            ]
        },
    )
    return n


def test_matching_client_metadata_does_not_acknowledge_a_pending_value(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    n.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    response = n.updates(SERIAL, sub(n))
    assert [row["value"] for row in response["objects"]] == [{"target_temperature": 23}]
    assert n.command_status(SERIAL)["temperature"] == "pending"
    assert n.core.states[SERIAL]["target_temperature"] == 22


def test_expired_intent_does_not_escape_via_a_stale_metadata_reply(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    request = sub(n)
    n.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    rig[3][0] += 31
    assert n.updates(SERIAL, request) == {"objects": []}
    receipt = n.control_view(SERIAL)["delivery_receipts"]["temperature"]
    assert receipt["outcome"] == "expired" and not receipt["stream_write_completed"]
    assert not receipt["offered"]
    assert SERIAL not in json.dumps(receipt) and "target_temperature" not in receipt


def test_multi_field_confirmation_cannot_borrow_an_old_matching_baseline(eco_native):
    n = eco_native
    n.enqueue(SERIAL, {"operation": "eco", "value": False})
    key = n.home_key(SERIAL)
    n.apply(SERIAL, {"objects": [{"object_key": key, "value": {"manual_eco_timestamp": 1000}}]})
    assert n.command_status(SERIAL)["eco"] == "pending"
    n.apply(SERIAL, {"objects": [{"object_key": key, "value": {"manual_eco_all": False}}]})
    receipt = n.control_view(SERIAL)["delivery_receipts"]["eco"]
    assert receipt["outcome"] == "confirmed"
    assert receipt["matching_reported_field_count"] == receipt["required_field_count"] == 2


def test_replacing_intent_resets_partial_confirmation(eco_native):
    n = eco_native
    key = n.home_key(SERIAL)
    n.enqueue(SERIAL, {"operation": "eco", "value": False})
    n.apply(SERIAL, {"objects": [{"object_key": key, "value": {"manual_eco_timestamp": 1000}}]})
    n.enqueue(SERIAL, {"operation": "eco", "value": False})
    n.apply(SERIAL, {"objects": [{"object_key": key, "value": {"manual_eco_all": False}}]})
    assert n.command_status(SERIAL)["eco"] == "pending"
    n.apply(SERIAL, {"objects": [{"object_key": key, "value": {"manual_eco_timestamp": 1000}}]})
    assert n.command_status(SERIAL)["eco"] == "confirmed"


async def test_stale_metadata_keeps_stream_open_for_control_then_shutdown_interrupts_settle(rig):
    core, token, admin, _ = rig
    app = create_app(core, native_telemetry=True, native_controls=True, native_hold_seconds=290)
    manager_headers = {"Authorization": "Bearer " + admin}
    async with TestClient(TestServer(app)) as client:
        async with client.post("/nest/transport/put", headers=auth(token), json=batch()) as reply:
            objects = (await reply.json())["objects"]
        for row in objects:
            row["object_revision"] = -(1 << 31)
        before = copy.deepcopy(core.states[SERIAL])
        stream = await client.post(
            "/nest/transport/v7/subscribe",
            headers=auth(token),
            json={"objects": objects, "chunked": True},
        )
        read = asyncio.create_task(stream.content.readany())
        await asyncio.sleep(0.02)
        assert not read.done(), "metadata-only reply closed the control carrier"
        async with client.get("/v1/manage/devices", headers=manager_headers) as reply:
            controls = (await reply.json())["devices"][0]["native_controls"]
        assert controls["transport"]["active_subscriptions"] == 1
        async with client.post(
            f"/v1/manage/devices/{SERIAL}/commands",
            headers=manager_headers,
            json={"operation": "temperature", "value": 23},
        ) as reply:
            assert reply.status == 202
        first = json.loads(await asyncio.wait_for(read, 1))
        assert [row["value"] for row in first["objects"]] == [{"target_temperature": 23}]
        assert core.states[SERIAL] == before
        async with client.get("/v1/manage/devices", headers=manager_headers) as reply:
            controls = (await reply.json())["devices"][0]["native_controls"]
        assert controls["transport"]["active_subscriptions"] == 1
        assert controls["pending"]["temperature"]["stream_write_completed"]
        assert controls["command_status"]["temperature"] == "pending"
        app[NATIVE_STOP].set()
        assert await asyncio.wait_for(stream.content.read(), 0.5) == b""
        row = first["objects"][0]
        async with client.post(
            "/nest/transport/put",
            headers=auth(token),
            json={
                "objects": [
                    {
                        "object_key": row["object_key"],
                        "if_object_revision": row["object_revision"],
                        "value": row["value"],
                    }
                ]
            },
        ) as reply:
            assert reply.status == 200
        async with client.get("/v1/manage/devices", headers=manager_headers) as reply:
            controls = (await reply.json())["devices"][0]["native_controls"]
        receipt = controls["delivery_receipts"]["temperature"]
        assert receipt["outcome"] == "confirmed" and receipt["stream_write_completed"]
        assert receipt["matching_reported_field_count"] == 1


def test_inline_compare_and_swap_failure_still_returns_current_metadata(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    key = f"device.{SERIAL}"
    before = copy.deepcopy(n.core.states)
    metadata = n._records_for(SERIAL)[key].metadata(key)
    reply = n.apply(
        SERIAL,
        {
            "objects": [
                {"object_key": key, "if_object_revision": 99, "value": {"current_humidity": 77}}
            ]
        },
        subscription=True,
    )
    assert reply == {"objects": [metadata]}
    assert n.core.states == before
