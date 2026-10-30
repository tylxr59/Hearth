"""Bounded raw sample extension; retains the geometry profile's configuration."""

import argparse
import hashlib
import shutil
from pathlib import Path

if __package__:
    from firmware.nand_metadata import configure as metadata
else:
    import metadata_configure as metadata

initramfs = metadata.initramfs
verify = metadata.verify
SERIAL_SHA256 = "30847eca679af58ddce6075fd31ecbc1dfff8711b412713989edf8ca2d0a2277"


def patch_serial(original):
    if hashlib.sha256(original.encode()).hexdigest() != SERIAL_SHA256:
        raise ValueError("unreviewed gadget tty source")
    marker = "\tgs_tty_driver->init_termios = tty_std_termios;"
    if original.count(marker) != 1:
        raise ValueError("unexpected gadget tty initialization")
    return original.replace(
        marker,
        marker
        + "\n\t/* Binary-only diagnostic: no newline, flow, canonical or echo processing. */\n"
        "\tgs_tty_driver->init_termios.c_iflag = 0;\n"
        "\tgs_tty_driver->init_termios.c_oflag = 0;\n"
        "\tgs_tty_driver->init_termios.c_lflag = 0;",
    )


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
    serial = Path("drivers/usb/gadget/u_serial.c")
    serial_original = serial.with_suffix(".hearth-sample-original")
    if not serial_original.exists():
        serial_original.write_bytes(serial.read_bytes())
    desired = patch_serial(serial_original.read_text())
    if serial.read_text() not in (serial_original.read_text(), desired):
        raise ValueError("unexpected existing gadget tty edits")
    serial.write_text(desired)


if __name__ == "__main__":
    main()
