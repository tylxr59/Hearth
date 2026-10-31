import hashlib
import json
import tarfile
from pathlib import Path

import pytest

from backend.registry import Registry
from backend.validation import Invalid
from firmware.prepare import FILES, build
from provisioning.cli import endpoint, prepare, usb_inventory
from tests.conftest import SERIAL


def test_credentials_and_report(tmp_path):
    registry = Registry.initialize(tmp_path / "registry", tmp_path / "admin")
    output = tmp_path / "device"
    report = prepare(registry.path, output, SERIAL, 2, "https://192.168.50.2:8443", ["off", "heat"])
    device = json.loads((output / "device.json").read_text())
    assert len(device["credential"]) == 64
    assert Registry(registry.path).authenticate(SERIAL, device["credential"])
    assert device["credential"] not in json.dumps(report)
    assert not report["flashed"] and not report["services_verified"]
    for path in (registry.path, output / "device.json", tmp_path / "admin"):
        assert path.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        prepare(registry.path, output, SERIAL, 2, "https://192.168.50.2:8443", ["off"])
    assert usb_inventory(tmp_path) == []


@pytest.mark.parametrize(
    "value",
    [
        "http://192.168.1.2:80",
        "https://google.com:443",
        "https://8.8.8.8:443",
        "https://192.168.1.2:443/?secret=x",
        "https://user@192.168.1.2:443",
        "https://192.168.1.2:443/;touch x",
        "https://0.0.0.0:443",
        "https://[::1]:443",
    ],
)
def test_endpoint_rejected(value):
    with pytest.raises(Invalid):
        endpoint(value)


def fixture_root(tmp_path):
    root = tmp_path / "root"
    values = (
        b"#!/bin/sh\n${INITDIR}/nestlabs start\n${INITDIR}/nleapi start\n/bin/dropbear\n",
        (
            b'<config><cloud><a key="cloudregisterurl" value="https://frontdoor.nest.com/entry"/>'
            b'</cloud><a key="uploadlogs" value="1"/></config>'
        ),
        b"root:oldhash:1:0:99999:7:::\n",
        b"include /etc/monit.d/*\n",
    )
    for relative, value in zip(FILES, values, strict=True):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    hashes = {
        relative: hashlib.sha256(value).hexdigest()
        for relative, value in zip(FILES, values, strict=True)
    }
    return root, hashes


def test_inert_reproducible_build(tmp_path):
    root, hashes = fixture_root(tmp_path)
    one, two = tmp_path / "one.tar", tmp_path / "two.tar"
    first = build(root, one, hashes, "https://192.168.50.2:8443")
    assert first == build(root, two, hashes, "https://192.168.50.2:8443")
    with tarfile.open(one) as archive:
        assert set(archive.getnames()) == {"DO-NOT-FLASH.txt", "plan.json", "SHA256SUMS"}
        plan = json.load(archive.extractfile("plan.json"))
        assert any(item["service"] == "dropbear" for item in plan["candidate_rcS_lines_to_disable"])
        assert "nlclient" in plan["preserve"]
    assert b"oldhash" not in one.read_bytes()
    assert b"frontdoor.nest.com" in (root / FILES[1]).read_bytes()
    hashes[FILES[0]] = "0" * 64
    with pytest.raises(Invalid):
        build(root, tmp_path / "bad.tar", hashes, "https://192.168.50.2:8443")


def test_symlink_input_rejected(tmp_path):
    root, hashes = fixture_root(tmp_path)
    path = root / FILES[0]
    path.unlink()
    path.symlink_to(Path("/etc/passwd"))
    with pytest.raises(Invalid):
        build(root, tmp_path / "bad.tar", hashes, "https://192.168.50.2:8443")


def test_offline_hardening_preserves_controls(tmp_path):
    from firmware.harden import stage

    root, hashes = fixture_root(tmp_path)
    output = tmp_path / "overlay"
    result = stage(root, output, hashes, "https://192.168.50.2:8443")
    replacement = output / "replacement-files"
    assert (replacement / "etc/shadow").read_text().startswith("root:!:")
    assert "nestlabs start" in (replacement / FILES[0]).read_text()
    assert "dropbear" not in (replacement / FILES[0]).read_text()
    assert "nleapi" not in (replacement / FILES[0]).read_text()
    assert "https://192.168.50.2:8443/nest/entry" in (replacement / FILES[1]).read_text()
    assert '<a key="uploadlogs" value="0"/>' in (replacement / FILES[1]).read_text()
    assert result["disabled_config_keys"] == ["uploadlogs"]
    assert (replacement / FILES[1]).stat().st_mode & 0o077 == 0
    assert "cgi-bin" in result["remove_before_any_deployment"][-1]
    assert "dropbear" in (root / FILES[0]).read_text()
    repeated = tmp_path / "overlay-again"
    assert stage(root, repeated, hashes, "https://192.168.50.2:8443") == result
    for name in FILES:
        assert (repeated / "replacement-files" / name).read_bytes() == (
            replacement / name
        ).read_bytes()


