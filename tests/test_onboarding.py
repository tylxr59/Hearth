import json
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.onboarding import candidate_origins
from backend.validation import Invalid
from installer import discovery, onboard
from tests.conftest import OTHER, SERIAL
from tests.test_installer import info


def adapter(*addresses, enabled=True, default=False):
    return {"enabled": enabled, "default": default, "ipv4": [{"address": a} for a in addresses]}


def test_addresses_are_local_private_deduplicated_and_preference_is_only_a_hint():
    adapters = [
        adapter("10.0.0.12", "192.168.50.2", default=True),
        adapter("192.168.50.2", "172.20.0.2", enabled=False),
        adapter("8.8.8.8", "127.0.0.1", "169.254.1.2", "0.0.0.0", "224.0.0.1", "bad"),
    ]
    assert candidate_origins(adapters, "http://192.168.50.2:8123") == [
        "https://192.168.50.2:8443",
        "https://10.0.0.12:8443",
        "https://172.20.0.2:8443",
    ]
    assert "https://10.0.0.99:8443" not in candidate_origins(adapters, "http://10.0.0.99:8123")
    assert len(candidate_origins([adapter(*[f"10.0.0.{i}" for i in range(1, 40)])])) == 32


@pytest.mark.parametrize("value", (None, {}, [None, {"ipv4": None}], [adapter("::1")]))
def test_no_usable_network_metadata_leaves_manual_setup_available(value):
    assert candidate_origins(value) == []


def disk(tmp, name, identity=("2464", "0002"), partition=False):
    usb = tmp / "devices" / name
    block = usb / "block" / name
    block.mkdir(parents=True)
    for field, value in zip(("idVendor", "idProduct"), identity, strict=True):
        (usb / field).write_text(value)
    if partition:
        (block / "partition").write_text("1")
    node = tmp / "class" / name
    node.parent.mkdir(exist_ok=True)
    node.symlink_to(block)


def test_usb_identity_is_bound_to_sysfs_and_partitions_other_disks_are_ignored(tmp_path):
    disk(tmp_path, "sdb")
    disk(tmp_path, "sdc", ("1234", "5678"))
    disk(tmp_path, "sdb1", partition=True)
    assert discovery.native_disk(tmp_path / "class", Path("/dev")) == Path("/dev/sdb")
    disk(tmp_path, "sdd")
    with pytest.raises(Invalid, match="one normal-mode Nest"):
        discovery.native_disk(tmp_path / "class")


def form():
    return {
        "handler": "hearth",
        "type": "form",
        "step_id": "user",
        "flow_id": "flow1",
        "data_schema": [
            {
                "name": "origin",
                "selector": {
                    "select": {"options": ["https://10.0.0.12:8443", "https://192.168.50.2:8443"]}
                },
            },
            {"name": "device_id", "type": "string"},
        ],
    }


class Client:
    def __init__(self):
        self.calls = []
        self.initial = form()
        self.result = {"handler": "hearth", "type": "create_entry"}

    def flow(self, path, data):
        self.calls.append((path, data))
        return self.initial if path == onboard.FLOW else self.result

    def request(self, method, path):
        self.calls.append((method, path))

    def bundle(self):
        self.calls.append(("bundle",))
        return b"private synthetic bundle"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    tmp_path.chmod(0o700)
    monkeypatch.setattr(
        onboard,
        "read_bundle",
        lambda _: ({"serial": SERIAL, "origin": "https://192.168.50.2:8443"}, b"ca", b"crl"),
    )
    return tmp_path / "session", Client()


