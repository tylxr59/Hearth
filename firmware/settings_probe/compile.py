"""Compile only original ARM diagnostic sources against generated public ABI stubs."""

import argparse
import json
from pathlib import Path

from firmware.tls_probe.compile import LIBC, run
from firmware.tls_probe.package import sha

ASSETS = Path(__file__).parent
SOURCES = ("init.c", "client.c", "faults.c", "faults.h", "capture.h")
SHARED = ("firmware/tls_probe/abi.h", "firmware/tls_probe/start.S")


def source_hashes():
    root = ASSETS.resolve().parents[1]
    return {n: sha((ASSETS / n).read_bytes()) for n in SOURCES} | {
        n: sha((root / n).read_bytes()) for n in SHARED
    }


def compile_helpers(output):
    output = Path(output).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
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
    symbols = sorted(
        set(LIBC + ["malloc", "free", "open", "mkdir", "umask", "memset", "__errno_location"])
    )
    for soname, names in (("libc.so.6", symbols), ("libdl.so.2", ["dlopen", "dlsym", "dlerror"])):
        stub = output / (soname + ".stub.c")
        stub.write_text("\n".join(f"long {n}(void) {{ return 0; }}" for n in names))
        run(
            common
            + ["-shared", "-fPIC", "-Wl,-soname," + soname, str(stub), "-o", str(output / soname)]
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
            "-no-pie",
            "-Wl,-e,_start,--export-dynamic,--dynamic-linker=/lib/ld-linux-armhf.so.3",
            str(ASSETS / "../tls_probe/start.S"),
            str(ASSETS / "client.c"),
            str(ASSETS / "faults.c"),
            str(output / "libc.so.6"),
            str(output / "libdl.so.2"),
            "-o",
            str(output / "settings-test"),
        ]
    )
    record = {
        "status": "original-arm-settings-helpers-compiled-not-executed",
        "source_sha256": source_hashes(),
        "link_stubs_not_for_target": True,
        "files": {n: sha((output / n).read_bytes()) for n in ("settings-init", "settings-test")},
    }
    (output / "helpers.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    compile_helpers(parser.parse_args().output)
