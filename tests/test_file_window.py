import ctypes
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def window_lab(tmp_path_factory):
    if not shutil.which("clang"):
        pytest.skip("Clang required for the original hardware-free policy lab")
    output = tmp_path_factory.mktemp("window-build")
    source = ROOT / "firmware/file_writer/core.c"
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            str(ROOT / "tests/file_window_harness.c"),
            str(source),
            "-o",
            str(output / "lab"),
        ],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-shared",
            "-fPIC",
            str(source),
            "-o",
            str(output / "range.so"),
        ],
        capture_output=True,
        check=True,
    )
    return output


@pytest.mark.parametrize("scenario", range(12))
def test_binding_protection_failures_and_freed_erase_request(window_lab, scenario):
    subprocess.run([str(window_lab / "lab"), str(scenario)], check=True, capture_output=True)


def test_exact_ranges_alignment_and_overflow(window_lab):
    lib = ctypes.CDLL(str(window_lab / "range.so"))
    lib.hf_range.argtypes = [ctypes.c_int, ctypes.c_ulonglong, ctypes.c_uint]
    lib.hf_range.restype = ctypes.c_int
    mib = 1048576
    for start, end in ((12 * mib, 58 * mib), (116 * mib, 124 * mib)):
        assert lib.hf_range(1, start, 2048) == 0
        assert lib.hf_range(1, end - 2048, 2048) == 0
        assert lib.hf_range(2, end - 131072, 131072) == 0
        assert lib.hf_range(3, start, 8) == 0
        for operation, offset, size in (
            (1, start - 2048, 2048),
            (1, end, 2048),
            (1, end - 2048, 4096),
            (1, start + 1, 2048),
            (1, start, 1),
            (1, start, 0),
            (2, start + 2048, 131072),
            (2, start, 2048),
            (3, start + 2048, 8),
            (3, start, 64),
            (1, (1 << 64) - 2048, 4096),
            (99, start, 2048),
        ):
            assert lib.hf_range(operation, offset, size) != 0


@pytest.fixture(scope="module")
def window_io_lab(tmp_path_factory):
    if not shutil.which("clang"):
        pytest.skip("Clang required")
    output = tmp_path_factory.mktemp("window-io-build")
    (output / "binding.h").write_text(
        "static const unsigned char hearth_expected_plan[32]={1};\n"
        "static const unsigned char hearth_expected_receipt[32]={2};\n"
    )
    subprocess.run(
        [
            "clang",
            "-D_GNU_SOURCE",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-pthread",
            "-I",
            str(output),
            str(ROOT / "tests/file_window_io_harness.c"),
            "-o",
            str(output / "lab"),
        ],
        capture_output=True,
        check=True,
    )
    return output / "lab"


@pytest.mark.parametrize("scenario", range(15))
def test_actual_io_adapter_protection_and_deferred_callback_lifetime(window_io_lab, scenario):
    subprocess.run([str(window_io_lab), str(scenario)], check=True, capture_output=True, timeout=5)
