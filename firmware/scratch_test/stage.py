"""Stage an OFFLINE-ONLY compile check. No execution wrapper or sealed profile."""

import argparse
import shutil
from pathlib import Path

from firmware.nand_metadata import stage as metadata


def stage(nestdfu, xloader, loader, base_build, output):
    output = metadata.stage(nestdfu, xloader, loader, base_build, output)
    assets = Path(__file__).resolve().parent
    shutil.copyfile(output / "configure.py", output / "metadata_configure.py")
    shutil.copyfile(assets.parent / "nand_contract/configure.py", output / "contract_configure.py")
    shutil.copyfile(assets.parent / "nand_contract/build.sh", output / "build.sh")
    for name in ("adapter.h", "core.c", "core.h", "configure.py"):
        shutil.copyfile(assets / name, output / name)
    # The borrowed geometry init cannot issue scratch-control commands. No host
    # loader execution is supported by this unfinished compile-only draft.
    (output / "boot.sh").write_text(
        "#!/bin/sh\n"
        "echo 'OFFLINE COMPILE DRAFT ONLY. No device execution is implemented.' >&2\n"
        "exit 2\n"
    )
    (output / "DO-NOT-FLASH.txt").write_text(
        "UNSEALED OFFLINE COMPILE DRAFT. Contains experimental NAND mutation code.\n"
        "Do not boot or flash. No complete transport/ECC verifier/execution wrapper exists.\n"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("nestdfu", "xloader", "loader", "base-build", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    stage(args.nestdfu, args.xloader, args.loader, args.base_build, args.output)
