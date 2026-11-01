import ast
import hashlib
import importlib
import importlib.util
import json
import sys

from aiohttp.test_utils import TestClient, TestServer

from tools.package_native_ha import package


def test_native_ha_package_reproduces_and_excludes_mqtt_and_private_data(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    first, second = package(one), package(two)
    assert (one / "source-manifest.json").read_bytes() == (
        two / "source-manifest.json"
    ).read_bytes()
    for path in first.rglob("*"):
        if path.is_file():
            assert path.read_bytes() == (second / path.relative_to(first)).read_bytes()
    manifest = json.loads((one / "source-manifest.json").read_bytes())
    assert set(manifest["files"]) == {
        path.relative_to(one).as_posix() for path in first.rglob("*") if path.is_file()
    }
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((one / name).read_bytes()).hexdigest() == expected
    for path in (first / "_backend").glob("*.py"):
        assert not any(
            isinstance(n, ast.ImportFrom)
            and n.module
            and (n.module == "backend" or n.module.startswith("backend."))
            for n in ast.walk(ast.parse(path.read_text()))
        )
    assert not list(first.rglob("mqtt.py"))
    assert not list(first.rglob("*.pem")) and not list(first.rglob("*.key"))
    assert json.loads((first / "manifest.json").read_bytes())["requirements"] == []
    assert "paho" not in (first / "_backend/api.py").read_text()
    assert "def main(" not in (first / "_backend/api.py").read_text()
    assert (first / "translations/en.json").read_bytes() == (first / "strings.json").read_bytes()


async def test_packaged_transport_preserves_auth_validation_and_command_disabling(tmp_path):
    component = package(tmp_path / "package")
    name = "hearth_native_packaged_test_backend"
    spec = importlib.util.spec_from_file_location(
        name,
        component / "_backend/__init__.py",
        submodule_search_locations=[str(component / "_backend")],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        api = importlib.import_module(name + ".api")
        registry_module = importlib.import_module(name + ".registry")
        core_module = importlib.import_module(name + ".core")
        registry = registry_module.Registry.initialize(
            tmp_path / "registry.json", tmp_path / "admin.json"
        )
        ident, token = "HEARTHLAB0001", "a" * 64
        registry.register(ident, token, {"modes": ["off", "heat", "cool"], "fan": False})
        core = core_module.Core(registry)
        import base64

        headers = {
            "Authorization": "Basic " + base64.b64encode(f"{ident}:{token}".encode()).decode()
        }
        async with TestClient(TestServer(api.create_app(core, native_telemetry=True))) as client:
            assert (await client.post("/nest/entry")).status == 401
            assert (await client.post("/nest/entry", headers=headers)).status == 200
            response = await client.post(
                "/nest/transport/put",
                headers=headers,
                json={
                    "objects": [
                        {"object_key": "device." + ident, "value": {"current_temperature": 0}}
                    ]
                },
            )
            assert response.status == 200 and core.states[ident]["temperature"] == 0
            assert core.command_delivery_enabled is False
            assert (await client.get("/v1/device/commands", headers=headers)).status == 409
            assert (await client.get("/v1/manage/devices", headers=headers)).status == 401
    finally:
        for key in list(sys.modules):
            if key == name or key.startswith(name + "."):
                del sys.modules[key]
