"""Saved recovery selection/cancellation never guesses a raw NAND write."""

import pytest

from backend.validation import Invalid
from installer import recovery_wizard, wizard


def test_saved_kit_selection_stays_inside_private_root(tmp_path, monkeypatch):
    from tools import elf_review

    tmp_path.chmod(0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    monkeypatch.setattr(recovery_wizard, "PRIVATE", tmp_path)
    kit = tmp_path / "setup-original/kit"
    kit.mkdir(mode=0o700, parents=True)
    (kit / "kit.json").write_text("{}")
    assert recovery_wizard.select_kit(lambda _: "") == kit
    with pytest.raises(Invalid):
        recovery_wizard.select_kit(lambda _: "999")


def test_restore_menu_has_no_device_action_if_no_saved_bundle(monkeypatch):
    monkeypatch.setattr(wizard, "prerequisites", lambda: None)
    monkeypatch.setattr(
        recovery_wizard, "select_kit", lambda ask: (_ for _ in ()).throw(Invalid("No bundle"))
    )
    monkeypatch.setattr(
        recovery_wizard.workflow, "restore", lambda *a, **kw: pytest.fail("must not open device")
    )
    assert recovery_wizard.run(ask=lambda _: "") == 1


def test_setup_menu_can_enter_recovery_without_starting_onboarding(monkeypatch):
    monkeypatch.setattr(recovery_wizard, "run", lambda **kw: 23)
    assert wizard.run(ask=lambda _: "RESTORE") == 23
