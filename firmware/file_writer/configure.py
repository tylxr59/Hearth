"""Write-capable kernel recipe; never used by a read-only profile verifier."""

import argparse
import hashlib
import shutil
from pathlib import Path

from firmware.file_snapshot import configure as base

initramfs = base.initramfs
ENABLED = ("BLK_DEV_INITRD", "RD_GZIP", "AEABI", "VFP", "FUTEX")
FILESYSTEM_SHA256 = "26079566bd00628927f5d949d304382a71ee7a0da50f183adb52a86c31f2e1ce"
COMPRESSION_SHA256 = "22b49ef7253ee9187126b0100c3259dbc16a7b32af06edb97bf3ff9897103f13"
IOCTL_SHA256 = "0e65d6b892fd402a43dc3928ba5c3e7cb9099f924d919d692c0470d3357d01ba"
COMPRESS_MODES = ("JFFS2_CMODE_PRIORITY", "JFFS2_CMODE_SIZE", "JFFS2_CMODE_FAVOURLZO")


def patch_compression(original):
    if hashlib.sha256(original.encode()).hexdigest() != COMPRESSION_SHA256:
        raise ValueError("unreviewed JFFS2 compression implementation")
    start = original.index("uint16_t jffs2_compress(")
    tail = original[start:]
    before = "switch (jffs2_compression_mode)"
    if tail.count(before) != 1:
        raise ValueError("unexpected JFFS2 compression dispatch")
    # Retain LZO decompression for already-written files, but no new compressor
    # may run regardless of a global mode setting or future mount option.
    return original[:start] + tail.replace(before, "switch (JFFS2_COMPR_MODE_NONE)")


def patch_ioctl(original):
    if hashlib.sha256(original.encode()).hexdigest() != IOCTL_SHA256:
        raise ValueError("unreviewed JFFS2 ioctl implementation")
    return original.replace(
        '#include "nodelist.h"', '#include "nodelist.h"\n#include "hearth-encoding.h"'
    ).replace("return -ENOTTY;", "return hearth_encoding_check(filp, cmd, arg);")


def patch_remount(original):
    if hashlib.sha256(original.encode()).hexdigest() != FILESYSTEM_SHA256:
        raise ValueError("unreviewed JFFS2 remount implementation")
    before = "if (c->flags & JFFS2_SB_FLAG_RO && !(sb->s_flags & MS_RDONLY))"
    if original.count(before) != 1:
        raise ValueError("unexpected read-only compatibility check")
    return original.replace(before, "if (c->flags & JFFS2_SB_FLAG_RO && !(*flags & MS_RDONLY))")


def configure(text):
    text = base.configure(text)
    for name in ENABLED:
        text = base.setting(text, name, True)
    text = base.setting(text, "JFFS2_CMODE_NONE", True)
    for name in COMPRESS_MODES:
        text = base.setting(text, name, False)
    return text


def verify(text):
    base.verify(text)
    for name in ENABLED:
        if text.splitlines().count(f"CONFIG_{name}=y") != 1:
            raise ValueError("required writer userspace support missing: " + name)
    if text.splitlines().count("CONFIG_JFFS2_CMODE_NONE=y") != 1 or any(
        f"CONFIG_{name}=y" in text.splitlines() for name in COMPRESS_MODES
    ):
        raise ValueError("UNSAFE writer compression: native compatibility requires NONE")


def patch_driver(original):
    text = base.patch_driver(original)
    marker = "static int __devinit omap_nand_probe(struct platform_device *pdev)"
    if text.count(marker) != 1:
        raise ValueError("unexpected filesystem driver entry")
    text = text.replace(marker, '#include "hearth-file-writer/adapter.h"\n\n' + marker)
    marker = "\thearth_block_mtd_writes(&info->mtd);"
    if text.count(marker) != 1:
        raise ValueError("unexpected initial protection guard")
    text = text.replace(
        marker,
        "\terr = hfw_save(&info->mtd);\n\tif (err) goto out_release_mem_region;\n"
        + marker
        + "\n\terr = hfw_install(&info->mtd);\n\tif (err) goto out_release_mem_region;",
    )
    start = text.index("\n#ifdef CONFIG_MTD_PARTITIONS\n", text.index("hfw_install(&info->mtd)"))
    end = text.index("\n\tplatform_set_drvdata(pdev, &info->mtd);", start)
    expected = (
        "\n#ifdef CONFIG_MTD_PARTITIONS\n"
        "\terr = 0; /* No host/bootargs partition override. */\n"
        "\tif (err > 0)\n\t\tadd_mtd_partitions(&info->mtd, info->parts, err);\n"
        "\telse if (pdata->parts)\n\t\tadd_mtd_partitions(&info->mtd, pdata->parts, pdata->nr_parts);\n"
        "\telse\n#endif\n\t\tadd_mtd_device(&info->mtd);\n"
    )
    if text[start:end] != expected:
        raise ValueError("unreviewed partition registration")
    text = (
        text[:start]
        + (
            "\n\terr = add_mtd_partitions(&info->mtd, hfw_partitions, 2);\n"
            "\tif (!err) err = hfw_register(&pdev->dev);\n"
            "\tif (err) {\n\t\tdel_mtd_partitions(&info->mtd);\n"
            "\t\tgoto out_release_mem_region;\n\t}\n"
        )
        + text[end:]
    )
    marker = "\tplatform_set_drvdata(pdev, NULL);"
    if text.count(marker) != 1:
        raise ValueError("unexpected filesystem driver removal")
    return text.replace(marker, "\thfw_remove(&pdev->dev);\n" + marker)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    if parser.parse_args().verify:
        verify(Path(".config").read_text())
        return
    driver = Path("drivers/mtd/nand/omap2.c")
    saved = driver.with_suffix(".hearth-original")
    if saved.exists() and driver.read_text() == patch_driver(saved.read_text()):
        driver.write_text(base.patch_driver(saved.read_text()))
    base.main()
    config = Path(".config")
    config.write_text(configure(config.read_text()))
    filesystem = Path("fs/jffs2/fs.c")
    saved_filesystem = filesystem.with_suffix(".hearth-writer-original")
    if not saved_filesystem.exists():
        saved_filesystem.write_bytes(filesystem.read_bytes())
    filesystem.write_text(patch_remount(saved_filesystem.read_text()))
    for name, patch in (("compr.c", patch_compression), ("ioctl.c", patch_ioctl)):
        path = Path("fs/jffs2") / name
        saved_source = path.with_suffix(".hearth-writer-original")
        if not saved_source.exists():
            saved_source.write_bytes(path.read_bytes())
        path.write_text(patch(saved_source.read_text()))
    shutil.copyfile(
        Path("/work/firmware/file_writer/encoding.h"), Path("fs/jffs2/hearth-encoding.h")
    )
    driver.write_text(patch_driver(saved.read_text()))
    target = driver.parent / "hearth-file-writer"
    target.mkdir(exist_ok=True)
    for name in ("core.c", "core.h", "io.h", "adapter.h", "binding.h"):
        shutil.copyfile(Path("/work") / name, target / name)


if __name__ == "__main__":
    main()
