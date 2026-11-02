from pathlib import Path

import pytest

from installer import workflow


@pytest.fixture
def flow(tmp_path, monkeypatch):
    root = tmp_path / "kit"
    root.mkdir()
    session = tmp_path / "session"
    calls = []
    monkeypatch.setattr(workflow, "checked", lambda *a, **k: (root, session, {}))
    monkeypatch.setattr(workflow, "identity", lambda: "ram")
    monkeypatch.setattr(workflow.core, "checked_pair", lambda *a: ({}, object()))
    monkeypatch.setattr(workflow.cleanup, "checked_pair", lambda *a: ({}, object()))
    for name in (
        "completed",
        "acquisition_install",
        "commissioning_to_cleanup",
        "cleanup_restore_to_commissioning",
    ):
        monkeypatch.setattr(workflow.chain, name, lambda *a: None)

    def runner(profile, recovery, output, **kwargs):
        calls.append((profile.name, output.name, kwargs))
        return {"complete": True, "safe_to_restart": True, "encoding_verified": True}

    return root, session, calls, runner


def test_install_orders_disjoint_phases_with_verified_ram_handoffs(flow):
    root, session, calls, runner = flow
    assert workflow.install(root, Path("/unused"), runner=runner)["complete"]
    assert [c[0] for c in calls] == ["commissioning-install", "cleanup-install"]
    assert calls[0][2]["entry"] == {"handoff_from_acquisition": session / "acquisition"}
    assert calls[1][2]["entry"] == {"handoff_from_commissioning": root / "install-commissioning"}
    assert [c[2]["restart_after"] for c in calls] == [False, True]
    assert (root / "commissioning-outcome.json").exists()
    assert (root / "cleanup-outcome.json").exists()


@pytest.mark.parametrize("field", ("complete", "safe_to_restart", "encoding_verified"))
@pytest.mark.parametrize("value", (False, 1, None))
def test_install_never_advances_on_incomplete_or_nonboolean_evidence(flow, field, value):
    root, _, calls, runner = flow

    def failed(*a, **kw):
        return {**runner(*a, **kw), field: value}

    assert not workflow.install(root, "/unused", runner=failed)["complete"]
    assert len(calls) == 1


def test_cancelled_unarmed_phase_does_not_consume_kit(flow):
    root, _, _, _ = flow
    result = workflow.install(root, "/unused", runner=lambda *a, **k: {"cancelled": True})
    assert not result["complete"]
    assert not (root / "commissioning-outcome.json").exists()


@pytest.mark.parametrize("operation", (workflow.install, workflow.restore))
def test_used_second_restore_is_refused_before_any_first_phase(flow, operation):
    root, _, calls, runner = flow
    (root / "restore-commissioning").mkdir()
    with pytest.raises(ValueError, match="one-use"):
        operation(root, "/unused", runner=runner)
    assert not calls


def test_native_identity_failure_precedes_any_loader(flow, monkeypatch):
    root, _, calls, runner = flow
    monkeypatch.setattr(workflow, "identity", lambda: "native")

    def mismatch(*a):
        raise ValueError("different unit")

    monkeypatch.setattr(workflow, "inspect_native", mismatch)
    with pytest.raises(ValueError, match="different unit"):
        workflow.install(root, "/unused", runner=runner)
    assert not calls


def test_explicit_continue_requires_completed_core_evidence(flow, monkeypatch):
    root, _, calls, runner = flow

    def incomplete(*a):
        raise ValueError("missing completion")

    monkeypatch.setattr(workflow.chain, "completed", incomplete)
    with pytest.raises(ValueError, match="missing completion"):
        workflow.install(root, "/unused", runner=runner, continue_cleanup=True)
    assert not calls


def test_explicit_continue_runs_only_cleanup(flow):
    root, _, calls, runner = flow
    assert workflow.install(root, "/unused", runner=runner, continue_cleanup=True)["complete"]
    assert [c[0] for c in calls] == ["cleanup-install"]


def test_restore_reverses_order_and_links_successful_ram_completion(flow):
    root, _, calls, runner = flow
    result = workflow.restore(root, "/unused", runner=runner)
    assert result["restored_phases"] == ["cleanup", "commissioning"]
    assert calls[0][2]["entry"] == {"recover_from": root / "install-cleanup"}
    assert calls[1][2]["entry"] == {"handoff_from_cleanup_restore": root / "restore-cleanup"}
    assert all(c[2]["restore"] for c in calls)
    assert [c[2]["restart_after"] for c in calls] == [False, True]


@pytest.mark.parametrize("phase", ("cleanup", "commissioning"))
def test_explicit_restore_scope_runs_only_selected_phase(flow, phase):
    root, _, calls, runner = flow
    result = workflow.restore(root, "/unused", runner=runner, phase=phase)
    assert result["restored_phases"] == [phase]
    assert [c[0] for c in calls] == [phase + "-restore"]
    assert calls[0][2]["restart_after"]


def test_restore_stops_after_first_refusal(flow):
    root, _, calls, runner = flow

    def failed(*a, **kw):
        return {**runner(*a, **kw), "complete": False}

    assert not workflow.restore(root, "/unused", runner=failed)["complete"]
    assert len(calls) == 1


def test_review_only_kit_refuses_before_usb(monkeypatch):
    monkeypatch.setattr(workflow, "private_path", Path)
    monkeypatch.setattr(workflow.kit, "check", lambda *a, **k: {"review_only": True})

    def forbidden():
        pytest.fail("must not inspect USB")

    monkeypatch.setattr(workflow, "identity", forbidden)
    with pytest.raises(ValueError, match="review-only"):
        workflow.install("/unused", "/unused")