def test_hardening_refuses_unknown_shell(tmp_path):
    from firmware.harden import stage

    root, hashes = fixture_root(tmp_path)
    path = root / FILES[0]
    path.write_text("/bin/dropbear; /etc/init.d/nestlabs start\n")
    hashes[FILES[0]] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(Invalid):
        stage(root, tmp_path / "overlay", hashes, "https://192.168.50.2:8443")


def test_config_hardening_preserves_unknown_settings_and_comments():
    from firmware.harden import client_config

    original = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
        '<!-- <a key="uploadlogs" value="1"/> -->\n'
        '<cloud><a value="https://old.invalid/entry" key="cloudregisterurl" /></cloud>\n'
        "<a value = '1' key = 'uploadlogs' />\n"
        '<native><a key="schedule" value="preserve &amp; café"/></native>\n</config>'
    )
    result = client_config(original, "https://192.168.50.2:8443")
    assert result == original.replace(
        "https://old.invalid/entry", "https://192.168.50.2:8443/nest/entry"
    ).replace("value = '1'", "value = '0'")
    assert client_config(result, "https://192.168.50.2:8443") == result


@pytest.mark.parametrize(
    "entry",
    [
        "",
        '<!-- <a key="uploadlogs" value="1"/> -->',
        '<a key="uploadlogs" value="1"/><a key="uploadlogs" value="0"/>',
        '<other><a key="uploadlogs" value="1"/></other>',
        '<a key="uploadlogs" value="true"/>',
        '<a key="uploadlogs" value="1" extra="unknown"/>',
        '<a key="uploadlogs" value="1"></a>',
        '<a key="uploadlogs" value="1">',
    ],
)
def test_ambiguous_upload_config_leaves_no_overlay(tmp_path, entry):
    from firmware.harden import stage

    root, hashes = fixture_root(tmp_path)
    config = root / FILES[1]
    config.write_text(
        '<config><cloud><a key="cloudregisterurl" value="https://old.invalid/entry"/>'
        "</cloud>" + entry + "</config>"
    )
    hashes[FILES[1]] = hashlib.sha256(config.read_bytes()).hexdigest()
    output = tmp_path / "overlay"
    with pytest.raises(Invalid):
        stage(root, output, hashes, "https://192.168.50.2:8443")
    assert not output.exists()


@pytest.mark.parametrize(
    "prefix",
    [
        '<!DOCTYPE config [<!ENTITY flag "1">]>',
        '<!DOCTYPE config SYSTEM "file:///etc/passwd">',
    ],
)
def test_config_hardening_rejects_dtds(prefix):
    from firmware.harden import client_config

    config = (
        prefix + '<config><cloud><a key="cloudregisterurl" value="https://old.invalid/"/>'
        '</cloud><a key="uploadlogs" value="1"/></config>'
    )
    with pytest.raises(Invalid, match="DTDs and entities"):
        client_config(config, "https://192.168.50.2:8443")


@pytest.mark.parametrize(
    "cloud",
    [
        '<a key="cloudregisterurl" value="https://old.invalid/"/>',
        (
            '<cloud><a key="cloudregisterurl" value="https://old.invalid/"/>'
            '<a key="cloudregisterurl" value="https://other.invalid/"/></cloud>'
        ),
        '<!-- <cloud><a key="cloudregisterurl" value="https://old.invalid/"/></cloud> -->',
    ],
)
def test_config_hardening_rejects_ambiguous_cloud_endpoint(cloud):
    from firmware.harden import client_config

    with pytest.raises(Invalid):
        client_config(
            "<config>" + cloud + '<a key="uploadlogs" value="1"/></config>',
            "https://192.168.50.2:8443",
        )


def test_config_hardening_bounds_parser_input():
    from firmware.harden import client_config

    for config in (
        "x" * (1024 * 1024 + 1),
        "<config>" * 65,
        '<?xml version="1.0" encoding="ISO-8859-1"?><config/>',
        '<?xml version="1.1"?><config/>',
    ):
        with pytest.raises(Invalid):
            client_config(config, "https://192.168.50.2:8443")
