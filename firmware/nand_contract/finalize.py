"""Finalize local controller-contract-build integrity records without opening any device."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from firmware.nand_contract import configure, stage
from firmware.probe import check as probe_check


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(root, base):
    root, base = Path(root), Path(base)
    target = root / "probe-manifest.json"
    if target.exists():
        raise ValueError("refusing to replace an existing manifest")
    probe_check.check(base)
    if not os.access(root / "artifacts/omap_loader", os.X_OK):
        raise ValueError("native host loader must be executable before finalization")
    assets = Path(__file__).resolve().parent
    kernel = root / "src/Dev/linux"
    driver = kernel / "drivers/mtd/nand/omap2.c"
    original = driver.with_suffix(".hearth-original")
    if driver.read_text() != configure.patch_driver(original.read_text()):
        raise ValueError("unexpected generated NAND driver")
    generator = kernel / "scripts/mkcompile_h"
    if generator.read_text() != configure.patch_build_metadata(
        generator.with_suffix(".hearth-original").read_text()
    ):
        raise ValueError("unexpected compile metadata generator")
    pairs = [
        (assets.parent / "nand_metadata/readonly.h", driver.parent / "hearth-metadata-readonly.h"),
        (assets / "contract.h", driver.parent / "hearth-contract.h"),
        (assets.parent / "nand_metadata/configure.py", root / "metadata_configure.py"),
        (assets.parent / "nand_metadata/report.py", root / "geometry_report.py"),
        (assets / "init.c", root / "probe-init.c"),
        (assets / "configure.py", root / "configure.py"),
        (assets / "build.sh", root / "build.sh"),
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
        "status": "experimental-nand-contract-only",
        "profile": "Display-2.6",
        "device_executed": False,
        "recovery": "unverified",
        "base_manifest_sha256": digest(base / "probe-manifest.json"),
        "files": {n: digest(root / "artifacts" / n) for n in sorted(probe_check.FILES)},
        "host_files": {n: digest(root / n) for n in sorted(stage.HOST_FILES)},
        "recipe_sha256": {p.name: digest(p) for p in sorted(assets.iterdir()) if p.is_file()},
        "generated_driver_sha256": digest(driver),
        "generated_guard_sha256": digest(driver.parent / "hearth-metadata-readonly.h"),
        "generated_contract_sha256": digest(driver.parent / "hearth-contract.h"),
    }
    with target.open("x") as stream:
        stream.write(json.dumps(record, sort_keys=True, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build_directory")
    parser.add_argument("--base-build", required=True)
    args = parser.parse_args()
    finalize(args.build_directory, args.base_build)
    print("Controller-contract integrity manifest finalized; no device executed.")
