import os
from dataclasses import replace

import pytest

from provisioning import file_backup as backup


@pytest.fixture
def captured():
    return tuple(
        backup.CapturedFile(
            i,
            i not in (4, 5),
            0 if i in (4, 5) else 0o644,
            0,
            0,
            b"" if i in (4, 5) else b"synthetic\x00original\xff",
        )
        for i in range(9)
    )


@pytest.fixture
def destination(tmp_path):
    os.chmod(tmp_path, 0o700)
    return tmp_path / "fresh-backup"


SCOPE = {"session": b"s" * 32, "plan": b"p" * 32, "native_root": "root0"}


def test_durable_backup_readback_and_fresh_destination(destination, captured):
    receipt = backup.preserve(destination, captured, **SCOPE)
    assert backup.verify(destination, captured, **SCOPE) == receipt
    assert destination.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in destination.iterdir())
    assert (destination / "4.original").read_bytes() == b""
    with pytest.raises(FileExistsError):
        backup.preserve(destination, captured, **SCOPE)


@pytest.mark.parametrize("change", ["bytes", "mode", "link", "extra", "receipt", "manifest"])
def test_backup_tampering_never_validates(destination, captured, change):
    backup.preserve(destination, captured, **SCOPE)
    target = destination / "0.original"
    if change == "bytes":
        target.write_bytes(b"different")
    elif change == "mode":
        target.chmod(0o644)
    elif change == "link":
        target.rename(destination.parent / "outside")
        target.symlink_to(destination.parent / "outside")
    elif change == "extra":
        (destination / "unexpected").write_bytes(b"")
    else:
        (destination / f"{change}.json").write_bytes(b"{}\n")
    with pytest.raises((ValueError, OSError)):
        backup.verify(destination, captured, **SCOPE)


@pytest.mark.parametrize(
    "field,value", [("session", b"x" * 32), ("plan", b"x" * 32), ("native_root", "root1")]
)
def test_receipt_is_bound_to_exact_session_plan_and_root(destination, captured, field, value):
    backup.preserve(destination, captured, **SCOPE)
    with pytest.raises(ValueError):
        backup.verify(destination, captured, **(SCOPE | {field: value}))


@pytest.mark.parametrize(
    "invalid",
    [
        {"target": 1},
        {"existed": False},
        {"mode": 0o4755},
        {"owner": 1000},
        {"group": 1000},
        {"data": b"x" * (backup.LIMIT + 1)},
        {"target": False},
    ],
)
def test_snapshot_scope_rejected_before_creating_output(destination, captured, invalid):
    records = (replace(captured[0], **invalid),) + captured[1:]
    with pytest.raises(ValueError):
        backup.preserve(destination, records, **SCOPE)
    assert not destination.exists()


def test_parent_symlink_and_permissive_directory_refused(destination, captured):
    link = destination.parent / "alias"
    link.symlink_to(destination.parent, target_is_directory=True)
    with pytest.raises(OSError):
        backup.preserve(link / "backup", captured, **SCOPE)
    destination.parent.chmod(0o755)
    with pytest.raises(ValueError):
        backup.preserve(destination, captured, **SCOPE)
    assert not destination.exists()


def test_fsync_failure_before_receipt_keeps_partial_evidence(destination, captured, monkeypatch):
    real_sync = os.fsync
    calls = 0

    def sync(fd):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError("injected disk failure")
        real_sync(fd)

    monkeypatch.setattr(backup.os, "fsync", sync)
    with pytest.raises(OSError):
        backup.preserve(destination, captured, **SCOPE)
    assert destination.is_dir() and (destination / "0.original").exists()
    assert not (destination / "receipt.json").exists()


def test_bad_readback_cannot_produce_receipt(destination, captured, monkeypatch):
    real_read = backup._read

    def read(directory, name, limit):
        data = real_read(directory, name, limit)
        return b"corrupted readback" if name == "0.original" else data

    monkeypatch.setattr(backup, "_read", read)
    with pytest.raises(ValueError):
        backup.preserve(destination, captured, **SCOPE)
    assert not (destination / "receipt.json").exists()


def test_partial_writes_preserve_all_original_bytes(destination, captured, monkeypatch):
    real_write = os.write

    def short_write(fd, data):
        return real_write(fd, data[:3])

    monkeypatch.setattr(backup.os, "write", short_write)
    backup.preserve(destination, captured, **SCOPE)
    backup.verify(destination, captured, **SCOPE)
