import io
import plistlib
import threading
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.validation import Invalid
from installer.bundle import device_info, read_bundle
from installer.cli import execute
from tests.conftest import OTHER, SERIAL


def info(**changes):
    return plistlib.dumps(
        {
            "Display": {
                "Model": "Display-2.6",
                "SoftwareVersion": "5.9.4-5",
                "ActivePartition": "primary",
                "SerialNumber": SERIAL,
                **changes,
            }
        },
        fmt=plistlib.FMT_XML,
    )


def test_identity_refuses_other_device_version_and_partition():
    assert device_info(info())["model"] == "Display-2.6"
    for changes in (
        {"SoftwareVersion": "other"},
        {"Model": "Display-3.4"},
        {"ActivePartition": "secondary"},
    ):
        with pytest.raises(Invalid):
            device_info(info(**changes))
    with pytest.raises(Invalid):
        device_info(
            info(),
            {"serial": OTHER},
        )


def test_bundle_rejects_traversal_duplicate_and_oversized_entries():
    for names in (
        ["../commissioning.json", "ca.pem", "ca.crl"],
        ["commissioning.json", "ca.pem", "ca.pem"],
        ["commissioning.json", "ca.pem", "ca.crl"],
    ):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            for name in names:
                archive.writestr(name, b"x" * 32769)
        with pytest.raises(Invalid):
            read_bundle(data.getvalue())


def test_installer_cancellation_never_starts_engine(tmp_path, monkeypatch):
    from installer import cli

    monkeypatch.setattr(cli, "private_path", lambda p: Path(p))
    engine = SimpleNamespace(
        checked_pair=lambda *a: ({}, SimpleNamespace(action=1)),
        run=lambda *a, **kw: pytest.fail("device opened"),
    )
    assert (
        execute(
            tmp_path / "p", tmp_path / "r", tmp_path / "out", ask=lambda _: "no", engine=engine
        )["device_executed"]
        is False
    )


@pytest.mark.parametrize("answer,committed", [("INSTALL", True), ("", False), ("install", False)])
def test_installer_separate_decision_only_after_preflight(tmp_path, monkeypatch, answer, committed):
    from installer import cli

    monkeypatch.setattr(cli, "private_path", lambda p: Path(p))
    output = tmp_path / "out"
    decisions = []
    event = threading.Event()

    def run(*args, **kwargs):
        output.mkdir()
        (output / "preflight.json").write_text("{}")
        assert event.wait(3)
        return {"complete": committed, "safe_to_restart": True}

    def decide(path, *, commit, expected_action):
        assert (output / "preflight.json").exists() and expected_action == 1
        decisions.append(commit)
        event.set()

    answers = iter(["y", answer])
    engine = SimpleNamespace(
        checked_pair=lambda *a: ({}, SimpleNamespace(action=1)), run=run, decide=decide
    )
    result = execute(
        tmp_path / "p", tmp_path / "r", output, ask=lambda _: next(answers), engine=engine
    )
    assert decisions == [committed] and result["safe_to_restart"]


def test_installer_uncertain_result_never_tells_user_to_restart(tmp_path, monkeypatch):
    from installer import cli

    monkeypatch.setattr(cli, "private_path", lambda p: Path(p))

    def run(*args, **kwargs):
        raise OSError("private data must not be printed")

    engine = SimpleNamespace(checked_pair=lambda *a: ({}, SimpleNamespace(action=1)), run=run)
    result = execute(
        tmp_path / "p", tmp_path / "r", tmp_path / "out", ask=lambda _: "y", engine=engine
    )
    assert result["safe_to_restart"] is False and result["error_type"] == "OSError"


def test_kit_checks_actual_config_not_url_hidden_in_comment(tmp_path, monkeypatch):
    from installer import cli

    origin = "https://127.0.0.1:18443"
    token = "a" * 64
    bundle = {"origin": origin, "serial": SERIAL, "credential": token, "_ca": b"ca", "_crl": b"crl"}
    settings = f'<settings><s key="assigned_cred_id" value="{SERIAL}"/><s key="assigned_cred_secret" value="{token}"/></settings>'.encode()
    valid = f'<config><cloud><a key="cloudregisterurl" value="{origin}/nest/entry"/></cloud><a key="uploadlogs" value="0"/></config>'.encode()
    values = {
        "7.replacement": settings,
        "1.replacement": b"ca",
        "2.replacement": b"crl",
        "8.replacement": valid,
    }
    monkeypatch.setattr(
        cli.writer,
        "checked_pair",
        lambda *a: ({"capsule": str(tmp_path)}, SimpleNamespace(action=1)),
    )
    monkeypatch.setattr(cli, "private_read", lambda p, n: values[p.name])
    cli.supported_kit(tmp_path, tmp_path, bundle)
    values["8.replacement"] = (
        valid.replace(origin.encode(), b"https://127.0.0.2:18443") + f"<!-- {origin} -->".encode()
    )
    with pytest.raises(Invalid):
        cli.supported_kit(tmp_path, tmp_path, bundle)
    values["8.replacement"] = valid.replace(b'value="0"', b'value="1"')
    with pytest.raises(Invalid):
        cli.supported_kit(tmp_path, tmp_path, bundle)
