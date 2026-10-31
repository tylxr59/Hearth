import json
import shutil
import subprocess
from pathlib import Path

import pytest

from firmware.settings_compat.compile import compile_library


def test_original_storage_core_with_host_nspr_under_sanitizers(tmp_path):
    if not shutil.which("clang") or not shutil.which("pkg-config"):
        pytest.skip("Clang/pkg-config required for original host checks")
    flags = subprocess.run(
        ["pkg-config", "--cflags", "--libs", "nspr"], capture_output=True, text=True, check=False
    )
    if flags.returncode:
        pytest.skip("host NSPR development library required; never substitute firmware")
    root = Path(__file__).resolve().parents[1]
    driver = tmp_path / "compat-driver"
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-pthread",
            str(root / "tests/settings_compat_core_harness.c"),
            str(root / "firmware/settings_compat/core.c"),
            *flags.stdout.split(),
            "-o",
            str(driver),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run([str(driver)], check=True, capture_output=True, timeout=10)


def test_candidate_builds_only_original_sources_and_keeps_stubs_separate(tmp_path):
    if not shutil.which("clang") or not shutil.which("ld.lld"):
        pytest.skip("Clang/LLD required for original ARM cross-compilation")
    output = tmp_path / "candidate"
    record = compile_library(output)
    assert record["link_stubs_not_for_target"]
    assert set(record["files"]) == {"libhearth-settings-compat.so"}
    assert json.loads((output / "compat.json").read_text()) == record
    meta = subprocess.run(
        ["readelf", "-d", "--dyn-syms", "--wide", str(output / "libhearth-settings-compat.so")],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "[libnlappcore.so]" in meta and "BIND_NOW" in meta
    assert "hearth_stub_native_dependency" not in meta
    for name in (
        "_ZN10nlSettings5WriteEv",
        "_ZN8nlConfig8AddEntryEPKcS1_",
        "nlLogWithComponent",
        "PR_Write",
    ):
        assert name in meta
    with pytest.raises(FileExistsError):
        compile_library(output)
