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


def test_setup_has_no_continuation_switches():
    launch = subprocess.run(
        [sys.executable, "-S", "provision.py", "--continue-prepared", "unused"],
        check=False,
        capture_output=True,
        timeout=10,
    )
    assert launch.returncode == 2 and b"unrecognized arguments" in launch.stderr
    assert b"Hearth setup" not in launch.stdout
    launch = subprocess.run(
        [sys.executable, "-S", "-m", "installer.cli", "install-kit", "--help"],
        check=True,
        capture_output=True,
        timeout=10,
    )
    assert b"--continue-cleanup" not in launch.stdout


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
    monkeypatch.setattr(wizard, "find_nest", lambda: "1-1")
    monkeypatch.setattr(wizard.discovery, "native_disk", lambda **_: Path("/dev/synthetic"))
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
    ask = answers("", server, "", "http://10.0.0.12:8123", "y", "y", "8123", "", "y")
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


@pytest.mark.parametrize("accept", (True, False))
def test_refused_offline_extraction_offers_live_reader_only_with_owner_consent(
    setup, monkeypatch, accept
):
    _, _, calls = setup
    previous = wizard.Worker.run

    def run(self, op, **kw):
        result = previous(self, op, **kw)
        return {"offline_refused": True} if op == "acquire" else result

    monkeypatch.setattr(wizard.Worker, "run", run)
    if accept:
        ask = answers("", "", "", "http://10.0.0.12:8123", "y", "y", "y", "8123", "", "y")
    else:
        ask = answers("", "", "", "http://10.0.0.12:8123", "y", "y", "")
    assert wizard.run(ask=ask, secret=lambda _: "hidden-token") == 0
    expected = ["prepare", "nand", "acquire"]
    assert [op for op, _ in calls] == (expected + ["acquire-live", "kit"] if accept else expected)


