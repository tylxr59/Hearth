import hashlib
import io
import json
import zipfile

import pytest

from firmware.file_writer.protocol import Binding
from firmware.file_writer.run import encode, save
from installer import bundle as bundle_module
from installer import kit, replacements
from installer.capacity import root_reserve
from tests import test_installer_replacements as stock_module
from tests.conftest import SERIAL
from tests.test_native_settings import TOKEN

stock_inputs = stock_module.stock


@pytest.fixture
def checked_kit(stock_inputs, monkeypatch):
    session, build, output, _ = stock_inputs
    output.mkdir(mode=0o700)
    replacements.prepare(session, build, output / "replacements")
    core_plan = json.loads((output / "replacements/commissioning-pin.json").read_bytes())["plan"]
    cleanup_plan = json.loads((output / "replacements/cleanup-pin.json").read_bytes())["plan"]
    record = {
        "format": kit.FORMAT,
        "session": str(session),
        "bundle_sha256": hashlib.sha256((session / "commissioning.zip").read_bytes()).hexdigest(),
        "commissioning_plan": core_plan,
        "cleanup_plan": cleanup_plan,
        "restore_order": ["cleanup", "commissioning"],
        "review_only": False,
    }
    save(output, "kit.json", encode(record))
    core = {
        "capsule": str(output / "replacements/commissioning"),
        "base": str(session / "acquisition"),
    }
    cleanup = {
        "plan_path": str(output / "replacements/cleanup"),
        "backup": str(session / "acquisition/network-backup"),
        "libraries": str(session / "acquisition"),
        "targets": 3,
    }
    monkeypatch.setattr(
        kit.core_run,
        "checked_pair",
        lambda *_: (core, Binding(bytes.fromhex(core_plan), b"r" * 32, 1)),
    )
    monkeypatch.setattr(
        kit.cleanup_run,
        "checked_pair",
        lambda profile, *_: (
            (
                {
                    **cleanup,
                    "preflight_only": True,
                    "capacity_reserve": root_reserve(
                        output / "replacements/commissioning",
                        output / "replacements/commissioning-pin.json",
                    ),
                }
                if profile.name == "capacity-preflight"
                else cleanup
            ),
            Binding(bytes.fromhex(cleanup_plan), b"r" * 32, 1),
        ),
    )
    return session, output, core, cleanup, record


def test_kit_checks_both_checked_pairs_against_intake_and_reconstructed_replacements(checked_kit):
    _, output, _, _, _ = checked_kit
    result = kit.check(output)
    assert result["commissioning_targets"] == 9 and result["cleanup_targets"] == 3
    assert not result["review_only"] and not result["device_executed"]
    assert result["restore_order"] == ["cleanup", "commissioning"]


@pytest.mark.parametrize(
    "fault",
    ("cleanup_count", "core_origin", "cleanup_origin", "bundle", "order", "extra", "shim", "ca"),
)
def test_kit_refuses_mixed_phases_changed_replacements_or_wrong_bundle(checked_kit, fault):
    session, output, core, cleanup, record = checked_kit
    if fault == "cleanup_count":
        cleanup["targets"] = 4
    elif fault == "core_origin":
        core["base"] = str(session / "other-acquisition")
    elif fault == "cleanup_origin":
        cleanup["backup"] = str(session / "other-backup")
    elif fault == "bundle":
        record["bundle_sha256"] = "0" * 64
    elif fault == "order":
        record["restore_order"].reverse()
    elif fault == "extra":
        record["arbitrary_action"] = "refused"
    elif fault == "shim":
        (output / "replacements/commissioning/4.replacement").write_bytes(b"different")
    else:
        (output / "replacements/commissioning/1.replacement").write_bytes(b"different")
    (output / "kit.json").write_bytes(encode(record))
    with pytest.raises(ValueError):
        kit.check(output)


def test_review_only_build_is_visible_and_never_claimed_a_device_test(checked_kit):
    _, output, _, _, record = checked_kit
    record["review_only"] = True
    (output / "kit.json").write_bytes(encode(record))
    assert kit.check(output)["review_only"] is True
    assert kit.check(output)["installation_checked"] is False
    assert kit.check(output, for_restore=True)["installation_checked"] is False


def test_expired_ha_leaf_metadata_blocks_install_but_not_original_restoration(monkeypatch):
    monkeypatch.setattr(bundle_module.ssl, "create_default_context", lambda **kw: object())
    data = {
        "format": bundle_module.FORMAT,
        "origin": "https://10.0.0.12:8443",
        "serial": SERIAL,
        "credential": TOKEN,
        "supported_model": "Display-2.6",
        "supported_version": "5.9.4-5",
        "supported_partition": "primary",
        "certificate_expires": "2000-01-01T00:00:00+00:00",
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("commissioning.json", json.dumps(data))
        archive.writestr("ca.pem", b"public CA fixture")
        archive.writestr("ca.crl", b"-----BEGIN X509 CRL-----\nfixture\n-----END X509 CRL-----\n")
    with pytest.raises(ValueError):
        bundle_module.read_bundle(output.getvalue())
    assert bundle_module.read_bundle(output.getvalue(), for_restore=True)[0] == data
