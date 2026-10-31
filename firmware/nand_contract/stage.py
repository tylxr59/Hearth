"""Stage a distinct, non-content read-only NAND contract diagnostic."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from firmware.nand_metadata import stage as parent

HOST_FILES = parent.HOST_FILES | {"metadata_configure.py", "geometry_report.py"}


def stage(nestdfu, xloader, loader, base_build, output):
    output = parent.stage(nestdfu, xloader, loader, base_build, output)
    assets = Path(__file__).resolve().parent
    old = assets.parent / "nand_metadata"
    shutil.copyfile(old / "configure.py", output / "metadata_configure.py")
    shutil.copyfile(old / "report.py", output / "geometry_report.py")
    for name, target in [
        ("init.c", "probe-init.c"),
        ("build.sh", "build.sh"),
        ("contract.h", "contract.h"),
        ("configure.py", "configure.py"),
        ("report.py", "metadata_report.py"),
    ]:
        shutil.copyfile(assets / name, output / target)
    check = (
        (output / "check.py")
        .read_text()
        .replace("experimental-nand-geometry-only", "experimental-nand-contract-only")
    )
    line = next(x for x in check.splitlines() if x.startswith("HOST_FILES = "))
    check = check.replace(
        line, "HOST_FILES = {" + ", ".join(repr(n) for n in sorted(HOST_FILES)) + "}"
    )
    (output / "check.py").write_text(check)
    boot = (
        (output / "boot.sh")
        .read_text()
        .replace("--execute-read-only-nand-metadata", "--execute-read-only-nand-contract")
    )
    boot = boot.replace(
        "EXPERIMENTAL NAND METADATA BOOT: asserts write protection; no backup or recovery.",
        "EXPERIMENTAL NAND CONTRACT BOOT: protected controller metadata only; no backup or recovery.",
    )
    boot = boot.replace("Geometry report", "Controller report").replace(
        "geometry report", "controller report"
    )
    (output / "boot.sh").write_text(boot)
    (output / "contract-sources.json").write_text(
        json.dumps(
            {
                "status": "unexecuted-read-only-controller-contract",
                "recipe_sha256": {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in assets.iterdir()
                    if p.is_file()
                },
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    (output / "DO-NOT-FLASH.txt").write_text(
        "Read-only NAND controller metadata RAM diagnostic. No data acquisition, flash writer or restoration.\n"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for n in ("nestdfu", "xloader", "loader", "base-build", "output"):
        parser.add_argument("--" + n, required=True)
    a = parser.parse_args()
    stage(a.nestdfu, a.xloader, a.loader, a.base_build, a.output)