def test_identity_and_chosen_vlan_pass_to_ha_and_bundle_stays_private(setup, capsys):
    session, client = setup
    answers = iter(("2", "y"))
    result = onboard.onboard(
        "http://10.0.0.12:8123",
        "admin-token",
        session,
        info(),
        ask=lambda _: next(answers),
        client=client,
    )
    assert result["ha_configured"] and not result["firmware_written"]
    assert client.calls[1][1] == {"origin": "https://192.168.50.2:8443", "device_id": SERIAL}
    assert (session / "commissioning.zip").read_bytes() == b"private synthetic bundle"
    assert json.loads((session / "identity.json").read_bytes())["serial"] == SERIAL
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in session.iterdir())
    assert SERIAL not in capsys.readouterr().out
    assert not any(b"admin-token" in p.read_bytes() for p in session.iterdir())


def test_cancel_aborts_only_the_new_flow_never_creates_profile(setup):
    session, client = setup
    result = onboard.onboard(
        "http://10.0.0.12:8123",
        "token",
        session,
        info(),
        target="https://192.168.50.2:8443",
        ask=lambda _: "",
        client=client,
    )
    assert result["cancelled"]
    assert client.calls == [
        (onboard.FLOW, {"handler": "hearth"}),
        ("DELETE", onboard.FLOW + "/flow1"),
    ]
    assert not (session / "commissioning.zip").exists()


@pytest.mark.parametrize("fault", ("existing", "unsupported", "nonprivate_parent"))
def test_local_refusals_happen_before_contacting_ha(setup, fault):
    session, client = setup
    raw = info()
    if fault == "existing":
        session.mkdir()
    elif fault == "unsupported":
        raw = info(SoftwareVersion="other")
    else:
        session.parent.chmod(0o755)
    with pytest.raises(Invalid):
        onboard.onboard("http://10.0.0.12:8123", "token", session, raw, client=client)
    assert not client.calls


@pytest.mark.parametrize(
    "fault", ("existing_profile", "already_in_progress", "unsafe_flow_id", "wrong_schema")
)
def test_unexpected_flow_never_posts_identity_or_creates_profile(setup, fault):
    session, client = setup
    if fault == "existing_profile":
        client.initial["data_schema"] = []
    elif fault == "already_in_progress":
        client.initial = {"type": "abort", "reason": "already_in_progress"}
    elif fault == "unsafe_flow_id":
        client.initial["flow_id"] = "../other"
    else:
        client.initial["data_schema"].append({"name": "unreviewed_field"})
    with pytest.raises(Invalid):
        onboard.onboard("http://10.0.0.12:8123", "token", session, info(), client=client)
    # The identity is never posted. A valid dialog this run opened is closed;
    # an abort or unsafe flow ID is never addressed.
    closes = (
        [("DELETE", onboard.FLOW + "/flow1")]
        if fault in ("existing_profile", "wrong_schema")
        else []
    )
    assert client.calls == [(onboard.FLOW, {"handler": "hearth"}), *closes]


@pytest.mark.parametrize("fault", ("serial", "origin", "server_refusal"))
def test_mismatch_or_server_refusal_is_preserved_without_resubmitting(setup, monkeypatch, fault):
    session, client = setup
    if fault == "server_refusal":
        client.result = {"type": "form", "errors": {"base": "profile_not_ready"}}
    else:
        bundle = {
            "serial": OTHER if fault == "serial" else SERIAL,
            "origin": "https://10.0.0.99:8443"
            if fault == "origin"
            else "https://192.168.50.2:8443",
        }
        monkeypatch.setattr(onboard, "read_bundle", lambda _: (bundle, b"ca", b"crl"))
    with pytest.raises(Invalid):
        onboard.onboard(
            "http://10.0.0.12:8123",
            "token",
            session,
            info(),
            target="https://192.168.50.2:8443",
            ask=lambda _: "y",
            client=client,
        )
    assert len([call for call in client.calls if call[0] == onboard.FLOW + "/flow1"]) == 1
    assert (session / "onboarding-result.json").exists()
    assert not (session / "commissioning.zip").exists()


