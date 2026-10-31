import hashlib
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from firmware.nand_contract import configure, report
from firmware.nand_metadata import configure as metadata
from tests.test_nand_metadata import geometry_frame


def test_original_attribute_producer_matches_parser_under_sanitizers(tmp_path):
    if not shutil.which("clang"):
        pytest.skip("Clang required for original host-only metadata fixture")
    executable = tmp_path / "contract"
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-g",
            "-fsanitize=address,undefined",
            str(Path(__file__).with_name("nand_contract_harness.c")),
            "-o",
            str(executable),
        ],
        check=True,
        capture_output=True,
    )
    run = subprocess.run([str(executable)], check=True, capture_output=True, timeout=3)
    assert report.parse(run.stdout)["bus_width"] == 16


def test_compile_metadata_patch_refuses_unreviewed_sources(monkeypatch):
    with pytest.raises(ValueError):
        configure.patch_build_metadata("unreviewed")
    text = (
        "time=`date +%T`\nuser=`whoami`\nhost=`hostname | $UTS_TRUNCATE`\n"
        '  domain=`dnsdomainname 2> /dev/null`\n  if [ -z "$domain" ]; then\n'
        "    domain=`domainname 2> /dev/null`\n  fi\n"
    )
    monkeypatch.setattr(configure, "MKCOMPILE_SHA256", hashlib.sha256(text.encode()).hexdigest())
    result = configure.patch_build_metadata(text)
    assert "date +%T" not in result and "dnsdomainname" not in result and "hostname |" not in result
    assert "isolated-builder" in result and "00:00:00" in result


def frame(**changes):
    fields = dict(x.split("=", 1) for x in geometry_frame().decode("ascii").splitlines()[1:-1])
    fields.update(
        {
            "protected": "1",
            "bus_width": "16",
            "badblock_position": "0",
            "scan_second_page": "1",
            "scan_last_page": "0",
            "scan_byte1_and6": "0",
            "pattern_present": "0",
            "pattern_offset": "0",
            "pattern_length": "0",
            "pattern_options": "0",
            "ecc_mode": "2",
            "ecc_size": "2048",
            "ecc_bytes": "28",
            "ecc_steps": "1",
            "ecc_total": "28",
            "oob_free_offset": "2",
            "oob_free_length": "34",
            "ecc_positions": ",".join(str(n) for n in range(36, 64)),
        }
    )
    fields.update(changes)
    return report.START + "".join(f"{k}={v}\n" for k, v in fields.items()).encode() + report.END


def test_observation_does_not_claim_native_map_or_writes():
    value = report.parse(frame())
    assert value["bus_width"] == 16 and value["ecc_positions"] == list(range(36, 64))
    assert value["write_path_verified"] is False and value["restoration"] == "unverified"
    assert value["firmware_acquired"] is False
    assert "not stock partition map" in value["source"]
    assert (
        report.parse(
            frame(
                bus_width="8",
                oob_free_offset="1",
                oob_free_length="35",
                pattern_present="1",
                pattern_length="1",
                pattern_options="3072",
            )
        )["bus_width"]
        == 8
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"protected": "0"},
        {"flags": "0x400"},
        {"bus_width": "32"},
        {"bus_width": "8"},
        {"pattern_present": "1"},
        {"pattern_options": "3072"},
        {"badblock_position": "5"},
        {"ecc_mode": "1"},
        {"ecc_bytes": "12"},
        {"ecc_steps": "4"},
        {"ecc_total": "112"},
        {"oob_free_offset": "0"},
        {"oob_free_length": "62"},
        {"scan_last_page": "2"},
        {"size": "536870912"},
        {"ecc_positions": ",".join(str(n) for n in range(35, 63))},
        {"ecc_positions": "36,36"},
        {"serial": "unexpected"},
        {"protected": "true"},
    ],
)
def test_inconsistent_or_extra_metadata_rejected(changes):
    with pytest.raises(ValueError):
        report.parse(frame(**changes))


def test_duplicate_missing_and_overlong_frames_fail_closed():
    for data in (
        frame().replace(b"protected=1\n", b""),
        frame().replace(b"protected=1\n", b"protected=1\nprotected=1\n"),
        b"x" * 1537,
        frame().replace(b"source=custom", b"source=\xffcustom"),
    ):
        with pytest.raises(ValueError):
            report.parse(data)


def test_serial_frame_normalization_without_content_transport():
    read, write = os.pipe()
    try:
        os.write(write, b"unrelated noise\n" + frame().replace(b"\n", b"\r\n"))
        assert (
            report.receive(read, time.monotonic() + 1)["status"]
            == "nand-readonly-contract-observed"
        )
    finally:
        os.close(read)
        os.close(write)


def test_attribute_registered_only_after_protection_and_master(monkeypatch):
    source = (
        "static int __devinit omap_nand_probe(struct platform_device *pdev)\n"
        "/* NAND write protect off */\n\tgpmc_cs_configure(info->gpmc_cs, GPMC_CONFIG_WP, 0);\n"
        "nand_scan_ident();\n\t/* second phase scan */\nnand_scan_tail();\n"
        "\n#ifdef CONFIG_MTD_PARTITIONS\n\terr = parse_mtd_partitions();\nadd_mtd_device();\n"
        "\tplatform_set_drvdata(pdev, &info->mtd);\n\tplatform_set_drvdata(pdev, NULL);"
    )
    monkeypatch.setattr(metadata, "DRIVER_SHA256", hashlib.sha256(source.encode()).hexdigest())
    text = configure.patch_driver(source)
    ordered = [
        "GPMC_CONFIG_WP, 1",
        "NAND_SKIP_BBTSCAN",
        "hearth_block_mtd_writes",
        "add_mtd_device()",
        "device_create_file",
    ]
    assert [text.index(x) for x in ordered] == sorted(text.index(x) for x in ordered)
    assert "GPMC_CONFIG_WP, 0" not in text
    with pytest.raises(ValueError):
        configure.patch_driver("unreviewed")
