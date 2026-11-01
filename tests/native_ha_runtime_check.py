"""Run only in the pinned real HA Core container, with synthetic private fixtures.

This is not a mock HA module test. No device, physical network or MQTT is used.
"""

import asyncio
import base64
import ipaddress
import json
import shutil
import ssl
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aiohttp import ClientConnectorError, ClientSession
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

IDENT, TOKEN, ADMIN = "HEARTHLAB0001", "a" * 64, "b" * 64


def fixture(root):
    import hashlib

    profile = root / ".storage/hearth"
    profile.mkdir(mode=0o700, parents=True)
    now = datetime.now(UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic Hearth Lab CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=7))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True
        )
        .sign(ca_key, hashes.SHA256())
    )
    server = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic Hearth Lab")]))
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.KeyUsage(True, False, True, False, False, False, False, False, False),
            critical=True,
        )
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address(x)) for x in ("192.168.50.2", "127.0.0.1")]
            ),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    blobs = {
        "profile.json": json.dumps(
            {"format": "hearth-native-ha-profile-v1", "origin": "https://192.168.50.2:8443"}
        ).encode(),
        "registry.json": json.dumps(
            {
                "admin": hashlib.sha256(ADMIN.encode()).hexdigest(),
                "devices": {
                    IDENT: {
                        "hash": hashlib.sha256(TOKEN.encode()).hexdigest(),
                        "capabilities": {"modes": ["off", "heat", "cool"], "fan": False},
                    }
                },
            }
        ).encode(),
        "ca.pem": ca.public_bytes(serialization.Encoding.PEM),
        "server.pem": server.public_bytes(serialization.Encoding.PEM),
        "server.key": key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    }
    for name, data in blobs.items():
        path = profile / name
        path.write_bytes(data)
        path.chmod(0o600)
    return profile


async def check(root, profile):
    from homeassistant.core import HomeAssistant
    from homeassistant.setup import async_setup_component

    from homeassistant import bootstrap, loader

    hass = HomeAssistant(str(root))
    try:
        loader.async_setup(hass)
        assert (
            await bootstrap.async_from_config_dict(
                {"homeassistant": {"unit_system": "metric", "time_zone": "UTC"}}, hass
            )
            is hass
        )
        assert await async_setup_component(hass, "hearth", {})
        await hass.async_start()
        form = await hass.config_entries.flow.async_init("hearth", context={"source": "user"})
        assert form["type"] == "form"
        result = await hass.config_entries.flow.async_configure(form["flow_id"], {})
        assert result["type"] == "create_entry"
        await hass.async_block_till_done()
        entry = result["result"]
        assert entry.data == {} and entry.runtime_data.core.command_delivery_enabled is False
        from homeassistant.helpers import entity_registry as er

        owned_entity_ids = {
            row.entity_id
            for row in er.async_get(hass).entities.values()
            if row.config_entry_id == entry.entry_id and row.platform == "hearth"
        }
        assert len(owned_entity_ids) == 3

        def sensor_states():
            return [hass.states.get(entity_id) for entity_id in owned_entity_ids]

        from custom_components.hearth.profile import PROFILE_ERRORS, load_profile

        async def refused():
            try:
                await hass.async_add_executor_job(load_profile, profile)
            except PROFILE_ERRORS:
                return
            raise AssertionError("unsafe commissioning profile accepted")

        original_profile = (profile / "profile.json").read_bytes()
        wrong_address = json.loads(original_profile)
        wrong_address["origin"] = "https://192.168.50.3:8443"
        (profile / "profile.json").write_text(json.dumps(wrong_address))
        await refused()
        (profile / "profile.json").write_bytes(original_profile)
        (profile / "server.key").chmod(0o644)
        await refused()
        (profile / "server.key").chmod(0o600)
        original_ca = (profile / "ca.pem").read_bytes()
        (profile / "ca.pem").write_bytes((profile / "server.pem").read_bytes())
        await refused()
        (profile / "ca.pem").write_bytes(original_ca)
        original_registry = (profile / "registry.json").read_bytes()
        empty_registry = json.loads(original_registry)
        empty_registry["devices"] = {}
        (profile / "registry.json").write_text(json.dumps(empty_registry))
        await refused()
        (profile / "registry.json").write_bytes(original_registry)
        states = sensor_states()
        assert len(states) == 3 and all(s.state == "unavailable" for s in states), {
            "entry_state": str(entry.state),
            "sensor_states": [(s.entity_id, s.state) for s in states],
        }
        context = ssl.create_default_context(cafile=str(profile / "ca.pem"))
        headers = {
            "Authorization": "Basic " + base64.b64encode(f"{IDENT}:{TOKEN}".encode()).decode()
        }
        async with ClientSession() as client:
            base = "https://127.0.0.1:8443"
            probe_url = "http://127.0.0.1:8123/api/h/204"
            async with client.get(probe_url) as response:
                assert response.status == 204 and await response.read() == b""
            async with client.get(probe_url + "?unexpected=value") as response:
                assert response.status == 400 and await response.read() == b""
            async with client.get(probe_url, data=b"unexpected") as response:
                assert response.status == 400 and await response.read() == b""
            async with client.post(probe_url) as response:
                assert response.status >= 400
            async with client.post(base + "/nest/entry", ssl=context) as response:
                assert response.status == 401
            async with client.post(base + "/nest/entry", headers=headers, ssl=context) as response:
                assert response.status == 200
                assert (await response.json())[
                    "transport_url"
                ] == "https://192.168.50.2:8443/nest/transport"
            body = {
                "objects": [
                    {
                        "object_key": "device." + IDENT,
                        "value": {"current_temperature": 0, "current_humidity": 48},
                    },
                    {"object_key": "shared." + IDENT, "value": {"target_temperature": 21}},
                ]
            }

            async def report():
                async with client.post(
                    base + "/nest/transport/put", headers=headers, json=body, ssl=context
                ) as response:
                    assert response.status == 200
                await hass.async_block_till_done()

            await report()
            states = sensor_states()
            assert len(states) == 3 and sorted(float(s.state) for s in states) == [0, 21, 48]
            entry.runtime_data.core.seen[IDENT] = entry.runtime_data.core.clock() - 91
            entry.runtime_data.changed(IDENT)
            await hass.async_block_till_done()
            assert all(s.state == "unavailable" for s in sensor_states())
            await report()
            async with client.get(
                base + "/v1/device/commands", headers=headers, ssl=context
            ) as response:
                assert response.status == 409
            duplicate = await hass.config_entries.flow.async_init(
                "hearth", context={"source": "user"}
            )
            assert duplicate["type"] == "abort" and duplicate["reason"] == "already_configured"
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()
            async with client.get(probe_url) as response:
                assert response.status == 503 and await response.read() == b""
            try:
                await client.get(base + "/nest/entry", ssl=context)
            except ClientConnectorError:
                pass
            else:
                raise AssertionError("listener survived config entry unload")
        print(
            json.dumps(
                {
                    "real_ha_core": "2026.10.4",
                    "config_flow": True,
                    "tls_auth": True,
                    "direct_sensor_updates": 3,
                    "zero_preserved": True,
                    "availability_expiry": True,
                    "commands_disabled": True,
                    "unload_closes_listener": True,
                    "mqtt_used": False,
                    "profile_refusal_cases": 4,
                    "local_probe_no_data_or_actions": True,
                }
            )
        )
    finally:
        await hass.async_stop()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="hearth-real-ha-") as directory:
        root = Path(directory)
        shutil.copytree("/package/custom_components", root / "custom_components")
        profile = fixture(root)
        asyncio.run(check(root, profile))
