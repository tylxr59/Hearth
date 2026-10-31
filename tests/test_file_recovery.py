import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def recovery_lab(tmp_path_factory):
    if not shutil.which("clang"):
        pytest.skip("Clang required for host process-interruption lab")
    output = tmp_path_factory.mktemp("recovery-build") / "lab"
    subprocess.run(
        [
            "clang",
            "-D_GNU_SOURCE",
            "-DHEARTH_HOST_LAB",
            "-std=c11",
            "-g",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            str(ROOT / "tests/file_recovery_harness.c"),
            str(ROOT / "firmware/file_install/posix.c"),
            str(ROOT / "firmware/file_install/transaction.c"),
            "-Wl,--wrap=write,--wrap=fsync,--wrap=renameat,--wrap=fchmod,--wrap=fchown",
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return output


@pytest.mark.parametrize("scenario", range(24))
def test_fresh_process_restoration_and_fail_closed_preflight(recovery_lab, tmp_path, scenario):
    result = subprocess.run(
        [str(recovery_lab), str(scenario), str(tmp_path)],
        capture_output=True,
        check=False,
        timeout=5,
    )
    if result.returncode == 77:
        pytest.skip("host filesystem lacks extended attributes")
    result.check_returncode()
