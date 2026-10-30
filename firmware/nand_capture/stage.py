"""Extend the measured read-only sample to one fixed whole-chip acquisition."""

import argparse
import shutil
from pathlib import Path

from firmware.nand_sample import stage as sample

HOST_FILES = sample.HOST_FILES | {"sample_configure.py"}


def raw_header():
    text = (Path(__file__).resolve().parent.parent / "nand_sample/sample.h").read_text()
    old = "#define HEARTH_SAMPLE_PAGES 64U"
    if text.count(old) != 1 or text.count('"hearth_sample"') != 1:
        raise ValueError("unexpected bounded raw reader")
    return text.replace(old, "#define HEARTH_SAMPLE_PAGES 131072U").replace(
        '"hearth_sample"', '"hearth_raw"'
    )


def protocol_header():
    text = (Path(__file__).resolve().parent.parent / "nand_sample/protocol.h").read_text()
    for old, new in (
        ("#define SAMPLE_PAGES 64U", "#define SAMPLE_PAGES 131072U"),
        ("'H','R','T','H','S','M','P','1'", "'H','R','T','H','R','A','W','1'"),
    ):
        if text.count(old) != 1:
            raise ValueError("unexpected framing source")
        text = text.replace(old, new)
    return text


def serial_helper():
    text = (Path(__file__).resolve().parent.parent / "probe/observe.py").read_text()
    # Only this profile sends the fixed acquisition-start token, never offsets/commands.
    for old, new in (
        ("os.O_RDONLY | os.O_NOCTTY", "os.O_RDWR | os.O_NOCTTY"),
        ("1 <= seconds <= 60", "1 <= seconds <= 1800"),
        ("1..60 second duration", "1..1800 second duration"),
    ):
        if text.count(old) != 1:
            raise ValueError("unexpected same-port serial helper")
        text = text.replace(old, new)
    return text


def stage(nestdfu, xloader, loader, base_build, output):
    output = sample.stage(nestdfu, xloader, loader, base_build, output)
    assets = Path(__file__).resolve().parent
    shutil.copyfile(output / "configure.py", output / "sample_configure.py")
    for name, target in (
        ("configure.py", "configure.py"),
        ("init.c", "probe-init.c"),
        ("observe.py", "observe.py"),
        ("receiver.py", "sample_receiver.py"),
    ):
        shutil.copyfile(assets / name, output / target)
    (output / "sample.h").write_text(raw_header())
    (output / "sample-protocol.h").write_text(protocol_header())
    (output / "serial_observe.py").write_text(serial_helper())
    template = (
        (output / "check.py")
        .read_text()
        .replace('"experimental-nand-sample-only"', '"experimental-nand-capture-only"')
    )
    old = "HOST_FILES = {" + ", ".join(repr(n) for n in sorted(sample.HOST_FILES)) + "}"
    if template.count(old) != 1:
        raise ValueError("unexpected sample image checker")
    (output / "check.py").write_text(
        template.replace(
            old, "HOST_FILES = {" + ", ".join(repr(n) for n in sorted(HOST_FILES)) + "}"
        )
    )
    template = (output / "boot.sh").read_text()
    template = template.replace(
        "--execute-read-only-nand-sample", "--execute-read-only-nand-capture"
    )
    template = template.replace(
        "EXPERIMENTAL RAW NAND SAMPLE: two reads of the first erase block, including OOB.",
        "EXPERIMENTAL FULL RAW NAND READ: two fixed whole-chip passes including OOB; no flash writes.",
    )
    template = template.replace("--seconds 60", "--seconds 1200")
    template = template.replace("Sample", "Capture").replace("sample", "capture")
    (output / "boot.sh").write_text(template)
    (output / "DO-NOT-FLASH.txt").write_text(
        "Experimental full raw read only: exactly two passes; one fixed start token.\n"
        "No deployment, restore, shell, offsets, write commands, or automated boot retries.\n"
        "Private output only. Keep off unwired base, on USB. Never flash this image.\n"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("nestdfu", "xloader", "loader", "base-build", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(stage(args.nestdfu, args.xloader, args.loader, args.base_build, args.output))
