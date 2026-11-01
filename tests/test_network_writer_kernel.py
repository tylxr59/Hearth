import ctypes
import shutil
import subprocess

import pytest


@pytest.fixture(scope="module")
def scoped_policy(tmp_path_factory):
    if shutil.which("clang") is None:
        pytest.skip("Clang required for original write policy checks")
    root = tmp_path_factory.mktemp("network-kernel-policy")
    common = ["clang", "-Wall", "-Wextra", "-Werror", "-DHEARTH_ROOT0_ONLY"]
    subprocess.run(
        common + ["-shared", "-fPIC", "firmware/file_writer/core.c", "-o", str(root / "range.so")],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        common
        + [
            "-fsanitize=address,undefined",
            "tests/file_window_harness.c",
            "firmware/file_writer/core.c",
            "-o",
            str(root / "gate"),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-DHEARTH_FILE_MASK=15",
            "-fsanitize=address,undefined",
            "tests/file_lifecycle_harness.c",
            "firmware/file_writer/lifecycle.c",
            "-o",
            str(root / "lifecycle"),
        ],
        check=True,
        capture_output=True,
    )
    return root


@pytest.mark.parametrize("scenario", range(12))
def test_root_only_gate_retains_protection_and_error_behavior(scoped_policy, scenario):
    subprocess.run(
        [str(scoped_policy / "gate"), str(scenario)], check=True, capture_output=True, timeout=5
    )


@pytest.mark.parametrize("scenario", range(16))
def test_four_file_lifecycle_retains_cleanup_and_restoration_masks(scoped_policy, scenario):
    subprocess.run(
        [str(scoped_policy / "lifecycle"), str(scenario)],
        check=True,
        capture_output=True,
        timeout=5,
    )


@pytest.mark.parametrize("operation,length", ((1, 2048), (2, 131072), (3, 8)))
def test_other_partitions_are_denied_including_previously_allowed_user_state(
    scoped_policy, operation, length
):
    library = ctypes.CDLL(str(scoped_policy / "range.so"))
    fn = library.hf_range
    fn.argtypes = [ctypes.c_int, ctypes.c_ulonglong, ctypes.c_uint]
    fn.restype = ctypes.c_int
    assert fn(operation, 12 * 1048576, length) == 0
    for location in (0, 8 * 1048576, 58 * 1048576, 116 * 1048576, 124 * 1048576):
        assert fn(operation, location, length) == -1
    assert fn(operation, 58 * 1048576 - (2048 if operation == 1 else 131072), length) == 0
