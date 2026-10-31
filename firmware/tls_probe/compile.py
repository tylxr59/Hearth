"""Cross-compile original helpers using public ABI link stubs, never firmware."""

import argparse
import hashlib
import json

# Fixed compiler/linker argv; no firmware is executed or used as a link input.
import subprocess  # nosec B404
from pathlib import Path

LIBC = [
    "__libc_start_main",
    "socket",
    "bind",
    "listen",
    "accept",
    "close",
    "setsockopt",
    "fork",
    "waitpid",
    "alarm",
    "_exit",
    "time",
    "write",
    "snprintf",
    "strcmp",
    "signal",
]


def run(argv):
    subprocess.run(argv, check=True, capture_output=True, timeout=60)  # nosec B603


def compile_helpers(output):
    output = Path(output).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    assets = Path(__file__).parent.resolve()
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
    for soname, symbols in (("libc.so.6", LIBC), ("libdl.so.2", ["dlopen", "dlsym", "dlerror"])):
        source = output / (soname + ".stub.c")
        source.write_text("\n".join(f"long {name}(void) {{ return 0; }}" for name in symbols))
        run(
            common
            + ["-shared", "-fPIC", "-Wl,-soname," + soname, str(source), "-o", str(output / soname)]
        )
    run(
        common
        + [
            "-fomit-frame-pointer",
            "-static",
            "-Wl,-e,_start",
            str(assets / "init.c"),
            "-o",
            str(output / "tls-init"),
        ]
    )
    run(
        common
        + [
            "-no-pie",
            "-Wl,-e,_start,--dynamic-linker=/lib/ld-linux-armhf.so.3",
            str(assets / "start.S"),
            str(assets / "client.c"),
            str(output / "libc.so.6"),
            str(output / "libdl.so.2"),
            "-o",
            str(output / "tls-test"),
        ]
    )
    record = {
        "status": "original-arm-helpers-compiled-not-executed",
        "link_stubs_not_for_target": True,
        "source_sha256": {
            n: hashlib.sha256((assets / n).read_bytes()).hexdigest()
            for n in ("init.c", "client.c", "abi.h", "start.S")
        },
        "files": {
            n: hashlib.sha256((output / n).read_bytes()).hexdigest()
            for n in ("tls-init", "tls-test")
        },
    }
    (output / "helpers.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    compile_helpers(parser.parse_args().output)
