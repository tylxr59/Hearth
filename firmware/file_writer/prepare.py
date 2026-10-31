"""Compile/check the write-capable kernel offline. No device execution path.

The temporary init is the original protected snapshot reader; it never opens
the write gate. A complete writer supervisor/launcher is a separate pending step.
"""

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from firmware.file_snapshot import prepare as snapshot
from firmware.file_writer import configure
from firmware.probe import check as base_check
from provisioning import file_capsule

ROOT = Path(__file__).resolve().parents[2]
RECIPES = (
    "firmware/file_writer/core.c",
    "firmware/file_writer/core.h",
    "firmware/file_writer/io.h",
    "firmware/file_writer/adapter.h",
    "firmware/file_writer/configure.py",
    "firmware/file_writer/prepare.py",
    "provisioning/file_capsule.py",
    "provisioning/file_backup.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin_read(pin):
    from firmware.tls_probe.package import private_read

    record = json.loads(private_read(pin, 4096))
    if set(record) != {"format", "plan"} or record["format"] != "hearth-local-file-plan-pin-v1":
        raise ValueError("separate private reviewed plan pin required")
    result = bytes.fromhex(record["plan"])
    if len(result) != 32:
        raise ValueError("32-byte plan pin required")
    return result


def binding(capsule, pin):
    expected = pin_read(pin)
    file_capsule.check(capsule, expected_plan=expected)
    receipt = json.loads((Path(capsule) / "backup/receipt.json").read_text())
    receipt_digest = bytes.fromhex(receipt["manifest_sha256"])
    return (
        "/* Private exact plan and durable host custody binding. */\n"
        "static const unsigned char hearth_expected_plan[32]={"
        + ",".join(str(value) for value in expected)
        + "};\n"
        "static const unsigned char hearth_expected_receipt[32]={"
        + ",".join(str(value) for value in receipt_digest)
        + "};\n"
    )


def prepare(nestdfu, xloader, loader, base, output, capsule, pin):
    bound = binding(capsule, pin)
    output = Path(output)
    snapshot.prepare(nestdfu, xloader, loader, base, output)
    output.chmod(0o700)
    record = json.loads((output / "snapshot-preparation.json").read_text())
    for name in RECIPES:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        package = target.parent
        while package != output:
            (package / "__init__.py").touch(exist_ok=True)
            package = package.parent
        record["recipes"][name] = digest(ROOT / name)
        if name not in record["host_files"]:
            record["host_files"].append(name)
    for name in ("core.c", "core.h", "io.h", "adapter.h"):
        shutil.copyfile(ROOT / "firmware/file_writer" / name, output / name)
    (output / "binding.h").write_text(bound)
    (output / "binding.h").chmod(0o600)
    (output / "configure.py").write_text(
        "from firmware.file_writer.configure import initramfs, verify, main\n"
        "if __name__ == '__main__':\n    main()\n"
    )
    checker = (
        (output / "check.py")
        .read_text()
        .replace(
            "experimental-readonly-file-snapshot", "experimental-file-writer-kernel-no-launcher"
        )
    )
    record["host_files"] = sorted(set(record["host_files"]) | {"binding.h"})
    line = next(line for line in checker.splitlines() if line.startswith("HOST_FILES = "))
    checker = checker.replace(line, "HOST_FILES = " + repr(set(record["host_files"])))
    (output / "check.py").write_text(checker)
    record["status"] = "write-capable-kernel-unexecuted-no-launcher"
    record["plan"] = pin_read(pin).hex()
    record["binding_sha256"] = digest(output / "binding.h")
    record["capsule"] = str(Path(capsule).resolve())
    record["pin"] = str(Path(pin).resolve())
    (output / "writer-kernel-preparation.json").write_text(
        json.dumps(record, sort_keys=True, indent=2) + "\n"
    )
    # Refuse the read-only snapshot launcher before it could open any device.
    (output / "snapshot-preparation.json").unlink()
    (output / "DO-NOT-FLASH.txt").write_text(
        "WRITE-CAPABLE KERNEL. Unexecuted offline compilation only. No writer supervisor/launcher.\n"
        "Temporary original init only reads files; never opens the bound write gate. Never flash.\n"
    )


def finalize(output, base):
    output, base = Path(output), Path(base)
    base_check.check(base)
    record = json.loads((output / "writer-kernel-preparation.json").read_text())
    if record["status"] != "write-capable-kernel-unexecuted-no-launcher":
        raise ValueError("unexpected writer kernel scope")
    for name, expected in record["recipes"].items():
        if digest(ROOT / name) != expected or digest(output / name) != expected:
            raise ValueError("writer recipe changed; stage a fresh build")
    if binding(record["capsule"], record["pin"]) != (output / "binding.h").read_text():
        raise ValueError("writer backup binding changed")
    kernel = output / "src/Dev/linux"
    driver = kernel / "drivers/mtd/nand/omap2.c"
    if driver.read_text() != configure.patch_driver(
        driver.with_suffix(".hearth-original").read_text()
    ):
        raise ValueError("unexpected writer driver source")
    filesystem = kernel / "fs/jffs2/fs.c"
    if filesystem.read_text() != configure.patch_remount(
        filesystem.with_suffix(".hearth-writer-original").read_text()
    ):
        raise ValueError("unexpected read-only compatibility guard")
    pairs = [
        (ROOT / "firmware/nand_metadata/readonly.h", driver.parent / "hearth-metadata-readonly.h"),
        (output / "probe-init.c", output / "firmware/file_snapshot/init.c"),
        (kernel / ".config", output / "artifacts/kernel.config"),
        (kernel / "arch/arm/boot/uImage", output / "artifacts/uImage"),
        (output / "root/init", output / "artifacts/probe-init"),
    ]
    for name in ("core.c", "core.h", "io.h", "adapter.h", "binding.h"):
        pairs.append((output / name, driver.parent / "hearth-file-writer" / name))
        if name != "binding.h":
            pairs.append((output / name, ROOT / "firmware/file_writer" / name))
    for name in ("snapshot.c", "snapshot.h", "posix.h", "transaction.h", "targets.h"):
        pairs.append((output / name, output / "firmware/file_install" / name))
    for name in ("x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        pairs.append((base / "artifacts" / name, output / "artifacts" / name))
    for first, second in pairs:
        if first.read_bytes() != second.read_bytes():
            raise ValueError("writer kernel source/artifact mismatch")
    configure.verify((output / "artifacts/kernel.config").read_text())
    for name, patch in (
        ("scripts/mkcompile_h", configure.base.patch_build_metadata),
        ("drivers/usb/gadget/u_serial.c", configure.base.patch_serial),
        ("arch/arm/mach-omap2/Kconfig", configure.base.disable_clock_updates),
    ):
        path = kernel / name
        if path.read_text() != patch(path.with_suffix(".hearth-snapshot-original").read_text()):
            raise ValueError("unexpected writer kernel setup")
    if not os.access(output / "artifacts/omap_loader", os.X_OK):
        raise ValueError("host loader must be executable")
    manifest = {
        "status": "experimental-file-writer-kernel-no-launcher",
        "device_executed": False,
        "recovery": "unverified",
        "files": {name: digest(output / "artifacts" / name) for name in base_check.FILES},
        "host_files": {name: digest(output / name) for name in record["host_files"]},
    }
    with (output / "probe-manifest.json").open("x") as stream:
        stream.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--base", required=True)
    parser.add_argument("--finalize", action="store_true")
    for name in ("nestdfu", "xloader", "loader", "capsule", "pin"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    if args.finalize:
        finalize(args.output, args.base)
    else:
        prepare(
            args.nestdfu, args.xloader, args.loader, args.base, args.output, args.capsule, args.pin
        )
