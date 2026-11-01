import shutil
import subprocess

import pytest


@pytest.fixture(scope="module")
def encoding_lab(tmp_path_factory):
    if shutil.which("clang") is None:
        pytest.skip("Clang required for original kernel encoding-audit fixture")
    folder = tmp_path_factory.mktemp("encoding-audit")
    headers = folder / "linux"
    headers.mkdir()
    for name in ("capability.h", "crc32.h"):
        (headers / name).write_text("/* Trusted host fixture declarations precede include. */\n")
    output = folder / "lab"
    subprocess.run(
        [
            "clang",
            "-D_GNU_SOURCE",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-I" + str(folder),
            "tests/file_encoding_harness.c",
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return output


@pytest.mark.parametrize("scenario", range(15))
def test_actual_kernel_audit_accepts_only_checked_uncompressed_active_fragments(
    encoding_lab, scenario
):
    subprocess.run([str(encoding_lab), str(scenario)], check=True, capture_output=True, timeout=5)