def test_declining_acquisition_never_arms_reader_or_writer(setup):
    _, _, calls = setup
    assert (
        wizard.run(
            ask=answers("", "", "", "http://10.0.0.12:8123", ""),
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
            ask=answers("", "", "", "http://10.0.0.12:8123", "y", "y", ""),
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
    wizard.usb_access(tmp_path, lambda _: "y")
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
        wizard.usb_access(tmp_path, lambda _: "y")


@pytest.mark.parametrize(
    ("release", "expected"),
    (
        ('ID=ubuntu\nID_LIKE=debian\nPRETTY_NAME="Ubuntu 24.04"', "sudo apt install"),
        ('ID=cachyos\nID_LIKE=arch\nPRETTY_NAME="CachyOS"', "sudo pacman -S --needed"),
        ('ID=fedora\nPRETTY_NAME="Fedora 43"', "sudo dnf install"),
        ('ID=plan9\nPRETTY_NAME="Other"', None),
    ),
)
def test_missing_tools_get_a_distribution_hint_but_nothing_is_installed(
    tmp_path, release, expected
):
    path = tmp_path / "os-release"
    path.write_text(release)
    _, family = wizard.os_release(path)
    hint = wizard.install_hint(["mtype", "setfacl", "libusb", "cc"], family)
    if expected is None:
        assert hint is None
    else:
        assert hint.startswith(expected) and "mtools" in hint and "acl" in hint
    assert wizard.os_release(tmp_path / "missing") == ("Linux", None)


def test_wizard_output_is_plain_when_captured(capsys):
    from installer import ui

    ui.step(2, 7, "Build")
    ui.box("Ready to write", ["line"])
    live = ui.Live("Reading")
    live.set_percent(55)
    live.set_stage(2, 5, "Building")
    live.refresh()
    live.clear()
    shown = capsys.readouterr().out
    assert "\033[" not in shown
    assert "Step 2 of 7" in shown and "Reading: 55%" in shown and "[2/5] Building" in shown


def _fake_worker(monkeypatch, script):
    real_popen = subprocess.Popen
    monkeypatch.setattr(
        wizard.subprocess,
        "Popen",
        lambda command, **kw: real_popen([sys.executable, "-c", script, command[-1]], **kw),
    )


def _session(tmp_path, monkeypatch):
    from tools import elf_review

    tmp_path.chmod(0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    folder = tmp_path / "session"
    folder.mkdir(mode=0o700)
    return folder


def test_backup_progress_loader_prompt_and_stages_render_through_a_real_pty(
    tmp_path, monkeypatch, capsys
):
    folder = _session(tmp_path, monkeypatch)
    script = (
        "import json,sys,time; from pathlib import Path; "
        "r=json.loads(Path(sys.argv[1]).read_bytes()); "
        "print('[stage 1/2] Getting ready',flush=True); "
        "print('[+] scanning for USB device matching 0451:d00e...',flush=True); time.sleep(.3); "
        "[print(json.dumps({'status':'capturing','records':n,'total_records':262144}),"
        "flush=True) or time.sleep(.05) for n in range(8192,262145,8192)]; "
        "Path(r['session'],'nand-worker-result.json').write_text('{\"complete\": true}')"
    )
    _fake_worker(monkeypatch, script)
    assert wizard.Worker(folder, tmp_path / "build").run("nand") == {"complete": True}
    shown = capsys.readouterr().out
    assert "The loader is waiting now" in shown
    assert "Reading flash (two passes): 50%" in shown and "100%" in shown
    assert "[1/2] Getting ready" in shown
    assert "total_records" not in shown


def test_an_error_in_the_wizard_never_blocks_or_kills_the_worker(tmp_path, monkeypatch):
    folder = _session(tmp_path, monkeypatch)
    done = tmp_path / "worker-finished"
    # Far more output than a PTY buffer holds, written after the wizard fails.
    script = (
        "import sys; from pathlib import Path; "
        "print('[stage 1/1] Busy',flush=True); "
        "[sys.stdout.write('x'*1023+'\\n') for _ in range(4096)]; sys.stdout.flush(); "
        f"Path({str(done)!r}).write_text('ok')"
    )
    _fake_worker(monkeypatch, script)

    def broken(*_):
        raise RuntimeError("synthetic wizard bug")

    monkeypatch.setattr(wizard.ui.Live, "set_stage", broken)
    with pytest.raises(RuntimeError, match="synthetic"):
        wizard.Worker(folder, tmp_path / "build").run("prepare")
    assert done.read_text() == "ok"
    assert (folder / "prepare.log").stat().st_size > 4_000_000


def test_unexpected_errors_are_recorded_and_explained(setup, monkeypatch, capsys):
    _, private, _ = setup

    def broken(self, op, **kw):
        raise AttributeError("synthetic")

    monkeypatch.setattr(wizard.Worker, "run", broken)
    ask = answers("", "", "", "http://10.0.0.12:8123")
    assert wizard.run(ask=ask, secret=lambda _: "hidden-token") == 1
    folder = next(private.iterdir())
    stopped = json.loads((folder / "wizard-stopped.json").read_bytes())
    assert stopped["unexpected"] and stopped["phase"] == "prepare"
    assert b"AttributeError" in (folder / "wizard-error.log").read_bytes()
    assert "This is a bug in the wizard" in capsys.readouterr().out


def test_y_n_prompts_need_an_explicit_yes_and_ha_step_can_quit(setup):
    from installer import ui

    assert ui.confirm(lambda _: " Yes ", "Go?") and ui.confirm(lambda _: "y", "Go?")
    for answer in ("", "n", "no", "READY", "yess"):
        assert not ui.confirm(lambda _, a=answer: a, "Go?")
    _, _, calls = setup
    assert wizard.run(ask=answers("", "", "q"), secret=lambda _: "unused") == 0
    assert calls == []


def _refusal(**overrides):
    row = {
        "preflight_only": 1,
        "protected": 1,
        "safe_to_restart": 1,
        "program": 0,
        "erase": 0,
        "marker": 0,
        "rw_attempted": 0,
        "window_opened": 0,
        "committed": 0,
        "diagnostic": 42,
        "space_available": 13_217_792,
        "space_required": 13_248_165,
    }
    return row | overrides


@pytest.mark.parametrize("row", (_refusal(), _refusal(program=3), _refusal(protected=0)))
def test_space_refusal_reports_numbers_and_only_calls_provable_zero_writes_safe(
    tmp_path, monkeypatch, capsys, row
):
    folder = _session(tmp_path, monkeypatch)
    output = folder / "check-capacity"
    output.mkdir(mode=0o700)
    observed = output / "observed.json"
    observed.write_text(json.dumps({"result": row}))
    observed.chmod(0o600)
    engine = SimpleNamespace(checked_pair=lambda *a: ({}, SimpleNamespace(action=1)))
    worker = wizard.Worker(folder, tmp_path)
    monkeypatch.setattr(
        worker, "run", lambda *a, **kw: {"preflight_passed": False, "safe_to_restart": True}
    )
    result = worker.writer(
        tmp_path / "capacity-preflight",
        tmp_path / "restore",
        output,
        engine=engine,
        ask=lambda _: "y",
    )
    shown = capsys.readouterr().out
    assert "13,248,165" in shown and "30,373 short" in shown
    safe = row["program"] == 0 and row["protected"] == 1
    assert result["zero_write_refusal"] is safe
    assert ("safe to restart" in shown) is safe


def test_zero_write_space_refusal_tells_the_owner_to_restart_normally(setup, monkeypatch, capsys):
    _, private, _ = setup
    monkeypatch.setattr(
        wizard.workflow,
        "install",
        lambda *a, **kw: {
            "complete": False,
            "capacity_passed": False,
            "capacity_zero_write_refusal": True,
        },
    )
    ask = answers("", "", "", "http://10.0.0.12:8123", "y", "y", "8123")
    assert wizard.run(ask=ask, secret=lambda _: "hidden-token") == 1
    stop = capsys.readouterr().out.split("Setup stopped")[-1]
    assert "nothing was written" in stop and "Restart it normally" in stop
    assert "don't restart the Nest" not in stop and "Keep USB connected" not in stop
    folder = next(private.iterdir())
    assert json.loads((folder / "wizard-stopped.json").read_bytes())["phase"] == "space-check"


def test_automatic_handoff_scanning_does_not_ask_for_another_ring_press(
    tmp_path, monkeypatch, capsys
):
    folder = _session(tmp_path, monkeypatch)
    script = (
        "import json,sys,time; from pathlib import Path; "
        "r=json.loads(Path(sys.argv[1]).read_bytes()); "
        "print('[+] scanning for USB device matching 0451:d00e...',flush=True); time.sleep(.3); "
        "Path(r['session'],'sequence-worker-result.json').write_text('{\"complete\": true}')"
    )
    _fake_worker(monkeypatch, script)
    assert wizard.Worker(folder, tmp_path / "build").run(
        "sequence", entry={"handoff_from_backup": "checked-backup"}
    )["complete"]
    shown = capsys.readouterr().out
    assert "Leave the ring untouched" in shown
    assert "hold the ring" not in shown.lower() and "The loader is waiting now" not in shown


@pytest.fixture
def worker_session(tmp_path, monkeypatch):
    from firmware.file_writer.run import encode, save
    from tools import elf_review

    tmp_path.chmod(0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    session = tmp_path / "session"
    session.mkdir(mode=0o700)
    names = iter(range(100))

    def request(op):
        name = f"{op}-{next(names)}-request.json"
        save(
            session,
            name,
            encode({"operation": op, "session": str(session), "build": str(tmp_path / "b")}),
        )
        return session / name

    return session, request


def test_worker_records_offline_refusal_and_gates_live_reader(worker_session, monkeypatch):
    from firmware.acquisition import run as acquisition
    from installer import nand_inputs, wizard_worker

    session, request = worker_session
    live, bound = [], []
    monkeypatch.setattr(
        acquisition, "run", lambda root, output, **k: live.append((root, output, k))
    )
    monkeypatch.setattr(wizard_worker, "bind_acquisition", lambda *a: bound.append(a[1]))
    # Never a live boot without a recorded offline refusal.
    with pytest.raises(ValueError):
        wizard_worker.work(request("acquire-live"))
    assert live == []

    def refuse(_session):
        raise ValueError("complete inode without extended attributes required")

    monkeypatch.setattr(nand_inputs, "extract", refuse)
    wizard_worker.work(request("acquire"))
    result = json.loads((session / "acquire-worker-result.json").read_bytes())
    assert result["offline_refused"] is True and result["flash_writes"] is False
    assert bound == []
    wizard_worker.work(request("acquire-live"))
    assert live == [
        (
            session / "reader",
            session / "acquisition",
            {"execute": True, "handoff_from_nand": session / "nand"},
        )
    ]
    assert bound == ["execution.json"]


def test_worker_refusal_after_partial_output_is_not_a_fallback(worker_session, monkeypatch):
    from installer import nand_inputs, wizard_worker

    session, request = worker_session

    def partial(session):
        (session / "acquisition").mkdir(mode=0o700)
        raise ValueError("late failure")

    monkeypatch.setattr(nand_inputs, "extract", partial)
    with pytest.raises(ValueError, match="late failure"):
        wizard_worker.work(request("acquire"))
    assert not (session / "nand-inputs-refused.json").exists()


@pytest.mark.parametrize(
    ("result", "result_flag", "phase", "shown", "hidden"),
    (
        (
            {"zero_write_cancel": True},
            None,
            "install-cancelled",
            "before anything was written",
            "don't restart the Nest",
        ),
        (
            {"partial_install_safe": True},
            None,
            "install-partial",
            "provision.py --restore",
            "don't restart the Nest",
        ),
        (
            {},
            None,
            "install",
            "Installation did not finish",
            "safe to restart",
        ),
    ),
)
def test_combined_install_stops_explain_what_was_written(
    setup, monkeypatch, capsys, result, result_flag, phase, shown, hidden
):
    _, private, _ = setup
    monkeypatch.setattr(wizard.workflow, "install", lambda *a, **kw: {"complete": False} | result)
    ask = answers("", "", "", "http://10.0.0.12:8123", "y", "y", "8123")
    assert wizard.run(ask=ask, secret=lambda _: "hidden-token") == 1
    stop = capsys.readouterr().out.split("Setup stopped")[-1]
    assert shown in stop and hidden not in stop
    folder = next(private.iterdir())
    assert json.loads((folder / "wizard-stopped.json").read_bytes())["phase"] == phase


def test_unstarted_combined_install_is_reported_as_safe(setup, monkeypatch, capsys):
    _, private, _ = setup

    def refuse(*a, **kw):
        raise wizard.workflow.NotStarted("The install did not start. Nothing was written.")

    monkeypatch.setattr(wizard.workflow, "install", refuse)
    ask = answers("", "", "", "http://10.0.0.12:8123", "y", "y", "8123")
    assert wizard.run(ask=ask, secret=lambda _: "hidden-token") == 1
    stop = capsys.readouterr().out.split("Setup stopped")[-1]
    assert "Nothing was written" in stop and "safe to restart normally" in stop
    assert "don't restart the Nest" not in stop
    folder = next(private.iterdir())
    assert json.loads((folder / "wizard-stopped.json").read_bytes())["phase"] == (
        "install-not-started"
    )


def _stage(output, name, commit):
    from firmware.file_writer.run import encode, save

    (output / name).mkdir(parents=True, mode=0o700)
    if commit is not None:
        save(output / name, "decision.json", encode({"execution": {}, "commit": commit}))


@pytest.mark.parametrize(
    ("completed", "failed", "commit", "safe", "flag"),
    (
        ([], "commissioning", False, True, "zero_write_cancel"),
        ([], "commissioning", True, True, None),
        ([], "commissioning", None, True, None),
        ([], "commissioning", False, False, None),
        (["commissioning"], "cleanup", False, True, "partial_install_safe"),
        (["commissioning"], "cleanup", True, True, None),
        (["commissioning"], "cleanup", False, False, None),
    ),
)
def test_sequence_outcome_flags_only_proven_owner_cancels(
    tmp_path, monkeypatch, capsys, completed, failed, commit, safe, flag
):
    from tools import elf_review

    tmp_path.chmod(0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    output = tmp_path / "install-combined"
    output.mkdir(mode=0o700)
    _stage(output, failed, commit)
    row = {
        "complete": False,
        "completed_phases": completed,
        "failed_stage": failed,
        "safe_to_restart": safe,
    }
    result = wizard.sequence_outcome(output, row)
    flags = {"zero_write_cancel", "partial_install_safe"} & set(result)
    assert flags == ({flag} if flag else set())
    shown = " ".join(capsys.readouterr().out.split())
    assert ("is installed and verified" in shown) is bool(completed)
    if flag is None:
        assert "do not restart the Nest" in shown
