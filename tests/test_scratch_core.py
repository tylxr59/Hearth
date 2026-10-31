"""Compile only original code and trusted host OpenSSL, never native firmware."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_fixed_scratch_transaction_fault_model(tmp_path):
    compiler = shutil.which("clang")
    if compiler is None:
        pytest.skip("host clang required for scratch core sanitizer test")
    root = Path(__file__).resolve().parents[1]
    exe = tmp_path / "scratch-model"
    subprocess.run(
        [
            compiler,
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O1",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            str(root / "firmware/scratch_test/core.c"),
            str(root / "tests/scratch_core_harness.c"),
            "-lcrypto",
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
    )
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60, check=True)
    assert result.stdout == "scratch state/fault model passed; no device or ECC qualification\n"
