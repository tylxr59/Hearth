import pytest

from backend.core import Core
from backend.mqtt import accept_command, discovery
from backend.validation import Invalid
from tests.conftest import SERIAL
from tests.test_security import auth


async def test_simulated_nest_to_ha_and_command(client, rig):
    core, token, admin, now = rig
    payload = {
        "objects": [
            {
                "object_key": "device." + SERIAL,
                "value": {
                    "current_temperature": 21.5,
                    "current_humidity": 45,
                    "software_version": "5.9.4",
                },
            },
            {
                "object_key": "shared." + SERIAL,
                "value": {"target_temperature": 22, "target_temperature_type": "heat"},
            },
        ]
    }
    response = await client.post("/nest/transport/v7/put", headers=auth(token), json=payload)
    assert response.status == 200
    assert await response.json() == {"objects": []}
    config = discovery(SERIAL, core.caps(SERIAL), "5.9.4")
    assert config["current_temperature_topic"] == f"hearth/{SERIAL}/state"
    assert config["device"]["sw_version"] == "5.9.4"
    assert config["availability_mode"] == "all"
    item = accept_command(core, config["temperature_command_topic"], b"23")
    response = await client.get("/v1/device/commands", headers=auth(token))
    assert (await response.json())["commands"] == [item]
    # Intent never becomes reported state until a device actually reports it.
    assert core.view(SERIAL)["state"]["target_temperature"] == 22
    assert (
        await client.post("/v1/device/ack", headers=auth(token), json=[item["id"]])
    ).status == 200
    assert core.poll(SERIAL) == []
    assert (
        await client.post(
            "/v1/device/state",
            headers=auth(token),
            json={"target_temperature": 23, "action": "heating"},
        )
    ).status == 200
    response = await client.get("/v1/manage/devices", headers={"Authorization": "Bearer " + admin})
    assert (await response.json())["devices"][0]["state"]["target_temperature"] == 23
    now[0] += 91
    assert not core.available(SERIAL)


def test_expiration_offline_and_restart(rig):
    core, _, _, now = rig
    with pytest.raises(Invalid):
        core.enqueue(SERIAL, {"operation": "temperature", "value": 20})
    core.report(SERIAL, {"temperature": 21})
    core.enqueue(SERIAL, {"operation": "temperature", "value": 23})
    core.enqueue(SERIAL, {"operation": "temperature", "value": 24})
    assert len(core.poll(SERIAL)) == 1
    now[0] += 31
    assert not core.poll(SERIAL)
    restarted = Core(core.registry)
    assert not restarted.poll(SERIAL)
    assert not restarted.available(SERIAL)


@pytest.mark.parametrize(
    "topic,payload,retained",
    [
        (f"hearth/{SERIAL}/device/target_temperature/set", b"23", False),
        (f"hearth/{SERIAL}/command/temperature", b"NaN", False),
        (f"hearth/{SERIAL}/command/temperature", b"Infinity", False),
        (f"hearth/{SERIAL}/command/temperature", b"true", False),
        (f"hearth/{SERIAL}/command/temperature", b"31", False),
        (f"hearth/{SERIAL}/command/mode", b"heat_cool", False),
        (f"hearth/{SERIAL}/command/raw", b"arbitrary", False),
        (f"hearth/{SERIAL}/command/mode", b"heat", True),
        (f"hearth/{SERIAL}/command/fan", b"\xff", False),
    ],
)
def test_mqtt_rejects_bypass(rig, topic, payload, retained):
    core = rig[0]
    core.report(SERIAL, {"temperature": 21})
    with pytest.raises(Invalid):
        accept_command(core, topic, payload, retained)
    assert not core.pending


def test_online_availability_is_never_retained(rig):
    from backend.mqtt import Bridge

    core = rig[0]
    core.report(SERIAL, {"temperature": 21})
    publications = []

    class Client:
        def is_connected(self):
            return True

        def publish(self, topic, payload, qos, retain):
            publications.append((topic, payload, retain))

    bridge = object.__new__(Bridge)
    bridge.core, bridge.client, bridge.known = core, Client(), set()
    bridge.connected()
    availability = [item for item in publications if item[0].endswith("/availability")]
    assert any(payload == "offline" and retain for _, payload, retain in availability)
    assert all(not retain for _, payload, retain in availability if payload == "online")
