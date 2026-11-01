"""Stage/build-check a root0-only NONE writer kernel. No device execution here.

Reuse the already pinned original public source archives, not a modified build
tree. The only private container input is the exact plan/receipt binding, never
owner firmware, credentials or working captures. No source is uploaded.
"""

import argparse
import hashlib
import json
import os
import shutil
import tarfile
from pathlib import Path

from firmware.file_snapshot.prepare import RECIPES as SNAPSHOT_RECIPES
from firmware.file_writer import configure
from firmware.file_writer.prepare import RECIPES as WRITER_RECIPES
from firmware.network_probe.profile import pinned_plan
from firmware.network_snapshot.profile import base_check, read_build
from firmware.probe.check import FILES
from firmware.tls_probe.check import zimage_payload
from firmware.tls_probe.package import unpack_image

ROOT = Path(__file__).resolve().parents[2]
STATUS = "network-root0-writer-kernel-unexecuted"
RECIPES = (
    set(SNAPSHOT_RECIPES)
    | set(WRITER_RECIPES)
    | {
        "firmware/network_writer/kernel.py",
        "firmware/network_writer/fallback.c",
        "firmware/network_writer/source-archives.json",
        "firmware/probe/inputs.json",
        "firmware/nand_contract/build.sh",
        "firmware/network_probe/profile.py",
        "provisioning/network_plan.py",
        "provisioning/network_backup.py",
        "provisioning/native_network.py",
    }
)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(65536):
            value.update(chunk)
    return value.hexdigest()


def binding(plan, backup, pin):
    bound = pinned_plan(plan, backup, pin)
    array = lambda value: "{" + ",".join(map(str, value)) + "}"
    return (
        "/* Private root0-only plan/verified host custody binding. */\n"
        "#define HEARTH_ROOT0_ONLY 1\n"
        "static const unsigned char hearth_expected_plan[32]=" + array(bound["plan"]) + ";\n"
        "static const unsigned char hearth_expected_receipt[32]=" + array(bound["receipt"]) + ";\n"
    ).encode()


def build_path(path):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_relative_to(ROOT / "build"):
        raise ValueError("literal repository build path required")
    return path


