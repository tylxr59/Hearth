"""Compile only original RAM lab sources/public ABI stubs. Never link firmware."""

import argparse
import json
from pathlib import Path

from firmware.settings_compat_probe.compile import compile_helpers as settings_helpers
from firmware.settings_compat_probe.compile import source_hashes as settings_sources
from firmware.tls_probe.compile import LIBC, run
from firmware.tls_probe.package import sha

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).parent
SOURCES = (
    "tests/file_install_harness.c",
    "firmware/file_install/transaction.c",
    "firmware/file_install/transaction.h",
    "firmware/file_install/posix.c",
    "firmware/file_install/posix.h",
    "firmware/file_install_probe/lab_abi.h",
    "firmware/settings_compat_probe/init.c",
)


def source_hashes():
    return {name: sha((ROOT / name).read_bytes()) for name in SOURCES} | {
        "settings/" + key: value for key, value in settings_sources().items()
    }


def supervisor_source():
    """Reuse the measured supervisor with exact, bounded substitutions."""
    source = (ROOT / "firmware/settings_compat_probe/init.c").read_text()
    begin = source.index("    char *const argv[] = ")
    end = source.index("    output_used = ", begin)
    source = (
        source[:begin]
        + """    char *const argv[] = {candidate == 2 ? "/file-test" : "/settings-test", (char *)variant, 0};
    char *const env[] = {"LD_LIBRARY_PATH=/lib", "HOME=/nonexistent", "LC_ALL=C",
        candidate == 2 ? "HEARTH_FILE_LAB=1" : candidate ?
        "LD_PRELOAD=/lib/libhearth-settings-compat.so:/lib/libhearth-settings-faults.so" :
        "LD_PRELOAD=/lib/libhearth-settings-faults.so",
        candidate == 1 ? "LD_DEBUG=files,reloc,bindings" : "HEARTH_LAB_ORIGINAL=1", 0};
"""
        + source[end:]
    )
    substitutions = {
        "static char report[32768];": "static char report[49152];",
        "2 * (SETTINGS_OUTPUT_LIMIT + 2 * SETTINGS_DIAGNOSTIC_LIMIT + 16 * 96 + 512)": "3 * (SETTINGS_OUTPUT_LIMIT + 2 * SETTINGS_DIAGNOSTIC_LIMIT + 16 * 96 + 512)",
        "    int original, candidate;": "    int original, candidate, files;",
        "    append(original == 0 && candidate == 0 ?": '    files = run("files",2);\n    append_captured("files"); process_result("files",files);\n'
        "    append(original == 0 && candidate == 0 && files == 0 ?",
    }
    for old, new in substitutions.items():
        if source.count(old) != 1:
            raise ValueError("reviewed supervisor template changed")
        source = source.replace(old, new)
    return source.replace("SETTINGS_COMPAT", "FILE_COMMISSIONING")


def compile_helpers(output, *, legacy_linker=True):
    output = Path(output).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    settings_helpers(output / "settings", legacy_linker=legacy_linker, candidate_trace=False)
    common = [
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
        "-fno-builtin",
        "-ffreestanding",
        "-fno-stack-protector",
        "-fuse-ld=lld",
        "-nostdlib",
        "-Wl,--build-id=none",
    ]
    imports = sorted(
        set(
            LIBC
            + [
                "__errno_location",
                "atoi",
                "close",
                "fchmod",
                "flistxattr",
                "fchown",
                "fsync",
                "getgid",
                "getuid",
                "linkat",
                "memcmp",
                "memcpy",
                "memset",
                "mkdir",
                "mkdirat",
                "mkfifoat",
                "open",
                "openat",
                "read",
                "readlink",
                "renameat",
                "strlen",
                "symlinkat",
                "syscall",
                "unlinkat",
                "__aeabi_memcpy",
                "__aeabi_memcpy4",
                "__aeabi_memclr4",
            ]
        )
    )
    stub = output / "libc.stub.c"
    stub.write_text("\n".join(f"long {name}(void) {{ return 0; }}" for name in imports))
    run(
        common
        + ["-shared", "-fPIC", "-Wl,-soname,libc.so.6", str(stub), "-o", str(output / "libc.so.6")]
    )
    run(
        common
        + [
            "-DHEARTH_RAM_LAB",
            "-no-pie",
            "-Wl,-e,_start,--dynamic-linker=/lib/ld-linux-armhf.so.3",
            "-Wl,--wrap=write,--wrap=fsync,--wrap=renameat,--wrap=fchmod,--wrap=fchown",
            str(ROOT / "firmware/tls_probe/start.S"),
            str(ROOT / SOURCES[0]),
            str(ROOT / "firmware/file_install/transaction.c"),
            str(ROOT / "firmware/file_install/posix.c"),
            str(output / "libc.so.6"),
            "-o",
            str(output / "file-test"),
        ]
    )
    init = output / "file-init.c"
    init.write_text(supervisor_source())
    run(
        common
        + [
            "-fomit-frame-pointer",
            "-static",
            "-Wl,-e,_start",
            "-I" + str(ROOT / "firmware/settings_compat_probe"),
            str(init),
            "-o",
            str(output / "file-init"),
        ]
    )
    files = {name: sha((output / name).read_bytes()) for name in ("file-init", "file-test")}
    record = {
        "status": "original-ram-only-file-lab-compiled-unexecuted",
        "source_sha256": source_hashes(),
        "generated_supervisor_sha256": sha(init.read_bytes()),
        "ram_only_file_adapter": True,
        "candidate_phase_trace": False,
        "settings_helpers_manifest_sha256": sha((output / "settings/helpers.json").read_bytes()),
        "files": files,
    }
    (output / "helpers.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    compile_helpers(parser.parse_args().output)
