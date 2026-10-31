"""Offline writer-adapter compile recipe, distinct from every read-only profile."""

import argparse
import re
import shutil
from pathlib import Path

if __package__:
    from firmware.nand_contract.configure import patch_build_metadata
    from firmware.nand_metadata import configure as metadata
else:
    import metadata_configure as metadata
    from contract_configure import patch_build_metadata

initramfs = metadata.initramfs


def verify(text):
    metadata.verify(text)
    if "CONFIG_CRYPTO_SHA256=y" not in text.splitlines():
        raise ValueError("generic SHA-256 required before any scratch transaction")


def patch_driver(original):
    text = metadata.patch_driver(original)
    marker = "static int __devinit omap_nand_probe(struct platform_device *pdev)"
    text = text.replace(marker, '#include "hearth-scratch/adapter.h"\n\n' + marker)
    marker = "\thearth_block_mtd_writes(&info->mtd);"
    if text.count(marker) != 1:
        raise ValueError("unexpected mutation guard placement")
    text = text.replace(marker, "\thearth_scratch_save_mutators(&info->mtd);\n" + marker)
    marker = "\t\tadd_mtd_device(&info->mtd);"
    if text.count(marker) != 1:
        raise ValueError("unexpected master registration")
    text = text.replace(
        marker,
        "\t{\n\t\terr = add_mtd_device(&info->mtd);\n"
        "\t\tif (err) goto out_release_mem_region;\n"
        "\t\terr = hearth_scratch_register(&info->mtd);\n"
        "\t\tif (err) {\n\t\t\tdel_mtd_device(&info->mtd);\n"
        "\t\t\tgoto out_release_mem_region;\n\t\t}\n\t}",
    )
    marker = "\t/* Release NAND device, its internal structures and partitions */"
    if text.count(marker) != 1:
        raise ValueError("unexpected NAND teardown")
    return text.replace(marker, "\thearth_scratch_remove(mtd);\n" + marker)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    if parser.parse_args().verify:
        verify(Path(".config").read_text())
        return
    metadata.main()
    path = Path(".config")
    text = path.read_text()
    text = re.sub(
        r"^(?:CONFIG_CRYPTO_SHA256=.*|# CONFIG_CRYPTO_SHA256 is not set)$",
        "CONFIG_CRYPTO_SHA256=y",
        text,
        flags=re.MULTILINE,
    )
    if "CONFIG_CRYPTO_SHA256=y" not in text.splitlines():
        text += "\nCONFIG_CRYPTO_SHA256=y\n"
    path.write_text(text)
    driver = Path("drivers/mtd/nand/omap2.c")
    original = driver.with_suffix(".hearth-original").read_text()
    driver.write_text(patch_driver(original))
    target = driver.parent / "hearth-scratch"
    target.mkdir(exist_ok=True)
    for name in ("adapter.h", "core.c", "core.h"):
        shutil.copyfile(Path("/work") / name, target / name)
    generator = Path("scripts/mkcompile_h")
    original = generator.with_suffix(".hearth-original")
    if not original.exists():
        original.write_bytes(generator.read_bytes())
    generator.write_text(patch_build_metadata(original.read_text()))


if __name__ == "__main__":
    main()
