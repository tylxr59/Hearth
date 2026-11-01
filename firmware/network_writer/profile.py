"""Offline four-file install/restore pair. No USB, commands or authorization.

Original firmware is packaged as root-only, non-executable opaque DATA. Only
original public helpers and the verified libc/interpreter pair execute on target.
"""

import argparse
import gzip
import json
import stat
import struct
from pathlib import Path

from firmware.file_writer.profile import elf_metadata, native_libraries
from firmware.network_probe.profile import archive as matrix_archive
from firmware.network_probe.profile import pinned_plan
from firmware.network_probe.profile import recipes as matrix_recipes
from firmware.network_snapshot.profile import read_build
from firmware.network_writer import kernel
from firmware.network_writer.compile import IMPORT_SET, compile_helpers
from firmware.probe.configure import initramfs
from firmware.settings_probe.artifact import parse_cpio
from firmware.tls_probe.check import split_multi
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
from provisioning.network_backup import load
from tools.elf_review import private_path

ROOT = Path(__file__).resolve().parents[2]
STATUS = "private-root0-network-action-unexecuted"
FILES = {
    "uImage",
    "rootfs.cpio",
    "kernel.config",
    "x-load-gen2.bin",
    "u-boot.bin",
    "omap_loader",
    "fallback-init",
    "init",
    "file-action",
    "network-transaction",
}


def recipes():
    names = set(matrix_recipes()) | set(kernel.RECIPES)
    for folder in ("network_writer", "file_writer", "file_reencode"):
        names |= {
            p.relative_to(ROOT).as_posix()
            for p in (ROOT / "firmware" / folder).iterdir()
            if p.suffix in (".py", ".c", ".h", ".json")
        }
    return {n: sha((ROOT / n).read_bytes()) for n in sorted(names)}


def execution_policy(data):
    # ELF32 little-endian ARM already checked by elf_metadata. No executable
    # stack or writable executable LOAD segment is needed by original helpers.
    elf_metadata(data)
    h = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    stack = []
    for i in range(h[10]):
        kind, _, _, _, _, _, flags, _ = struct.unpack_from("<8I", data, h[5] + i * h[9])
        if kind == 0x6474E551:
            stack.append(flags)
        if kind == 1 and flags & 1 and flags & 2:
            raise ValueError("writable executable helper segment refused")
    if len(stack) != 1 or stack[0] & 1:
        raise ValueError("explicit non-executable helper stack required")


def archive(program, action, harness, libraries, backup):
    initramfs(program)
    needed, imports, _ = elf_metadata(action)
    if (
        needed != {"libc.so.6"}
        or not imports <= IMPORT_SET
        or helper_interpreter(action) != "/lib/ld-linux-armhf.so.3"
    ):
        raise ValueError("standalone original action closure differs")
    library = [r[3] for r in libraries if r[0] == "lib/libc.so.6"]
    if len(library) != 1:
        raise ValueError("exact native libc export evidence required")
    exports = elf_metadata(library[0])[2]
    for helper in (action, harness):
        execution_policy(helper)
        if not elf_metadata(helper)[1] <= exports:
            raise ValueError("helper imports absent from preserved native libc")
    entries = parse_cpio(matrix_archive(program, harness, libraries))[:-1]
    entries += [(n, stat.S_IFDIR | 0o700, 0, b"", 0, 0) for n in ("native", "archive", "originals")]
    entries += [("file-action", stat.S_IFREG | 0o700, 0, action, 0, 0)]
    snapshot = load(backup)
    entries += [
        (f"originals/{i}", stat.S_IFREG | 0o400, 0, r.data, 0, 0)
        for i, r in enumerate(snapshot.records)
    ]
    entries += [("TRAILER!!!", 0, 0, b"", 0, 0)]
    raw = cpio(entries)
    if len(entries) != 40 or len(raw) > MAX_ROOT:
        raise ValueError("fixed40-entry bounded network action archive required")
    return raw


