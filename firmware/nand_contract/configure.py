"""Read-only controller metadata; retain every geometry profile restriction."""

import argparse
import hashlib
import shutil
from pathlib import Path

if __package__:
    from firmware.nand_metadata import configure as base
else:
    import metadata_configure as base

configure = base.configure
verify = base.verify
initramfs = base.initramfs
MKCOMPILE_SHA256 = "96197db4f07fd8046fd7d6cc650fa6d6b28e0b6d84cad4b8945c1f0cc20c816d"


def patch_build_metadata(original):
    if hashlib.sha256(original.encode()).hexdigest() != MKCOMPILE_SHA256:
        raise ValueError("unreviewed compile metadata generator")
    changes = {
        "`date +%T`": "`printf 00:00:00`",
        "`whoami`": "`printf hearth`",
        "`hostname | $UTS_TRUNCATE`": "`printf isolated-builder`",
        'domain=`dnsdomainname 2> /dev/null`\n  if [ -z "$domain" ]; then\n'
        "    domain=`domainname 2> /dev/null`\n  fi": "domain=hearth.invalid",
    }
    text = original
    for old, new in changes.items():
        if text.count(old) != 1:
            raise ValueError("unexpected compile metadata template")
        text = text.replace(old, new)
    return text


def patch_driver(original):
    text = base.patch_driver(original)
    marker = "static int __devinit omap_nand_probe(struct platform_device *pdev)"
    if text.count(marker) != 1:
        raise ValueError("unexpected controller probe")
    text = text.replace(marker, '#include "hearth-contract.h"\n\n' + marker)
    marker = "\tplatform_set_drvdata(pdev, &info->mtd);"
    if text.count(marker) != 1:
        raise ValueError("unexpected MTD registration")
    text = text.replace(
        marker,
        "\terr = device_create_file(&info->mtd.dev, &dev_attr_hearth_contract);\n"
        "\tif (err) {\n\t\tdel_mtd_device(&info->mtd);\n"
        "\t\tgoto out_release_mem_region;\n\t}\n" + marker,
    )
    marker = "\tplatform_set_drvdata(pdev, NULL);"
    if text.count(marker) != 1:
        raise ValueError("unexpected controller removal")
    return text.replace(
        marker, "\tdevice_remove_file(&mtd->dev, &dev_attr_hearth_contract);\n" + marker
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    if parser.parse_args().verify:
        verify(Path(".config").read_text())
        return
    base.main()
    generator = Path("scripts/mkcompile_h")
    saved = generator.with_suffix(".hearth-original")
    if not saved.exists():
        saved.write_bytes(generator.read_bytes())
    generator.write_text(patch_build_metadata(saved.read_text()))
    driver = Path("drivers/mtd/nand/omap2.c")
    original = driver.with_suffix(".hearth-original").read_text()
    driver.write_text(patch_driver(original))
    shutil.copyfile("/work/contract.h", driver.parent / "hearth-contract.h")


if __name__ == "__main__":
    main()
