"""Observed native settings are exact third bytes, never an unknown-data bypass."""

import hashlib
import json
from dataclasses import replace

import pytest

from firmware.acquisition import codec, run
from firmware.file_snapshot.run import decode
from firmware.file_writer import restore_settings
from firmware.file_writer.run import encode, save
from installer import replacements
from provisioning import network_backup, network_plan
from tests import test_installer_replacements as stock_module
from tests.test_acquisition import SESSION, group_frame, payload
from tests.test_file_snapshot_profile import frame as snapshot_frame
from tests.test_network_snapshot import frame as network_frame
from tests.test_network_stream import plan_snapshot

stock = stock_module.stock


@pytest.fixture
def admission(stock):
    session, build, output, _ = stock
    replacements.prepare(session, build, output)
    capsule = output / "commissioning"
    pin = output / "commissioning-pin.json"
    network = plan_snapshot()
    network = replace(
        network,
        records=network.records[:3]
        + (replace(network.records[3], data=(capsule / "8.replacement").read_bytes(), mode=0o600),),
    )
    backup, plan, npin = (
        session / "legacy-backup",
        session / "legacy-plan",
        session / "legacy-pin.json",
    )
    network_backup.preserve(backup, network)
    network_plan.prepare(plan, network, backup, "https://10.0.0.12:8443", "https://10.0.0.123:8443")
    value = hashlib.sha256(
        b"hearth-network-offline-plan-v1\n" + (plan / "plan.json").read_bytes()
    ).hexdigest()
    save(session, npin.name, encode({"format": "hearth-network-reviewed-pin-v1", "plan": value}))
    records = list(decode(snapshot_frame(), SESSION))
    manifest = json.loads((capsule / "plan.json").read_bytes())
    for i, old in enumerate(records):
        data = (
            (plan / "3.replacement").read_bytes()
            if i == 8
            else (capsule / f"{i}.replacement").read_bytes()
        )
        if i == 7:
            data += b"\n<!-- separately observed native preference -->\n"
        records[i] = replace(
            old, existed=True, mode=manifest["files"][i]["replacement_mode"], data=data
        )
    installed_net = replace(
        network,
        records=tuple(
            replace(r, data=(plan / f"{i}.replacement").read_bytes())
            for i, r in enumerate(network.records)
        ),
    )
    acquired = session / "observed"
    acquired.mkdir(mode=0o700)
    decoder = codec.Decoder(SESSION, lambda name, data: save(acquired, name, data))
    libraries = [(b"a.so", b"synthetic passive data", 0o100644)]
    apps = [
        (b"nlclient", installed_net.records[0].data, 0o100000 | installed_net.records[0].mode),
        (b"hearth-nlclient", records[5].data, 0o100750),
    ]
    for frame in (
        snapshot_frame(tuple(records)),
        network_frame(installed_net),
        group_frame(0),
        group_frame(1),
        group_frame(2, payload(libraries)),
        group_frame(3, payload(apps)),
        codec.DONE,
    ):
        decoder.feed(frame)
    run.preserve_inputs(acquired, decoder)
    return restore_settings.observed(acquired, capsule, pin, plan, backup, npin), capsule, pin


def test_admission_reconstructs_full_custody_and_restoration_header(admission):
    (record, header), capsule, pin = admission
    assert restore_settings.check(record, capsule, pin) == header
    assert b"hearth_observed_settings" in header
    assert record["format"] == "hearth-exact-settings-stock-return-v1"


@pytest.mark.parametrize(
    "fault", ("capture_sha256", "settings_sha256", "header_sha256", "extra", "capsule")
)
def test_changed_or_mixed_admission_is_refused(admission, fault):
    (record, _), capsule, pin = admission
    record = dict(record)
    record[fault] = "changed"
    with pytest.raises((ValueError, OSError)):
        restore_settings.check(record, capsule, pin)


def test_admission_is_restore_only_and_compiled_header_must_match(admission, tmp_path, monkeypatch):
    from firmware.file_writer import profile

    monkeypatch.setattr(profile, "read_build", lambda path, limit: path.read_bytes())
    (record, header), capsule, pin = admission
    compiled = {"restore_observation": record}
    with pytest.raises(ValueError, match="cannot authorize"):
        restore_settings.check_helpers(compiled, tmp_path, capsule, pin, 1)
    with pytest.raises(ValueError, match="cannot authorize"):
        restore_settings.check_helpers(compiled, tmp_path, capsule, pin, 3)
    save(tmp_path, "restore-settings.h", header)
    assert restore_settings.check_helpers(compiled, tmp_path, capsule, pin, 2) == record
    (tmp_path / "restore-settings.h").write_bytes(header + b"changed")
    with pytest.raises(ValueError):
        restore_settings.check_helpers(compiled, tmp_path, capsule, pin, 2)


@pytest.mark.parametrize(
    "fault", (None, "libraries", "plan_path", "backup", "pin", "action", "missing-admission")
)
def test_legacy_handoff_requires_complete_exact_prior_scope_and_observation(
    admission, monkeypatch, tmp_path, fault
):
    from types import SimpleNamespace

    from firmware.file_writer import chain

    (observation, _), capsule, pin = admission
    record = {
        "restore_observation": observation,
        "capsule": str(capsule),
        "pin": str(pin),
        "base": "preserved-library-source",
    }
    prior = {
        "targets": 4,
        "libraries": record["base"],
        "plan_path": observation["network"],
        "backup": observation["network_backup"],
        "pin": observation["network_pin"],
    }
    if fault in prior:
        prior[fault] = "different"
    if fault == "missing-admission":
        record.pop("restore_observation")
    checks = []

    def completed(previous, engine, action, count):
        checks.append((action, count))
        return prior

    monkeypatch.setattr(chain, "completed", completed)
    monkeypatch.setattr(chain, "ram", lambda _: checks.append("ram"))
    binding = SimpleNamespace(action=1 if fault == "action" else 2)
    if fault is None:
        assert (
            chain.legacy_network_restore_to_stock(record, binding, tmp_path)[
                "native_startup_required"
            ]
            is False
        )
        assert checks == [(2, 4), "ram"]
    else:
        with pytest.raises(ValueError):
            chain.legacy_network_restore_to_stock(record, binding, tmp_path)
        assert "ram" not in checks
