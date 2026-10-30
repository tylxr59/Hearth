"""Bounded raw sample extension; retains the geometry profile's configuration."""

import argparse
import shutil
from pathlib import Path

if __package__:
    from firmware.nand_metadata import configure as metadata
else:
    import metadata_configure as metadata

initramfs = metadata.initramfs
verify = metadata.verify


def patch_driver(original):
    text = metadata.patch_driver(original)
    marker = "static int __devinit omap_nand_probe(struct platform_device *pdev)"
    text = text.replace(marker, '#include "hearth-sample.h"\n\n' + marker)
    old = "\t\tadd_mtd_device(&info->mtd);"
    if text.count(old) != 1:
        raise ValueError("unexpected master registration")
    text = text.replace(
        old,
        "\t{\n\t\terr = add_mtd_device(&info->mtd);\n"
        "\t\tif (err)\n\t\t\tgoto out_release_mem_region;\n"
        "\t\terr = hearth_register_sample(&info->mtd);\n"
        "\t\tif (err) {\n\t\t\tdel_mtd_device(&info->mtd);\n"
        "\t\t\tgoto out_release_mem_region;\n\t\t}\n\t}",
    )
    old = "\t/* Release NAND device, its internal structures and partitions */"
    if text.count(old) != 1:
        raise ValueError("unexpected NAND teardown")
    return text.replace(
        old, "\tsysfs_remove_bin_file(&mtd->dev.kobj, &hearth_sample_attr);\n" + old
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify(Path(".config").read_text())
        return
    driver = Path("drivers/mtd/nand/omap2.c")
    saved = driver.with_suffix(".hearth-original")
    if saved.exists() and driver.read_text() == patch_driver(saved.read_text()):
        # Let the unchanged metadata recipe check/reapply its own exact patch.
        driver.write_text(metadata.patch_driver(saved.read_text()))
    metadata.main()
    driver.write_text(patch_driver(saved.read_text()))
    shutil.copyfile("/work/sample.h", driver.parent / "hearth-sample.h")


if __name__ == "__main__":
    main()
