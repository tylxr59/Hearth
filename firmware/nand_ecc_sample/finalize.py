"""Finalize sample-build integrity without opening USB or reading user firmware."""

import argparse
import json
import os
from pathlib import Path

from firmware.nand_ecc_sample import configure, stage
from firmware.nand_metadata.finalize import digest
from firmware.probe import check as probe


def finalize(root, base):
    root, base = Path(root), Path(base)
    target = root / "probe-manifest.json"
    if target.exists():
        raise ValueError("refusing to replace existing manifest")
    probe.check(base)
    if not os.access(root / "artifacts/omap_loader", os.X_OK):
        raise ValueError("executable native loader required")
    assets = Path(__file__).resolve().parent
    kernel = root / "src/Dev/linux"
    driver = kernel / "drivers/mtd/nand/omap2.c"
    if driver.read_text() != configure.patch_driver(
        driver.with_suffix(".hearth-original").read_text()
    ):
        raise ValueError("unexpected sample driver")
    serial = kernel / "drivers/usb/gadget/u_serial.c"
    if serial.read_text() != configure.patch_serial(
        serial.with_suffix(".hearth-sample-original").read_text()
    ):
        raise ValueError("binary gadget tty configuration missing")
    generator = kernel / "scripts/mkcompile_h"
    if generator.read_text() != configure.patch_build_metadata(
        generator.with_suffix(".hearth-original").read_text()
    ):
        raise ValueError("unexpected compile metadata generator")
    pairs = [
        (assets / "sample.h", driver.parent / "hearth-sample.h"),
        (assets.parent / "nand_metadata/readonly.h", driver.parent / "hearth-metadata-readonly.h"),
        (assets / "protocol.h", root / "sample-protocol.h"),
        (assets / "init.c", root / "probe-init.c"),
        (assets / "configure.py", root / "configure.py"),
        (assets / "receiver.py", root / "sample_receiver.py"),
        (assets / "observe.py", root / "observe.py"),
        (assets / "boot.sh", root / "boot.sh"),
        (assets / "build.sh", root / "build.sh"),
        (assets / "reference.py", root / "reference_helper.py"),
        (assets.parent / "nand_sample/configure.py", root / "raw_sample_configure.py"),
        (assets.parent / "nand_contract/configure.py", root / "contract_configure.py"),
        (assets.parent / "nand_metadata/configure.py", root / "metadata_configure.py"),
        (kernel / ".config", root / "artifacts/kernel.config"),
        (kernel / "arch/arm/boot/uImage", root / "artifacts/uImage"),
        (root / "root/init", root / "artifacts/probe-init"),
    ]
    for name in ("x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        pairs.append((base / "artifacts" / name, root / "artifacts" / name))
    for expected, actual in pairs:
        if expected.read_bytes() != actual.read_bytes():
            raise ValueError("source/artifact mismatch: " + actual.name)
    configure.verify((root / "artifacts/kernel.config").read_text())
    record = {
        "status": "experimental-nand-ecc-sample-only",
        "profile": "Display-2.6",
        "device_executed": False,
        "full_backup": False,
        "read_mode": "MTD_OOB_PLACE; normal ECC data and physical OOB",
        "write_path_verified": False,
        "restoration": "unverified",
        "base_manifest_sha256": digest(base / "probe-manifest.json"),
        "files": {n: digest(root / "artifacts" / n) for n in sorted(probe.FILES)},
        "host_files": {n: digest(root / n) for n in sorted(stage.HOST_FILES)},
        "recipe_sha256": {p.name: digest(p) for p in sorted(assets.iterdir()) if p.is_file()},
        "generated_driver_sha256": digest(driver),
        "generated_guard_sha256": digest(driver.parent / "hearth-metadata-readonly.h"),
        "generated_sample_sha256": digest(driver.parent / "hearth-sample.h"),
        "generated_serial_sha256": digest(serial),
        "range": {
            "first_page": 12160,
            "pages": 64,
            "page_bytes": 2048,
            "oob_bytes": 64,
            "passes": 2,
        },
    }
    with target.open("x") as stream:
        stream.write(json.dumps(record, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build_directory")
    parser.add_argument("--base-build", required=True)
    args = parser.parse_args()
    finalize(args.build_directory, args.base_build)
    print("Bounded sample manifest finalized; no device executed.")
