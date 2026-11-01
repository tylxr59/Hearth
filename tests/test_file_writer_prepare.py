import hashlib
import json

import pytest

from firmware.file_writer import configure
from firmware.file_writer.prepare import binding
from firmware.file_writer.prepare import prepare as stage_writer
from tests.test_file_capsule import preparation as capsule_fixture
from tests.test_file_capsule import prepare

preparation = capsule_fixture


def test_writer_patch_preserves_initial_guards_and_registers_only_two_views(monkeypatch):
    source = (
        "static int __devinit omap_nand_probe(struct platform_device *pdev)\n"
        "/* NAND write protect off */\n\tgpmc_cs_configure(info->gpmc_cs, GPMC_CONFIG_WP, 0);\n"
        "nand_scan_ident();\n\t/* second phase scan */\nnand_scan_tail();\n"
        "\n#ifdef CONFIG_MTD_PARTITIONS\n"
        "\terr = parse_mtd_partitions(&info->mtd, part_probes, &info->parts, 0);\n"
        "\tif (err > 0)\n\t\tadd_mtd_partitions(&info->mtd, info->parts, err);\n"
        "\telse if (pdata->parts)\n\t\tadd_mtd_partitions(&info->mtd, pdata->parts, pdata->nr_parts);\n"
        "\telse\n#endif\n\t\tadd_mtd_device(&info->mtd);\n"
        "\n\tplatform_set_drvdata(pdev, &info->mtd);\n"
        "\tplatform_set_drvdata(pdev, NULL);\n"
    )
    monkeypatch.setattr(
        configure.base.metadata, "DRIVER_SHA256", hashlib.sha256(source.encode()).hexdigest()
    )
    patched = configure.patch_driver(source)
    ordered = [
        "GPMC_CONFIG_WP, 1",
        "nand_scan_ident()",
        "NAND_ROM",
        "nand_scan_tail()",
        "hearth_wp_is_asserted",
        "hfw_save(&info->mtd)",
        "hearth_block_mtd_writes",
        "hfw_install(&info->mtd)",
        "add_mtd_partitions(&info->mtd, hfw_partitions, 2)",
        "hfw_register(&pdev->dev)",
    ]
    positions = [patched.index(item) for item in ordered]
    assert positions == sorted(positions)
    assert "parse_mtd_partitions(" not in patched
    assert "add_mtd_device(&info->mtd)" not in patched
    assert "pdata->parts" not in patched
    assert "hfw_remove(&pdev->dev)" in patched


def test_writer_rejects_unreviewed_driver():
    with pytest.raises(ValueError):
        configure.patch_driver("unreviewed source")


def test_writer_must_read_lzo_but_never_select_compression_for_writes():
    from firmware.probe.configure import configure as basic

    text = configure.configure(basic(""))
    configure.verify(text)
    assert "CONFIG_JFFS2_LZO=y" in text.splitlines()
    assert "CONFIG_JFFS2_CMODE_NONE=y" in text.splitlines()
    for mode in configure.COMPRESS_MODES:
        with pytest.raises(ValueError):
            configure.verify(configure.base.setting(text, mode, True))
    with pytest.raises(ValueError):
        configure.verify(configure.base.setting(text, "JFFS2_CMODE_NONE", False))


def test_binding_requires_complete_capsule_and_external_pin(preparation, monkeypatch):
    from tools import elf_review

    _, _, capsule = preparation
    plan = prepare(preparation)
    monkeypatch.setattr(elf_review, "PRIVATE", capsule.parent)
    pin = capsule.parent / "plan-pin.json"
    pin.write_text(json.dumps({"format": "hearth-local-file-plan-pin-v1", "plan": plan.hex()}))
    pin.chmod(0o600)
    value = binding(capsule, pin)
    assert "hearth_expected_plan[32]" in value and "hearth_expected_receipt[32]" in value
    (capsule / "0.replacement").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        binding(capsule, pin)
    # Refusal happens before source staging or repository/build access.
    output = capsule.parent / "kernel"
    with pytest.raises(ValueError):
        stage_writer(None, None, None, None, output, capsule, pin)
    assert not output.exists()
