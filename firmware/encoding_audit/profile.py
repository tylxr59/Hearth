"""Read-only ioctl extension of the protected, write-denying snapshot kernel."""

import json
import os
import shutil
import subprocess  # nosec B404
from pathlib import Path

from firmware.file_writer.configure import patch_ioctl
from firmware.startup_diagnostic import profile as base
from firmware.tls_probe.package import multi_image
from tools.elf_review import private_path

ROOT = base.ROOT


def ioctl_source(original):
    patched = patch_ioctl(original)
    before = "return hearth_encoding_check(filp, cmd, arg);"
    if patched.count(before) != 1:
        raise ValueError("exact read-only encoding dispatch required")
    return patched.replace(
        before,
        "return cmd==0x4872U ? hearth_encoding_types(filp,cmd,arg) : hearth_encoding_check(filp,cmd,arg);",
    )


def encoding_header():
    return (ROOT / "firmware/file_writer/encoding.h").read_bytes() + (
        ROOT / "firmware/encoding_audit/codecs.h"
    ).read_bytes()


def archive_name(plan):
    if plan is None:
        return ".hearth-rollback"
    if type(plan) is not bytes or len(plan) != 32 or plan == bytes(32):
        raise ValueError("exact nonzero archive plan required")
    return ".hearth-rollback-" + plan.hex()


SCRIPT = """#!/bin/sh
set -eu
export ARCH=arm CROSS_COMPILE=arm-none-linux-gnueabi-
export KBUILD_BUILD_USER=hearth KBUILD_BUILD_HOST=isolated-builder
export KBUILD_BUILD_TIMESTAMP='Fri Oct 30 00:00:00 UTC 2026'
export SOURCE_DATE_EPOCH=1793318400 KCONFIG_NOTIMESTAMP=1
cd /work/src/Dev/linux
make -j4 uImage
cp arch/arm/boot/uImage /work/artifacts/uImage
"""


def stage(parent, output):
    parent, output = Path(parent).absolute(), Path(output).absolute()
    _, _, digest = base.base_check(parent)
    if output.resolve() != output or not output.is_relative_to(ROOT / "build") or output.exists():
        raise ValueError("fresh repository build directory required")
    shutil.copytree(parent, output, symlinks=True)
    fs = output / "src/Dev/linux/fs/jffs2"
    original = base.read_build(fs / "ioctl.c", 65536)
    (fs / "ioctl.encoding-audit-original").write_bytes(original)
    (fs / "ioctl.c").write_text(ioctl_source(original.decode()))
    (fs / "hearth-encoding.h").write_bytes(encoding_header())
    (output / "build-encoding.sh").write_text(SCRIPT)
    (output / "encoding-derivation.json").write_text(
        json.dumps({"parent": str(parent), "parent_manifest_sha256": digest})
    )


