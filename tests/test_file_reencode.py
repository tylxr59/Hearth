import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def reencode_lab(tmp_path_factory):
    if not shutil.which("clang"):
        pytest.skip("Clang required for original forced-rewrite sanitizer checks")
    output = tmp_path_factory.mktemp("reencode-build") / "lab"
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
            str(ROOT / "tests/file_reencode_harness.c"),
            str(ROOT / "firmware/file_reencode/reencode.c"),
            str(ROOT / "firmware/file_install/transaction.c"),
            "-Wl,--wrap=write,--wrap=fsync,--wrap=renameat,--wrap=fchmod,--wrap=fchown",
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return output


@pytest.mark.parametrize("scenario", range(13))
def test_forced_original_and_archive_rewrite_or_fail_closed(reencode_lab, tmp_path, scenario):
    subprocess.run(
        [str(reencode_lab), str(scenario), str(tmp_path)],
        capture_output=True,
        check=True,
        timeout=5,
    )