def package(kernel_build, libraries, plan, backup, pin, build, output, *, action):
    if type(action) is not int or action not in (1, 2):
        raise ValueError("install1/restore2 only")
    output = private_path(output)
    if output.parent.stat().st_mode & 0o077:
        raise ValueError("owner-only output parent required")
    record = kernel.check(kernel_build)
    if any(
        str(Path(v).absolute()) != record[k]
        for k, v in (("plan", plan), ("backup", backup), ("pin", pin))
    ):
        raise ValueError("exact kernel plan/receipt custody required")
    bound = pinned_plan(plan, backup, pin)
    build = Path(build).absolute()
    compile_helpers(build, plan, backup, pin)
    files = {
        n: read_build(Path(kernel_build) / "artifacts" / n, MAX_IMAGE)
        for n in ("kernel.config", "x-load-gen2.bin", "u-boot.bin", "omap_loader")
    }
    files |= {
        "init": read_build(build / f"init-{action}", 65536),
        "file-action": read_build(build / f"action-{action}", 1048576),
        "network-transaction": read_build(build / "network-transaction", 1048576),
        "fallback-init": read_build(Path(kernel_build) / "artifacts/probe-init", 65536),
    }
    raw = archive(
        files["init"],
        files["file-action"],
        files["network-transaction"],
        native_libraries(libraries),
        backup,
    )
    payload = unpack_image(read_build(Path(kernel_build) / "artifacts/uImage", MAX_IMAGE), 2)
    files |= {"rootfs.cpio": raw, "uImage": multi_image(payload, gzip.compress(raw, mtime=0))}
    if len(files["uImage"]) > MAX_IMAGE:
        raise ValueError("reviewed USB image load bound exceeded")
    output.mkdir(mode=0o700, exist_ok=False)
    (output / "artifacts").mkdir(mode=0o700)
    for n, d in files.items():
        path = output / "artifacts" / n
        with path.open("xb") as f:
            path.chmod(0o700 if n == "omap_loader" else 0o600)
            f.write(d)
    profile = {
        "status": STATUS,
        "device_executed": False,
        "action": action,
        "kernel": str(Path(kernel_build).absolute()),
        "libraries": str(Path(libraries).absolute()),
        "plan_path": str(Path(plan).absolute()),
        "backup": str(Path(backup).absolute()),
        "pin": str(Path(pin).absolute()),
        "plan": bound["plan"].hex(),
        "receipt": bound["receipt"].hex(),
        "recipes": recipes(),
        "files": {n: sha(d) for n, d in files.items()},
    }
    p = output / "profile.json"
    p.write_text(json.dumps(profile, sort_keys=True, indent=2) + "\n")
    p.chmod(0o600)
    return check(output)


def check(output):
    output = private_path(output)
    if (
        output.stat().st_mode & 0o777 != 0o700
        or (output / "artifacts").stat().st_mode & 0o777 != 0o700
    ):
        raise ValueError("owner-only profile/artifact directories required")
    for name in ("profile.json", *("artifacts/" + n for n in FILES)):
        path = output / name
        meta = path.stat()
        expected = 0o700 if name == "artifacts/omap_loader" else 0o600
        if (
            path.is_symlink()
            or not stat.S_ISREG(meta.st_mode)
            or meta.st_nlink != 1
            or meta.st_mode & 0o777 != expected
        ):
            raise ValueError("exact private regular artifact permissions required")
    record = json.loads(private_read(output / "profile.json", 65536))
    if (
        record["status"] != STATUS
        or record["device_executed"] is not False
        or type(record["action"]) is not int
        or record["action"] not in (1, 2)
        or record["recipes"] != recipes()
        or set(record["files"]) != FILES
    ):
        raise ValueError("exact original network action scope/source required")
    provenance = kernel.check(record["kernel"])
    source_pins = json.loads((ROOT / "firmware/file_writer/sources.json").read_bytes())["files"]
    tree = Path(record["kernel"]) / "src/Dev/linux"
    if any(
        sha(read_build(tree / n, 256 * 1024)) != expected for n, expected in source_pins.items()
    ):
        raise ValueError("critical NAND/partition/filesystem source differs")
    if (
        any(record[k] != provenance[k] for k in ("backup", "pin"))
        or record["plan_path"] != provenance["plan"]
    ):
        raise ValueError("network kernel custody changed")
    bound = pinned_plan(record["plan_path"], record["backup"], record["pin"])
    if bound["plan"].hex() != record["plan"] or bound["receipt"].hex() != record["receipt"]:
        raise ValueError("exact plan/receipt changed")
    files = {
        n: private_read(output / "artifacts" / n, MAX_ROOT if n == "rootfs.cpio" else MAX_IMAGE)
        for n in FILES
    }
    if any(sha(d) != record["files"][n] for n, d in files.items()):
        raise ValueError("network artifact changed")
    for n in ("kernel.config", "x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        if files[n] != read_build(Path(record["kernel"]) / "artifacts" / n, MAX_IMAGE):
            raise ValueError("root0-only kernel/bootstrap differs")
    payload, compressed = split_multi(files["uImage"])
    expected_kernel = unpack_image(
        read_build(Path(record["kernel"]) / "artifacts/uImage", MAX_IMAGE), 2
    )
    raw = archive(
        files["init"],
        files["file-action"],
        files["network-transaction"],
        native_libraries(record["libraries"]),
        record["backup"],
    )
    if (
        payload != expected_kernel
        or files["rootfs.cpio"] != raw
        or compressed != gzip.compress(raw, mtime=0)
        or files["fallback-init"]
        != read_build(Path(record["kernel"]) / "artifacts/probe-init", 65536)
    ):
        raise ValueError("exact checked kernel/private DATA archive required")
    return {
        "status": "network-action-offline-checked",
        "action": record["action"],
        "device_executed": False,
        "targets": 4,
        "ram_cases": 61,
        "image_bytes": len(files["uImage"]),
        "root0_only": True,
        "recovery": "whole-firmware-unverified",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pack = sub.add_parser("package")
    for name in ("kernel-build", "libraries", "plan", "backup", "pin", "build", "output"):
        pack.add_argument("--" + name, required=True)
    pack.add_argument("--action", type=int, required=True)
    sub.add_parser("check").add_argument("output")
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(package(**args) if command == "package" else check(args["output"]), indent=2))
