import shutil
import subprocess
from pathlib import Path

import pytest


def test_original_supervisor_control_flow_under_host_syscall_model(tmp_path):
    compiler = shutil.which("clang")
    if compiler is None:
        pytest.skip("host clang required for supervisor sanitizer model")
    root = Path(__file__).resolve().parents[1]
    source = (root / "firmware/scratch_test/init.c").read_text()
    start = source.index("static long call5(")
    end = source.index("static unsigned char snapshot[", start)
    # Replace only the architecture-specific syscall instruction with a simulator.
    source = source[:start] + "static long call5(long,long,long,long,long,long);\n" + source[end:]
    source = source.replace("_start(void)", "hs_supervisor(void)")
    (tmp_path / "supervisor-under-test.c").write_text(source)
    shutil.copyfile(root / "firmware/scratch_test/protocol.h", tmp_path / "scratch-protocol.h")
    exe = tmp_path / "supervisor"
    subprocess.run(
        [
            compiler,
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O1",
            "-fsanitize=address,undefined",
            "-I",
            str(tmp_path),
            str(root / "tests/scratch_supervisor_harness.c"),
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
    )
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=3)
    assert result.stdout == "supervisor syscall model passed; no device execution\n"
