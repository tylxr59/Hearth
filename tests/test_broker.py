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
from tests.test_security import auth

IMAGE = "eclipse-mosquitto:2.0.22@sha256:09b62ff32c2e7b64d4b431b9a89236073289b68db273de2b089edeb9b0d92b5c"
pytestmark = pytest.mark.skipif(
    os.environ.get("HEARTH_BROKER_TEST") != "1", reason="opt-in Docker broker"
)


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


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
        "docker",
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
        "docker",
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
            "docker",
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
        port = int(run("docker", "port", name, "8883/tcp").split(":")[-1])
        time.sleep(0.5)
        yield root, port, password
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)
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
