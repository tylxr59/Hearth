import json
import secrets

import pytest
from aiohttp.test_utils import TestClient, TestServer

from backend.api import create_app
from backend.core import Core
from backend.registry import Registry
from firmware.probe import port as usb_port

SERIAL = "02AA01AB501203EQ"
OTHER = "02AA01AB501203ER"


@pytest.fixture(autouse=True)
def pinned_usb_port(monkeypatch):
    """Fixture sysfs trees use port 1-1; never discover the real host's USB bus."""
    monkeypatch.setattr(usb_port, "_pinned", "1-1")


@pytest.fixture
def rig(tmp_path):
    registry = Registry.initialize(tmp_path / "registry.json", tmp_path / "admin.json")
    token = secrets.token_hex(32)
    registry.register(SERIAL, token, {"modes": ["off", "heat", "cool"], "fan": True})
    admin = json.loads((tmp_path / "admin.json").read_text())["token"]
    now = [100.0]
    core = Core(registry, lambda: now[0])
    return core, token, admin, now


@pytest.fixture
async def client(rig):
    async with TestClient(TestServer(create_app(rig[0], experimental_nest=True))) as client:
        yield client
