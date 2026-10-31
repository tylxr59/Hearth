import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def snapshot_lab(tmp_path_factory):
    if not shutil.which("clang"):
        pytest.skip("Clang required for trusted-host snapshot lab")
    output = tmp_path_factory.mktemp("snapshot-build") / "lab"
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
            str(ROOT / "tests/file_snapshot_harness.c"),
            str(ROOT / "firmware/file_install/snapshot.c"),
            "-Wl,--wrap=read",
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return output


@pytest.mark.parametrize("scenario", range(18))
def test_bounded_readonly_snapshot(snapshot_lab, tmp_path, scenario):
    result = subprocess.run(
        [str(snapshot_lab), str(scenario), str(tmp_path)],
        capture_output=True,
        timeout=5,
        check=False,
    )
    if result.returncode == 77:
        pytest.skip("host fixture filesystem has no extended attributes")
    result.check_returncode()


def test_snapshot_arm_object_has_no_mutation_or_execution_imports(tmp_path):
    if not shutil.which("clang") or not shutil.which("nm"):
        pytest.skip("Clang and nm required")
    output = tmp_path / "snapshot.o"
    subprocess.run(
        [
            "clang",
            "--target=arm-linux-gnueabihf",
            "-marm",
            "-march=armv7-a",
            "-Os",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-ffreestanding",
            "-fno-builtin",
            "-fno-stack-protector",
            "-c",
            str(ROOT / "firmware/file_install/snapshot.c"),
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    symbols = subprocess.check_output(["nm", "-u", str(output)], text=True)
    imports = {line.split()[-1] for line in symbols.splitlines()}
    assert imports <= {
        "__errno_location",
        "close",
        "flistxattr",
        "lseek",
        "openat",
        "read",
        "syscall",
    }
    # Production object deliberately has no alternate writable RAM mode.
    rejected = subprocess.run(
        [
            "clang",
            "--target=arm-linux-gnueabihf",
            "-DHEARTH_RAM_LAB",
            "-c",
            str(ROOT / "firmware/file_install/snapshot.c"),
            "-o",
            str(tmp_path / "bad.o"),
        ],
        capture_output=True,
        check=False,
    )
    assert rejected.returncode != 0