def stage(source_build, base, plan, backup, pin, output):
    source_build = build_path(source_build)
    output = build_path(output)
    _, _, base_digest = base_check(base)
    bound = binding(plan, backup, pin)
    source = json.loads(read_build(source_build / "sources.json", 65536))
    inputs = json.loads((ROOT / "firmware/probe/inputs.json").read_text())
    pins = json.loads((ROOT / "firmware/network_writer/source-archives.json").read_text())[
        "archives"
    ]
    if source["inputs"] != inputs:
        raise ValueError("original pinned source provenance differs")
    archives = {}
    for name in ("nestdfu", "xloader"):
        if {key: pins[name][key] for key in ("repository", "revision", "paths")} != inputs[
            name
        ] or pins[name]["sha256"] != source["source_archive_sha256"][name]:
            raise ValueError("public source archive pin differs")
        path = source_build / (name + "-source.tar")
        if (
            path.resolve() != path
            or not path.is_file()
            or path.stat().st_size > 512 * 1048576
            or digest(path) != source["source_archive_sha256"][name]
        ):
            raise ValueError("original public source archive differs")
        archives[name] = path
    output.mkdir(mode=0o700, exist_ok=False)
    (output / "src").mkdir()
    (output / "root").mkdir()
    (output / "artifacts").mkdir()
    for name, path in archives.items():
        target = output / path.name
        shutil.copyfile(path, target)
        with tarfile.open(target) as archive:
            archive.extractall(output / "src", filter="data")
    for name in RECIPES:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        parent = target.parent
        while parent != output:
            (parent / "__init__.py").touch(exist_ok=True)
            parent = parent.parent
    for name in ("core.c", "core.h", "io.h", "adapter.h"):
        shutil.copyfile(ROOT / "firmware/file_writer" / name, output / name)
    (output / "binding.h").write_bytes(bound)
    (output / "binding.h").chmod(0o600)
    shutil.copyfile(ROOT / "firmware/network_writer/fallback.c", output / "probe-init.c")
    shutil.copyfile(ROOT / "firmware/nand_metadata/readonly.h", output / "metadata-readonly.h")
    (output / "configure.py").write_text(
        "from firmware.file_writer.configure import main\nif __name__ == '__main__':\n    main()\n"
    )
    shutil.copyfile(ROOT / "firmware/nand_contract/build.sh", output / "build.sh")
    for name in ("x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        shutil.copy2(Path(base) / "artifacts" / name, output / "artifacts" / name)
    record = {
        "status": STATUS,
        "device_executed": False,
        "root0_only": True,
        "base": str(Path(base).absolute()),
        "base_manifest_sha256": base_digest,
        "plan": str(Path(plan).absolute()),
        "backup": str(Path(backup).absolute()),
        "pin": str(Path(pin).absolute()),
        "inputs": inputs,
        "source_archives": {name: digest(path) for name, path in archives.items()},
        "recipes": {name: digest(ROOT / name) for name in sorted(RECIPES)},
        "staged_files": {
            name: digest(output / name)
            for name in (
                "binding.h",
                "build.sh",
                "configure.py",
                "probe-init.c",
                "metadata-readonly.h",
                "core.c",
                "core.h",
                "io.h",
                "adapter.h",
            )
        },
    }
    (output / "network-kernel-preparation.json").write_text(
        json.dumps(record, sort_keys=True, indent=2) + "\n"
    )
    return {
        "status": "root0-only-kernel-sources-staged",
        "device_executed": False,
        "writer_launched": False,
    }


def verify_sources(output):
    output = build_path(output)
    record = json.loads(read_build(output / "network-kernel-preparation.json", 65536))
    if (
        record["status"] != STATUS
        or record["device_executed"] is not False
        or record["root0_only"] is not True
        or set(record["recipes"]) != RECIPES
    ):
        raise ValueError("exact unexecuted root0-only scope required")
    if any(
        digest(ROOT / name) != expected or digest(output / name) != expected
        for name, expected in record["recipes"].items()
    ):
        raise ValueError("kernel source recipe changed; stage a fresh build")
    if any(
        digest(output / name) != expected for name, expected in record["staged_files"].items()
    ) or (output / "binding.h").read_bytes() != binding(
        record["plan"], record["backup"], record["pin"]
    ):
        raise ValueError("kernel binding/staged files changed")
    if any(
        digest(output / (name + "-source.tar")) != expected
        for name, expected in record["source_archives"].items()
    ):
        raise ValueError("pinned kernel archive changed")
    _, _, base_digest = base_check(record["base"])
    if base_digest != record["base_manifest_sha256"]:
        raise ValueError("proven bootstrap identity changed")
    tree = output / "src/Dev/linux"
    driver = tree / "drivers/mtd/nand/omap2.c"
    if driver.read_text() != configure.patch_driver(
        driver.with_suffix(".hearth-original").read_text()
    ):
        raise ValueError("root0-only writer driver differs")
    for name in ("core.c", "core.h", "io.h", "adapter.h", "binding.h"):
        if (output / name).read_bytes() != (
            driver.parent / "hearth-file-writer" / name
        ).read_bytes():
            raise ValueError("kernel control source/binding differs")
    for name, patch in (
        ("fs.c", configure.patch_remount),
        ("compr.c", configure.patch_compression),
        ("ioctl.c", configure.patch_ioctl),
    ):
        path = tree / "fs/jffs2" / name
        if path.read_text() != patch(path.with_suffix(".hearth-writer-original").read_text()):
            raise ValueError("native-compatible filesystem policy differs")
    for name, patch in (
        ("scripts/mkcompile_h", configure.base.patch_build_metadata),
        ("drivers/usb/gadget/u_serial.c", configure.base.patch_serial),
        ("arch/arm/mach-omap2/Kconfig", configure.base.disable_clock_updates),
    ):
        path = tree / name
        if path.read_text() != patch(path.with_suffix(".hearth-snapshot-original").read_text()):
            raise ValueError("kernel clock/serial/metadata source differs")
    for first, second in (
        (ROOT / "firmware/nand_metadata/readonly.h", driver.parent / "hearth-metadata-readonly.h"),
        (ROOT / "firmware/file_writer/encoding.h", tree / "fs/jffs2/hearth-encoding.h"),
        (tree / ".config", output / "artifacts/kernel.config"),
        (tree / "arch/arm/boot/uImage", output / "artifacts/uImage"),
        (output / "root/init", output / "artifacts/probe-init"),
    ):
        if first.read_bytes() != second.read_bytes():
            raise ValueError("kernel artifact/source differs")
    configure.verify((output / "artifacts/kernel.config").read_text())
    for name in ("x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        if (output / "artifacts" / name).read_bytes() != (
            Path(record["base"]) / "artifacts" / name
        ).read_bytes():
            raise ValueError("proven loader/bootstrap differs")
    if not os.access(output / "artifacts/omap_loader", os.X_OK):
        raise ValueError("executable loader required")
    zimage_payload(
        unpack_image((output / "artifacts/uImage").read_bytes(), 2),
        (output / "artifacts/probe-init").read_bytes(),
    )
    return record


def finalize(output):
    record = verify_sources(output)
    output = build_path(output)
    manifest = {
        "status": STATUS,
        "device_executed": False,
        "root0_only": True,
        "preparation_sha256": digest(output / "network-kernel-preparation.json"),
        "files": {name: digest(output / "artifacts" / name) for name in FILES},
    }
    with (output / "network-kernel-manifest.json").open("x") as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return {
        "status": "root0-only-writer-kernel-checked",
        "device_executed": False,
        "plan_bound": bool(record["plan"]),
        "compression": "forced-NONE",
        "persistent_launcher": False,
    }


def check(output):
    record = verify_sources(output)
    output = build_path(output)
    manifest = json.loads(read_build(output / "network-kernel-manifest.json", 65536))
    if (
        manifest["status"] != STATUS
        or manifest["device_executed"] is not False
        or manifest["root0_only"] is not True
        or manifest["preparation_sha256"] != digest(output / "network-kernel-preparation.json")
        or set(manifest["files"]) != FILES
        or any(
            digest(output / "artifacts" / name) != expected
            for name, expected in manifest["files"].items()
        )
    ):
        raise ValueError("exact root0-only kernel manifest required")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("stage")
    for name in ("source-build", "base", "plan", "backup", "pin", "output"):
        prepare.add_argument("--" + name, required=True)
    sub.add_parser("finalize").add_argument("output")
    sub.add_parser("check").add_argument("output")
    args = vars(parser.parse_args())
    command = args.pop("command")
    result = (
        stage(**args)
        if command == "stage"
        else finalize(args["output"])
        if command == "finalize"
        else {
            "status": "root0-only-kernel-checked",
            "device_executed": False,
            "root0_only": bool(check(args["output"])["root0_only"]),
        }
    )
    print(json.dumps(result, indent=2))
