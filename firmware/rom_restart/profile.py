"""Build/check a fresh nonce-bound experiment on the existing protected kernel."""

import json
import secrets
from pathlib import Path

from firmware.acquisition.profile import base_check, expected_archive, read_build
from firmware.file_writer.run import encode, save
from firmware.probe.configure import initramfs
from firmware.tls_probe.compile import run
from firmware.tls_probe.package import MAX_IMAGE, MAX_ROOT, multi_image, private_read, sha
from tools.elf_review import private_path

ROOT = Path(__file__).resolve().parents[2]
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
    return {
        p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
        for p in sorted(Path(__file__).parent.iterdir())
        if p.suffix in (".py", ".c")
    }


def build(base, work, output):
    output = private_path(output)
    work = Path(work).absolute()
    if work.resolve() != work or not work.is_relative_to(ROOT / "build"):
        raise ValueError("literal fresh build path required")
    blobs, kernel, manifest = base_check(base)
    work.mkdir(mode=0o700, exist_ok=False)
    nonce = secrets.token_bytes(32)
    (work / "session.h").write_text(
        "static const unsigned char hearth_session[32]={" + ",".join(map(str, nonce)) + "};\n"
    )
    run(
        [
            "clang",
            "--target=arm-linux-gnueabihf",
            "-marm",
            "-march=armv7-a",
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
    files |= {
        "init": program,
        "rootfs.cpio": raw,
        # The unchanged protected kernel has RD_GZIP disabled. Its proven
        # acquisition path uses raw newc, so this experiment must do the same.
        "uImage": multi_image(kernel, raw),
    }
    if len(files["uImage"]) > MAX_IMAGE:
        raise ValueError("existing image load bound exceeded")
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
                "format": "hearth-ram-warm-restart-experiment-v1",
                "base": str(Path(base).absolute()),
                "base_manifest": manifest,
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
        row.get("format") != "hearth-ram-warm-restart-experiment-v1"
        or row.get("device_executed") is not False
        or row["recipes"] != recipes()
        or set(row["files"]) != FILES
        or len(bytes.fromhex(row["session"])) != 32
    ):
        raise ValueError("fixed one-shot experiment profile required")
    blobs, kernel, manifest = base_check(row["base"])
    files = {n: private_read(output / "artifacts" / n, MAX_ROOT) for n in FILES}
    if (
        manifest != row["base_manifest"]
        or any(sha(d) != row["files"][n] for n, d in files.items())
        or any(
            files[n] != blobs[n]
            for n in ("kernel.config", "omap_loader", "x-load-gen2.bin", "u-boot.bin")
        )
    ):
        raise ValueError("experiment source/kernel/artifacts changed")
    initramfs(files["init"])
    if (
        files["init"] != read_build(Path(row["build"]) / "init", 65536)
        or expected_archive(files["init"]) != files["rootfs.cpio"]
        or multi_image(kernel, files["rootfs.cpio"]) != files["uImage"]
        or len(files["uImage"]) > MAX_IMAGE
    ):
        raise ValueError("bounded original RAM experiment required")
    return {
        "status": "ram-warm-restart-experiment-offline-checked",
        "device_executed": False,
        "flash_writes": False,
        "rom_restart_measured": False,
    }
