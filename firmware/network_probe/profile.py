"""Offline protected RAM matrix/preflight packaging. No USB or persistent writer."""

import argparse
import json
import os
import stat
from pathlib import Path

from firmware.file_writer.compile import IMPORTS
from firmware.file_writer.profile import elf_metadata, native_libraries
from firmware.network_snapshot.profile import base_check, read_build, sha
from firmware.probe.configure import initramfs
from firmware.settings_probe.artifact import parse_cpio
from firmware.tls_probe.check import split_multi
from firmware.tls_probe.compile import run
from firmware.tls_probe.package import MAX_IMAGE, MAX_ROOT, cpio, multi_image, private_read
from provisioning import network_plan
from tools.elf_review import private_path

ROOT = Path(__file__).resolve().parents[2]
FILES = {
    "uImage",
    "rootfs.cpio",
    "init",
    "network-transaction",
    "kernel.config",
    "x-load-gen2.bin",
    "u-boot.bin",
    "omap_loader",
    "fallback-init",
}
STATUS = "protected-network-ram-preflight-unexecuted"


def recipes():
    from firmware.network_snapshot.profile import recipes as reader_recipes

    paths = set(reader_recipes()) | {
        "provisioning/network_plan.py",
        "tests/network_memory.h",
        "tests/network_transaction_harness.c",
        "firmware/file_install/posix.c",
        "firmware/file_install/transaction.c",
        "firmware/file_install/transaction.h",
        "firmware/file_install_probe/lab_abi.h",
        "firmware/tls_probe/abi.h",
        "firmware/tls_probe/start.S",
        "firmware/file_writer/profile.py",
        "firmware/file_writer/compile.py",
    }
    for folder in ("network_update", "network_probe"):
        paths |= {
            p.relative_to(ROOT).as_posix()
            for p in (ROOT / "firmware" / folder).iterdir()
            if p.suffix in (".c", ".h", ".py")
        }
    return {name: sha((ROOT / name).read_bytes()) for name in sorted(paths)}


def pinned_plan(plan, backup, pin):
    record = json.loads(private_read(pin, 4096))
    if (
        not isinstance(record, dict)
        or set(record) != {"format", "plan"}
        or record["format"] != "hearth-network-reviewed-pin-v1"
    ):
        raise ValueError("separate reviewed network plan pin required")
    return network_plan.check(plan, backup, bytes.fromhex(record["plan"]))


def archive(program, harness, libraries):
    initramfs(program)
    needed, imports, _ = elf_metadata(harness)
    allowed = set(IMPORTS) | {"strstr", "memcpy", "malloc", "free"}
    if needed != {"libc.so.6"} or not imports <= allowed:
        raise ValueError("standalone original harness dependency scope changed")
    entries = [
        (name, stat.S_IFDIR | 0o755, 0, b"", 0, 0) for name in (".", "dev", "proc", "sys", "lib")
    ]
    entries += [
        (name, stat.S_IFDIR | 0o700, 65534, b"", 0, 0)
        for name in ("state", *(f"state/transaction-{i:02d}" for i in range(20)))
    ]
    entries += [
        ("dev/console", stat.S_IFCHR | 0o600, 0, b"", 5, 1),
        ("init", stat.S_IFREG | 0o700, 0, program, 0, 0),
        ("network-transaction", stat.S_IFREG | 0o555, 0, harness, 0, 0),
    ]
    entries += list(libraries)
    entries += [("TRAILER!!!", 0, 0, b"", 0, 0)]
    return cpio(entries)


