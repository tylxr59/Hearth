"""Fixed cleanup3 excludes commissioning paths and cannot replay a four-file scope."""

import hashlib
import json
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from firmware.file_writer import protocol
from firmware.network_writer.compile import compile_helpers
from firmware.network_writer.session import NetworkSession
from provisioning import network_backup, network_plan
from tests.test_file_writer_protocol import BINDING
from tests.test_file_writer_protocol import result as result_frame
from tests.test_network_stream import plan_snapshot
from tests.test_network_writer_session import evidence, info


@pytest.fixture
def plan(tmp_path, monkeypatch):
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    tmp_path.chmod(0o700)
    snapshot = plan_snapshot()
    # This is deliberately not an endpoint which the registration patch accepts.
    # Cleanup cannot inspect/modify it; commissioning owns the full client file.
    snapshot = replace(
        snapshot,
        records=snapshot.records[:3]
        + (replace(snapshot.records[3], data=b"untouched arbitrary stock client configuration"),),
    )
    backup, destination = tmp_path / "backup", tmp_path / "plan"
    network_backup.preserve(backup, snapshot)
    result = network_plan.prepare(
        destination, snapshot, backup, None, "https://10.0.0.12:8443", target_count=3
    )
    raw = (destination / "plan.json").read_bytes()
    pin = hashlib.sha256(b"hearth-network-cleanup-plan-v1\n" + raw).digest()
    pin_path = tmp_path / "pin.json"
    pin_path.write_text(json.dumps({"format": "hearth-network-reviewed-pin-v1", "plan": pin.hex()}))
    pin_path.chmod(0o600)
    assert result["targets"] == 3
    return snapshot, backup, destination, pin, pin_path


def test_cleanup_plan_has_no_client_config_or_endpoint_length_transition(plan):
    snapshot, backup, destination, pin, _ = plan
    bound = network_plan.check(destination, backup, pin)
    assert bound["target_count"] == 3
    manifest = json.loads((destination / "plan.json").read_bytes())
    assert [row["path"] for row in manifest["files"]] == list(network_backup.TARGETS[:3])
    assert manifest["previous_origin"] is None
    assert not (destination / "3.replacement").exists()
    assert (backup / "3.original").read_bytes() == snapshot.records[3].data
    assert b"hn_plans[3]" in bound["header"] and b"hn_modes[3]" in bound["header"]


def test_cleanup_scope_cannot_be_reinterpreted_as_legacy_four_file_plan(plan):
    _, backup, destination, pin, _ = plan
    manifest = json.loads((destination / "plan.json").read_bytes())
    manifest["format"] = "hearth-network-offline-plan-v1"
    (destination / "plan.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, TypeError)):
        network_plan.check(destination, backup, pin)


@pytest.mark.parametrize("action", (1, 2))
def test_three_file_evidence_requires_exact_scope_and_separate_commit(action):
    saved = {}
    session = NetworkSession(
        protocol.Binding(BINDING.plan, BINDING.receipt, action),
        lambda n, d: saved.setdefault(n, d),
        target_count=3,
    )
    session.event(protocol.SELFTEST, evidence())
    with pytest.raises(ValueError):
        session.event(protocol.PREFLIGHT_INFO, info())
    # Failed evidence is not allowed to be replaced inside the same attempt.
    session = NetworkSession(
        protocol.Binding(BINDING.plan, BINDING.receipt, action), lambda n, d: None, target_count=3
    )
    session.event(protocol.SELFTEST, evidence())
    session.event(protocol.PREFLIGHT_INFO, info(targets=3, originals_verified=3))
    session.event(protocol.READY, b"")
    assert not session.committed
    session.decide(True)
    session.event(
        protocol.RESULT,
        result_frame(action, attempted=7, restored=7 if action == 2 else 0, program=100),
    )
    assert session.result["complete"] == 1


@pytest.mark.parametrize("preflight_only", (False, True))
def test_original_arm_cleanup_helpers_exclude_the_client_path(plan, preflight_only):
    _, backup, destination, _, pin_path = plan
    root = Path(__file__).resolve().parents[1]
    (root / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="cleanup-helper-test-", dir=root / "build"
    ) as directory:
        output = Path(directory) / "helpers"
        compile_helpers(output, destination, backup, pin_path, preflight_only=preflight_only)
        for action in (1, 2):
            data = (output / f"action-{action}").read_bytes()
            assert data[:7] == b"\x7fELF\x01\x01\x01"
            assert (b'"preflight_only"' in data) == preflight_only
            if preflight_only:
                assert all(token not in data for token in (b"HFW_RUN1", b"HFW_RDY1"))
            assert b"etc/nestlabs/client.config" not in data
            assert b"nestlabs/sbin/nlclient" in data and b"etc/connman/main.conf" in data
