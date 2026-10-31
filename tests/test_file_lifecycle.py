import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def lifecycle_lab(tmp_path_factory):
    if not shutil.which("clang"):
        pytest.skip("Clang required")
    output = tmp_path_factory.mktemp("lifecycle-build") / "lab"
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            str(ROOT / "tests/file_lifecycle_harness.c"),
            str(ROOT / "firmware/file_writer/lifecycle.c"),
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return output


@pytest.mark.parametrize("scenario", range(16))
def test_cleanup_order_commit_uncertainty_and_restart_evidence(lifecycle_lab, scenario):
    subprocess.run([str(lifecycle_lab), str(scenario)], check=True, capture_output=True, timeout=5)
