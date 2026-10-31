"""Stage/finalize the protected file reader. No device execution."""

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from firmware.file_snapshot import configure
from firmware.probe import check, stage

ROOT = Path(__file__).resolve().parents[2]
RECIPES = (
    "firmware/file_snapshot/configure.py",
    "firmware/file_snapshot/init.c",
    "firmware/file_snapshot/prepare.py",
    "firmware/file_snapshot/run.py",
    "firmware/file_install/snapshot.c",
    "firmware/file_install/snapshot.h",
    "firmware/file_install/posix.h",
    "firmware/file_install/transaction.h",
    "firmware/file_install/targets.h",
    "provisioning/file_backup.py",
    "firmware/probe/configure.py",
    "firmware/probe/check.py",
    "firmware/probe/observe.py",
    "firmware/nand_metadata/configure.py",
    "firmware/nand_metadata/readonly.h",
    "firmware/nand_contract/configure.py",
    "firmware/nand_sample/configure.py",
    "firmware/tls_probe/configure.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(nestdfu, xloader, loader, base, output):
    base, output = Path(base), Path(output)
    check.check(base)
    stage.stage(nestdfu, xloader, loader, output)
    for name in RECIPES:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        if name.endswith(".py"):
            package = target.parent
            while package != output:
                (package / "__init__.py").touch(exist_ok=True)
                package = package.parent
    shutil.copyfile(ROOT / "firmware/nand_metadata/readonly.h", output / "metadata-readonly.h")
    shutil.copyfile(ROOT / "firmware/file_snapshot/init.c", output / "probe-init.c")
    for name in ("snapshot.c", "snapshot.h", "posix.h", "transaction.h", "targets.h"):
        shutil.copyfile(ROOT / "firmware/file_install" / name, output / name)
    (output / "configure.py").write_text(
        "from firmware.file_snapshot.configure import initramfs, verify, main\n"
        "if __name__ == '__main__':\n    main()\n"
    )
    session = os.urandom(32)
    (output / "session.h").write_text(
        "static const unsigned char hearth_session[32]={" + ",".join(map(str, session)) + "};\n"
    )
    build = (ROOT / "firmware/nand_contract/build.sh").read_text()
    build = build.replace("-o root/init probe-init.c", "-o root/init probe-init.c snapshot.c")
    (output / "build.sh").write_text(build)
    (output / "artifacts").mkdir()
    for name in ("x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        shutil.copy2(base / "artifacts" / name, output / "artifacts" / name)
    checker = (
        (ROOT / "firmware/probe/check.py")
        .read_text()
        .replace("experimental-unexecuted-ram-probe", "experimental-readonly-file-snapshot")
    )
    host_files = {"configure.py", "check.py", "session.h", "build.sh"} | set(RECIPES)
    old = 'HOST_FILES = {"boot.sh", "check.py", "configure.py", "observe.py"}'
    if checker.count(old) != 1:
        raise ValueError("unexpected shared checker")
    checker = checker.replace(old, "HOST_FILES = " + repr(host_files))
    (output / "check.py").write_text(checker)
    (output / "snapshot-preparation.json").write_text(
        json.dumps(
            {
                "status": "unexecuted-readonly-snapshot",
                "session": session.hex(),
                "base_manifest_sha256": digest(base / "probe-manifest.json"),
                "recipes": {name: digest(ROOT / name) for name in RECIPES},
                "host_files": sorted(host_files),
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    (output / "DO-NOT-FLASH.txt").write_text(
        "RAM-only protected JFFS2 snapshot. No installer. Never flash this image.\n"
    )


def finalize(output, base):
    output, base = Path(output), Path(base)
    check.check(base)
    prepared = json.loads((output / "snapshot-preparation.json").read_text())
    for name, expected in prepared["recipes"].items():
        if digest(ROOT / name) != expected or digest(output / name) != expected:
            raise ValueError("snapshot recipe changed; prepare a fresh build")
    kernel = output / "src/Dev/linux"
    driver = kernel / "drivers/mtd/nand/omap2.c"
    if driver.read_text() != configure.patch_driver(
        driver.with_suffix(".hearth-original").read_text()
    ):
        raise ValueError("unexpected protected driver")
    pairs = [
        (ROOT / "firmware/nand_metadata/readonly.h", driver.parent / "hearth-metadata-readonly.h"),
        (output / "probe-init.c", output / "firmware/file_snapshot/init.c"),
        (kernel / ".config", output / "artifacts/kernel.config"),
        (kernel / "arch/arm/boot/uImage", output / "artifacts/uImage"),
        (output / "root/init", output / "artifacts/probe-init"),
    ]
    for name in ("snapshot.c", "snapshot.h", "posix.h", "transaction.h", "targets.h"):
        pairs.append((output / name, output / "firmware/file_install" / name))
    for name in ("x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        pairs.append((base / "artifacts" / name, output / "artifacts" / name))
    for first, second in pairs:
        if first.read_bytes() != second.read_bytes():
            raise ValueError("snapshot source/artifact mismatch")
    if not os.access(output / "artifacts/omap_loader", os.X_OK):
        raise ValueError("host loader must be executable")
    configure.verify((output / "artifacts/kernel.config").read_text())
    kconfig = kernel / "arch/arm/mach-omap2/Kconfig"
    if kconfig.read_text() != configure.disable_clock_updates(
        kconfig.with_suffix(".hearth-snapshot-original").read_text()
    ):
        raise ValueError("unexpected hardware clock selection")
    # Require the exact raw tty and reproducible metadata patches too.
    for name, patch in (
        ("scripts/mkcompile_h", configure.patch_build_metadata),
        ("drivers/usb/gadget/u_serial.c", configure.patch_serial),
    ):
        path = kernel / name
        if path.read_text() != patch(path.with_suffix(".hearth-snapshot-original").read_text()):
            raise ValueError("unexpected snapshot source edit")
    manifest = {
        "status": "experimental-readonly-file-snapshot",
        "device_executed": False,
        "recovery": "unverified",
        "files": {name: digest(output / "artifacts" / name) for name in check.FILES},
        "host_files": {name: digest(output / name) for name in prepared["host_files"]},
    }
    with (output / "probe-manifest.json").open("x") as stream:
        stream.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--base", required=True)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--nestdfu")
    parser.add_argument("--xloader")
    parser.add_argument("--loader")
    args = parser.parse_args()
    if args.finalize:
        finalize(args.output, args.base)
    else:
        prepare(args.nestdfu, args.xloader, args.loader, args.base, args.output)
