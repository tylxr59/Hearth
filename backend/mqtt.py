"""MQTT discovery and validated commands. Broker ACLs are the authorization boundary."""

import asyncio
import contextlib
import json
import ssl
from pathlib import Path

import paho.mqtt.client as mqtt

from backend.validation import Invalid, loads, serial


def discovery(ident, caps, firmware="unknown"):
    prefix = f"hearth/{ident}"
    state_topic = prefix + "/state"
    result = {
        "name": "Thermostat",
        "unique_id": f"hearth_{ident}",
        "device": {
            "identifiers": [f"hearth_{ident}"],
            "manufacturer": "Nest",
            "model": "Learning Thermostat (experimental)",
            "sw_version": firmware,
        },
        "availability": [
            {"topic": "hearth/bridge/availability"},
            {"topic": prefix + "/availability"},
        ],
        "availability_mode": "all",
        "temperature_unit": "C",
        "min_temp": 10,
        "max_temp": 30,
        "temp_step": 0.5,
        "modes": caps["modes"],
        "mode_command_topic": prefix + "/command/mode",
        "temperature_command_topic": prefix + "/command/temperature",
    }
    for name, field in (
        ("current_temperature", "temperature"),
        ("temperature_state", "target_temperature"),
        ("current_humidity", "humidity"),
        ("mode_state", "mode"),
        ("action", "action"),
    ):
        result[name + "_topic"] = state_topic
        result[name + "_template"] = "{{ value_json." + field + " | default('None') }}"
    if caps["fan"]:
        result.update(
            fan_modes=["auto", "on"],
            fan_mode_command_topic=prefix + "/command/fan",
            fan_mode_state_topic=state_topic,
            fan_mode_state_template="{{ value_json.fan | default('None') }}",
        )
    return result


def accept_command(core, topic, payload, retained=False):
    if retained or len(payload) > 128:
        raise Invalid("retained or oversized command rejected")
    parts = topic.split("/")
    if len(parts) != 4 or parts[0] != "hearth" or parts[2] != "command":
        raise Invalid("unsupported topic")
    ident, op = serial(parts[1]), parts[3]
    try:
        text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise Invalid("invalid payload") from exc
    value = loads(text) if op == "temperature" else text
    return core.enqueue(ident, {"operation": op, "value": value})


class Bridge:
    def __init__(self, core, config, loop):
        self.core, self.loop = core, loop
        self.known = set()
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id="hearth-bridge", protocol=mqtt.MQTTv5
        )
        self.client.username_pw_set(config["username"], config["password"])
        context = ssl.create_default_context(cafile=config.get("ca"))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.client.tls_set_context(context)
        self.client.will_set("hearth/bridge/availability", "offline", qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.max_queued_messages_set(128)
        self.client.connect_async(config["host"], config.get("port", 8883), keepalive=30)

    def on_connect(self, client, userdata, flags, reason, properties):
        if reason == 0:
            client.subscribe(
                "hearth/+/command/+",
                options=mqtt.SubscribeOptions(qos=0, retainAsPublished=True, retainHandling=2),
            )
            # Publish device offline/online before declaring bridge online.
            self.loop.call_soon_threadsafe(self.connected)

    def connected(self):
        # Persist offline, then send live online heartbeats. A restarted broker must
        # not resurrect a retained online state while this process is absent.
        self.client.publish("hearth/bridge/availability", "offline", qos=1, retain=True)
        for ident in self.core.registry.data["devices"]:
            self.client.publish(f"hearth/{ident}/availability", "offline", qos=1, retain=True)
        self.publish()

    def on_message(self, client, userdata, message):
        self.loop.call_soon_threadsafe(
            self.receive, message.topic, bytes(message.payload), message.retain
        )

    def receive(self, topic, payload, retained):
        with contextlib.suppress(Invalid):
            accept_command(self.core, topic, payload, retained)

    def publish(self):
        if not self.client.is_connected():
            return
        current = set(self.core.registry.data["devices"])
        for ident in self.known - current:
            self.client.publish(f"hearth/{ident}/availability", "offline", qos=1, retain=True)
            self.client.publish(
                f"homeassistant/climate/hearth_{ident}/config", "", qos=1, retain=True
            )
            self.client.publish(f"hearth/{ident}/state", "", qos=1, retain=True)
        for ident in current:
            view = self.core.view(ident)
            config = discovery(
                ident, view["capabilities"], view["state"].get("firmware", "unknown")
            )
            self.client.publish(
                f"homeassistant/climate/hearth_{ident}/config",
                json.dumps(config),
                qos=1,
                retain=True,
            )
            self.client.publish(
                f"hearth/{ident}/state", json.dumps(view["state"]), qos=1, retain=True
            )
            self.client.publish(
                f"hearth/{ident}/availability",
                "online" if view["available"] else "offline",
                qos=1,
                retain=not view["available"],
            )
        self.known = current
        self.client.publish("hearth/bridge/availability", "online", qos=1, retain=False)

    async def run(self):
        self.client.loop_start()
        try:
            while True:
                self.publish()
                await asyncio.sleep(5)
        finally:
            self.client.publish("hearth/bridge/availability", "offline", qos=1, retain=True)
            self.client.disconnect()
            self.client.loop_stop()


def install(app, core, path):
    async def lifecycle(app):
        config_path = Path(path)
        if config_path.is_symlink() or config_path.stat().st_mode & 0o077:
            raise Invalid("MQTT configuration must be private")
        config = loads(config_path.read_bytes())
        if not config.get("username") or not config.get("password"):
            raise Invalid("dedicated MQTT credentials required")
        bridge = Bridge(core, config, asyncio.get_running_loop())
        task = asyncio.create_task(bridge.run())
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    app.cleanup_ctx.append(lifecycle)
