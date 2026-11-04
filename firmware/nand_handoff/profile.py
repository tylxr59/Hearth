"""Fresh private restart endpoint on the unchanged checked full-read kernel."""

import json
import secrets
from pathlib import Path

from firmware.acquisition.profile import expected_archive, read_build
from firmware.file_writer.run import encode, save
from firmware.nand_capture import profile as base
from firmware.nand_capture.stage import protocol_header
from firmware.probe.configure import initramfs
from firmware.tls_probe.check import zimage_payload
from firmware.tls_probe.compile import run
from firmware.tls_probe.package import (
    MAX_IMAGE,
    MAX_ROOT,
    multi_image,
    private_read,
    sha,
    unpack_image,
)
from tools.elf_review import private_path

ROOT = Path(__file__).resolve().parents[2]
FORMAT = "hearth-restartable-whole-nand-reader-v1"
FILES = {
    "uImage",
    "rootfs.cpio",
    "init",
    "omap_loader",
    "x-load-gen2.bin",
    "u-boot.bin",
    "kernel.config",
}


def recipes():
    names = {
        "firmware/nand_capture/init.c",
        "firmware/nand_capture/stage.py",
        "installer/ram_handoff.py",
    }
    names |= {
        p.relative_to(ROOT).as_posix()
        for p in Path(__file__).parent.iterdir()
        if p.suffix in (".py", ".c")
    }
    return {n: sha((ROOT / n).read_bytes()) for n in sorted(names)}


def kernel(root):
    base.check(root)
    root = Path(root)
    blobs = {
        n: read_build(root / "artifacts" / n, MAX_IMAGE)
        for n in (
            "uImage",
            "probe-init",
            "kernel.config",
            "omap_loader",
            "x-load-gen2.bin",
            "u-boot.bin",
        )
    }
    if "CONFIG_BLK_DEV_INITRD=y" not in blobs["kernel.config"].decode().splitlines():
        raise ValueError("raw external initramfs support required")
    payload = unpack_image(blobs["uImage"], 2)
    zimage_payload(payload, blobs["probe-init"])
    return blobs, payload


def build(reader, work, output):
    output = private_path(output)
    work = Path(work).absolute()
    if (
        work.resolve() != work
        or not work.is_relative_to(ROOT / "build")
        or output.parent.stat().st_mode & 0o077
    ):
        raise ValueError("fresh bounded build and private profile required")
    blobs, payload = kernel(reader)
    work.mkdir(mode=0o700, exist_ok=False)
    nonce = secrets.token_bytes(32)
    (work / "session.h").write_text(
        "static const unsigned char hearth_session[32]={" + ",".join(map(str, nonce)) + "};\n"
    )
    (work / "sample-protocol.h").write_text(protocol_header())
    run(
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
            "-ffreestanding",
            "-fno-builtin",
            "-fno-stack-protector",
            "-fomit-frame-pointer",
            "-fuse-ld=lld",
            "-nostdlib",
            "-static",
            "-Wl,-e,_start,--build-id=none,-z,noexecstack",
            "-I" + str(work),
            str(Path(__file__).with_name("init.c")),
            "-o",
            str(work / "init"),
        ]
    )
    program = read_build(work / "init", 65536)
    raw = expected_archive(program)
    files = {n: blobs[n] for n in ("kernel.config", "omap_loader", "x-load-gen2.bin", "u-boot.bin")}
    files |= {"init": program, "rootfs.cpio": raw, "uImage": multi_image(payload, raw)}
    if len(files["uImage"]) > MAX_IMAGE:
        raise ValueError("unchanged image load bound exceeded")
    output.mkdir(mode=0o700)
    (output / "artifacts").mkdir(mode=0o700)
    for n, data in files.items():
        save(output / "artifacts", n, data)
    (output / "artifacts/omap_loader").chmod(0o700)
    save(
        output,
        "profile.json",
        encode(
            {
                "format": FORMAT,
                "base": str(Path(reader).absolute()),
                "base_manifest_sha256": sha(
                    read_build(Path(reader) / "probe-manifest.json", 65536)
                ),
                "build": str(work),
                "session": nonce.hex(),
                "recipes": recipes(),
                "files": {n: sha(d) for n, d in files.items()},
                "device_executed": False,
            }
        ),
    )
    return check(output)


def check(output):
    output = private_path(output)
    row = json.loads(private_read(output / "profile.json", 65536))
    if (
        row.get("format") != FORMAT
        or row.get("device_executed") is not False
        or row["recipes"] != recipes()
        or set(row["files"]) != FILES
        or len(bytes.fromhex(row["session"])) != 32
    ):
        raise ValueError("fixed nonce-bound restartable full reader required")
    blobs, payload = kernel(row["base"])
    if (
        sha(read_build(Path(row["base"]) / "probe-manifest.json", 65536))
        != row["base_manifest_sha256"]
    ):
        raise ValueError("same full-read kernel provenance required")
    files = {n: private_read(output / "artifacts" / n, MAX_ROOT) for n in FILES}
    if any(sha(d) != row["files"][n] for n, d in files.items()) or any(
        files[n] != blobs[n]
        for n in ("kernel.config", "omap_loader", "x-load-gen2.bin", "u-boot.bin")
    ):
        raise ValueError("restartable reader artifacts changed")
    initramfs(files["init"])
    if (
        files["init"] != read_build(Path(row["build"]) / "init", 65536)
        or expected_archive(files["init"]) != files["rootfs.cpio"]
        or multi_image(payload, files["rootfs.cpio"]) != files["uImage"]
        or len(files["uImage"]) > MAX_IMAGE
    ):
        raise ValueError("exact original program and raw newc RAM image required")
    return {
        "status": "restartable-whole-nand-reader-checked",
        "flash_writes": False,
        "device_executed": False,
        "automatic_restart_tested": False,
    }
