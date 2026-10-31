"""Original static reader on the unchanged protected snapshot kernel. Offline only."""

import argparse
import hashlib
import json
import os
import stat
import subprocess  # nosec B404
from pathlib import Path

from firmware.file_snapshot import configure
from firmware.file_snapshot import prepare as snapshot
from firmware.probe.check import FILES as BASE_FILES
from firmware.probe.configure import initramfs
from firmware.settings_probe.artifact import parse_cpio
from firmware.tls_probe.check import split_multi, zimage_payload
from firmware.tls_probe.package import MAX_IMAGE, cpio, multi_image, private_read, unpack_image
from tools.elf_review import private_path

ROOT = Path(__file__).resolve().parents[2]
FILES = {
    "uImage",
    "kernel.config",
    "x-load-gen2.bin",
    "u-boot.bin",
    "omap_loader",
    "fallback-init",
    "rootfs.cpio",
    "init",
}
STATUS = "protected-readonly-startup-diagnostic-unexecuted"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_build(path, maximum):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_relative_to(ROOT / "build"):
        raise ValueError("generated build file without symlinks required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > maximum:
            raise ValueError("bounded generated file required")
        with os.fdopen(os.dup(fd), "rb") as stream:
            return stream.read(maximum + 1)
    finally:
        os.close(fd)


def recipes():
    paths = set(snapshot.RECIPES) | {
        "firmware/probe/observe.py",
        "firmware/settings_compat_probe/observe.py",
        "firmware/settings_probe/artifact.py",
        "firmware/tls_probe/package.py",
        "firmware/tls_probe/check.py",
        "tools/elf_review.py",
    }
    paths |= {
        p.relative_to(ROOT).as_posix()
        for p in Path(__file__).parent.iterdir()
        if p.suffix in (".py", ".c", ".h")
    }
    return {name: sha((ROOT / name).read_bytes()) for name in sorted(paths)}


def base_check(base):
    base = Path(base).absolute()
    manifest = json.loads(read_build(base / "probe-manifest.json", 65536))
    if (
        manifest["status"] != "experimental-readonly-file-snapshot"
        or set(manifest["files"]) != BASE_FILES
    ):
        raise ValueError("proven protected snapshot kernel required")
    blobs = {name: read_build(base / "artifacts" / name, 4 * 1024 * 1024) for name in BASE_FILES}
    if any(sha(data) != manifest["files"][name] for name, data in blobs.items()):
        raise ValueError("protected kernel artifacts changed")
    text = blobs["kernel.config"].decode()
    configure.verify(text)
    if "CONFIG_BLK_DEV_INITRD=y" not in text.splitlines():
        raise ValueError("raw external initramfs support required")
    tree = base / "src/Dev/linux"
    driver = tree / "drivers/mtd/nand/omap2.c"
    if read_build(driver, 65536).decode() != configure.patch_driver(
        read_build(driver.with_suffix(".hearth-original"), 65536).decode()
    ):
        raise ValueError("protected registration differs")
    if (
        read_build(driver.parent / "hearth-metadata-readonly.h", 65536)
        != (ROOT / "firmware/nand_metadata/readonly.h").read_bytes()
    ):
        raise ValueError("WP/write-denial source differs")
    if blobs["kernel.config"] != read_build(tree / ".config", 65536) or blobs[
        "uImage"
    ] != read_build(tree / "arch/arm/boot/uImage", 4 * 1024 * 1024):
        raise ValueError("kernel build differs from saved artifacts")
    kernel = unpack_image(blobs["uImage"], 2)
    zimage_payload(kernel, blobs["probe-init"])
    return blobs, kernel, sha(read_build(base / "probe-manifest.json", 65536))


def expected_archive(program):
    initramfs(program)  # Passive static ARM ELF checks.
    entries = [(name, stat.S_IFDIR | 0o755, 0, b"", 0, 0) for name in (".", "dev", "proc", "sys")]
    entries += [
        ("dev/console", stat.S_IFCHR | 0o600, 0, b"", 5, 1),
        ("init", stat.S_IFREG | 0o555, 0, program, 0, 0),
        ("TRAILER!!!", 0, 0, b"", 0, 0),
    ]
    return cpio(entries)


def package(base, build, output):
    output = private_path(output)
    if output.parent.stat().st_mode & 0o077:
        raise ValueError("owner-only output parent required")
    blobs, kernel, base_digest = base_check(base)
    build = Path(build).absolute()
    if build.resolve() != build or not build.is_relative_to(ROOT / "build"):
        raise ValueError("fresh repository build path required")
    build.mkdir(mode=0o700, exist_ok=False)
    session = os.urandom(32)
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
            "-Wl,-e,_start,--build-id=none",
            "-I" + str(build),
            "-I" + str(ROOT / "firmware/file_install"),
            str(ROOT / "firmware/startup_diagnostic/init.c"),
            str(ROOT / "firmware/startup_diagnostic/logs.c"),
            str(ROOT / "firmware/file_install/snapshot.c"),
            "-o",
            str(build / "init"),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    program = read_build(build / "init", 1024 * 1024)
    archive = expected_archive(program)
    files = {
        name: blobs[name]
        for name in ("kernel.config", "x-load-gen2.bin", "u-boot.bin", "omap_loader")
    }
    # Raw newc, not gzip: the unchanged proven kernel has RD_GZIP disabled.
    files |= {
        "init": program,
        "rootfs.cpio": archive,
        "uImage": multi_image(kernel, archive),
        "fallback-init": blobs["probe-init"],
    }
    if len(files["uImage"]) > MAX_IMAGE:
        raise ValueError("diagnostic exceeds reviewed RAM load bounds")
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
        "base_manifest_sha256": base_digest,
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
    ):
        raise ValueError("diagnostic source/scope differs")
    session = bytes.fromhex(record["session"])
    if len(session) != 32:
        raise ValueError("fixed fresh diagnostic session required")
    blobs, kernel, digest = base_check(record["base"])
    if digest != record["base_manifest_sha256"]:
        raise ValueError("protected source manifest differs")
    files = {name: private_read(output / "artifacts" / name, MAX_IMAGE) for name in FILES}
    if any(sha(data) != record["files"][name] for name, data in files.items()):
        raise ValueError("diagnostic artifact differs")
    for name in ("kernel.config", "x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        if files[name] != blobs[name]:
            raise ValueError("protected kernel/bootstrap differs")
    actual_kernel, archive = split_multi(files["uImage"])
    if (
        actual_kernel != kernel
        or files["fallback-init"] != blobs["probe-init"]
        or archive != files["rootfs.cpio"]
        or archive != expected_archive(files["init"])
    ):
        raise ValueError("exact static diagnostic archive required")
    if len(parse_cpio(archive)) != 7:
        raise ValueError("diagnostic archive inventory differs")
    return {
        "status": "readonly-startup-diagnostic-checked",
        "device_executed": False,
        "flash_writes": "disabled-in-kernel",
        "native_execution": False,
        "image_bytes": len(files["uImage"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pack = sub.add_parser("package")
    for name in ("base", "build", "output"):
        pack.add_argument("--" + name, required=True)
    sub.add_parser("check").add_argument("output")
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(package(**args) if command == "package" else check(args["output"]), indent=2))
