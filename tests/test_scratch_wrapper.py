import shutil
import subprocess
from pathlib import Path

import pytest

from firmware.scratch_test import stage


@pytest.mark.parametrize("mode", ["offline", "wrong-flag", "missing-archive", "existing-output"])
def test_wrapper_cannot_open_usb_before_explicit_inputs_and_private_preflight(tmp_path, mode):
    root = tmp_path / "workspace"
    work = root / "build/probe"
    work.mkdir(parents=True)
    private = root / "private"
    private.mkdir(mode=0o700)
    for source, name in stage.pairs():
        shutil.copyfile(source, work / name)
    (work / "check.py").write_text('print("synthetic integrity check")\n')
    (work / "duplex_observe.py").write_text(
        'def observe(*args): raise AssertionError("unexpected USB access")\n'
    )
    (work / "serial_observe.py").write_text(
        "from pathlib import Path\n"
        'Path(__file__).with_name("usb-opened").touch()\nraise SystemExit(93)\n'
    )
    (work / "artifacts").mkdir()
    loader = work / "artifacts/omap_loader"
    loader.write_text("#!/bin/sh\nexit 94\n")
    loader.chmod(0o700)
    output = private / "output"
    args = []
    if mode != "offline":
        args = [
            "--execute-experimental-scratch-restore" if mode != "wrong-flag" else "--execute",
            str(output),
            str(private / "missing-archive"),
            str(private / "missing-mask.json"),
        ]
    if mode == "existing-output":
        output.mkdir(mode=0o700)
    result = subprocess.run(
        ["sh", str(work / "boot.sh"), *args], check=False, capture_output=True, text=True, timeout=3
    )
    assert result.returncode == (0 if mode == "offline" else 2 if mode == "wrong-flag" else 1)
    assert not (work / "usb-opened").exists()
    if mode != "existing-output":
        assert not output.exists()


def test_duplex_derivation_does_not_change_original_read_only_observer():
    source = Path(__file__).resolve().parents[1] / "firmware/probe/observe.py"
    before = source.read_bytes()
    derived = stage.duplex_source(before.decode())
    assert "os.O_RDWR | os.O_NOCTTY" in derived
    assert "Scratch-only duplex copy" in derived
    assert source.read_bytes() == before and "os.O_RDWR" not in before.decode()
