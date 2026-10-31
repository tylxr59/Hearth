"""Private file-action image packaging and passive checks; never opens USB.

Only libc and its interpreter execute from the retained native libraries. The
capsule-bearing action is root-readable/executable only. Link stubs never ship.
"""

import argparse
import gzip
import json
import os
import re
import stat
import struct
import subprocess  # nosec B404
import zlib
from pathlib import Path

from firmware.file_snapshot import prepare as snapshot
from firmware.file_writer import compile, configure, prepare
from firmware.probe.check import FILES as KERNEL_FILES
from firmware.probe.configure import initramfs
from firmware.settings_probe.artifact import inventory, parse_cpio
from firmware.tls_probe.check import check as check_base
from firmware.tls_probe.check import split_multi, zimage_payload
from firmware.tls_probe.package import (
    MAX_IMAGE,
    MAX_ROOT,
    cpio,
    helper_interpreter,
    multi_image,
    private_read,
    sha,
    unpack_image,
)
from provisioning.file_capsule import check as check_capsule
from tools.elf_review import ArmElf, private_path

ROOT = Path(__file__).resolve().parents[2]
STATUS = "experimental-private-file-action-preflight-v1"
FILES = {
    "uImage",
    "rootfs.cpio",
    "kernel.config",
    "x-load-gen2.bin",
    "u-boot.bin",
    "omap_loader",
    "fallback-init",
}
LIBRARIES = {"lib/libc.so.6", "lib/ld-linux-armhf.so.3"}


def recipes():
    paths = set(compile.SOURCES) | set(prepare.RECIPES) | set(snapshot.RECIPES)
    for folder in ("file_writer", "file_install"):
        paths |= {
            p.relative_to(ROOT).as_posix()
            for p in (ROOT / "firmware" / folder).iterdir()
            if p.is_file() and p.suffix in (".py", ".c", ".h", ".sh", ".json")
        }
    paths |= {
        "tools/elf_review.py",
        "backend/validation.py",
        "firmware/probe/observe.py",
        "firmware/settings_compat_probe/observe.py",
        "firmware/tls_probe/check.py",
        "firmware/tls_probe/package.py",
    }
    return {name: sha((ROOT / name).read_bytes()) for name in sorted(paths)}


