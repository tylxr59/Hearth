"""Offline-only packaging of a fixed four-file protected RAM reader."""

import argparse
import json
import os
import subprocess  # nosec B404 B607
from pathlib import Path

from firmware.settings_probe.artifact import parse_cpio
from firmware.startup_diagnostic import profile as shared
from firmware.tls_probe.check import split_multi
from firmware.tls_probe.package import MAX_IMAGE, multi_image, private_read
from tools.elf_review import private_path

ROOT = Path(__file__).resolve().parents[2]
FILES = shared.FILES
STATUS = "protected-readonly-network-snapshot-unexecuted"
sha, read_build, base_check, expected_archive = (
    shared.sha,
    shared.read_build,
    shared.base_check,
    shared.expected_archive,
)


def recipes():
    paths = set(shared.recipes()) | {"provisioning/network_backup.py"}
    paths |= {
        p.relative_to(ROOT).as_posix()
        for p in Path(__file__).parent.iterdir()
        if p.suffix in (".py", ".c", ".h")
    }
    return {name: sha((ROOT / name).read_bytes()) for name in sorted(paths)}


def package(base, build, output, *, session=None):
    output = private_path(output)
    if output.parent.stat().st_mode & 0o077:
        raise ValueError("owner-only output parent required")
    blobs, kernel, base_digest = base_check(base)
    build = Path(build).absolute()
    if build.resolve() != build or not build.is_relative_to(ROOT / "build"):
        raise ValueError("fresh repository build path required")
    build.mkdir(mode=0o700, exist_ok=False)
    session = os.urandom(32) if session is None else session
    if type(session) is not bytes or len(session) != 32:
        raise ValueError("32-byte session required")
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
            str(ROOT / "firmware/network_snapshot/init.c"),
            str(ROOT / "firmware/network_snapshot/reader.c"),
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
        "status": "readonly-network-snapshot-checked",
        "device_executed": False,
        "flash_writes": "disabled-in-kernel",
        "native_execution": False,
        "targets": 4,
        "max_cached_bytes": 7471232,
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
