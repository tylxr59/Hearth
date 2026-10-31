"""Seal exact scratch-test sources/artifacts offline; opens no device."""

import argparse
import json
import os
from pathlib import Path

from firmware.nand_metadata.finalize import digest
from firmware.probe import check as probe
from firmware.scratch_test import configure, stage


def finalize(root, base):
    root, base = Path(root), Path(base)
    target = root / "probe-manifest.json"
    if target.exists():
        raise ValueError("refusing to replace existing manifest")
    probe.check(base)
    if not os.access(root / "artifacts/omap_loader", os.X_OK):
        raise ValueError("executable validated loader required")
    assets = Path(__file__).resolve().parent
    kernel = root / "src/Dev/linux"
    driver = kernel / "drivers/mtd/nand/omap2.c"
    if driver.read_text() != configure.patch_driver(
        driver.with_suffix(".hearth-original").read_text()
    ):
        raise ValueError("unexpected scratch driver")
    serial = kernel / "drivers/usb/gadget/u_serial.c"
    if serial.read_text() != configure.patch_serial(
        serial.with_suffix(".hearth-sample-original").read_text()
    ):
        raise ValueError("binary duplex tty configuration missing")
    generator = kernel / "scripts/mkcompile_h"
    if generator.read_text() != configure.patch_build_metadata(
        generator.with_suffix(".hearth-original").read_text()
    ):
        raise ValueError("unexpected build metadata generator")
    pairs = [(source, root / name) for source, name in stage.pairs()]
    pairs += [
        (assets / n, driver.parent / "hearth-scratch" / n)
        for n in ("adapter.h", "io.h", "core.h", "core.c")
    ]
    pairs += [
        (assets.parent / "nand_metadata/readonly.h", driver.parent / "hearth-metadata-readonly.h"),
        (kernel / ".config", root / "artifacts/kernel.config"),
        (kernel / "arch/arm/boot/uImage", root / "artifacts/uImage"),
        (root / "root/init", root / "artifacts/probe-init"),
    ]
    pairs += [
        (base / "artifacts" / n, root / "artifacts" / n)
        for n in ("x-load-gen2.bin", "u-boot.bin", "omap_loader")
    ]
    for expected, actual in pairs:
        if expected.read_bytes() != actual.read_bytes():
            raise ValueError("source/artifact mismatch: " + actual.name)
    if (root / "duplex_observe.py").read_text() != stage.duplex_source(
        (root / "serial_observe.py").read_text()
    ):
        raise ValueError("unexpected duplex observer")
    # Reconstruct the checker exactly, including its separate writer status.
    text = (
        (assets.parent / "probe/check.py")
        .read_text()
        .replace("experimental-unexecuted-ram-probe", "experimental-fixed-scratch-restore")
    )
    line = next(x for x in text.splitlines() if x.startswith("HOST_FILES = "))
    text = text.replace(
        line, "HOST_FILES = {" + ", ".join(repr(n) for n in sorted(stage.HOST_FILES)) + "}"
    )
    if (root / "check.py").read_text() != text:
        raise ValueError("unexpected integrity checker")
    configure.verify((root / "artifacts/kernel.config").read_text())
    record = {
        "status": "experimental-fixed-scratch-restore",
        "profile": "Display-2.6",
        "device_executed": False,
        "persistent_operation_executed": False,
        "firmware_backup": False,
        "restoration": "unverified",
        "base_manifest_sha256": digest(base / "probe-manifest.json"),
        "files": {n: digest(root / "artifacts" / n) for n in sorted(probe.FILES)},
        "host_files": {n: digest(root / n) for n in sorted(stage.HOST_FILES)},
        "recipe_sha256": {p.name: digest(p) for p in sorted(assets.iterdir()) if p.is_file()},
        "generated_driver_sha256": digest(driver),
        "generated_serial_sha256": digest(serial),
        "range": {
            "block": 1312,
            "data_offset": 171966464,
            "erase_bytes": 131072,
            "program_page": 1,
            "pages": 64,
            "record_bytes": 2112,
        },
        "maximum_operations": {"data_page_program": 1, "block_erase": 1, "oob_marker_program": 1},
    }
    with target.open("x") as stream:
        stream.write(json.dumps(record, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build_directory")
    parser.add_argument("--base-build", required=True)
    args = parser.parse_args()
    finalize(args.build_directory, args.base_build)
    print("Fixed scratch manifest sealed offline; no device executed.")
