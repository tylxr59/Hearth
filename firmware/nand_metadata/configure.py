"""Separate geometry-only kernel profile; the original no-MTD probe stays strict."""

import argparse
import hashlib
import re
import shutil
from pathlib import Path

if __package__:
    from firmware.probe import configure as base
else:
    import probe_configure as base

initramfs = base.initramfs
DRIVER_SHA256 = "11a7613442cc30c15b79df4cf9f4e660cc858d2ae83fa2c80c135669ec31f583"
ENABLED = ("MTD", "MTD_NAND", "MTD_NAND_OMAP2", "MTD_NAND_ECC", "MTD_NAND_IDS")
DISABLED = (
    "MTD_CHAR",
    "MTD_BLKDEVS",
    "MTD_BLOCK",
    "MTD_BLOCK_RO",
    "MTD_PARTITIONS",
    "MTD_CMDLINE_PARTS",
    "MTD_OOPS",
    "MTD_UBI",
    "MTD_ONENAND",
    "MTD_NAND_NANDSIM",
    "MTD_NAND_DISKONCHIP",
    "MTD_M25P80",
    "MTD_DATAFLASH",
)


def configure(text):
    for names, value in ((ENABLED, "y"), (DISABLED, "n")):
        for name in names:
            line = f"CONFIG_{name}=y" if value == "y" else f"# CONFIG_{name} is not set"
            pattern = rf"^(?:CONFIG_{name}=.*|# CONFIG_{name} is not set)$"
            if re.search(pattern, text, flags=re.MULTILINE):
                text = re.sub(pattern, lambda _, v=line: v, text, flags=re.MULTILINE)
            else:
                text += "\n" + line + "\n"
    return text


def verify(text):
    # Validate all original no-network/block/filesystem probe constraints, then
    # independently require the one deliberate MTD exception and its restrictions.
    base.verify(text.replace("CONFIG_MTD=y\n", "# CONFIG_MTD is not set\n"))
    for name in ENABLED:
        if f"CONFIG_{name}=y" not in text.splitlines():
            raise ValueError("missing geometry subsystem: " + name)
    for name in DISABLED:
        if re.search(rf"^CONFIG_{name}=[ym]$", text, flags=re.MULTILINE):
            raise ValueError("forbidden geometry subsystem: " + name)


def patch_driver(original):
    if hashlib.sha256(original.encode()).hexdigest() != DRIVER_SHA256:
        raise ValueError("unreviewed OMAP NAND driver")
    marker = "static int __devinit omap_nand_probe(struct platform_device *pdev)"
    text = original.replace(marker, '#include "hearth-metadata-readonly.h"\n\n' + marker)
    text = text.replace(
        "/* NAND write protect off */\n\tgpmc_cs_configure(info->gpmc_cs, GPMC_CONFIG_WP, 0);",
        "/* Geometry-only profile: assert NAND hardware write protection. */\n"
        "\tgpmc_cs_configure(info->gpmc_cs, GPMC_CONFIG_WP, 1);",
    )
    marker = "\t/* second phase scan */"
    text = text.replace(
        marker,
        "\t/* ID probing clears low chip-option bits, so set NAND_ROM afterward. */\n"
        "\tif (!(info->nand.options & NAND_SKIP_BBTSCAN) ||\n"
        "\t    (info->nand.options & NAND_USE_FLASH_BBT)) {\n"
        "\t\terr = -EROFS;\n\t\tgoto out_release_mem_region;\n\t}\n"
        "\tinfo->nand.options |= NAND_ROM;\n\n" + marker,
    )
    marker = "\n#ifdef CONFIG_MTD_PARTITIONS\n\terr = parse_mtd_partitions"
    text = text.replace(
        marker,
        "\n\tif (!hearth_wp_is_asserted(&info->mtd)) {\n"
        "\t\terr = -EROFS;\n\t\tgoto out_release_mem_region;\n\t}\n"
        "\thearth_block_mtd_writes(&info->mtd);\n" + marker,
    )
    if text.count("hearth_block_mtd_writes(&info->mtd)") != 1 or "GPMC_CONFIG_WP, 0" in text:
        raise ValueError("unexpected NAND initialization patch")
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    path = Path(".config")
    if args.verify:
        verify(path.read_text())
        return
    # Apply the original Perl/serial/NET=n compatibility changes and minimal CPIO.
    base.main()
    path.write_text(configure(path.read_text()))
    driver = Path("drivers/mtd/nand/omap2.c")
    saved = driver.with_suffix(".hearth-original")
    if not saved.exists():
        saved.write_bytes(driver.read_bytes())
    original = saved.read_text()
    desired = patch_driver(original)
    if driver.read_text() not in (original, desired):
        raise ValueError("unexpected existing driver edits")
    driver.write_text(desired)
    shutil.copyfile("/work/metadata-readonly.h", driver.parent / "hearth-metadata-readonly.h")


if __name__ == "__main__":
    main()
