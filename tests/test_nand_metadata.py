import hashlib
import os
import time

import pytest

from firmware.nand_metadata import configure, report
from firmware.probe import configure as probe


def geometry_frame(**overrides):
    fields = {
        "source": "custom-ram-kernel",
        "name": "omap2-nand.0",
        "type": "nand",
        "flags": "0x0",
        "size": "268435456",
        "erasesize": "131072",
        "writesize": "2048",
        "oobsize": "64",
    }
    fields.update(overrides)
    return report.START + "".join(f"{k}={v}\n" for k, v in fields.items()).encode() + report.END


def test_geometry_profile_is_separate_from_no_mtd_probe():
    selected = configure.configure(probe.configure(""))
    configure.verify(selected)
    with pytest.raises(ValueError, match="forbidden"):
        probe.verify(selected)


@pytest.mark.parametrize(
    "name", ["MTD_CHAR", "MTD_BLKDEVS", "MTD_PARTITIONS", "MTD_OOPS", "MTD_UBI", "NET"]
)
def test_geometry_profile_rejects_write_capable_consumers(name):
    text = configure.configure(probe.configure(""))
    text = text.replace(f"# CONFIG_{name} is not set", f"CONFIG_{name}=y")
    with pytest.raises(ValueError):
        configure.verify(text)


def test_geometry_patch_rejects_unreviewed_driver():
    with pytest.raises(ValueError, match="unreviewed"):
        configure.patch_driver("unexpected driver source")


def test_geometry_guard_ordering(monkeypatch):
    # Exercise insertion order independently of the immutable upstream digest.
    source = (
        "static int __devinit omap_nand_probe(struct platform_device *pdev)\n"
        "/* NAND write protect off */\n\tgpmc_cs_configure(info->gpmc_cs, GPMC_CONFIG_WP, 0);\n"
        "nand_scan_ident();\n\t/* second phase scan */\nnand_scan_tail();\n"
        "\n#ifdef CONFIG_MTD_PARTITIONS\n\terr = parse_mtd_partitions();\nadd_mtd_device();"
    )
    monkeypatch.setattr(configure, "DRIVER_SHA256", hashlib.sha256(source.encode()).hexdigest())
    patched = configure.patch_driver(source)
    assert "GPMC_CONFIG_WP, 0" not in patched
    ordered = [
        "GPMC_CONFIG_WP, 1",
        "nand_scan_ident()",
        "NAND_SKIP_BBTSCAN",
        "NAND_USE_FLASH_BBT",
        "info->nand.options |= NAND_ROM",
        "nand_scan_tail()",
        "hearth_wp_is_asserted",
        "hearth_block_mtd_writes",
        "add_mtd_device()",
    ]
    positions = [patched.index(item) for item in ordered]
    assert positions == sorted(positions)


def test_geometry_report_retains_unknown_stock_layout_and_backup_state():
    parsed = report.parse(geometry_frame())
    assert parsed["size"] == 268435456 and parsed["writesize"] == 2048
    assert parsed["flags"] == 0 and parsed["firmware_acquired"] is False
    assert "not stock partition map" in parsed["source"]


@pytest.mark.parametrize(
    "changes",
    [
        {"flags": "0x400"},
        {"flags": "0x1"},
        {"flags": "0"},
        {"type": "missing"},
        {"size": "0"},
        {"size": "1"},
        {"size": "9" * 30},
        {"size": "268435457"},
        {"writesize": "0"},
        {"writesize": "2049"},
        {"erasesize": "0"},
        {"oobsize": "0"},
        {"source": "stock-kernel"},
        {"name": "PRIVATE\x1bDATA"},
        {"serial": "PRIVATE"},
    ],
)
def test_geometry_rejects_unknown_unsafe_or_inconsistent_reports(changes):
    with pytest.raises(ValueError) as error:
        report.parse(geometry_frame(**changes))
    assert "PRIVATE" not in str(error.value)


def test_geometry_rejects_duplicates_and_oversize():
    frame = geometry_frame().replace(report.END, b"flags=0x400\n" + report.END)
    for bad in (frame, b"x" * 1025, geometry_frame()[:-1]):
        with pytest.raises(ValueError):
            report.parse(bad)


def test_geometry_stream_discards_unknown_bytes_and_accepts_crlf():
    reader, writer = os.pipe()
    try:
        os.write(writer, b"PRIVATE-UNKNOWN\n" + geometry_frame().replace(b"\n", b"\r\n"))
        result = report.receive(reader, time.monotonic() + 1)
        assert result["status"] == "nand-geometry-observed"
        assert "PRIVATE" not in str(result)
        with pytest.raises(TimeoutError):
            report.receive(reader, time.monotonic() - 1)
    finally:
        os.close(reader)
        os.close(writer)
