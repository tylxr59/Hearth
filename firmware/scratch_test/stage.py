"""Stage an explicit fixed-block program/erase/restore RAM experiment."""

import argparse
import shutil
from pathlib import Path

from firmware.nand_metadata import stage as metadata

HOST_FILES = metadata.HOST_FILES | {
    "metadata_configure.py",
    "contract_configure.py",
    "raw_sample_configure.py",
    "raw_receiver.py",
    "reference_helper.py",
    "backup_helper.py",
    "ecc_helper.py",
    "preflight_helper.py",
    "session_helper.py",
    "duplex_observe.py",
}


def duplex_source(text):
    old = "os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK | os.O_NOFOLLOW"
    if text.count(old) != 1:
        raise ValueError("unexpected shared serial observer")
    text = text.replace(old, "os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK | os.O_NOFOLLOW")
    doc = "No commands or payload bytes are written to the serial device."
    if text.count(doc) != 1:
        raise ValueError("unexpected shared serial observer documentation")
    return text.replace(
        doc, "Scratch-only duplex copy: the receiver sends fixed start/backup-ACK tokens."
    )


def pairs():
    assets = Path(__file__).resolve().parent
    files = [
        (assets / n, n)
        for n in ("adapter.h", "io.h", "core.c", "core.h", "configure.py", "observe.py", "boot.sh")
    ]
    files += [
        (assets / a, b)
        for a, b in (
            ("init.c", "probe-init.c"),
            ("protocol.h", "scratch-protocol.h"),
            ("backup.py", "backup_helper.py"),
            ("ecc.py", "ecc_helper.py"),
            ("preflight.py", "preflight_helper.py"),
            ("session.py", "session_helper.py"),
        )
    ]
    files += [
        (assets.parent / a, b)
        for a, b in (
            ("nand_metadata/configure.py", "metadata_configure.py"),
            ("nand_contract/configure.py", "contract_configure.py"),
            ("nand_contract/build.sh", "build.sh"),
            ("nand_sample/configure.py", "raw_sample_configure.py"),
            ("nand_sample/receiver.py", "raw_receiver.py"),
            ("nand_ecc_sample/reference.py", "reference_helper.py"),
            ("probe/observe.py", "serial_observe.py"),
            ("probe/configure.py", "probe_configure.py"),
            ("nand_metadata/report.py", "metadata_report.py"),
        )
    ]
    return files


def stage(nestdfu, xloader, loader, base_build, output):
    output = metadata.stage(nestdfu, xloader, loader, base_build, output)
    for source, target in pairs():
        shutil.copyfile(source, output / target)
    (output / "duplex_observe.py").write_text(
        duplex_source((output / "serial_observe.py").read_text())
    )
    text = (
        (output / "check.py")
        .read_text()
        .replace("experimental-nand-geometry-only", "experimental-fixed-scratch-restore")
    )
    line = next(x for x in text.splitlines() if x.startswith("HOST_FILES = "))
    text = text.replace(
        line, "HOST_FILES = {" + ", ".join(repr(n) for n in sorted(HOST_FILES)) + "}"
    )
    (output / "check.py").write_text(text)
    (output / "DO-NOT-FLASH.txt").write_text(
        "Experimental fixed scratch NAND write/erase/restore RAM kernel. NEVER FLASH THIS IMAGE.\n"
        "One private region backup must be durable before writes. No firmware recovery guarantee.\n"
        "Advance owner notification/readiness required; detached unwired base, USB only.\n"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("nestdfu", "xloader", "loader", "base-build", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    stage(args.nestdfu, args.xloader, args.loader, args.base_build, args.output)