def read_build(path, limit):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_relative_to(ROOT / "build"):
        raise ValueError("generated build path without symlinks required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
            raise ValueError("bounded generated file required")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("generated file exceeded bound")
        return data
    finally:
        os.close(fd)


def kernel_check(root):
    """Checks data with trusted repository code; never executes a staged script."""
    root = Path(root).absolute()
    record = json.loads(read_build(root / "probe-manifest.json", 65536))
    provenance = json.loads(read_build(root / "writer-kernel-preparation.json", 65536))
    expected_hosts = (
        set(snapshot.RECIPES)
        | set(prepare.RECIPES)
        | {"configure.py", "check.py", "session.h", "build.sh", "binding.h"}
    )
    if (
        record.get("status") != "experimental-file-writer-kernel-no-launcher"
        or set(record["files"]) != KERNEL_FILES
        or set(record["host_files"]) != expected_hosts
    ):
        raise ValueError("unexpected writer kernel inventory/scope")
    for name in expected_hosts:
        if sha(read_build(root / name, 65536)) != record["host_files"][name]:
            raise ValueError("writer kernel host recipe changed")
    for name, expected in provenance["recipes"].items():
        if name not in expected_hosts or sha((ROOT / name).read_bytes()) != expected:
            raise ValueError("writer source changed since build")
    blobs = {name: read_build(root / "artifacts" / name, 4 * 1024 * 1024) for name in KERNEL_FILES}
    if any(sha(value) != record["files"][name] for name, value in blobs.items()):
        raise ValueError("writer kernel artifact changed")
    configure.verify(blobs["kernel.config"].decode())
    tree = root / "src/Dev/linux"
    driver = tree / "drivers/mtd/nand/omap2.c"
    if read_build(driver, 65536).decode() != configure.patch_driver(
        read_build(driver.with_suffix(".hearth-original"), 65536).decode()
    ):
        raise ValueError("writer kernel driver changed")
    for name in ("core.c", "core.h", "io.h", "adapter.h"):
        if (
            read_build(driver.parent / "hearth-file-writer" / name, 65536)
            != (ROOT / "firmware/file_writer" / name).read_bytes()
        ):
            raise ValueError("writer gate source changed")
    if (
        read_build(driver.parent / "hearth-metadata-readonly.h", 65536)
        != (ROOT / "firmware/nand_metadata/readonly.h").read_bytes()
    ):
        raise ValueError("initial protection source changed")
    if (
        read_build(driver.parent / "hearth-file-writer/binding.h", 65536)
        != prepare.binding(provenance["capsule"], provenance["pin"]).encode()
    ):
        raise ValueError("kernel host custody binding changed")
    sources = json.loads((ROOT / "firmware/file_writer/sources.json").read_text())
    for name, expected in sources["files"].items():
        if sha(read_build(tree / name, 256 * 1024)) != expected:
            raise ValueError("critical kernel source changed")
    fs = tree / "fs/jffs2/fs.c"
    if read_build(fs, 65536).decode() != configure.patch_remount(
        read_build(fs.with_suffix(".hearth-writer-original"), 65536).decode()
    ):
        raise ValueError("read-only compatibility protection changed")
    for name, patch in (
        ("scripts/mkcompile_h", configure.base.patch_build_metadata),
        ("drivers/usb/gadget/u_serial.c", configure.base.patch_serial),
        ("arch/arm/mach-omap2/Kconfig", configure.base.disable_clock_updates),
    ):
        path = tree / name
        if read_build(path, 65536).decode() != patch(
            read_build(path.with_suffix(".hearth-snapshot-original"), 65536).decode()
        ):
            raise ValueError("writer setup source changed")
    if blobs["kernel.config"] != read_build(tree / ".config", 65536):
        raise ValueError("writer saved kernel config differs")
    if blobs["uImage"] != read_build(tree / "arch/arm/boot/uImage", 4 * 1024 * 1024):
        raise ValueError("writer saved kernel image differs")
    kernel = unpack_image(blobs["uImage"], 2)
    zimage_payload(kernel, blobs["probe-init"])
    return record, provenance, blobs, kernel


def elf_metadata(data):
    """Static readelf on a passed anonymous descriptor, never ELF execution."""
    ArmElf(data)
    fd = os.memfd_create("hearth-passive-elf-review", os.MFD_CLOEXEC)
    try:
        at = 0
        while at < len(data):
            amount = os.write(fd, data[at:])
            if amount <= 0:
                raise OSError("ELF metadata buffer incomplete")
            at += amount
        result = subprocess.run(  # nosec B603 B607
            ["readelf", "--wide", "--dyn-syms", "--dynamic", f"/proc/self/fd/{fd}"],
            pass_fds=(fd,),
            capture_output=True,
            check=True,
            timeout=10,
            text=True,
        ).stdout
    finally:
        os.close(fd)
    needed = set(re.findall(r"\(NEEDED\).*?\[(.*?)\]", result))
    if re.search(r"\((?:RPATH|RUNPATH)\)", result):
        raise ValueError("unexpected dynamic search path")
    imported, exported = set(), set()
    for line in result.splitlines():
        fields = line.split()
        if len(fields) >= 8 and fields[0].endswith(":") and fields[4] in ("GLOBAL", "WEAK"):
            name = fields[7].split("@")[0]
            if fields[6] != "UND":
                exported.add(name)
            elif fields[4] == "GLOBAL":
                imported.add(name)
    return needed, imported, exported


def native_libraries(base):
    check_base(base)
    entries = parse_cpio(private_read(Path(base) / "artifacts/rootfs.cpio", MAX_ROOT))
    selected = [row for row in entries if row[0] in LIBRARIES]
    if len(selected) != 2:
        raise ValueError("exact native libc/interpreter pair required")
    for name, mode, uid, data, major, minor in selected:
        expected = stat.S_IFREG | (0o555 if name.endswith("ld-linux-armhf.so.3") else 0o444)
        if (mode, uid, major, minor) != (expected, 0, 0, 0):
            raise ValueError("native execution library metadata changed")
        needed, _, _ = elf_metadata(data)
        if needed != ({"ld-linux-armhf.so.3"} if name.endswith("libc.so.6") else set()):
            raise ValueError("native dependency closure changed")
    return selected


def validate_entries(
    entries, action, expected_action, expected_bootstrap, expected_selftest, libraries
):
    names = [row[0] for row in entries]
    expected = {
        ".",
        "dev",
        "proc",
        "sys",
        "lib",
        "state",
        "native",
        "user",
        "dev/console",
        "init",
        "file-action",
        "file-selftest",
        "TRAILER!!!",
    } | LIBRARIES
    if (
        set(names) != expected
        or len(names) != len(expected)
        or type(action) is not int
        or action not in (1, 2)
    ):
        raise ValueError("unexpected writer archive scope")
    by_name = {row[0]: row for row in entries}
    for name in (".", "dev", "proc", "sys", "lib", "native", "user", "state"):
        _, mode, uid, data, major, minor = by_name[name]
        permissions = 0o700 if name in ("native", "user", "state") else 0o755
        if (mode, uid, data, major, minor) != (
            stat.S_IFDIR | permissions,
            65534 if name == "state" else 0,
            b"",
            0,
            0,
        ):
            raise ValueError("writer directory permissions changed")
    if by_name["dev/console"][1:] != (stat.S_IFCHR | 0o600, 0, b"", 5, 1):
        raise ValueError("writer console node changed")
    for name, permissions, expected_data in (
        ("init", 0o555, expected_bootstrap),
        ("file-action", 0o500, expected_action),
        ("file-selftest", 0o555, expected_selftest),
    ):
        _, mode, uid, data, major, minor = by_name[name]
        if (mode, uid, data, major, minor) != (stat.S_IFREG | permissions, 0, expected_data, 0, 0):
            raise ValueError("writer program/data permissions or bytes changed")
        if name == "init":
            initramfs(data)  # Static original ARM program, no interpreter.
        else:
            helper_interpreter(data)
            if struct.unpack_from("<H", data, 16)[0] != 2:
                raise ValueError("fixed ARM executable required")
    for row in libraries:
        if by_name[row[0]] != row:
            raise ValueError("native execution library differs")
    if by_name["TRAILER!!!"][1:] != (0, 0, b"", 0, 0):
        raise ValueError("archive trailer changed")
    _, _, exports = elf_metadata(by_name["lib/libc.so.6"][3])
    for name in ("file-action", "file-selftest"):
        needed, imported, _ = elf_metadata(by_name[name][3])
        if needed != {"libc.so.6"} or imported - exports:
            raise ValueError("helper native ABI/dependency mismatch")


def package(kernel_root, base, helpers, capsule, pin, output, action):
    if type(action) is not int or action not in (1, 2):
        raise ValueError("explicit install or restore profile required")
    output, capsule, pin = private_path(output), private_path(capsule), private_path(pin)
    if not output.parent.is_dir() or output.parent.stat().st_mode & 0o077:
        raise ValueError("existing owner-only private output parent required")
    plan = prepare.pin_read(pin)
    check_capsule(capsule, expected_plan=plan)
    kernel_record, provenance, blobs, kernel = kernel_check(kernel_root)
    if (
        provenance["plan"] != plan.hex()
        or prepare.binding(capsule, pin)
        != read_build(Path(kernel_root) / "binding.h", 65536).decode()
    ):
        raise ValueError("kernel/capsule plan binding differs")
    helpers = Path(helpers)
    compiled = json.loads(read_build(helpers / "helpers.json", 65536))
    if (
        compiled.get("status") != "private-file-action-helpers-unexecuted"
        or compiled["source_sha256"] != compile.source_hashes()
        or compiled["plan"] != plan.hex()
        or compiled["selftest_cases"] != 56
        or compiled["stub_not_for_target"] is not True
        or compiled["binding_sha256"] != sha(prepare.binding(capsule, pin).encode())
        or compiled["capsule_header_sha256"]
        != sha(private_read(capsule / "capsule.h", 96 * 1024 * 1024))
    ):
        raise ValueError("action helpers changed")
    if set(compiled["files"]) != {
        "file-install",
        "file-restore",
        "install-init",
        "restore-init",
        "file-selftest",
    }:
        raise ValueError("unexpected original helper set")
    programs = {name: read_build(helpers / name, 2 * 1024 * 1024) for name in compiled["files"]}
    if any(sha(data) != compiled["files"][name] for name, data in programs.items()):
        raise ValueError("original action helper bytes changed")
    libraries = native_libraries(base)
    action_data = programs["file-install" if action == 1 else "file-restore"]
    bootstrap = programs["install-init" if action == 1 else "restore-init"]
    entries = [
        (
            name,
            stat.S_IFDIR | (0o700 if name in ("state", "native", "user") else 0o755),
            65534 if name == "state" else 0,
            b"",
            0,
            0,
        )
        for name in (".", "dev", "proc", "sys", "lib", "state", "native", "user")
    ]
    entries += [
        ("dev/console", stat.S_IFCHR | 0o600, 0, b"", 5, 1),
        ("init", stat.S_IFREG | 0o555, 0, bootstrap, 0, 0),
        ("file-action", stat.S_IFREG | 0o500, 0, action_data, 0, 0),
        ("file-selftest", stat.S_IFREG | 0o555, 0, programs["file-selftest"], 0, 0),
    ]
    entries += libraries + [("TRAILER!!!", 0, 0, b"", 0, 0)]
    validate_entries(entries, action, action_data, bootstrap, programs["file-selftest"], libraries)
    archive = cpio(entries)
    files = {
        name: blobs[name]
        for name in ("kernel.config", "x-load-gen2.bin", "u-boot.bin", "omap_loader")
    }
    files |= {
        "fallback-init": blobs["probe-init"],
        "rootfs.cpio": archive,
        "uImage": multi_image(kernel, gzip.compress(archive, mtime=0)),
    }
    if len(archive) > MAX_ROOT or len(files["uImage"]) > MAX_IMAGE:
        raise ValueError("writer RAM image exceeds reviewed load regions")
    output.mkdir(mode=0o700, exist_ok=False)
    (output / "artifacts").mkdir(mode=0o700)
    for name, data in files.items():
        path = output / "artifacts" / name
        with path.open("xb") as stream:
            path.chmod(0o700 if name == "omap_loader" else 0o600)
            stream.write(data)
    record = {
        "status": STATUS,
        "action": action,
        "device_executed": False,
        "plan": plan.hex(),
        "capsule": str(capsule),
        "pin": str(pin),
        "kernel": str(Path(kernel_root).absolute()),
        "base": str(private_path(base)),
        "helpers": str(helpers.absolute()),
        "selftest_cases": 56,
        "kernel_manifest_sha256": sha(read_build(Path(kernel_root) / "probe-manifest.json", 65536)),
        "kernel_files": kernel_record["files"],
        "helpers_files": compiled["files"],
        "recipes": recipes(),
        "files": {name: sha(data) for name, data in files.items()},
        "root_inventory": inventory(entries),
    }
    path = output / "file-action-profile.json"
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    path.chmod(0o600)
    return check(output)


def check(root):
    root = private_path(root)
    record = json.loads(private_read(root / "file-action-profile.json", 1024 * 1024))
    if (
        record.get("status") != STATUS
        or record.get("device_executed") is not False
        or record["recipes"] != recipes()
        or type(record["action"]) is not int
        or record["action"] not in (1, 2)
        or record["selftest_cases"] != 56
        or set(record["files"]) != FILES
    ):
        raise ValueError("file-action profile scope/source changed")
    plan = prepare.pin_read(record["pin"])
    if plan.hex() != record["plan"]:
        raise ValueError("external file-action plan pin differs")
    check_capsule(record["capsule"], expected_plan=plan)
    kernel_record, provenance, kernel_files, kernel = kernel_check(record["kernel"])
    if (
        kernel_record["files"] != record["kernel_files"]
        or provenance["plan"] != plan.hex()
        or prepare.binding(record["capsule"], record["pin"])
        != read_build(Path(record["kernel"]) / "binding.h", 65536).decode()
        or sha(read_build(Path(record["kernel"]) / "probe-manifest.json", 65536))
        != record["kernel_manifest_sha256"]
    ):
        raise ValueError("original writer kernel changed")
    blobs = {name: private_read(root / "artifacts" / name, MAX_ROOT) for name in FILES}
    if any(sha(data) != record["files"][name] for name, data in blobs.items()):
        raise ValueError("file-action artifact changed")
    for name in ("kernel.config", "x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        if blobs[name] != kernel_files[name]:
            raise ValueError("file-action bootstrap changed")
    if blobs["fallback-init"] != kernel_files["probe-init"] or len(blobs["uImage"]) > MAX_IMAGE:
        raise ValueError("file-action fallback/load bound changed")
    configure.verify(blobs["kernel.config"].decode())
    image_kernel, compressed = split_multi(blobs["uImage"])
    if image_kernel != kernel:
        raise ValueError("file-action kernel payload differs")
    zimage_payload(image_kernel, blobs["fallback-init"])
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    archive = decoder.decompress(compressed, MAX_ROOT + 1)
    if (
        not decoder.eof
        or decoder.unused_data
        or len(archive) > MAX_ROOT
        or archive != blobs["rootfs.cpio"]
    ):
        raise ValueError("file-action RAM archive differs/exceeds bound")
    helpers = Path(record["helpers"])
    compiled = json.loads(read_build(helpers / "helpers.json", 65536))
    if (
        compiled["source_sha256"] != compile.source_hashes()
        or compiled["files"] != record["helpers_files"]
        or compiled["plan"] != plan.hex()
        or compiled["binding_sha256"]
        != sha(prepare.binding(record["capsule"], record["pin"]).encode())
        or compiled["capsule_header_sha256"]
        != sha(private_read(Path(record["capsule"]) / "capsule.h", 96 * 1024 * 1024))
    ):
        raise ValueError("file-action original helper compilation changed")
    action_name = "file-install" if record["action"] == 1 else "file-restore"
    init_name = "install-init" if record["action"] == 1 else "restore-init"
    expected_programs = {
        name: read_build(helpers / name, 2 * 1024 * 1024)
        for name in (action_name, init_name, "file-selftest")
    }
    if any(sha(data) != compiled["files"][name] for name, data in expected_programs.items()):
        raise ValueError("file-action original programs changed")
    entries = parse_cpio(archive)
    validate_entries(
        entries,
        record["action"],
        expected_programs[action_name],
        expected_programs[init_name],
        expected_programs["file-selftest"],
        native_libraries(record["base"]),
    )
    if inventory(entries) != record["root_inventory"]:
        raise ValueError("file-action complete RAM inventory differs")
    return {
        "status": "file-action-offline-preflight-checked",
        "action": record["action"],
        "selftest_cases": 56,
        "targets": 9,
        "device_executed": False,
        "installed": False,
        "image_bytes": len(blobs["uImage"]),
        "rootfs_bytes": len(archive),
        "recovery": "unverified",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("package")
    for name in ("kernel-root", "base", "helpers", "capsule", "pin", "output"):
        create.add_argument("--" + name, required=True)
    create.add_argument("--action", required=True, type=int, choices=(1, 2))
    sub.add_parser("check").add_argument("root")
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(package(**args) if command == "package" else check(args["root"]), indent=2))
