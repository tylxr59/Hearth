"""Opt-in smoke test of our built host image, no thermostat access."""

import base64
import json
import os
import secrets
import shutil
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from backend.registry import Registry, private_json
from tests.conftest import SERIAL
from tests.containers import ENGINE, command

pytestmark = pytest.mark.skipif(
    os.environ.get("HEARTH_CONTAINER_TEST") != "1", reason="opt-in built image"
)


def run(*args):
    return subprocess.run(command(args), check=True, capture_output=True, text=True).stdout.strip()


@pytest.mark.parametrize("native", [False, True])
def test_unprivileged_container_tls_api(native):
    root = Path(tempfile.mkdtemp(prefix="hearth-container-"))
    name = "hearth-container-" + secrets.token_hex(6)
    try:
        tls = root / "tls"
        tls.mkdir()
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
            "subjectAltName=IP:127.0.0.1",
            "-keyout",
            str(tls / "server.key"),
            "-out",
            str(tls / "server.pem"),
        )
        registry = Registry.initialize(root / "registry.json", root / "admin.json")
        token = secrets.token_hex(32)
        registry.register(SERIAL, token, {"modes": ["off", "heat"], "fan": False})
        admin = json.loads((root / "admin.json").read_text())["token"]
        private_json(
            root / "mqtt.json",
            {
                "host": "127.0.0.1",
                "port": 1,
                "username": "isolated-test",
                "password": secrets.token_hex(32),
                "ca": "/config/tls/server.pem",
            },
        )
        if native:
            private_json(root / "native-telemetry.json", {"origin": "https://127.0.0.1:8443"})
        # First prove the image defaults to its documented unprivileged identity.
        assert (
            run(
                ENGINE,
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "hearth:dev",
                "python",
                "-c",
                "import os; print(os.getuid())",
            )
            == "10001"
        )
        # Match the private host fixture's uid without changing permissions/ownership.
        run(
            ENGINE,
            "run",
            "--rm",
            "-d",
            "--name",
            name,
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-p",
            "127.0.0.1::8443",
            "-v",
            f"{root}:/config:rw",
            "hearth:dev",
        )
        port = int(run(ENGINE, "port", name, "8443/tcp").split(":")[-1])
        context = ssl.create_default_context(cafile=str(tls / "server.pem"))
        origin = f"https://127.0.0.1:{port}"

        def request(path, credential, data=None):
            req = urllib.request.Request(
                origin + path,
                data=None if data is None else json.dumps(data).encode(),
                headers={"Authorization": credential, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, context=context, timeout=2) as response:
                return json.load(response)

        deadline = time.monotonic() + 15
        while True:
            try:
                state = request("/v1/manage/devices", "Bearer " + admin)
                break
            except (urllib.error.URLError, TimeoutError):
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.1)
        assert not state["devices"][0]["available"]
        basic = "Basic " + base64.b64encode(f"{SERIAL}:{token}".encode()).decode()
        if native:
            entry = request("/nest/entry", basic)
            assert entry == {"transport_url": "https://127.0.0.1:8443/nest/transport"}
            result = request(
                "/nest/transport/v7/put",
                basic,
                {
                    "objects": [
                        {"object_key": f"shared.{SERIAL}", "value": {"current_temperature": 21}}
                    ]
                },
            )
            assert result["objects"][0]["object_revision"] == 1
            assert "value" not in result["objects"][0]
            with pytest.raises(urllib.error.HTTPError) as disabled:
                request(
                    f"/v1/manage/devices/{SERIAL}/commands",
                    "Bearer " + admin,
                    {"operation": "temperature", "value": 22},
                )
            assert disabled.value.code == 409
        else:
            assert request("/v1/device/state", basic, {"temperature": 21}) == {"accepted": True}
            result = request(
                f"/v1/manage/devices/{SERIAL}/commands",
                "Bearer " + admin,
                {"operation": "temperature", "value": 22},
            )
            assert request("/v1/device/commands", basic)["commands"] == [result]
        with pytest.raises(urllib.error.HTTPError) as error:
            request("/v1/manage/devices", "Bearer incorrect")
        assert error.value.code == 401
    finally:
        subprocess.run([ENGINE, "rm", "-f", name], capture_output=True, check=False)
        shutil.rmtree(root)
