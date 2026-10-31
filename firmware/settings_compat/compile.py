"""Cross-compile original startup-only storage candidate using public ABI stubs."""

import argparse
import json
from pathlib import Path

from firmware.tls_probe.compile import LIBC, run
from firmware.tls_probe.package import sha

ASSETS = Path(__file__).parent
SOURCES = ("core.h", "core.c", "bind.c", "log_forward.S", "exports.map")


def source_hashes():
    return {n: sha((ASSETS / n).read_bytes()) for n in SOURCES}


def compile_library(output):
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
    imports = sorted(set(LIBC + ["memcpy", "strlen", "strncmp", "__tls_get_addr"]))
    for soname, names in (
        ("libc.so.6", imports),
        ("libdl.so.2", ["dlopen", "dlsym", "dlerror"]),
        ("libnlappcore.so", ["hearth_stub_native_dependency"]),
    ):
        stub = output / (soname + ".stub.c")
        stub.write_text("\n".join(f"long {n}(void) {{ return 0; }}" for n in names))
        run(
            common
            + ["-shared", "-fPIC", "-Wl,-soname," + soname, str(stub), "-o", str(output / soname)]
        )
    run(
        common
        + [
            "-shared",
            "-fPIC",
            "-Wl,-z,defs,-z,now,-soname,libhearth-settings-compat.so",
            "-Wl,--version-script=" + str(ASSETS / "exports.map"),
            str(ASSETS / "core.c"),
            str(ASSETS / "bind.c"),
            str(ASSETS / "log_forward.S"),
            "-Wl,--no-as-needed",
            str(output / "libc.so.6"),
            str(output / "libdl.so.2"),
            str(output / "libnlappcore.so"),
            "-o",
            str(output / "libhearth-settings-compat.so"),
        ]
    )
    record = {
        "status": "original-arm-storage-candidate-compiled-not-executed",
        "source_sha256": source_hashes(),
        "link_stubs_not_for_target": True,
        "files": {
            "libhearth-settings-compat.so": sha(
                (output / "libhearth-settings-compat.so").read_bytes()
            )
        },
    }
    (output / "compat.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    compile_library(parser.parse_args().output)
