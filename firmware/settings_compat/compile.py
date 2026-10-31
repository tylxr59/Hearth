"""Cross-compile original startup-only storage candidate using public ABI stubs."""

import argparse
import json
import shutil
import subprocess  # nosec B404
from pathlib import Path

from firmware.tls_probe.compile import LIBC, run
from firmware.tls_probe.package import sha

ASSETS = Path(__file__).parent
SOURCES = ("core.h", "core.c", "bind.c", "trace.h", "log_forward.S", "exports.map")


def source_hashes():
    return {n: sha((ASSETS / n).read_bytes()) for n in SOURCES}


def compile_library(output, *, trace=False, legacy_linker=False):
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
    linker_record = {"profile": "clang-lld"}
    if legacy_linker:
        # Only this fresh directory of original objects/public stubs is mounted.
        # The historical toolchain was already acquired for the GPL RAM kernel.
        objects = []
        for name in ("core.c", "bind.c", "log_forward.S"):
            target = output / (name + ".o")
            run(
                [x for x in common if not x.startswith(("-Wl,", "-fuse-ld="))]
                + [
                    "-fPIC",
                    *(["-DHEARTH_STORAGE_TRACE"] if trace else []),
                    "-c",
                    str(ASSETS / name),
                    "-o",
                    str(target),
                ]
            )
            objects.append("/work/" + target.name)
        shutil.copyfile(ASSETS / "exports.map", output / "exports.map")
        engine = shutil.which("podman")
        if engine is None:
            raise FileNotFoundError("Podman required for historical linker comparison")
        result = subprocess.run(  # nosec B603
            [
                engine,
                "image",
                "inspect",
                "--format",
                "{{.Id}}",
                "localhost/hearth-probe-builder:20261030",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        image = result.stdout.strip()
        if len(image) == 64:
            image = "sha256:" + image
        if (
            len(image) != 71
            or not image.startswith("sha256:")
            or any(c not in "0123456789abcdef" for c in image[7:])
        ):
            raise ValueError("local builder image identity required")
        run(
            [
                engine,
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "all",
                "--security-opt",
                "no-new-privileges",
                "-v",
                str(output) + ":/work:rw",
                image,
                "/opt/arm-2008q3/bin/arm-none-linux-gnueabi-ld",
                "-shared",
                "-z",
                "defs",
                "-z",
                "now",
                "-z",
                "relro",
                "--hash-style=both",
                "-soname",
                "libhearth-settings-compat.so",
                "--version-script=/work/exports.map",
                *objects,
                "/work/libc.so.6",
                "/work/libdl.so.2",
                "/work/libnlappcore.so",
                "-o",
                "/work/libhearth-settings-compat.so",
            ]
        )
        linker_record = {
            "profile": "gnu-2008q3-container",
            "builder_image": image,
            "toolchain_input_record": "firmware/probe/inputs.json",
        }
    else:
        run(
            common
            + [
                "-shared",
                "-fPIC",
                *(["-DHEARTH_STORAGE_TRACE"] if trace else []),
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
        "fixed_phase_trace": trace,
        "linker": linker_record,
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
