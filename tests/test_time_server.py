"""Literal NTP selection and both private file recipes; no network or device I/O."""

import hashlib
import json

import pytest

from firmware.network_writer.compile import compile_helpers
from provisioning import network_backup, network_plan
from provisioning.native_network import connman_time_config
from provisioning.native_settings import nist_time_config
from provisioning.time_server import DEFAULT, time_server
from tests.test_network_stream import plan_snapshot


@pytest.mark.parametrize(
    "value", ("time.nist.gov", "pool.ntp.org", "ntp.example.test", "10.0.0.8", "NTP.Example.Test")
)
def test_literal_choice_updates_both_sources_without_changing_other_bytes(value):
    expected = value.lower().encode()
    assert time_server(value).encode() == expected
    assert (
        nist_time_config(b"# keep\nserver time.nest.com\n# tail\n", value)
        == b"# keep\nserver " + expected + b" minpoll 6 maxpoll 10\n# tail\n"
    )
    original = b"# keep\n[General]\nFallbackTimeservers=time.nest.com\nPreferFallbackTimeservers=true\n# tail\n"
    assert connman_time_config(original, value) == original.replace(b"time.nest.com", expected)
    assert DEFAULT == "time.nist.gov"


@pytest.mark.parametrize(
    "value",
    (
        "",
        "x\nserver evil",
        "ntp.test:123",
        "a b",
        "a,b",
        "::1",
        "0.0.0.0",
        "127.0.0.1",
        "224.1.1.1",
        "999.1.2.3",
        "-bad.test",
        "bad..test",
        "x" * 64 + ".test",
        "é.test",
        "https://ntp.test",
    ),
)
def test_time_server_refuses_configuration_injection_and_invalid_literals(value):
    with pytest.raises(ValueError):
        time_server(value)


@pytest.fixture
def custom_plan(tmp_path, monkeypatch):
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    tmp_path.chmod(0o700)
    backup, output = tmp_path / "backup", tmp_path / "plan"
    snapshot = plan_snapshot()
    network_backup.preserve(backup, snapshot)
    network_plan.prepare(
        output,
        snapshot,
        backup,
        None,
        "https://10.0.0.12:8443",
        target_count=3,
        ntp_server="ntp.example.test",
    )
    raw = (output / "plan.json").read_bytes()
    pin = hashlib.sha256(b"hearth-network-cleanup-time-plan-v1\n" + raw).digest()
    pinfile = tmp_path / "pin.json"
    pinfile.write_text(json.dumps({"format": "hearth-network-reviewed-pin-v1", "plan": pin.hex()}))
    pinfile.chmod(0o600)
    return output, backup, pin, pinfile


def test_custom_plan_pins_full_text_and_changed_length(custom_plan):
    output, backup, pin, _ = custom_plan
    result = network_plan.check(output, backup, pin)
    assert result["custom_time"] and result["target_count"] == 3
    assert b"hn_plans[2]" in result["header"]
    assert b"HN_CUSTOM_TIME" in result["header"]
    assert b"ntp.example.test" in (output / "2.replacement").read_bytes()
    record = json.loads((output / "plan.json").read_bytes())
    assert record["files"][2]["bytes"] != record["files"][2]["replacement_bytes"]
    record["ntp_server"] = "another.test"
    (output / "plan.json").write_text(json.dumps(record))
    with pytest.raises(ValueError):
        network_plan.check(output, backup, pin)


def test_custom_time_original_arm_helpers_compile_with_scoped_variable_length_adapter(
    custom_plan, tmp_path
):
    output, backup, _, pinfile = custom_plan
    # Compiler output must be below the repository's build directory.
    import tempfile
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="custom-time-", dir=root / "build") as folder:
        destination = Path(folder) / "helpers"
        compile_helpers(destination, output, backup, pinfile)
        for action in (1, 2):
            assert (destination / f"action-{action}").read_bytes()[:4] == b"\x7fELF"
