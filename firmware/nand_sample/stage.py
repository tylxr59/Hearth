"""Stage a separate fixed-range raw sample from validated bootstrap inputs."""

import argparse
import shutil
from pathlib import Path

from firmware.nand_metadata import stage as metadata

HOST_FILES = metadata.HOST_FILES | {"metadata_configure.py", "sample_receiver.py"}


def stage(nestdfu, xloader, loader, base_build, output):
    output = metadata.stage(nestdfu, xloader, loader, base_build, output)
    assets = Path(__file__).resolve().parent
    shutil.copyfile(output / "configure.py", output / "metadata_configure.py")
    for name, target in (
        ("configure.py", "configure.py"),
        ("init.c", "probe-init.c"),
        ("sample.h", "sample.h"),
        ("protocol.h", "sample-protocol.h"),
        ("observe.py", "observe.py"),
        ("receiver.py", "sample_receiver.py"),
        ("boot.sh", "boot.sh"),
    ):
        shutil.copyfile(assets / name, output / target)
    template = (output / "check.py").read_text()
    template = template.replace(
        '"experimental-nand-geometry-only"', '"experimental-nand-sample-only"'
    )
    old = "HOST_FILES = {" + ", ".join(repr(n) for n in sorted(metadata.HOST_FILES)) + "}"
    if template.count(old) != 1:
        raise ValueError("unexpected metadata integrity checker")
    template = template.replace(
        old, "HOST_FILES = {" + ", ".join(repr(n) for n in sorted(HOST_FILES)) + "}"
    )
    (output / "check.py").write_text(template)
    (output / "DO-NOT-FLASH.txt").write_text(
        "Experimental first-erase-block sample only, two raw reads including OOB.\n"
        "Cached USB retransmission; private output only. No full backup or recovery.\n"
        "Notify owner before execution; keep off unwired base. Never flash this image.\n"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("nestdfu", "xloader", "loader", "base-build", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(stage(args.nestdfu, args.xloader, args.loader, args.base_build, args.output))
