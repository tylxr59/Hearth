"""Guided setup orchestration and real PTY lifecycle, with synthetic workers only."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.validation import Invalid
from installer import cli, wizard
from tests.test_installer import info


def answers(*values):
    iterator = iter(values)
    return lambda _: next(iterator)


def test_ntp_prompt_defaults_and_reprompts_without_accepting_config_fragments():
    assert wizard.choose_time(answers("")) == "time.nist.gov"
    assert wizard.choose_time(answers("x\nserver bad", "NTP.Example.Test")) == "ntp.example.test"


def test_no_argument_cli_launches_wizard(monkeypatch):
    monkeypatch.setattr(wizard, "run", lambda: 37)
    assert cli.main([]) == 37
    assert cli.main(["wizard"]) == 37


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from tools import elf_review

    tmp_path.chmod(0o700)
    root = tmp_path / "source"
    root.mkdir(mode=0o700)
    private = root / "private"
    monkeypatch.setattr(elf_review, "PRIVATE", private)
    monkeypatch.setattr(wizard, "PRIVATE", private)
    monkeypatch.setattr(wizard, "ROOT", root)
    monkeypatch.setattr(wizard, "prerequisites", lambda: None)
    monkeypatch.setattr(wizard.discovery, "native_disk", lambda: Path("/dev/synthetic"))
    monkeypatch.setattr(wizard.workflow, "identity", lambda: "native")
    monkeypatch.setattr(cli, "inspect_disk", lambda *a, **kw: info())
    monkeypatch.setattr(wizard, "usb_access", lambda *a: None)
    monkeypatch.setattr(wizard, "read_bundle", lambda _: ({}, b"ca", b"crl"))
    calls = []

    def onboard(ha, token, folder, raw, **kw):
        assert token == "hidden-token"
        folder.mkdir(mode=0o700)
        (folder / "commissioning.zip").write_bytes(b"synthetic")
        return {"ha_configured": True}

    class Worker:
        def __init__(self, folder, build, **kw):
            self.folder = folder

        def run(self, operation, **kw):
            calls.append((operation, kw))
            return {}

        def writer(self, *a, **kw):
            raise AssertionError("No hardware runner in a wizard unit test")

    monkeypatch.setattr(wizard.onboard, "onboard", onboard)
    monkeypatch.setattr(wizard, "Worker", Worker)
    monkeypatch.setattr(wizard.workflow, "install", lambda *a, **kw: {"complete": True})
    # The second read normally checks against a real commissioning bundle.
    monkeypatch.setattr(wizard, "device_info", lambda *a: {})
    return root, private, calls


@pytest.mark.parametrize("server", ("", "ntp.example.test", "10.0.0.8"))
def test_single_wizard_routes_selected_time_and_keeps_tokens_out_of_artifacts(setup, server):
    _, private, calls = setup
    ask = answers(
        "", server, "HA READY", "http://10.0.0.12:8123", "READY", "READY", "8123", "", "YES"
    )
    assert wizard.run(ask=ask, secret=lambda _: "hidden-token") == 0
    folder = next(private.iterdir())
    expected = server or "time.nist.gov"
    assert calls == [
        ("prepare", {}),
        ("nand", {}),
        ("acquire", {}),
        ("kit", {"ntp_server": expected, "probe_port": 8123}),
    ]
    assert json.loads((folder / "wizard-settings.json").read_bytes())["ntp_server"] == expected
    for file in folder.iterdir():
        assert b"hidden-token" not in file.read_bytes()
    assert json.loads((folder / "wizard-complete.json").read_bytes())[
        "fresh_readings_owner_verified"
    ]


def test_declining_acquisition_never_arms_reader_or_writer(setup):
    _, _, calls = setup
    assert (
        wizard.run(
            ask=answers("", "", "HA READY", "http://10.0.0.12:8123", ""),
            secret=lambda _: "hidden-token",
        )
        == 0
    )
    assert calls == [("prepare", {})]


def test_failed_kit_does_not_run_writer_or_retry(setup, monkeypatch):
    _, private, calls = setup
    previous = wizard.Worker.run

    def run(self, op, **kw):
        if op == "kit":
            raise Invalid("Existing installation requires recovery, not a stock install.")
        return previous(self, op, **kw)

    monkeypatch.setattr(wizard.Worker, "run", run)
    monkeypatch.setattr(wizard.workflow, "install", lambda *a, **kw: pytest.fail("must not write"))
    assert (
        wizard.run(
            ask=answers("", "", "HA READY", "http://10.0.0.12:8123", "READY", "READY", ""),
            secret=lambda _: "hidden-token",
        )
        == 1
    )
    folder = next(private.iterdir())
    assert json.loads((folder / "wizard-stopped.json").read_bytes())["phase"] == "kit"
    assert [op for op, _ in calls] == ["prepare", "nand", "acquire"]


@pytest.mark.parametrize("failure", (False, True))
def test_real_pty_worker_hides_technical_output_and_never_retries(
    tmp_path, monkeypatch, capsys, failure
):
    from tools import elf_review

    tmp_path.chmod(0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    folder = tmp_path / "session"
    folder.mkdir(mode=0o700)
    real_popen = subprocess.Popen
    starts = []
    script = (
        "import json,os,sys,time; from pathlib import Path; "
        "r=json.loads(Path(sys.argv[1]).read_bytes()); "
        "print('PRIVATE-TECHNICAL-DATA',flush=True); "
        "print('scanning for USB device',flush=True); time.sleep(.2); "
        "p=Path(r['session'])/'acquire-worker-result.json'; "
        "p.write_text(json.dumps({'complete':True})); sys.exit(int(sys.argv[2]))"
    )

    def launch(command, **kw):
        starts.append(command)
        return real_popen([sys.executable, "-c", script, command[-1], str(int(failure))], **kw)

    monkeypatch.setattr(wizard.subprocess, "Popen", launch)
    worker = wizard.Worker(folder, tmp_path / "build")
    if failure:
        with pytest.raises(Invalid, match="stopped"):
            worker.run("acquire")
    else:
        assert worker.run("acquire") == {"complete": True}
    assert len(starts) == 1
    shown = capsys.readouterr().out
    assert "loader is waiting now" in shown
    assert "PRIVATE-TECHNICAL-DATA" not in shown
    assert b"PRIVATE-TECHNICAL-DATA" in (folder / "acquire.log").read_bytes()
    assert (folder / "acquire.log").stat().st_mode & 0o777 == 0o600


def test_writer_cancel_before_arming_runs_nothing(tmp_path, monkeypatch):
    engine = SimpleNamespace(checked_pair=lambda *a: ({}, SimpleNamespace(action=1)))
    worker = wizard.Worker(tmp_path, tmp_path)
    monkeypatch.setattr(worker, "run", lambda *a, **kw: pytest.fail("must not launch"))
    result = worker.writer(
        tmp_path / "commissioning-install",
        tmp_path / "restore",
        tmp_path / "output",
        engine=engine,
        ask=lambda _: "",
    )
    assert result == {"cancelled": True}


@pytest.mark.parametrize(
    "answer", ("INSTALL", "", "interrupt", "interrupt-early", "interrupt-after")
)
def test_pty_preflight_requires_separate_decision_and_waits_for_exit(tmp_path, monkeypatch, answer):
    from tools import elf_review

    tmp_path.chmod(0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    folder = tmp_path / "session"
    folder.mkdir(mode=0o700)
    output = folder / "output"
    output.mkdir(mode=0o700)
    decisions = []
    engine = SimpleNamespace(decide=lambda path, **kw: decisions.append(kw))
    real_popen = subprocess.Popen
    script = (
        "import json,sys,time; from pathlib import Path; "
        "r=json.loads(Path(sys.argv[1]).read_bytes()); "
        "p=Path(r['output']); (p/'preflight.json').write_text('{}'); time.sleep(.8); "
        "(Path(r['session'])/'commissioning-worker-result.json').write_text(json.dumps({'complete':True}))"
    )
    monkeypatch.setattr(
        wizard.subprocess,
        "Popen",
        lambda command, **kw: real_popen([sys.executable, "-c", script, command[-1]], **kw),
    )

    original_select = wizard.select.select
    interrupted = False

    def select_once(*args):
        nonlocal interrupted
        if not interrupted and (
            answer == "interrupt-early" or (answer == "interrupt-after" and decisions)
        ):
            interrupted = True
            raise KeyboardInterrupt
        return original_select(*args)

    monkeypatch.setattr(wizard.select, "select", select_once)

    def ask(_):
        if answer == "interrupt":
            raise KeyboardInterrupt
        if answer == "interrupt-early":
            pytest.fail("An early interruption must abort without asking to install")
        return "INSTALL" if answer == "interrupt-after" else answer

    worker = wizard.Worker(folder, tmp_path / "build", ask=ask)

    def run():
        return worker.run(
            "commissioning", engine=engine, binding=SimpleNamespace(action=1), output=str(output)
        )

    if answer.startswith("interrupt"):
        with pytest.raises(Invalid, match="interrupted"):
            run()
    else:
        assert run() == {"complete": True}
    assert decisions == [{"commit": answer in ("INSTALL", "interrupt-after"), "expected_action": 1}]


def test_usb_rule_requires_explicit_permission_and_never_grants_disk_access(tmp_path, monkeypatch):
    # Redirect only the fixed rule destination; never touch /etc or use sudo here.
    original_path = wizard.Path
    target = tmp_path / "70-hearth-wizard.rules"

    class RootACL:
        def is_file(self):
            return True

        def is_symlink(self):
            return False

        def stat(self):
            return SimpleNamespace(st_uid=0, st_mode=0o100755)

        def __str__(self):
            return "/usr/bin/setfacl"

    monkeypatch.setattr(
        wizard,
        "Path",
        lambda value: (
            target
            if value == "/etc/udev/rules.d/70-hearth-wizard.rules"
            else RootACL()
            if value == "/usr/bin/setfacl"
            else original_path(value)
        ),
    )
    monkeypatch.setattr(wizard.workflow, "identity", lambda: "native")
    monkeypatch.setattr(wizard.shutil, "which", lambda _: "/usr/bin/setfacl")
    calls = []
    monkeypatch.setattr(wizard.subprocess, "run", lambda command, **kw: calls.append(command))
    with pytest.raises(Invalid, match="cancelled"):
        wizard.usb_access(tmp_path, lambda _: "")
    assert not calls
    wizard.usb_access(tmp_path, lambda _: "USB ACCESS")
    assert len(calls) == 2 and all(command[:2] == ["sudo", "--"] for command in calls)
    content = (tmp_path / "70-hearth-wizard.rules").read_text()
    assert f"u:{wizard.os.getuid()}:rw" in content
    assert 'SUBSYSTEM=="block"' not in content and "/dev/sd" not in content
    assert 'KERNEL=="1-1"' in content and 'KERNELS=="1-1"' in content


@pytest.mark.parametrize("fault", ("missing", "symlink", "owner", "writable"))
def test_root_udev_helper_never_comes_from_user_path(monkeypatch, tmp_path, fault):
    class ACL:
        def is_file(self):
            return fault != "missing"

        def is_symlink(self):
            return fault == "symlink"

        def stat(self):
            return SimpleNamespace(
                st_uid=1000 if fault == "owner" else 0,
                st_mode=0o100777 if fault == "writable" else 0o100755,
            )

    monkeypatch.setattr(wizard, "Path", lambda _: ACL())
    monkeypatch.setattr(wizard.workflow, "identity", lambda: "native")
    monkeypatch.setattr(wizard.shutil, "which", lambda _: "/home/user/bin/setfacl")
    monkeypatch.setattr(
        wizard.subprocess, "run", lambda *a, **kw: pytest.fail("must not invoke sudo")
    )
    with pytest.raises(Invalid, match="root-managed"):
        wizard.usb_access(tmp_path, lambda _: "USB ACCESS")