def package(base, libraries, plan, backup, pin, build, output, *, session=None):
    output = private_path(output)
    if output.parent.stat().st_mode & 0o077:
        raise ValueError("owner-only private profile parent required")
    bound = pinned_plan(plan, backup, pin)
    blobs, kernel, digest = base_check(base)
    native = native_libraries(libraries)
    build = Path(build).absolute()
    if build.resolve() != build or not build.is_relative_to(ROOT / "build"):
        raise ValueError("fresh repository build path required")
    build.mkdir(mode=0o700, exist_ok=False)
    session = os.urandom(32) if session is None else session
    if type(session) is not bytes or len(session) != 32:
        raise ValueError("fresh32-byte session required")
    (build / "session.h").write_text(
        "static const unsigned char hearth_session[32]={" + ",".join(map(str, session)) + "};\n"
    )
    (build / "plan.h").write_bytes(bound["header"])
    (build / "plan.h").chmod(0o600)
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
        "-fomit-frame-pointer",
        "-fuse-ld=lld",
        "-nostdlib",
        "-Wl,--build-id=none",
        "-I" + str(build),
    ]
    imports = set(IMPORTS) | {"strstr", "memcpy", "malloc", "free"}
    stub = build / "libc.stub.c"
    stub.write_text("\n".join(f"long {name}(void) {{ return 0; }}" for name in sorted(imports)))
    run(
        common
        + ["-shared", "-fPIC", "-Wl,-soname,libc.so.6", str(stub), "-o", str(build / "libc.so.6")]
    )
    run(
        common
        + [
            "-no-pie",
            "-Wl,-e,_start,--dynamic-linker=/lib/ld-linux-armhf.so.3",
            "-DHEARTH_RAM_LAB",
            "-DHEARTH_NETWORK_ADAPTER",
            "-Wl,--wrap=write,--wrap=read,--wrap=fsync,--wrap=renameat,--wrap=fchmod,--wrap=fchown",
            *[
                str(ROOT / name)
                for name in (
                    "firmware/tls_probe/start.S",
                    "tests/network_transaction_harness.c",
                    "firmware/file_install/posix.c",
                    "firmware/file_install/transaction.c",
                )
            ],
            str(build / "libc.so.6"),
            "-o",
            str(build / "network-transaction"),
        ]
    )
    run(
        common
        + [
            "-static",
            "-Wl,-e,_start",
            *[
                str(ROOT / name)
                for name in (
                    "firmware/network_probe/init.c",
                    "firmware/network_snapshot/reader.c",
                    "firmware/network_update/ram.c",
                    "firmware/network_update/stream.c",
                    "firmware/network_update/hash.c",
                )
            ],
            "-o",
            str(build / "init"),
        ]
    )
    program = read_build(build / "init", 65536)
    harness = read_build(build / "network-transaction", 1048576)
    root = archive(program, harness, native)
    files = {
        name: blobs[name]
        for name in ("kernel.config", "x-load-gen2.bin", "u-boot.bin", "omap_loader")
    }
    files |= {
        "init": program,
        "network-transaction": harness,
        "rootfs.cpio": root,
        "uImage": multi_image(kernel, root),
        "fallback-init": blobs["probe-init"],
    }
    if len(files["uImage"]) > MAX_IMAGE or len(root) > MAX_ROOT:
        raise ValueError("protected image load bound exceeded")
    output.mkdir(mode=0o700)
    (output / "artifacts").mkdir(mode=0o700)
    for name, data in files.items():
        path = output / "artifacts" / name
        with path.open("xb") as stream:
            path.chmod(0o700 if name == "omap_loader" else 0o600)
            stream.write(data)
    record = {
        "status": STATUS,
        "device_executed": False,
        "session": session.hex(),
        "base": str(Path(base).absolute()),
        "base_manifest_sha256": digest,
        "libraries": str(Path(libraries).absolute()),
        "plan": str(Path(plan).absolute()),
        "backup": str(Path(backup).absolute()),
        "pin": str(Path(pin).absolute()),
        "recipes": recipes(),
        "files": {name: sha(data) for name, data in files.items()},
    }
    path = output / "profile.json"
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    path.chmod(0o600)
    return check(output)


def check(output):
    output = private_path(output)
    record = json.loads(private_read(output / "profile.json", 65536))
    if (
        record["status"] != STATUS
        or record["device_executed"] is not False
        or record["recipes"] != recipes()
        or set(record["files"]) != FILES
        or len(bytes.fromhex(record["session"])) != 32
    ):
        raise ValueError("network RAM preflight source/scope differs")
    pinned_plan(record["plan"], record["backup"], record["pin"])
    blobs, kernel, digest = base_check(record["base"])
    if digest != record["base_manifest_sha256"]:
        raise ValueError("protected kernel identity differs")
    files = {name: private_read(output / "artifacts" / name, MAX_IMAGE) for name in FILES}
    if any(sha(data) != record["files"][name] for name, data in files.items()):
        raise ValueError("protected RAM artifact differs")
    for name in ("kernel.config", "x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        if files[name] != blobs[name]:
            raise ValueError("protected bootstrap differs")
    actual_kernel, root = split_multi(files["uImage"])
    expected = archive(
        files["init"], files["network-transaction"], native_libraries(record["libraries"])
    )
    if (
        actual_kernel != kernel
        or files["fallback-init"] != blobs["probe-init"]
        or root != files["rootfs.cpio"]
        or root != expected
    ):
        raise ValueError("exact private RAM archive required")
    if len(parse_cpio(root)) != 32:
        raise ValueError("fixed protected RAM inventory required")
    return {
        "status": "protected-network-ram-preflight-checked",
        "device_executed": False,
        "stream_cases": 41,
        "transaction_cases": 20,
        "real_targets": 4,
        "flash_writes": "disabled-in-kernel",
        "persistent_commit_supported": False,
        "image_bytes": len(files["uImage"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pack = sub.add_parser("package")
    for name in ("base", "libraries", "plan", "backup", "pin", "build", "output"):
        pack.add_argument("--" + name, required=True)
    sub.add_parser("check").add_argument("output")
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(package(**args) if command == "package" else check(args["output"]), indent=2))
