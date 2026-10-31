"""Separate protected JFFS2 mount profile, preserving prior profile verifiers."""

import argparse
import re
import shutil
from pathlib import Path

from firmware.nand_contract.configure import patch_build_metadata
from firmware.nand_metadata import configure as metadata
from firmware.nand_sample.configure import patch_serial
from firmware.tls_probe.configure import disable_clock_updates

initramfs = metadata.initramfs

ENABLED = (
    "MTD_PARTITIONS",
    "JFFS2_FS",
    "JFFS2_FS_WRITEBUFFER",
    "EXPERIMENTAL",
    "JFFS2_FS_XATTR",
    "JFFS2_FS_POSIX_ACL",
    "JFFS2_FS_SECURITY",
    "JFFS2_ZLIB",
    "JFFS2_RTIME",
    "JFFS2_LZO",
)
DISABLED = (
    "RTC",
    "RTC_CLASS",
    "RTC_DRV_TWL4030",
    "RTC_HCTOSYS",
    "RTC_SYSTOHC",
    "GENERIC_CMOS_UPDATE",
)


def setting(text, name, enabled):
    line = f"CONFIG_{name}=y" if enabled else f"# CONFIG_{name} is not set"
    pattern = rf"^(?:CONFIG_{name}=.*|# CONFIG_{name} is not set)$"
    if re.search(pattern, text, re.MULTILINE):
        return re.sub(pattern, lambda _: line, text, flags=re.MULTILINE)
    return text + "\n" + line + "\n"


def configure(text):
    text = metadata.configure(text)
    for name in ENABLED:
        text = setting(text, name, True)
    for name in DISABLED:
        text = setting(text, name, False)
    return text


def verify(text):
    masked = text
    for name in ("MTD_PARTITIONS", "JFFS2_FS"):
        masked = setting(masked, name, False)
    metadata.verify(masked)
    lines = text.splitlines()
    for name in ENABLED:
        if lines.count(f"CONFIG_{name}=y") != 1:
            raise ValueError("missing snapshot subsystem: " + name)
    for name in DISABLED:
        if re.search(rf"^CONFIG_{name}=[ym]$", text, re.MULTILINE):
            raise ValueError("forbidden snapshot subsystem: " + name)


def patch_driver(original):
    # The same WP/status/callback guards precede registration. Disallow command
    # line partition parsers; use only the source-reviewed platform table.
    text = metadata.patch_driver(original)
    old = "\terr = parse_mtd_partitions(&info->mtd, part_probes, &info->parts, 0);"
    if text.count(old) != 1:
        raise ValueError("unexpected partition registration")
    return text.replace(old, "\terr = 0; /* No host/bootargs partition override. */")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    if parser.parse_args().verify:
        verify(Path(".config").read_text())
        return
    driver = Path("drivers/mtd/nand/omap2.c")
    saved_driver = driver.with_suffix(".hearth-original")
    if saved_driver.exists() and driver.read_text() == patch_driver(saved_driver.read_text()):
        # Permit only our exact prior patch during an offline reproducibility
        # rebuild, before the parent independently checks/reapplies its guards.
        driver.write_text(metadata.patch_driver(saved_driver.read_text()))
    metadata.main()
    kconfig = Path("arch/arm/mach-omap2/Kconfig")
    saved_kconfig = kconfig.with_suffix(".hearth-snapshot-original")
    if not saved_kconfig.exists():
        saved_kconfig.write_bytes(kconfig.read_bytes())
    kconfig.write_text(disable_clock_updates(saved_kconfig.read_text()))
    Path(".config").write_text(configure(Path(".config").read_text()))
    driver = Path("drivers/mtd/nand/omap2.c")
    original = driver.with_suffix(".hearth-original").read_text()
    driver.write_text(patch_driver(original))
    for name, patch in (
        ("scripts/mkcompile_h", patch_build_metadata),
        ("drivers/usb/gadget/u_serial.c", patch_serial),
    ):
        path = Path(name)
        saved = path.with_suffix(".hearth-snapshot-original")
        if not saved.exists():
            saved.write_bytes(path.read_bytes())
        path.write_text(patch(saved.read_text()))
    shutil.copyfile("/work/metadata-readonly.h", driver.parent / "hearth-metadata-readonly.h")


if __name__ == "__main__":
    main()
