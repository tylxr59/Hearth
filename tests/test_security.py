import base64
import json
import secrets

from aiohttp.test_utils import TestClient, TestServer
from hypothesis import given
from hypothesis import strategies as st

from backend.api import basic, create_app
from backend.registry import Registry
from backend.validation import Invalid, command, loads
from tests.conftest import OTHER, SERIAL


def auth(token, ident=SERIAL):
    value = base64.b64encode(f"nest.{ident}:{token}".encode()).decode()
    return {"Authorization": f"Basic {value}"}


async def test_authentication_and_roles(client, rig):
    core, token, admin, _ = rig
    for path in ("/v1/device/state", "/nest/transport/put"):
        for headers in (
            {},
            auth("wrong"),
            auth(token, OTHER),
            {"X-NL-Device-Serial": SERIAL},
            {"Authorization": "Bearer " + admin},
        ):
            assert (await client.post(path, headers=headers, json={})).status == 401
    assert (await client.get("/v1/manage/devices")).status == 401
    assert (await client.get("/v1/manage/devices", headers=auth(token))).status == 401
    response = await client.get("/v1/manage/devices", headers={"Authorization": "Bearer " + admin})
    assert response.status == 200
    assert token not in await response.text()
    assert (await client.get("/v1/device/commands", headers=auth(token))).status == 200
    core.registry.revoke(SERIAL)
    assert (await client.get("/v1/device/commands", headers=auth(token))).status == 401


async def test_native_bootstrap_claims_cannot_enroll_or_restore_revoked_device(client, rig):
    core, token, _, _ = rig
    before = core.registry.path.read_bytes()
    # Native software may fall back to default credentials after a 401. Neither
    # that fallback nor an assigned-looking username constitutes enrollment.
    for ident in (SERIAL, OTHER):
        for username in (f"d.{ident}.fixture", "d.bootstrap.fixture"):
            response = await client.post(
                "/nest/entry",
                headers={
                    "Authorization": "Basic "
                    + base64.b64encode(f"{username}:{token}".encode()).decode(),
                    "X-nl-device-id": ident,
                },
                data={"reset": "true", "model": "Display-2.6", "request_id": "1"},
            )
            assert response.status == 401
            assert "X-nl-set-client-credentials" not in response.headers
    assert core.registry.path.read_bytes() == before
    core.registry.revoke(SERIAL)
    revoked = core.registry.path.read_bytes()
    for username in (SERIAL, f"nest.{SERIAL}", f"d.{SERIAL}.fixture", "d.bootstrap.fixture"):
        response = await client.post(
            "/nest/entry",
            headers={
                "Authorization": "Basic "
                + base64.b64encode(f"{username}:{token}".encode()).decode()
            },
            data={"reset": "true"},
        )
        assert response.status == 401
    assert core.registry.path.read_bytes() == revoked


async def test_native_credential_header_is_not_a_rotation_request(client, rig, caplog):
    core, token, _, _ = rig
    proposed = secrets.token_hex(32)
    before = core.registry.path.read_bytes()
    response = await client.post(
        "/nest/entry",
        headers={**auth(token), "X-nl-set-client-credentials": f"{SERIAL} {proposed}"},
    )
    assert response.status == 200
    assert "X-nl-set-client-credentials" not in response.headers
    assert proposed not in await response.text()
    assert token not in caplog.text and proposed not in caplog.text
    assert core.registry.path.read_bytes() == before
    assert core.registry.authenticate(SERIAL, token)
    assert not core.registry.authenticate(SERIAL, proposed)


async def test_native_bootstrap_stays_disabled_in_normal_runtime(rig):
    core, token, _, _ = rig
    async with TestClient(TestServer(create_app(core))) as normal:
        response = await normal.post("/nest/entry", headers=auth(token), data={"reset": "true"})
        assert response.status == 404
        assert "X-nl-set-client-credentials" not in response.headers