def finalize(root):
    root = Path(root).absolute()
    manifest = json.loads(base.read_build(root / "probe-manifest.json", 65536))
    manifest["files"]["uImage"] = base.sha(base.read_build(root / "artifacts/uImage", 4 * 1048576))
    (root / "probe-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return kernel_check(root)


def kernel_check(root):
    root = Path(root).absolute()
    derivation = json.loads(base.read_build(root / "encoding-derivation.json", 4096))
    parent_files, _, parent_digest = base.base_check(derivation["parent"])
    if derivation != {
        "parent": str(Path(derivation["parent"]).absolute()),
        "parent_manifest_sha256": parent_digest,
    }:
        raise ValueError("protected parent derivation changed")
    files, kernel, digest = base.base_check(root)
    fs = root / "src/Dev/linux/fs/jffs2"
    original = base.read_build(Path(derivation["parent"]) / "src/Dev/linux/fs/jffs2/ioctl.c", 65536)
    if (
        base.read_build(fs / "ioctl.encoding-audit-original", 65536) != original
        or base.read_build(fs / "ioctl.c", 65536).decode() != ioctl_source(original.decode())
        or base.read_build(fs / "hearth-encoding.h", 65536) != encoding_header()
        or base.read_build(root / "build-encoding.sh", 4096).decode() != SCRIPT
        or any(files[n] != parent_files[n] for n in files if n != "uImage")
    ):
        raise ValueError("read-only kernel extension differs from reviewed source")
    return files, kernel, digest


def recipes():
    names = set(base.recipes()) | {
        "firmware/file_writer/encoding.h",
        "firmware/file_writer/configure.py",
        "firmware/file_install/targets.h",
        "firmware/network_update/hash.c",
        "firmware/network_update/hash.h",
    }
    names |= {
        p.relative_to(ROOT).as_posix()
        for p in Path(__file__).parent.iterdir()
        if p.suffix in (".py", ".c", ".h")
    }
    return {n: base.sha((ROOT / n).read_bytes()) for n in sorted(names)}


def package(kernel_root, build, output, *, session=None, archive_plan=None):
    output = private_path(output)
    files, kernel, digest = kernel_check(kernel_root)
    build = Path(build).absolute()
    if build.resolve() != build or not build.is_relative_to(ROOT / "build"):
        raise ValueError("fresh repository helper build required")
    build.mkdir(mode=0o700)
    name = archive_name(archive_plan)
    (build / "audit-archive.h").write_text('#define HEARTH_AUDIT_ARCHIVE "' + name + '"\n')
    session = os.urandom(32) if session is None else session
    if type(session) is not bytes or len(session) != 32:
        raise ValueError("fixed profile nonce required")
    (build / "session.h").write_text(
        "static const unsigned char hearth_session[32]={" + ",".join(map(str, session)) + "};\n"
    )
    subprocess.run(  # nosec B603 B607
        [
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
            "-static",
            "-Wl,-e,_start,--build-id=none,-z,noexecstack",
            "-I" + str(build),
            "-I" + str(ROOT / "firmware/file_install"),
            str(ROOT / "firmware/encoding_audit/init.c"),
            str(ROOT / "firmware/file_install/snapshot.c"),
            str(ROOT / "firmware/network_update/hash.c"),
            "-o",
            str(build / "init"),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    program = base.read_build(build / "init", 1048576)
    archive = base.expected_archive(program)
    artifacts = {
        n: files[n] for n in ("kernel.config", "x-load-gen2.bin", "u-boot.bin", "omap_loader")
    }
    artifacts |= {
        "init": program,
        "rootfs.cpio": archive,
        "fallback-init": files["probe-init"],
        "uImage": multi_image(kernel, archive),
    }
    if len(artifacts["uImage"]) > base.MAX_IMAGE:
        raise ValueError("encoding audit exceeds bounded load region")
    output.mkdir(mode=0o700)
    (output / "artifacts").mkdir(mode=0o700)
    for name, data in artifacts.items():
        path = output / "artifacts" / name
        path.write_bytes(data)
        path.chmod(0o700 if name == "omap_loader" else 0o600)
    record = {
        "status": "protected-readonly-encoding-audit-unexecuted",
        "session": session.hex(),
        **({"archive_plan": archive_plan.hex()} if archive_plan is not None else {}),
        "kernel": str(Path(kernel_root).absolute()),
        "kernel_manifest_sha256": digest,
        "recipes": recipes(),
        "files": {n: base.sha(d) for n, d in artifacts.items()},
    }
    (output / "profile.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    (output / "profile.json").chmod(0o600)
    return check(output)


def check(root):
    root = private_path(root)
    record = json.loads(base.private_read(root / "profile.json", 65536))
    if (
        record["status"] != "protected-readonly-encoding-audit-unexecuted"
        or record["recipes"] != recipes()
        or set(record["files"]) != base.FILES
    ):
        raise ValueError("fixed protected encoding audit required")
    files, kernel, digest = kernel_check(record["kernel"])
    actual = {n: base.private_read(root / "artifacts" / n, 4 * 1048576) for n in base.FILES}
    plan = record.get("archive_plan")
    name = archive_name(None if plan is None else bytes.fromhex(plan))
    if name.encode() + b"\0" not in actual["init"]:
        raise ValueError("compiled read-only archive path differs")
    if digest != record["kernel_manifest_sha256"] or any(
        base.sha(d) != record["files"][n] for n, d in actual.items()
    ):
        raise ValueError("encoding audit changed")
    if actual["rootfs.cpio"] != base.expected_archive(actual["init"]) or actual[
        "uImage"
    ] != multi_image(kernel, actual["rootfs.cpio"]):
        raise ValueError("exact static read-only archive required")
    if (
        any(
            actual[n] != files[n]
            for n in ("kernel.config", "x-load-gen2.bin", "u-boot.bin", "omap_loader")
        )
        or actual["fallback-init"] != files["probe-init"]
    ):
        raise ValueError("protected bootstrap changed")
    return {
        "status": "protected-encoding-audit-checked",
        "flash_writes": False,
        "native_execution": False,
    }
