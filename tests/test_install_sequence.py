"""One-boot ordering, failure containment and original ARM supervisor builds."""

import shutil
import subprocess
from pathlib import Path

import pytest

from firmware.file_writer import protocol
from firmware.install_sequence import run as sequence
from tests import test_installer_workflow as workflow_tests
from tests.test_installer_capacity import successful_capacity

flow = workflow_tests.flow

ROOT = Path(__file__).resolve().parents[1]


def test_gate_keeps_sealed_windows_and_requires_exact_next_binding(tmp_path):
    if not shutil.which("cc"):
        pytest.skip("cc unavailable")
    out = tmp_path / "test"
    subprocess.run(
        [
            "cc",
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            str(ROOT / "tests/install_sequence_harness.c"),
            str(ROOT / "firmware/file_writer/core.c"),
            "-o",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run([str(out)], check=True, capture_output=True)


@pytest.mark.parametrize("component", ("install_sequence", "rom_restart"))
def test_original_static_arm_supervisors_compile_without_native_libraries(component, tmp_path):
    if not shutil.which("clang") or not shutil.which("ld.lld"):
        pytest.skip("clang/lld unavailable")
    if component == "install_sequence":
        (tmp_path / "sequence-binding.h").write_text(
            "static const unsigned char hearth_sequence_plans[3][32]={{1},{2},{3}};\nstatic const unsigned char hearth_sequence_receipts[3][32]={{4},{5},{6}};\n"
        )
    else:
        (tmp_path / "session.h").write_text("static const unsigned char hearth_session[32]={1};\n")
    out = tmp_path / "init"
    subprocess.run(
        [
            "clang",
            "--target=arm-linux-gnueabihf",
            "-marm",
            "-march=armv7-a",
            "-Os",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-ffreestanding",
            "-fno-builtin",
            "-fno-stack-protector",
            "-fomit-frame-pointer",
            "-fuse-ld=lld",
            "-nostdlib",
            "-static",
            "-Wl,-e,_start,--build-id=none,-z,noexecstack",
            "-I" + str(tmp_path),
            str(ROOT / "firmware" / component / "init.c"),
            "-o",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    from firmware.probe.configure import initramfs

    initramfs(out.read_bytes())


@pytest.fixture
def fake_boot(tmp_path, monkeypatch):
    from firmware.file_writer import chain
    from installer import kit as kit_module
    from installer import nand_backup

    monkeypatch.setattr(kit_module, "check", lambda *a, **k: {"review_only": False})
    monkeypatch.setattr(sequence, "private_path", lambda p: Path(p))
    monkeypatch.setattr(chain, "acquisition_install", lambda *a: None)
    monkeypatch.setattr(nand_backup, "check", lambda *a: None)
    root, kit, session = [tmp_path / n for n in ("profile", "kit", "session")]
    for p in (root, kit, session):
        p.mkdir(mode=0o700)
    roots = [kit / n for n in ("capacity", "commissioning", "cleanup")]
    for p in roots:
        p.mkdir(mode=0o700)
    records = [{"plan": bytes([i + 1] * 32).hex(), "receipt": b"r".hex() * 32} for i in range(3)]
    records[1]["capsule"] = str(kit)
    scoped = tuple(protocol.Binding(bytes([i + 1] * 32), b"r" * 32, 1) for i in range(3))
    monkeypatch.setattr(sequence, "checked_pair", lambda *a: ({"kit": str(kit)}, scoped[1]))
    monkeypatch.setattr(sequence.profile, "constituents", lambda *a: (roots, records))
    monkeypatch.setattr(sequence, "bindings", lambda *a: scoped)
    monkeypatch.setattr(sequence.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(sequence, "observe", lambda *a, receive_fn, **k: receive_fn(99, 0, None))
    sent = []
    monkeypatch.setattr(sequence.shared, "write_token", lambda fd, token: sent.append(token))
    calls = []
    rows = [
        successful_capacity(),
        {"complete": 1, "safe_to_restart": 1, "encoding_verified": 1},
        {"complete": 1, "safe_to_restart": 1, "encoding_verified": 1},
    ]

    def receive(fd, dest, *a, **k):
        calls.append(dest.name)
        return rows[len(calls) - 1]

    monkeypatch.setattr(sequence.shared, "receive", receive)
    return root, kit, session, rows, calls, sent, tmp_path / "output"


@pytest.mark.parametrize("refusal", (None, 0, 1, 2))
def test_one_loader_orders_stages_and_never_advances_after_refusal(fake_boot, refusal):
    root, kit, session, rows, calls, sent, output = fake_boot
    if refusal == 0:
        rows[0]["diagnostic"] = 42
    elif refusal is not None:
        rows[refusal]["complete"] = 0
    result = sequence.boot(
        root, kit, output, execute=True, handoff_from_acquisition=session / "acquisition"
    )
    expected = 3 if refusal is None else refusal + 1
    assert calls == ["capacity", "commissioning", "cleanup"][:expected]
    assert len(sent) == (3 if refusal is None else refusal)
    assert result["complete"] is (refusal is None)
    assert (output / "finished.json").exists()
    assert all((p / "execution-started.json").exists() for p in kit.iterdir())
    if refusal is not None:
        assert not (output / calls[-1] / "terminal-ack-sending.json").exists()
    with pytest.raises(ValueError, match="fresh"):
        sequence.boot(
            root, kit, output, execute=True, handoff_from_acquisition=session / "acquisition"
        )


def test_new_kit_selects_one_boot_and_old_kit_keeps_legacy_flow(flow):
    from installer import workflow

    root, session, calls, runner = flow
    (root / "kit.json").write_text('{"single_boot":true}')
    result = workflow.install(root, "/unused", runner=runner)
    assert result["complete"]
    assert [c[0] for c in calls] == ["install-sequence"]
    assert calls[0][2]["entry"] == {"handoff_from_acquisition": session / "acquisition"}


def test_combined_archive_shares_libraries_and_originals_without_dot_paths(tmp_path, monkeypatch):
    import stat

    from firmware.install_sequence import profile
    from firmware.settings_probe.artifact import parse_cpio
    from firmware.tls_probe.package import cpio

    monkeypatch.setattr(profile, "private_read", lambda p, limit: p.read_bytes())
    monkeypatch.setattr(profile, "initramfs", lambda _: None)
    roots = []
    for name in ("capacity", "commissioning", "cleanup"):
        root = tmp_path / name
        (root / "artifacts").mkdir(parents=True)
        rows = [(n, stat.S_IFDIR | 0o755, 0, b"", 0, 0) for n in (".", "lib", "originals")]
        rows += [
            ("lib/libc.so.6", stat.S_IFREG | 0o444, 0, b"shared library", 0, 0),
            ("init", stat.S_IFREG | 0o555, 0, b"child", 0, 0),
        ]
        if name != "commissioning":
            rows += [("originals/0", stat.S_IFREG | 0o400, 0, b"original", 0, 0)]
        rows += [("TRAILER!!!", 0, 0, b"", 0, 0)]
        (root / "artifacts/rootfs.cpio").write_bytes(cpio(rows))
        roots.append(root)
    result = parse_cpio(profile.archive(roots, b"supervisor"))
    names = [r[0] for r in result]
    assert names.count("lib/libc.so.6") == names.count("originals/0") == 1
    assert all(not n.endswith("/.") for n in names)
    assert {"capacity/lib", "commissioning/lib", "cleanup/lib"} <= set(names)
    assert {r[0]: r[1] for r in result}["lib"] == stat.S_IFDIR | 0o755


@pytest.mark.parametrize("scope", ("none", "commissioning", "cleanup"))
def test_saved_write_intent_controls_restore_scope(tmp_path, monkeypatch, scope):
    monkeypatch.setattr(sequence, "private_path", lambda p: Path(p))
    monkeypatch.setattr(sequence, "private_read", lambda p, limit: p.read_bytes())
    kit = tmp_path
    output = kit / "install-combined"
    output.mkdir()
    (kit / "install-sequence").mkdir()
    execution = {
        "profile": "fixed",
        "recovery": "fixed",
        "nonce": "nonce",
        "plan": "core",
        "started_monotonic": 1,
    }
    sequence.shared.save(output, "execution.json", sequence.shared.encode(execution))
    sequence.shared.save(
        kit / "install-sequence", "execution-started.json", sequence.shared.encode(execution)
    )
    sequence.shared.save(
        output, "finished.json", sequence.shared.encode({"host_command_exited": True})
    )
    expected = (
        []
        if scope == "none"
        else ["commissioning"]
        if scope == "commissioning"
        else ["commissioning", "cleanup"]
    )
    for name in expected:
        dest = output / name
        dest.mkdir()
        live = execution | {"stage": name, "plan": name, "started_monotonic": 2}
        sequence.shared.save(dest, "execution.json", sequence.shared.encode(live))
        sequence.shared.save(
            dest,
            "decision-sending.json",
            sequence.shared.encode({"execution": live, "commit": True}),
        )
    assert sequence.attempted_stages(kit) == expected
    (output / "finished.json").unlink()
    with pytest.raises(FileNotFoundError):
        sequence.attempted_stages(kit)


def test_cli_requests_both_write_decisions_in_a_single_engine_run(tmp_path, monkeypatch):
    import threading
    from types import SimpleNamespace

    from installer import cli
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    tmp_path.chmod(0o700)
    output = tmp_path / "output"
    decisions = []
    events = [threading.Event(), threading.Event()]

    def run(profile, recovery, out, **kwargs):
        out.mkdir(mode=0o700)
        for i, name in enumerate(("commissioning", "cleanup")):
            dest = out / name
            dest.mkdir(mode=0o700)
            sequence.shared.save(dest, "preflight.json", b"{}")
            assert events[i].wait(3)
            sequence.shared.save(dest, "finished.json", b"{}")
        return {"complete": True, "safe_to_restart": True, "encoding_verified": True}

    def decide(out, **kwargs):
        stage = sequence.pending_stage(out)
        decisions.append((stage, kwargs["commit"]))
        sequence.shared.save(out / stage, "decision.json", b"{}")
        events[len(decisions) - 1].set()

    engine = SimpleNamespace(
        checked_pair=lambda *a: (
            {"format": "hearth-one-boot-install-v1"},
            protocol.Binding(b"p" * 32, b"r" * 32, 1),
        ),
        run=run,
        decide=decide,
        pending_stage=sequence.pending_stage,
    )
    answers = iter(("y", "INSTALL", "INSTALL"))
    result = cli.execute(
        tmp_path / "profile", tmp_path / "kit", output, ask=lambda _: next(answers), engine=engine
    )
    assert result["complete"] and decisions == [("commissioning", True), ("cleanup", True)]


def test_restart_experiment_defaults_to_no_without_arming_or_consuming_profile(
    tmp_path, monkeypatch
):
    from firmware.rom_restart import run as experiment

    monkeypatch.setattr(experiment, "private_path", lambda p: Path(p))
    monkeypatch.setattr(experiment.profile, "check", lambda _: None)
    monkeypatch.setattr(experiment, "require_native", lambda _: None)
    monkeypatch.setattr(experiment.os, "isatty", lambda _: True)
    calls = []
    monkeypatch.setattr(experiment.subprocess, "run", lambda *a, **k: calls.append(a))
    root = tmp_path / "profile"
    root.mkdir()
    output = tmp_path / "output"
    assert experiment.run(root, output, ask=lambda _: "") == {"cancelled": True}
    assert not calls and not output.exists() and not (root / "execution-started.json").exists()


def test_review_only_sequence_cannot_arm_or_consume_profiles(fake_boot, monkeypatch):
    from installer import kit as kit_module

    monkeypatch.setattr(kit_module, "check", lambda *a, **k: {"review_only": True})
    root, kit, session, _, calls, _, output = fake_boot
    with pytest.raises(ValueError, match="review-only"):
        sequence.boot(
            root, kit, output, execute=True, handoff_from_acquisition=session / "acquisition"
        )
    assert not output.exists() and not calls and not (root / "execution-started.json").exists()


@pytest.mark.parametrize("fault", (None, "cleanup", "backup", "pin"))
def test_kernel_scope_must_match_checked_cleanup_profiles(tmp_path, monkeypatch, fault):
    from firmware.install_sequence import profile

    monkeypatch.setattr(profile, "private_read", lambda p, limit: p.read_bytes())
    records = [{}, {}, {"plan_path": "cleanup", "backup": "backup", "pin": "pin"}]
    row = {
        "format": "hearth-install-sequence-binding-v1",
        "cleanup": "cleanup",
        "backup": "backup",
        "pin": "pin",
    }
    if fault:
        row[fault] = "another scope"
    (tmp_path / "sequence-binding.json").write_bytes(sequence.shared.encode(row))
    if fault:
        with pytest.raises(ValueError, match="exact checked cleanup"):
            profile.check_scope(tmp_path, records)
    else:
        profile.check_scope(tmp_path, records)


@pytest.mark.parametrize("offline", (False, True))
def test_restartable_backup_selects_handoff_for_current_acquisition(flow, offline, monkeypatch):
    from installer import ram_handoff, workflow

    root, session, calls, runner = flow
    checked = []
    monkeypatch.setattr(ram_handoff, "await_ready", lambda p: checked.append(p))
    (root / "kit.json").write_text('{"single_boot":true}')
    (session / "nand/execution.json").write_text('{"handoff_profile":"checked-reader"}')
    if offline:
        (session / "acquisition").mkdir()
        (session / "acquisition/nand-inputs.json").write_text("{}")
    assert workflow.install(root, "/unused", runner=runner)["complete"]
    expected = {"handoff_from_acquisition": session / "acquisition"}
    if offline:
        expected["handoff_from_backup"] = session / "nand"
    assert calls[0][2]["entry"] == expected
    assert checked == ([session / "nand"] if offline else [])


@pytest.mark.parametrize("answers", (["y"], [""]))
def test_silent_backup_reader_asks_owner_and_never_consumes_kit(flow, monkeypatch, answers):
    from installer import ram_handoff, workflow

    root, session, calls, runner = flow
    (root / "kit.json").write_text('{"single_boot":true}')
    (session / "nand/execution.json").write_text('{"handoff_profile":"checked-reader"}')
    (session / "acquisition").mkdir()
    (session / "acquisition/nand-inputs.json").write_text("{}")
    attempts = []

    def ready(previous):
        attempts.append(previous)
        if len(attempts) == 1:
            raise TimeoutError("exact backup restart readiness not received; no token sent")

    monkeypatch.setattr(ram_handoff, "await_ready", ready)
    asked = iter(answers)
    if answers == ["y"]:
        assert workflow.install(root, "/unused", ask=lambda _: next(asked), runner=runner)[
            "complete"
        ]
        assert len(attempts) == 2 and len(calls) == 1
    else:
        with pytest.raises(workflow.NotStarted, match="Nothing was written"):
            workflow.install(root, "/unused", ask=lambda _: next(asked), runner=runner)
        assert len(attempts) == 1 and calls == []
    assert not (root / "install-combined").exists()


def test_single_boot_after_nest_left_ram_mode_is_reported_as_not_started(flow, monkeypatch):
    from installer import workflow

    root, _session, calls, runner = flow
    (root / "kit.json").write_text('{"single_boot":true}')
    monkeypatch.setattr(workflow, "identity", lambda: "native")
    monkeypatch.setattr(workflow, "inspect_native", lambda *a, **k: None)
    with pytest.raises(workflow.NotStarted, match="Nothing was written"):
        workflow.install(root, "/unused", runner=runner)
    assert calls == []


def test_sequence_automatic_handoff_does_not_start_a_second_manual_loader(fake_boot, monkeypatch):
    from installer import ram_handoff

    root, kit, session, _, _, _, output = fake_boot
    calls = []
    monkeypatch.setattr(ram_handoff, "await_ready", lambda p: calls.append(("ready", p)))
    monkeypatch.setattr(ram_handoff, "load", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(
        sequence.subprocess, "run", lambda *a, **k: pytest.fail("manual loader forbidden")
    )
    assert sequence.boot(
        root,
        kit,
        output,
        execute=True,
        handoff_from_acquisition=session / "acquisition",
        handoff_from_backup=session / "nand",
    )["complete"]
    assert calls[0] == ("ready", session / "nand")
    assert len(calls) == 2 and calls[1][2] == session / "nand"


@pytest.mark.parametrize("error", (TimeoutError, OSError, ValueError))
def test_unanswered_backup_reader_leaves_kit_unused(fake_boot, monkeypatch, error):
    from installer import ram_handoff

    root, kit, session, _, calls, sent, output = fake_boot

    def silent(_previous):
        raise error("backup reader not answering")

    monkeypatch.setattr(ram_handoff, "await_ready", silent)
    monkeypatch.setattr(ram_handoff, "load", lambda *a, **k: pytest.fail("must not restart"))
    with pytest.raises(error):
        sequence.boot(
            root,
            kit,
            output,
            execute=True,
            handoff_from_acquisition=session / "acquisition",
            handoff_from_backup=session / "nand",
        )
    assert not output.exists() and not (root / "execution-started.json").exists()
    assert not any((p / "execution-started.json").exists() for p in kit.iterdir())
    assert calls == [] and sent == []


def test_legacy_rootfs_ram_setup_uses_links_and_moves_preserving_original_link_count(tmp_path):
    if not shutil.which("cc"):
        pytest.skip("cc unavailable")
    (tmp_path / "sequence-binding.h").write_text(
        "static const unsigned char hearth_sequence_plans[3][32]={{1},{2},{3}};\nstatic const unsigned char hearth_sequence_receipts[3][32]={{4},{5},{6}};\n"
    )
    for name in (
        "lib",
        "originals",
        "capacity/lib",
        "capacity/originals",
        "commissioning/lib",
        "cleanup/lib",
        "cleanup/originals",
    ):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    for name, mode in (
        ("lib/libc.so.6", 0o444),
        ("lib/ld-linux-armhf.so.3", 0o555),
        ("originals/0", 0o400),
        ("originals/1", 0o400),
        ("originals/2", 0o400),
    ):
        (tmp_path / name).write_bytes(b"synthetic immutable RAM data")
        (tmp_path / name).chmod(mode)
    out = tmp_path / "test"
    subprocess.run(
        [
            "cc",
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-I" + str(tmp_path),
            str(ROOT / "tests/sequence_ram_harness.c"),
            "-o",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run([str(out), str(tmp_path)], check=True, capture_output=True)


def test_supervisor_bootstrap_failure_is_saved_before_the_session_refuses(tmp_path):
    import socket

    from firmware.file_writer import run as receiver

    host, device = socket.socketpair()
    report = b"HFW_BOOTSTRAP_FAILED_V1\nHSEQERR1 00000002 ffffffff\n"
    device.sendall(report)
    try:
        with pytest.raises(ValueError, match="root action launch failed"):
            receiver.receive(
                host.fileno(),
                tmp_path,
                protocol.Binding(b"p" * 32, b"r" * 32, 1),
                {},
                lambda: pytest.fail("must not recheck or commit"),
            )
    finally:
        host.close()
        device.close()
    assert (tmp_path / "invalid-input.bin").read_bytes() == report
    assert not (tmp_path / "decision-sending.json").exists()
