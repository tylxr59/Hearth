"""Opt-in real TLS/authenticated Mosquitto integration, bound only to loopback."""

import asyncio
import json
import os
import queue
import secrets
import ssl
import subprocess
import threading
import time
from pathlib import Path

import aiohttp
import paho.mqtt.client as mqtt
import pytest
from aiohttp.test_utils import TestClient, TestServer

from backend.api import create_app
from backend.mqtt import install
from backend.registry import private_json
from tests.conftest import SERIAL
from tests.containers import ENGINE, command
from tests.test_security import auth

IMAGE = "eclipse-mosquitto:2.0.22@sha256:09b62ff32c2e7b64d4b431b9a89236073289b68db273de2b089edeb9b0d92b5c"
pytestmark = pytest.mark.skipif(
    os.environ.get("HEARTH_BROKER_TEST") != "1", reason="opt-in container broker"
)


def run(*args):
    return subprocess.run(command(args), check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def broker(tmp_path):
    # Use a traversable temporary directory for the unprivileged container uid.
    root = Path(run("mktemp", "-d", "/tmp/hearth-broker-XXXXXXXX"))
    root.chmod(0o755)
    name = "hearth-test-" + secrets.token_hex(6)
    password = secrets.token_hex(32)
    run(
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-days",
        "1",
        "-subj",
        "/CN=localhost",
        "-addext",
        "subjectAltName=IP:127.0.0.1,DNS:localhost",
        "-keyout",
        str(root / "key.pem"),
        "-out",
        str(root / "cert.pem"),
    )
    (root / "key.pem").chmod(0o600)
    # Both local processes and the container use the current unprivileged uid.
    uid = f"{os.getuid()}:{os.getgid()}"
    run(
        ENGINE,
        "run",
        "--rm",
        "--user",
        uid,
        "-v",
        f"{root}:/test",
        IMAGE,
        "mosquitto_passwd",
        "-b",
        "-c",
        "/test/passwords",
        "bridge",
        password,
    )
    run(
        ENGINE,
        "run",
        "--rm",
        "--user",
        uid,
        "-v",
        f"{root}:/test",
        IMAGE,
        "mosquitto_passwd",
        "-b",
        "/test/passwords",
        "ha",
        password,
    )
    (root / "acl").write_text("""user bridge
 topic write homeassistant/climate/+/config
 topic write hearth/+/state
 topic write hearth/+/availability
 topic read hearth/+/command/+
user ha
 topic read homeassistant/climate/+/config
 topic read hearth/+/state
 topic read hearth/+/availability
 topic write hearth/+/command/temperature
 topic write hearth/+/command/mode
 topic write hearth/+/command/fan
""")
    (root / "mosquitto.conf").write_text("""listener 8883
allow_anonymous false
password_file /test/passwords
acl_file /test/acl
certfile /test/cert.pem
keyfile /test/key.pem
persistence false
""")
    try:
        run(
            ENGINE,
            "run",
            "--rm",
            "-d",
            "--name",
            name,
            "--user",
            uid,
            "-p",
            "127.0.0.1::8883",
            "-v",
            f"{root}:/test:ro",
            IMAGE,
            "mosquitto",
            "-c",
            "/test/mosquitto.conf",
        )
        port = int(run(ENGINE, "port", name, "8883/tcp").split(":")[-1])
        time.sleep(0.5)
        yield root, port, password
    finally:
        subprocess.run([ENGINE, "rm", "-f", name], capture_output=True, check=False)
        import shutil

        shutil.rmtree(root)


async def wait_for(predicate, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("MQTT integration timed out")


async def test_real_broker_discovery_commands_and_auth(broker, rig, tmp_path):
    root, port, password = broker
    core, token, _, _ = rig
    messages = queue.Queue()
    connected = threading.Event()
    observer = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    observer.tls_set(ca_certs=str(root / "cert.pem"))
    observer.username_pw_set("ha", password)

    def on_connect(client, userdata, flags, reason, properties):
        if reason == 0:
            client.subscribe("homeassistant/climate/+/config")
            client.subscribe("hearth/+/state")
            connected.set()

    observer.on_connect = on_connect
    observer.on_message = lambda c, u, m: messages.put((m.topic, bytes(m.payload)))
    observer.connect("127.0.0.1", port)
    observer.loop_start()
    config = tmp_path / "mqtt.json"
    private_json(
        config,
        {
            "host": "127.0.0.1",
            "port": port,
            "username": "bridge",
            "password": password,
            "ca": str(root / "cert.pem"),
        },
    )
    app = create_app(core)
    install(app, core, config)
    try:
        await wait_for(connected.is_set)
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(root / "cert.pem", root / "key.pem")
        server = TestServer(app, scheme="https")
        await server.start_server(ssl=server_context)
        client_context = ssl.create_default_context(cafile=str(root / "cert.pem"))
        async with TestClient(server, connector=aiohttp.TCPConnector(ssl=client_context)) as client:
            response = await client.post(
                "/v1/device/state",
                headers=auth(token),
                json={
                    "temperature": 20.5,
                    "target_temperature": 21,
                    "mode": "heat",
                    "humidity": 42,
                    "firmware": "sim-1",
                },
            )
            assert response.status == 200
            received = {}

            def discovered():
                while not messages.empty():
                    topic, payload = messages.get_nowait()
                    received[topic] = json.loads(payload)
                return (
                    f"homeassistant/climate/hearth_{SERIAL}/config" in received
                    and received.get(f"hearth/{SERIAL}/state", {}).get("temperature") == 20.5
                )

            await wait_for(discovered)
            config = received[f"homeassistant/climate/hearth_{SERIAL}/config"]
            observer.publish(config["temperature_command_topic"], "22.5", qos=1)
            await wait_for(lambda: bool(core.poll(SERIAL)))
            assert core.poll(SERIAL)[0]["value"] == 22.5
            observer.publish(config["temperature_command_topic"], "23", qos=1, retain=True)
            # The subscriber preserves the retain flag even for a live retained publish.
            await asyncio.sleep(0.3)
            assert core.poll(SERIAL)[0]["value"] == 22.5
            # ACL denies the old raw command path; validation also has no such operation.
            observer.publish(f"hearth/{SERIAL}/device/target_temperature/set", "100", qos=1)
            observer.publish(config["temperature_command_topic"], "99", qos=1)
            await asyncio.sleep(0.3)
            assert len(core.poll(SERIAL)) == 1 and core.poll(SERIAL)[0]["value"] == 22.5
        rejected = threading.Event()
        bad = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        bad.tls_set(ca_certs=str(root / "cert.pem"))
        bad.username_pw_set("ha", "incorrect")
        bad.on_connect = lambda c, u, f, reason, p: rejected.set() if reason != 0 else None
        bad.connect("127.0.0.1", port)
        bad.loop_start()
        try:
            await wait_for(rejected.is_set)
        finally:
            bad.disconnect()
            bad.loop_stop()
    finally:
        observer.disconnect()
        observer.loop_stop()


async def test_offline_revocation_cleans_retained_records_after_backend_restarts(broker, rig):
    import contextlib

    from backend.core import Core
    from backend.mqtt import Bridge
    from backend.registry import Registry
    from tests.conftest import OTHER

    root, port, password = broker
    old_core, revoked_token, _, _ = rig
    caps = old_core.caps(SERIAL)
    other_token = secrets.token_hex(32)
    old_core.registry.register(OTHER, other_token, caps)
    old_core.registry.revoke(SERIAL)  # no bridge running during this offline change
    peers = []
    config_topic = f"homeassistant/climate/hearth_{SERIAL}/config"
    state_topic = f"hearth/{SERIAL}/state"

    def peer(user, topics=()):
        messages, connected, subscribed = queue.Queue(), threading.Event(), threading.Event()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
        client.tls_set(ca_certs=str(root / "cert.pem"))
        client.username_pw_set(user, password)

        def on_connect(client, userdata, flags, reason, properties):
            if reason == 0:
                if topics:
                    client.subscribe([(topic, 1) for topic in topics])
                connected.set()

        client.on_connect = on_connect
        client.on_subscribe = lambda *args: subscribed.set()
        client.on_message = lambda c, u, m: messages.put((m.topic, bytes(m.payload), m.retain))
        client.connect("127.0.0.1", port)
        client.loop_start()
        peers.append(client)
        return client, messages, connected, subscribed

    def drain(messages, into):
        while not messages.empty():
            topic, payload, retained = messages.get_nowait()
            into[topic] = (payload, retained)

    seed, _, seed_ready, _ = peer("bridge")
    topics = ("homeassistant/climate/+/config", "hearth/+/state", "hearth/+/availability")
    config = {
        "host": "127.0.0.1",
        "port": port,
        "username": "bridge",
        "password": password,
        "ca": str(root / "cert.pem"),
    }
    try:
        await wait_for(seed_ready.is_set)
        # Reintroduce stale broker data between two independent backend instances.
        # The cleanup ledger must survive even after the first successful deletion.
        for _ in range(2):
            for topic in (config_topic, state_topic):
                publication = seed.publish(topic, b'{"stale":true}', qos=1, retain=True)
                await asyncio.to_thread(publication.wait_for_publish, 3)
                assert publication.is_published()
            observer, messages, ready, subscribed = peer("ha", topics)
            await wait_for(
                lambda ready=ready, subscribed=subscribed: ready.is_set() and subscribed.is_set()
            )
            initial = {}

            def stale_received(messages=messages, initial=initial):
                drain(messages, initial)
                return all(
                    initial.get(topic, (None,))[0] == b'{"stale":true}'
                    for topic in (config_topic, state_topic)
                )

            await wait_for(stale_received)
            fresh = Core(Registry(old_core.registry.path))
            assert not fresh.registry.authenticate(SERIAL, revoked_token)
            assert fresh.registry.authenticate(OTHER, other_token)
            mqtt_bridge = Bridge(fresh, config, asyncio.get_running_loop())
            task = asyncio.create_task(mqtt_bridge.run())
            try:
                deleted = {}

                def cleanup_received(messages=messages, deleted=deleted):
                    drain(messages, deleted)
                    return all(
                        deleted.get(topic, (None,))[0] == b""
                        for topic in (config_topic, state_topic)
                    )

                await wait_for(cleanup_received)
                # A fresh subscriber checks retained broker contents, rather than
                # merely observing that this process attempted deletion messages.
                check, retained, check_ready, check_subscribed = peer("ha", topics)
                await wait_for(
                    lambda check_ready=check_ready, check_subscribed=check_subscribed: (
                        check_ready.is_set() and check_subscribed.is_set()
                    )
                )
                actual = {}

                def active_and_offline_received(retained=retained, actual=actual):
                    drain(retained, actual)
                    return (
                        f"homeassistant/climate/hearth_{OTHER}/config" in actual
                        and f"hearth/{OTHER}/state" in actual
                        and actual.get(f"hearth/{SERIAL}/availability", (None,))[0] == b"offline"
                    )

                await wait_for(active_and_offline_received)
                await asyncio.sleep(0.3)
                drain(retained, actual)
                assert config_topic not in actual and state_topic not in actual
                assert (
                    json.loads(actual[f"homeassistant/climate/hearth_{OTHER}/config"][0])[
                        "unique_id"
                    ]
                    == f"hearth_{OTHER}"
                )
                observer.publish(f"hearth/{SERIAL}/command/mode", "heat", qos=1)
                await asyncio.sleep(0.2)
                assert not fresh.pending
                assert Registry(old_core.registry.path).revoked_devices() == {SERIAL}
                check.disconnect()
                check.loop_stop()
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                observer.disconnect()
                observer.loop_stop()
    finally:
        for client in peers:
            client.disconnect()
            client.loop_stop()