@pytest.mark.parametrize("failure", ("redirect", "oversized", "wrong_handler"))
def test_admin_http_client_refuses_redirects_unbounded_or_foreign_flow(failure):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            calls.append((self.path, self.headers.get("Authorization")))
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(302 if failure == "redirect" else 200)
            if failure == "redirect":
                self.send_header("Location", "/stolen")
            self.end_headers()
            if failure == "oversized":
                self.wfile.write(b"x" * 65537)
            elif failure == "wrong_handler":
                self.wfile.write(b'{"handler":"other","type":"form"}')

        def do_GET(self):
            calls.append((self.path, self.headers.get("Authorization")))
            self.send_response(200)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        client = onboard.HAClient(f"http://127.0.0.1:{server.server_port}", "temporary-admin")
        with pytest.raises((Invalid, urllib.error.HTTPError)):
            client.flow(onboard.FLOW, {"handler": "hearth"})
        assert calls == [(onboard.FLOW, "Bearer temporary-admin")]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_only_read_only_bundle_fetch_retries_transient_startup(monkeypatch):
    monkeypatch.setattr(onboard.time, "sleep", lambda _: None)
    client = onboard.HAClient("http://127.0.0.1:8123", "temporary-admin")
    methods = []

    def request(method, path, data=None):
        methods.append(method)
        if len(methods) < 3:
            raise urllib.error.HTTPError("http://127.0.0.1:8123", 503, "starting", {}, None)
        return b"bounded synthetic bundle"

    monkeypatch.setattr(client, "request", request)
    assert client.bundle() == b"bounded synthetic bundle"
    assert methods == ["GET"] * 3


def test_explicit_sudo_flag_wraps_only_the_fixed_readonly_mtype_command(monkeypatch):
    from installer import cli

    monkeypatch.setattr(Path, "is_block_device", lambda _: True)
    monkeypatch.setattr(Path, "is_symlink", lambda _: False)
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=info())

    monkeypatch.setattr(cli.subprocess, "run", run)
    assert cli.inspect_disk("/dev/sdb", sudo_read=True) == info()
    assert calls[0][0] == ["sudo", "--", "mtype", "-i", "/dev/sdb", "::/Technical Info.plist"]
    assert calls[0][1]["capture_output"] and calls[0][1]["check"]
    cli.inspect_disk("/dev/sdb")
    assert calls[1][0][0] == "mtype"
    with pytest.raises(Invalid):
        cli.inspect_disk("/dev/../private", sudo_read=True)
    assert len(calls) == 2


@pytest.mark.parametrize("fault", ("leftover_profile", "interrupted", "bad_address"))
def test_refusal_after_ha_opens_a_dialog_always_closes_it(setup, fault):
    session, client = setup
    if fault == "leftover_profile":
        client.initial = form() | {"data_schema": []}
        ask, expected = (lambda _: pytest.fail("must refuse before asking")), Invalid
    elif fault == "interrupted":

        def ask(_):
            raise KeyboardInterrupt

        expected = KeyboardInterrupt
    else:
        ask, expected = (lambda _: "http://public.example"), Invalid
    with pytest.raises(expected) as caught:
        onboard.onboard("http://10.0.0.12:8123", "t", session, info(), ask=ask, client=client)
    if fault == "leftover_profile":
        assert "config/.storage/hearth" in str(caught.value)
    assert client.calls[-1] == ("DELETE", onboard.FLOW + "/flow1")
    assert not (session / "commissioning.zip").exists()


@pytest.mark.parametrize(
    ("reason", "message"),
    (("already_in_progress", "restart Home Assistant"), ("already_configured", "Remove it")),
)
def test_ha_aborts_get_plain_guidance_without_a_flow_to_close(setup, reason, message):
    session, client = setup
    client.initial = {"handler": "hearth", "type": "abort", "reason": reason, "flow_id": "x"}
    with pytest.raises(Invalid, match=message):
        onboard.onboard(
            "http://10.0.0.12:8123", "t", session, info(), ask=lambda _: "", client=client
        )
    assert client.calls == [(onboard.FLOW, {"handler": "hearth"})]
