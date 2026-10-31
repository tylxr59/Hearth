import shutil
import subprocess
from pathlib import Path

import pytest


def test_actual_adapter_io_callbacks_under_sanitizers(tmp_path):
    compiler = shutil.which("clang")
    if compiler is None:
        pytest.skip("host clang required for adapter I/O sanitizer model")
    source = Path(__file__).with_name("scratch_io_harness.c")
    exe = tmp_path / "io"
    subprocess.run(
        [
            compiler,
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O1",
            "-fsanitize=address,undefined",
            str(source),
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
    )
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=3)
    assert result.stdout == "fixed scratch adapter I/O model passed; hardware unqualified\n"
