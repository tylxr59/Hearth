import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def file_installer_lab(tmp_path_factory):
    if not shutil.which("clang"):
        pytest.skip("Clang required for the original filesystem lab")
    output = tmp_path_factory.mktemp("file-install-build") / "lab"
    subprocess.run(
        [
            "clang",
            "-D_GNU_SOURCE",
            "-DHEARTH_HOST_LAB",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            str(ROOT / "tests/file_install_harness.c"),
            str(ROOT / "firmware/file_install/transaction.c"),
            str(ROOT / "firmware/file_install/posix.c"),
            "-Wl,--wrap=write,--wrap=fsync,--wrap=renameat,--wrap=fchmod,--wrap=fchown",
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return output


@pytest.mark.parametrize("scenario", range(33))
def test_actual_file_transaction_and_failure_recovery(file_installer_lab, tmp_path, scenario):
    result = subprocess.run(
        [str(file_installer_lab), str(scenario), str(tmp_path)],
        check=False,
        capture_output=True,
        timeout=5,
    )
    if result.returncode == 77:
        pytest.skip("host filesystem does not support extended attributes")
    result.check_returncode()


def test_original_file_sources_cross_compile_for_arm_without_firmware(tmp_path):
    if not shutil.which("clang"):
        pytest.skip("Clang required")
    for name in ("transaction", "posix"):
        subprocess.run(
            [
                "clang",
                "--target=arm-linux-gnueabihf",
                "-marm",
                "-march=armv7-a",
                "-mfpu=vfpv3-d16",
                "-mfloat-abi=hard",
                "-Os",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-ffreestanding",
                "-fno-builtin",
                "-c",
                str(ROOT / f"firmware/file_install/{name}.c"),
                "-o",
                str(tmp_path / f"{name}.o"),
            ],
            check=True,
            capture_output=True,
        )
