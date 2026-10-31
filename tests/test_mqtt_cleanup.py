import secrets
from types import SimpleNamespace

import paho.mqtt.client as mqtt
import pytest

from backend.core import Core
from backend.mqtt import Bridge, accept_command
from backend.registry import Registry
from backend.validation import Invalid
from tests.conftest import OTHER, SERIAL


class Publications:
    def __init__(self):
        self.items = []
        self.online = True
        self.fail = set()

    def is_connected(self):
        return self.online

    def publish(self, topic, payload, qos, retain):
        self.items.append((topic, payload, qos, retain))
        return SimpleNamespace(
            rc=mqtt.MQTT_ERR_QUEUE_SIZE if topic in self.fail else mqtt.MQTT_ERR_SUCCESS
        )


def bridge(core):
    result = object.__new__(Bridge)
    result.core, result.client, result.known, result.cleaned = core, Publications(), set(), set()
    return result


def cleanup(ident=SERIAL):
    return [
        (f"hearth/{ident}/availability", "offline", 1, True),
        (f"homeassistant/climate/hearth_{ident}/config", "", 1, True),
        (f"hearth/{ident}/state", "", 1, True),
    ]


def test_offline_revocation_survives_registry_core_and_bridge_restart(rig):
    core, token, _, _ = rig
    core.registry.revoke(SERIAL)
    fresh = Core(Registry(core.registry.path))
    assert fresh.registry.revoked_devices() == {SERIAL}
    assert not fresh.registry.authenticate(SERIAL, token)
    mqtt_bridge = bridge(fresh)
    mqtt_bridge.connected()
    assert all(item in mqtt_bridge.client.items for item in cleanup())
    assert mqtt_bridge.cleaned == {SERIAL}
    assert mqtt_bridge.known == set()
    # Cleanup identifiers hold no old credential, digest, capabilities or state.
    assert fresh.registry.data["revoked"] == [SERIAL]
    assert fresh.registry.data["devices"] == {}
    with pytest.raises(Invalid):
        accept_command(fresh, f"hearth/{SERIAL}/command/mode", b"heat")


def test_cleanup_repeats_after_reconnect_and_process_loss_without_erasing_ledger(rig):
    core = rig[0]
    core.registry.revoke(SERIAL)
    mqtt_bridge = bridge(core)
    mqtt_bridge.connected()
    mqtt_bridge.client.items.clear()
    mqtt_bridge.publish()
    assert not any(item in mqtt_bridge.client.items for item in cleanup())
    mqtt_bridge.client.items.clear()
    mqtt_bridge.connected()
    assert all(item in mqtt_bridge.client.items for item in cleanup())
    assert Registry(core.registry.path).revoked_devices() == {SERIAL}
    # Even an already-cleaned broker may later restore stale retained data.
    restarted = bridge(Core(Registry(core.registry.path)))
    restarted.connected()
    assert all(item in restarted.client.items for item in cleanup())


def test_full_publish_queue_retries_entire_idempotent_cleanup_on_next_tick(rig):
    core = rig[0]
    core.registry.revoke(SERIAL)
    mqtt_bridge = bridge(core)
    mqtt_bridge.client.fail.add(f"hearth/{SERIAL}/state")
    mqtt_bridge.connected()
    assert not mqtt_bridge.cleaned
    mqtt_bridge.client.items.clear()
    mqtt_bridge.client.fail.clear()
    mqtt_bridge.publish()
    assert all(item in mqtt_bridge.client.items for item in cleanup())
    assert mqtt_bridge.cleaned == {SERIAL}


def test_no_cleanup_progress_without_broker_connection(rig):
    core = rig[0]
    core.registry.revoke(SERIAL)
    mqtt_bridge = bridge(core)
    mqtt_bridge.client.online = False
    mqtt_bridge.publish()
    assert not mqtt_bridge.cleaned and not mqtt_bridge.client.items
    mqtt_bridge.client.online = True
    mqtt_bridge.connected()
    assert all(item in mqtt_bridge.client.items for item in cleanup())


def test_reenrollment_cancels_stale_cleanup_and_later_revocation_cleans_again(rig):
    core = rig[0]
    caps = core.caps(SERIAL)
    core.registry.revoke(SERIAL)
    mqtt_bridge = bridge(core)
    mqtt_bridge.connected()
    token = secrets.token_hex(32)
    core.registry.register(SERIAL, token, caps)
    assert not Registry(core.registry.path).revoked_devices()
    mqtt_bridge.client.items.clear()
    mqtt_bridge.publish()
    assert not mqtt_bridge.cleaned
    assert not any(item in mqtt_bridge.client.items for item in cleanup()[1:])
    config = [item for item in mqtt_bridge.client.items if item[0] == cleanup()[1][0]]
    assert (
        len(config) == 1 and config[0][1]
    )  # publish fresh discovery, never delete active identity
    core.registry.revoke(SERIAL)
    mqtt_bridge.client.items.clear()
    mqtt_bridge.publish()
    assert all(item in mqtt_bridge.client.items for item in cleanup())


def test_live_revocation_preserves_other_device_discovery_and_auth(rig):
    core = rig[0]
    caps = core.caps(SERIAL)
    other_token = secrets.token_hex(32)
    core.registry.register(OTHER, other_token, caps)
    mqtt_bridge = bridge(core)
    mqtt_bridge.connected()
    core.registry.revoke(SERIAL)
    mqtt_bridge.client.items.clear()
    mqtt_bridge.publish()
    assert all(item in mqtt_bridge.client.items for item in cleanup())
    assert cleanup(OTHER)[1] not in mqtt_bridge.client.items
    assert core.registry.authenticate(OTHER, other_token)
    assert mqtt_bridge.known == {OTHER}


def test_older_registry_loads_and_explicit_revoke_can_clean_known_orphan(rig):
    registry = rig[0].registry
    registry.data.pop("revoked", None)
    registry.save()
    original = Registry(registry.path)
    assert original.revoked_devices() == set()
    # A prior release cannot reconstruct already-forgotten identities. An owner
    # can explicitly revoke a known orphan once to add the durable cleanup record.
    original.revoke(OTHER)
    assert Registry(registry.path).revoked_devices() == {OTHER}


@pytest.mark.parametrize("value", [SERIAL, ["hearth/+/state"], ["#"], [None], [123], {}])
def test_invalid_cleanup_identities_fail_before_bridge_topic_construction(rig, value):
    registry = rig[0].registry
    registry.data["revoked"] = value
    registry.save()
    with pytest.raises(Invalid):
        Registry(registry.path)
