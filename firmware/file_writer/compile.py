"""Cross-compile original private file actions against public ABI stubs only.

Proprietary original/replacement bytes are embedded strictly as validated DATA.
No proprietary ELF executes on the host or becomes a host linker input.
"""

import argparse
import json
from pathlib import Path

from firmware.file_writer.prepare import binding, pin_read
from firmware.tls_probe.compile import run
from firmware.tls_probe.package import sha
from provisioning.file_capsule import check as check_capsule

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "firmware/file_writer/abi.h",
    "firmware/file_writer/action.c",
    "firmware/file_writer/bootstrap.c",
    "firmware/file_writer/lifecycle.c",
    "firmware/file_writer/lifecycle.h",
    "firmware/file_writer/compile.py",
    "firmware/file_install/posix.c",
    "firmware/file_install/posix.h",
    "firmware/file_install/transaction.c",
    "firmware/file_install/transaction.h",
    "firmware/file_install/targets.h",
    "firmware/file_install/snapshot.c",
    "firmware/file_install/snapshot.h",
    "tests/file_install_harness.c",
    "tests/file_recovery_harness.c",
    "firmware/file_install_probe/lab_abi.h",
    "firmware/settings_probe/capture.h",
    "firmware/settings_compat_probe/transmit.h",
    "firmware/settings_compat_probe/exec.h",
    "firmware/tls_probe/start.S",
    "firmware/tls_probe/abi.h",
    "provisioning/file_capsule.py",
)
IMPORTS = (
    "__libc_start_main",
    "__errno_location",
    "__aeabi_memcpy",
    "__aeabi_memcpy4",
    "__aeabi_memclr4",
    "open",
    "openat",
    "close",
    "read",
    "write",
    "fsync",
    "fchmod",
    "fchown",
    "fchmodat",
    "mkdir",
    "mkdirat",
    "renameat",
    "unlinkat",
    "flistxattr",
    "getuid",
    "getgid",
    "syscall",
    "memcmp",
    "memset",
    "strlen",
    "snprintf",
    "sscanf",
    "mount",
    "umount2",
    "nanosleep",
    "umask",
    "lseek",
    "fork",
    "waitpid",
    "atoi",
    "linkat",
    "symlinkat",
    "mkfifoat",
    "readlink",
    "_exit",
    "strcmp",
)


def source_hashes():
    return {name: sha((ROOT / name).read_bytes()) for name in SOURCES}


def compile_helpers(output, capsule, pin):
    output, capsule = Path(output).resolve(), Path(capsule).resolve()
    plan = pin_read(pin)
    check_capsule(capsule, expected_plan=plan)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, data in (
        ("capsule.h", (capsule / "capsule.h").read_bytes()),
        ("binding.h", binding(capsule, pin).encode()),
    ):
        path = output / name
        path.write_bytes(data)
        path.chmod(0o600)
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
        "-I" + str(output),
        "-I" + str(ROOT / "firmware/file_install"),
    ]
    stub = output / "libc.stub.c"
    stub.write_text("\n".join(f"long {name}(void) {{ return 0; }}" for name in IMPORTS))
    run(
        common
        + ["-shared", "-fPIC", "-Wl,-soname,libc.so.6", str(stub), "-o", str(output / "libc.so.6")]
    )
    entry = [
        "-no-pie",
        "-Wl,-e,_start,--dynamic-linker=/lib/ld-linux-armhf.so.3",
        str(ROOT / "firmware/tls_probe/start.S"),
    ]
    for action in (1, 2):
        run(
            common
            + entry
            + [
                "-DHEARTH_FILE_ACTION=" + str(action),
                *[
                    str(ROOT / name)
                    for name in (
                        "firmware/file_writer/action.c",
                        "firmware/file_writer/lifecycle.c",
                        "firmware/file_install/posix.c",
                        "firmware/file_install/transaction.c",
                        "firmware/file_install/snapshot.c",
                    )
                ],
                str(output / "libc.so.6"),
                "-o",
                str(output / ("file-install" if action == 1 else "file-restore")),
            ]
        )
        run(
            common
            + [
                "-DHEARTH_FILE_ACTION=" + str(action),
                "-fomit-frame-pointer",
                "-static",
                "-Wl,-e,_start",
                str(ROOT / "firmware/file_writer/bootstrap.c"),
                "-o",
                str(output / ("install-init" if action == 1 else "restore-init")),
            ]
        )
    run(
        common
        + entry
        + [
            "-DHEARTH_RAM_LAB",
            "-DHEARTH_FILE_RECOVERY_CASES=25",
            "-Wl,--wrap=write,--wrap=fsync,--wrap=renameat,--wrap=fchmod,--wrap=fchown",
            *[
                str(ROOT / name)
                for name in (
                    "tests/file_recovery_harness.c",
                    "firmware/file_install/transaction.c",
                    "firmware/file_install/posix.c",
                )
            ],
            str(output / "libc.so.6"),
            "-o",
            str(output / "file-selftest"),
        ]
    )
    names = ("file-install", "file-restore", "install-init", "restore-init", "file-selftest")
    record = {
        "status": "private-file-action-helpers-unexecuted",
        "source_sha256": source_hashes(),
        "plan": plan.hex(),
        "binding_sha256": sha((output / "binding.h").read_bytes()),
        "capsule_header_sha256": sha((output / "capsule.h").read_bytes()),
        "selftest_cases": 56,
        "stub_not_for_target": True,
        "files": {name: sha((output / name).read_bytes()) for name in names},
    }
    path = output / "helpers.json"
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    for path in output.iterdir():
        if path.is_file():
            path.chmod(0o600)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--capsule", required=True)
    parser.add_argument("--pin", required=True)
    args = parser.parse_args()
    compile_helpers(args.output, args.capsule, args.pin)
