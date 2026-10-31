import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.api import create_app
from backend.mqtt import Bridge, accept_command, sensor_discovery
from backend.validation import Invalid
from tests.conftest import SERIAL
from tests.test_mqtt_cleanup import bridge


def test_sensor_discovery_has_no_commands_and_preserves_zero():
    configs = sensor_discovery(SERIAL, "5.9.4-5")
    assert len(configs) == 3
    assert all("command" not in json.dumps(config) for config in configs.values())
    temperature = configs[f"homeassistant/sensor/hearth_{SERIAL}_temperature/config"]
    assert temperature["device_class"] == "temperature"
    assert temperature["unit_of_measurement"] == "°C"
    assert temperature["state_class"] == "measurement"
    assert temperature["availability_mode"] == "all"
    assert "default('None')" in temperature["value_template"]
    assert "true" not in temperature["value_template"].lower()


def test_native_mode_rejects_http_core_and_mqtt_command_ingress(rig):
    core = rig[0]
    create_app(core, native_telemetry=True)
    core.report(SERIAL, {"temperature": 0})
    with pytest.raises(Invalid, match="no command delivery"):
        accept_command(core, f"hearth/{SERIAL}/command/temperature", b"22")
    mqtt_bridge = bridge(core)
    mqtt_bridge.read_only = True
    mqtt_bridge.receive(f"hearth/{SERIAL}/command/mode", b"heat", False)
    assert core.pending == {}
    mqtt_bridge.read_only = False  # Core still rejects a misconfigured subscriber.
    mqtt_bridge.receive(f"hearth/{SERIAL}/command/mode", b"heat", False)
    assert core.pending == {}


def test_read_only_migration_and_durable_revocation_cleanup(rig):
    core = rig[0]
    mqtt_bridge = bridge(core)
    mqtt_bridge.read_only = True
    mqtt_bridge.loop = SimpleNamespace(call_soon_threadsafe=lambda fn: fn())
    # Publications deliberately has no subscribe(): readonly mode must not call it.
    mqtt_bridge.on_connect(mqtt_bridge.client, None, None, 0, None)
    publications = {topic: payload for topic, payload, _, _ in mqtt_bridge.client.items}
    assert publications[f"homeassistant/climate/hearth_{SERIAL}/config"] == ""
    assert all(publications[topic] for topic in sensor_discovery(SERIAL))
    core.registry.revoke(SERIAL)
    mqtt_bridge.client.items.clear()
    failed_topic = next(iter(sensor_discovery(SERIAL)))
    mqtt_bridge.client.fail.add(failed_topic)
    mqtt_bridge.publish()
    assert not mqtt_bridge.cleaned
    mqtt_bridge.client.fail.clear()
    mqtt_bridge.publish()
    assert mqtt_bridge.cleaned == {SERIAL}
    for topic in sensor_discovery(SERIAL):
        assert (topic, "", 1, True) in mqtt_bridge.client.items


async def test_bridge_derives_read_only_from_native_profile_without_extra_flag(rig):
    core = rig[0]
    create_app(core, native_telemetry=True)
    mqtt_bridge = Bridge(
        core,
        {"host": "127.0.0.1", "username": "fixture", "password": "fixture"},
        asyncio.get_running_loop(),
    )
    assert mqtt_bridge.read_only is True
    # connect_async only configures the client; its network loop was never started.
    mqtt_bridge.client.disconnect()
