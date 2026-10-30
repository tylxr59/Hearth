import json
import stat
import struct

import pytest

from tools import elf_review


def image():
    data = bytearray(1024)
    struct.pack_into(
        "<16sHHIIIIIHHHHHH",
        data,
        0,
        b"\x7fELF\x01\x01\x01" + bytes(9),
        2,
        40,
        1,
        0x1100,
        52,
        0,
        0,
        52,
        32,
        2,
        0,
        0,
        0,
    )
    struct.pack_into("<8I", data, 52, 1, 0, 0x1000, 0, 512, 512, 5, 4)
    struct.pack_into("<8I", data, 84, 1, 512, 0x2000, 0, 512, 768, 4, 4)
    data[768 : 768 + 17] = b"com.example.Test\0"
    data[800:805] = b"Read\0"
    struct.pack_into("<III", data, 512, 0x2100, 0x2120, 0x1101)
    return data


def test_private_offline_review_does_not_execute_input(tmp_path, monkeypatch):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    source, output = root / "input.elf", root / "report.json"
    source.write_bytes(image())
    monkeypatch.setattr(elf_review, "PRIVATE", root)
    summary = elf_review.review(source, [0x2000], output)
    assert summary == {
        "status": "offline-dispatch-review",
        "tables": 1,
        "methods": 1,
        "runtime_verified": False,
    }
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    entry = json.loads(output.read_text())["tables"][0]["entries"][0]
    assert entry == {"interface": "com.example.Test", "method": "Read", "handler": 0x1101}
    assert "source_sha256" not in summary
    with pytest.raises(ValueError, match="fresh"):
        elf_review.review(source, [0x2000], output)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.__setitem__(slice(0, 4), b"BAD!"),
        lambda d: struct.pack_into("<H", d, 18, 62),
        lambda d: struct.pack_into("<H", d, 42, 31),
        lambda d: struct.pack_into("<I", d, 68, 99999),
        lambda d: struct.pack_into("<I", d, 92, 0x1100),
    ],
)
def test_invalid_elf_bounds_and_mappings(mutate):
    data = image()
    mutate(data)
    with pytest.raises(ValueError):
        elf_review.ArmElf(data)


@pytest.mark.parametrize(
    "address,size", [(0, 4), (0x1FFF, 2), (0x2200, 1), (0x1000, 65537), (-1, 1)]
)
def test_read_rejects_holes_bss_and_excessive_ranges(address, size):
    with pytest.raises(ValueError):
        elf_review.ArmElf(image()).read(address, size)


@pytest.mark.parametrize(
    "fields", [(0, 0x2120, 0x1100), (0x2100, 0x2120, 0x2100), (0x2300, 0x2120, 0x1100)]
)
def test_dispatch_rejects_partial_records_noncode_and_unmapped_strings(fields):
    data = image()
    struct.pack_into("<III", data, 512, *fields)
    with pytest.raises(ValueError):
        elf_review.ArmElf(data).dispatch(0x2000)


def test_identifier_and_table_limits():
    data = image()
    data[768 : 768 + 130] = b"x" * 130
    with pytest.raises(ValueError):
        elf_review.ArmElf(data).dispatch(0x2000)
    elf = elf_review.ArmElf(image())
    for address, limit in [(0x2001, 64), (0x2000, 0), (0x2000, 129)]:
        with pytest.raises(ValueError):
            elf.dispatch(address, limit)


def test_private_path_and_directory_policy(tmp_path, monkeypatch):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    source = root / "source"
    source.write_bytes(image())
    alias = root / "alias"
    alias.symlink_to(source)
    monkeypatch.setattr(elf_review, "PRIVATE", root)
    for path in (alias, tmp_path / "outside"):
        with pytest.raises(ValueError):
            elf_review.private_path(path)
    root.chmod(0o755)
    with pytest.raises(ValueError, match="restricted"):
        elf_review.review(source, [0x2000], root / "report")


def test_fixed_count_command_table():
    data = image()
    struct.pack_into("<III", data, 512, 0x2120, 0x1101, 7)
    assert elf_review.ArmElf(data).commands(0x2000, 1) == [
        {"name": "Read", "handler": 0x1101, "metadata_word": 7}
    ]
    struct.pack_into("<III", data, 524, 0x2120, 0x1100, 0)
    with pytest.raises(ValueError, match="duplicate"):
        elf_review.ArmElf(data).commands(0x2000, 2)


@pytest.mark.parametrize("address,count", [(0x2001, 1), (0x2000, 0), (0x2000, 129)])
def test_command_table_bounds(address, count):
    with pytest.raises(ValueError):
        elf_review.ArmElf(image()).commands(address, count)