async def test_nle_regressions(client, rig):
    _, token, admin, _ = rig
    # Neither serial disclosure nor update endpoints exist, even for authenticated users.
    for path in (
        "/cgi-bin/api/settings",
        "/cgi-bin/update",
        "/control/command",
        "/nest/upload",
        "/nest/weather/v1",
    ):
        response = await client.post(path, headers=auth(token), json={"initialize": SERIAL})
        assert response.status == 404
        assert token not in await response.text()
    forged = {"objects": [{"object_key": "device." + OTHER, "value": {"current_temperature": 20}}]}
    assert (
        await client.post("/nest/transport/put", headers=auth(token), json=forged)
    ).status == 400
    headers = {"Authorization": "Bearer " + admin}
    assert (await client.post("/v1/manage/raw", headers=headers, json={})).status == 404
    for value in (True, None, {}, 1000, -273, "25", float("inf")):
        response = await client.post(
            f"/v1/manage/devices/{SERIAL}/commands",
            headers={**headers, "Content-Type": "application/json"},
            data=json.dumps({"operation": "temperature", "value": value}),
        )
        assert response.status == 400
    assert not rig[0].pending


async def test_rotation_registration_and_restart(client, rig):
    core, token, admin, _ = rig
    headers = {"Authorization": "Bearer " + admin}
    data = {"capabilities": {"modes": ["off", "heat"], "fan": False}}
    assert (
        await client.post(f"/v1/manage/devices/{SERIAL}", headers=headers, json=data)
    ).status == 400
    response = await client.put(f"/v1/manage/devices/{SERIAL}", headers=headers, json=data)
    assert response.status == 201
    new = (await response.json())["credential"]
    assert (await client.get("/v1/device/commands", headers=auth(token))).status == 401
    assert (await client.get("/v1/device/commands", headers=auth(new))).status == 200
    restarted = Registry(core.registry.path)
    assert restarted.authenticate(SERIAL, new)
    assert not restarted.authenticate(SERIAL, token)
    assert new not in restarted.path.read_text()
    assert (await client.delete(f"/v1/manage/devices/{SERIAL}", headers=headers)).status == 200
    assert (await client.get("/v1/device/commands", headers=auth(new))).status == 401


async def test_parser_limits(client, rig):
    headers = auth(rig[1])
    for raw in (
        "[]",
        "null",
        '{"temperature":20,"temperature":30}',
        '{"temperature":NaN}',
        '{"mode":{}}',
        '{"firmware":"<script>"}',
        '{"temperature":true}',
    ):
        assert (
            await client.post(
                "/v1/device/state",
                headers={**headers, "Content-Type": "application/json"},
                data=raw,
            )
        ).status == 400
    assert (
        await client.post(
            "/v1/device/state",
            headers={**headers, "Content-Type": "application/json"},
            data=b"x" * 20000,
        )
    ).status == 413


@given(st.binary(max_size=1024))
def test_untrusted_json_never_crashes(raw):
    try:
        loads(raw)
    except Invalid:
        pass


@given(st.text(max_size=1024))
def test_basic_parser_never_crashes(raw):
    try:
        basic(raw)
    except Invalid:
        pass


@given(
    st.one_of(
        st.none(),
        st.booleans(),
        st.floats(allow_nan=True),
        st.text(),
        st.lists(st.integers()),
        st.dictionaries(st.text(), st.integers()),
    )
)
def test_command_schema_never_crashes(value):
    try:
        command({"operation": "temperature", "value": value}, {"modes": ["off"], "fan": False})
    except Invalid:
        pass


def test_unique_role_specific_credentials(rig):
    import pytest

    from tests.conftest import OTHER

    core, token, admin, _ = rig
    caps = {"modes": ["off"], "fan": False}
    with pytest.raises(Invalid):
        core.registry.register(OTHER, token, caps)
    with pytest.raises(Invalid):
        core.registry.register(OTHER, admin, caps)


def test_offline_admin_rotation(tmp_path):
    registry = Registry.initialize(tmp_path / "registry", tmp_path / "old-admin")
    old = json.loads((tmp_path / "old-admin").read_text())["token"]
    registry.rotate_admin(tmp_path / "new-admin")
    new = json.loads((tmp_path / "new-admin").read_text())["token"]
    assert new != old and registry.admin(new) and not registry.admin(old)
    assert Registry(registry.path).admin(new)
    assert (tmp_path / "new-admin").stat().st_mode & 0o077 == 0
