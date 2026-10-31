import hashlib
import shutil
import socket
import struct
import subprocess
import time
import zlib
from dataclasses import replace
from pathlib import Path

import pytest

from firmware.file_snapshot import configure
from firmware.file_snapshot.run import END, MAGIC, MAX_PAYLOAD, decode, receive_frame
from firmware.probe.configure import configure as probe_configure
from provisioning.file_backup import CapturedFile


def frame(records=None, session=b"s" * 32):
    if records is None:
        records = tuple(
            CapturedFile(
                i,
                i not in (4, 5),
                0 if i in (4, 5) else 0o644,
                0,
                0,
                b"" if i in (4, 5) else b"fixture\x00\xff",
            )
            for i in range(9)
        )
    data = bytearray(struct.pack("<II", 0, 9))
    for item in records:
        data.extend(
            struct.pack(
                "<6I", item.target, item.existed, item.mode, item.owner, item.group, len(item.data)
            )
        )
        data.extend(item.data)
    return MAGIC + session + struct.pack("<II", len(data), zlib.crc32(data)) + data + END


def test_binary_snapshot_preserves_exact_bytes_and_absence():
    records = decode(frame(), b"s" * 32)
    assert records[0].data == b"fixture\x00\xff"
    assert not records[4].existed and records[4].data == b""
    assert records[7].target == 7


@pytest.mark.parametrize("change", ["crc", "session", "footer", "truncated", "extra", "bound"])
def test_snapshot_transport_fails_closed(change):
    data = frame()
    if change == "crc":
        data = data[:60] + bytes([data[60] ^ 1]) + data[61:]
    elif change == "session":
        data = frame(session=b"x" * 32)
    elif change == "footer":
        data = data[:-8] + b"INVALID\n"
    elif change == "truncated":
        data = data[:-1]
    elif change == "extra":
        data += b"extra"
    else:
        data = data[:40] + struct.pack("<I", MAX_PAYLOAD + 1) + data[44:]
    with pytest.raises(ValueError):
        decode(data, b"s" * 32)


def test_valid_crc_does_not_allow_scope_substitution():
    records = list(decode(frame(), b"s" * 32))
    records[0] = replace(records[0], target=8)
    with pytest.raises(ValueError):
        decode(frame(records), b"s" * 32)


def test_receiver_discards_stale_session_and_preserves_complete_frame(tmp_path):
    left, right = socket.socketpair()
    try:
        data = frame()
        right.sendall(frame(session=b"x" * 32) + data)
        result = receive_frame(
            left.fileno(), time.monotonic() + 1, b"s" * 32, tmp_path / "capture.bin"
        )
        assert result[0].data == b"fixture\x00\xff"
        assert (tmp_path / "capture.bin").read_bytes() == data
        assert (tmp_path / "capture.bin").stat().st_mode & 0o777 == 0o600
    finally:
        left.close()
        right.close()


def test_profile_keeps_mutation_interfaces_disabled():
    text = configure.configure(probe_configure(""))
    configure.verify(text)
    for name in ("BLOCK", "MTD_CHAR", "MTD_BLOCK", "NET", "MTD_CMDLINE_PARTS", "RTC_CLASS"):
        with pytest.raises(ValueError):
            configure.verify(configure.setting(text, name, True))
    for name in ("JFFS2_FS", "JFFS2_FS_XATTR", "MTD_PARTITIONS", "JFFS2_FS_WRITEBUFFER"):
        with pytest.raises(ValueError):
            configure.verify(configure.setting(text, name, False))


def test_snapshot_registration_retains_protection_before_partitions(monkeypatch):
    source = (
        "static int __devinit omap_nand_probe(struct platform_device *pdev)\n"
        "/* NAND write protect off */\n\tgpmc_cs_configure(info->gpmc_cs, GPMC_CONFIG_WP, 0);\n"
        "nand_scan_ident();\n\t/* second phase scan */\nnand_scan_tail();\n"
        "\n#ifdef CONFIG_MTD_PARTITIONS\n"
        "\terr = parse_mtd_partitions(&info->mtd, part_probes, &info->parts, 0);\n"
        "add_mtd_partitions();"
    )
    monkeypatch.setattr(
        configure.metadata, "DRIVER_SHA256", hashlib.sha256(source.encode()).hexdigest()
    )
    patched = configure.patch_driver(source)
    ordered = [
        "GPMC_CONFIG_WP, 1",
        "nand_scan_ident()",
        "NAND_ROM",
        "nand_scan_tail()",
        "hearth_wp_is_asserted",
        "hearth_block_mtd_writes",
        "add_mtd_partitions()",
    ]
    positions = [patched.index(item) for item in ordered]
    assert positions == sorted(positions)
    assert "parse_mtd_partitions(" not in patched


def test_reader_allowlist_matches_host_backup():
    import re

    from provisioning.file_backup import TARGETS

    source = Path("firmware/file_install/targets.h").read_text()
    assert tuple(re.findall(r'"([^"\n]+)"', source)) == TARGETS


def test_freestanding_snapshot_links_without_native_firmware(tmp_path):
    if not shutil.which("clang") or not shutil.which("ld.lld"):
        pytest.skip("Clang and LLD required")
    (tmp_path / "session.h").write_text("static const unsigned char hearth_session[32]={0};\n")
    subprocess.run(
        [
            "clang",
            "--target=arm-linux-gnueabihf",
            "-marm",
            "-march=armv7-a",
            "-fuse-ld=lld",
            "-fomit-frame-pointer",
            "-ffreestanding",
            "-fno-builtin",
            "-fno-stack-protector",
            "-Os",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-nostdlib",
            "-static",
            "-Wl,-e,_start",
            "-I",
            str(tmp_path),
            "-I",
            "firmware/file_install",
            "firmware/file_snapshot/init.c",
            "firmware/file_install/snapshot.c",
            "-o",
            str(tmp_path / "init"),
        ],
        capture_output=True,
        check=True,
    )
