"""Stage a fixed physical block's normal-ECC read comparison, never a writer."""

import argparse
import shutil
from pathlib import Path

from firmware.nand_sample import stage as parent

HOST_FILES = parent.HOST_FILES | {
    "raw_sample_configure.py",
    "contract_configure.py",
    "reference_helper.py",
}


def stage(nestdfu, xloader, loader, base_build, output):
    output = parent.stage(nestdfu, xloader, loader, base_build, output)
    assets = Path(__file__).resolve().parent
    shutil.copyfile(assets.parent / "nand_sample/configure.py", output / "raw_sample_configure.py")
    shutil.copyfile(assets.parent / "nand_contract/configure.py", output / "contract_configure.py")
    for name, target in [
        ("configure.py", "configure.py"),
        ("init.c", "probe-init.c"),
        ("sample.h", "sample.h"),
        ("protocol.h", "sample-protocol.h"),
        ("observe.py", "observe.py"),
        ("receiver.py", "sample_receiver.py"),
        ("reference.py", "reference_helper.py"),
        ("boot.sh", "boot.sh"),
        ("build.sh", "build.sh"),
    ]:
        shutil.copyfile(assets / name, output / target)
    text = (
        (output / "check.py")
        .read_text()
        .replace("experimental-nand-sample-only", "experimental-nand-ecc-sample-only")
    )
    line = next(x for x in text.splitlines() if x.startswith("HOST_FILES = "))
    text = text.replace(
        line, "HOST_FILES = {" + ", ".join(repr(n) for n in sorted(HOST_FILES)) + "}"
    )
    (output / "check.py").write_text(text)
    (output / "DO-NOT-FLASH.txt").write_text(
        "Experimental fixed-block normal-ECC read comparison; no flash writer, installation or recovery. Private reference and output required.\n"
    )
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for n in ("nestdfu", "xloader", "loader", "base-build", "output"):
        p.add_argument("--" + n, required=True)
    a = p.parse_args()
    stage(a.nestdfu, a.xloader, a.loader, a.base_build, a.output)
