import stat
import struct

import pytest

from firmware.file_writer import profile


@pytest.fixture
def archive(monkeypatch):
    monkeypatch.setattr(profile, "initramfs", lambda _: None)
    monkeypatch.setattr(profile, "helper_interpreter", lambda _: None)

    def metadata(data):
        if data == b"libc":
            return {"ld-linux-armhf.so.3"}, set(), {"open"}
        if data == b"loader":
            return set(), set(), set()
        return {"libc.so.6"}, {"open"}, set()

    monkeypatch.setattr(profile, "elf_metadata", metadata)
    program = b"\0" * 16 + struct.pack("<H", 2) + b"fixture"
    libraries = [
        ("lib/libc.so.6", stat.S_IFREG | 0o444, 0, b"libc", 0, 0),
        ("lib/ld-linux-armhf.so.3", stat.S_IFREG | 0o555, 0, b"loader", 0, 0),
    ]
    entries = [
        (
            name,
            stat.S_IFDIR | (0o700 if name in ("state", "native", "user") else 0o755),
            65534 if name == "state" else 0,
            b"",
            0,
            0,
        )
        for name in (".", "dev", "proc", "sys", "lib", "state", "native", "user")
    ]
    entries += [
        ("init", stat.S_IFREG | 0o555, 0, b"init", 0, 0),
        ("file-action", stat.S_IFREG | 0o500, 0, program, 0, 0),
        ("file-selftest", stat.S_IFREG | 0o555, 0, program, 0, 0),
        ("dev/console", stat.S_IFCHR | 0o600, 0, b"", 5, 1),
        *libraries,
        ("TRAILER!!!", 0, 0, b"", 0, 0),
    ]
    return entries, (1, program, b"init", program, libraries)


def test_private_capsule_program_is_inaccessible_to_unprivileged_selftest(archive):
    entries, args = archive
    profile.validate_entries(entries, *args)
    assert next(row for row in entries if row[0] == "file-action")[1] & 0o077 == 0


@pytest.mark.parametrize(
    "name,field,value",
    (
        ("file-action", 1, stat.S_IFREG | 0o555),
        ("file-action", 2, 65534),
        ("file-action", 3, b"different executable"),
        ("lib/ld-linux-armhf.so.3", 1, stat.S_IFREG | 0o444),
        ("state", 2, 0),
        ("native", 1, stat.S_IFDIR | 0o777),
        ("dev/console", 5, 2),
    ),
)
def test_archive_permission_identity_payload_and_device_changes_rejected(
    archive, name, field, value
):
    entries, args = archive
    changed = []
    for row in entries:
        copy = list(row)
        if row[0] == name:
            copy[field] = value
        changed.append(tuple(copy))
    with pytest.raises(ValueError):
        profile.validate_entries(changed, *args)


@pytest.mark.parametrize("extra", ("bin/sh", "lib/libc.stub.so", "native/settings.config"))
def test_shell_link_stub_and_real_settings_cannot_ship_as_extra_archive_entries(archive, extra):
    entries, args = archive
    with pytest.raises(ValueError):
        profile.validate_entries(entries + [(extra, stat.S_IFREG | 0o500, 0, b"bad", 0, 0)], *args)


def test_unresolved_native_abi_rejected(archive, monkeypatch):
    entries, args = archive
    monkeypatch.setattr(profile, "elf_metadata", lambda _: ({"libc.so.6"}, {"missing_abi"}, set()))
    with pytest.raises(ValueError):
        profile.validate_entries(entries, *args)


def test_generated_build_inputs_are_bounded_and_no_symlinks(tmp_path, monkeypatch):
    monkeypatch.setattr(profile, "ROOT", tmp_path)
    folder = tmp_path / "build"
    folder.mkdir()
    (folder / "input").write_bytes(b"data")
    assert profile.read_build(folder / "input", 4) == b"data"
    with pytest.raises(ValueError):
        profile.read_build(folder / "input", 3)
    (folder / "alias").symlink_to(folder / "input")
    with pytest.raises(ValueError):
        profile.read_build(folder / "alias", 4)
