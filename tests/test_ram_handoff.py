"""Synthetic PTY loaders and sockets; never opens USB or requests a real reboot."""

import json
import socket
import sys
import time
from pathlib import Path

import pytest

from firmware.file_writer.run import encode, save
from installer import ram_handoff as h


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from installer import nand_backup
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    tmp_path.chmod(0o700)
    session = tmp_path / "session"
    session.mkdir(mode=0o700)
    source = session / "nand-handoff-reader"
    source.mkdir(mode=0o700)
    backup = session / "nand"
    backup.mkdir(mode=0o700)
    artifacts = tmp_path / "target"
    artifacts.mkdir(mode=0o700)
    save(artifacts, "uImage", b"synthetic image")
    output = tmp_path / "result"
    output.mkdir(mode=0o700)
    save(backup, "execution.json", encode({"handoff_profile": str(source)}))
    save(source, "profile.json", encode({"session": (b"n" * 32).hex()}))
    monkeypatch.setattr(nand_backup, "require_handoff", lambda *a: None)
    monkeypatch.setattr(h.profile, "check", lambda *a: None)
    return source, backup, artifacts, output


def loader(artifacts, code):
    p = artifacts / "omap_loader"
    p.write_text("#!" + sys.executable + "\n" + code)
    p.chmod(0o700)


def test_live_successor_scanning_and_durable_intent_precede_one_token(setup, monkeypatch):
    source, backup, artifacts, output = setup
    release = output / "mock-token"
    loader(
        artifacts,
        "from pathlib import Path\nimport time\nprint('scanning for USB device matching 0451:d00e...',flush=True)\np=Path("
        + repr(str(release))
        + ")\nend=time.monotonic()+5\nwhile not p.exists() and time.monotonic()<end: time.sleep(0.01)\nraise SystemExit(0 if p.exists() else 4)\n",
    )
    sent = []

    def send(fd, token):
        assert (output / "handoff-loader-ready.json").exists()
        assert (backup / "restart-sending.json").exists()
        assert (output / "restart-sending.json").exists()
        sent.append(token)
        release.write_text("once")

    monkeypatch.setattr(h, "write_token", send)
    result = h.transfer(99, b"n" * 32, artifacts, output, source)
    assert result["loader_transfer_complete"]
    assert sent == [b"HNBRST1\n" + b"n" * 32]
    assert (output / "restart-sent.json").exists()
    assert (
        json.loads((output / "handoff-transfer-finished.json").read_bytes())["second_image_ready"]
        == "pending"
    )


def test_loader_failure_before_scanning_never_requests_restart(setup, monkeypatch):
    source, _, artifacts, output = setup
    loader(artifacts, "print('failed before scanning',flush=True)\nraise SystemExit(4)\n")
    sent = []
    monkeypatch.setattr(h, "write_token", lambda *a: sent.append(a))
    with pytest.raises(ValueError, match="transfer failed"):
        h.transfer(99, b"n" * 32, artifacts, output, source)
    assert not sent and not (output / "restart-sending.json").exists()


def test_partial_token_failure_consumes_source_without_retry(setup, monkeypatch):
    source, backup, artifacts, output = setup
    loader(
        artifacts,
        "import time\nprint('scanning for USB device matching 0451:d00e...',flush=True)\ntime.sleep(5)\n",
    )
    sent = []

    def fail(*args):
        sent.append(args)
        raise OSError("partial token transfer")

    monkeypatch.setattr(h, "write_token", fail)
    with pytest.raises(OSError, match="partial token"):
        h.transfer(99, b"n" * 32, artifacts, output, source)
    assert len(sent) == 1 and (backup / "restart-sending.json").exists()
    assert not (output / "restart-sent.json").exists()
    with pytest.raises(ValueError, match="no second restart"):
        h.load(artifacts, output, backup, recheck=lambda: None)


@pytest.mark.parametrize("correct_nonce", (True, False))
def test_exact_reader_nonce_required_before_starting_successor(setup, monkeypatch, correct_nonce):
    _source, backup, artifacts, output = setup
    host, device = socket.socketpair()
    called = []
    monkeypatch.setattr(h, "transfer", lambda *a: called.append("transfer") or {"loaded": True})
    monkeypatch.setattr(
        h,
        "observe",
        lambda *a, receive_fn, **k: receive_fn(host.fileno(), time.monotonic() + 0.05, None),
    )
    device.sendall(b"HNBRDY1\n" + (b"n" if correct_nonce else b"x") * 32)
    try:
        if correct_nonce:
            assert h.load(artifacts, output, backup, recheck=lambda: called.append("recheck")) == {
                "loaded": True
            }
            assert called == ["recheck", "transfer"]
        else:
            with pytest.raises(TimeoutError, match="exact backup restart"):
                h.load(artifacts, output, backup, recheck=lambda: called.append("recheck"))
            assert called == ["recheck"]
    finally:
        host.close()
        device.close()


@pytest.mark.parametrize("correct_nonce", (True, False))
def test_readiness_check_only_reads_and_never_sends_or_records(setup, monkeypatch, correct_nonce):
    _source, backup, _artifacts, output = setup
    host, device = socket.socketpair()
    monkeypatch.setattr(h, "write_token", lambda *a: pytest.fail("readiness check must not send"))
    monkeypatch.setattr(h, "transfer", lambda *a: pytest.fail("readiness check must not load"))
    monkeypatch.setattr(
        h,
        "observe",
        lambda *a, receive_fn, **k: receive_fn(host.fileno(), time.monotonic() + 0.05, None),
    )
    before = sorted(p.name for p in backup.iterdir())
    device.sendall(b"HNBRDY1\n" + (b"n" if correct_nonce else b"x") * 32)
    device.setblocking(False)
    try:
        if correct_nonce:
            assert h.await_ready(backup) == {"backup_reader_ready": True, "restart_sent": False}
        else:
            with pytest.raises(TimeoutError, match="no token sent"):
                h.await_ready(backup)
        with pytest.raises(BlockingIOError):
            device.recv(1)
    finally:
        host.close()
        device.close()
    assert sorted(p.name for p in backup.iterdir()) == before
    assert list(output.iterdir()) == []


def test_missing_backup_or_kit_checks_never_start_successor(setup, monkeypatch):
    _, backup, artifacts, output = setup
    monkeypatch.setattr(h, "observe", lambda *a, **k: pytest.fail("must not open serial"))

    def refuse():
        raise ValueError("kit changed")

    with pytest.raises(ValueError, match="kit changed"):
        h.load(artifacts, output, backup, recheck=refuse)
    assert not (output / "restart-sending.json").exists()


def test_actual_backup_init_requires_successful_export_and_exact_nonce_for_one_reboot(tmp_path):
    import shutil
    import subprocess

    from firmware.nand_capture.stage import protocol_header

    if not shutil.which("cc"):
        pytest.skip("cc unavailable")
    (tmp_path / "sample-protocol.h").write_text(protocol_header().replace("131072U", "3U"))
    (tmp_path / "session.h").write_text("static const unsigned char hearth_session[32]={1};\n")
    output = tmp_path / "test"
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [
            "cc",
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-I" + str(tmp_path),
            str(root / "tests/nand_handoff_harness.c"),
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run([str(output)], check=True, capture_output=True)
