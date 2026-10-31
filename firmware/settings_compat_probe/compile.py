"""Compile original comparison helpers/fault DSO; never link or execute firmware."""

import argparse
import json
from pathlib import Path

from firmware.settings_compat.compile import compile_library
from firmware.settings_compat.compile import source_hashes as candidate_sources
from firmware.tls_probe.compile import LIBC, run
from firmware.tls_probe.package import sha

ASSETS = Path(__file__).parent
SHARED = (
    "firmware/settings_probe/capture.h",
    "firmware/settings_probe/faults.c",
    "firmware/settings_probe/faults.h",
    "firmware/tls_probe/abi.h",
    "firmware/tls_probe/start.S",
)


def source_hashes():
    root = ASSETS.resolve().parents[1]
    return (
        {
            n: sha((ASSETS / n).read_bytes())
            for n in ("init.c", "client.c", "control.c", "control.h", "scan.h", "tail.h")
        }
        | {n: sha((root / n).read_bytes()) for n in SHARED}
        | {"candidate/" + n: v for n, v in candidate_sources().items()}
    )


def compile_helpers(output, *, legacy_linker=False):
    output = Path(output).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    compile_library(output / "candidate", trace=True, legacy_linker=legacy_linker)
    stubs = output / "stubs"
    stubs.mkdir(mode=0o700)
    common = [
        "clang",
        "--target=arm-linux-gnueabihf",
        "-marm",
        "-march=armv7-a",
        "-mfpu=vfpv3-d16",
        "-mfloat-abi=hard",
        "-Os",
        "-DHEARTH_STORAGE_TRACE",
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
    symbols = sorted(
        set(LIBC + ["malloc", "free", "open", "mkdir", "umask", "memset", "__errno_location"])
    )
    controls = [
        "fault_load",
        "fault_begin",
        "fault_disarm",
        "fault_snapshot",
        "allocation_begin",
        "allocation_end",
        "allocation_snapshot",
        "permission_begin",
        "permission_end",
        "permission_snapshot",
    ]
    for soname, names in (
        ("libc.so.6", symbols),
        ("libdl.so.2", ["dlopen", "dlsym", "dlerror"]),
        ("libhearth-settings-faults.so", controls),
    ):
        source = stubs / (soname + ".c")
        source.write_text("\n".join(f"long {n}(void) {{ return 0; }}" for n in names))
        run(
            common
            + ["-shared", "-fPIC", "-Wl,-soname," + soname, str(source), "-o", str(stubs / soname)]
        )
    run(
        common
        + [
            "-fomit-frame-pointer",
            "-static",
            "-Wl,-e,_start",
            str(ASSETS / "init.c"),
            "-o",
            str(output / "settings-init"),
        ]
    )
    run(
        common
        + [
            "-shared",
            "-fPIC",
            "-Wl,-z,defs,-soname,libhearth-settings-faults.so",
            str(ASSETS / "../settings_probe/faults.c"),
            str(ASSETS / "control.c"),
            "-Wl,--no-as-needed",
            str(stubs / "libc.so.6"),
            str(stubs / "libdl.so.2"),
            str(output / "candidate/libnlappcore.so"),
            "-o",
            str(output / "libhearth-settings-faults.so"),
        ]
    )
    run(
        common
        + [
            "-no-pie",
            "-Wl,-e,_start,--dynamic-linker=/lib/ld-linux-armhf.so.3",
            str(ASSETS / "../tls_probe/start.S"),
            str(ASSETS / "client.c"),
            str(stubs / "libc.so.6"),
            str(stubs / "libdl.so.2"),
            str(stubs / "libhearth-settings-faults.so"),
            "-o",
            str(output / "settings-test"),
        ]
    )
    record = {
        "status": "original-arm-storage-comparison-compiled-not-executed",
        "link_stubs_not_for_target": True,
        "source_sha256": source_hashes(),
        "files": {
            n: sha((output / n).read_bytes())
            for n in ("settings-init", "settings-test", "libhearth-settings-faults.so")
        },
        "candidate_sha256": sha((output / "candidate/libhearth-settings-compat.so").read_bytes()),
    }
    (output / "helpers.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--legacy-linker", action="store_true")
    args = parser.parse_args()
    compile_helpers(args.output, legacy_linker=args.legacy_linker)
