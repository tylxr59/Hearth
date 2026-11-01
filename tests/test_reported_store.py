import os

import pytest

from backend import reported_store as store
from backend.validation import Invalid
from tests.test_reported_cache import fixture


def test_private_cache_atomic_readback_and_replace(tmp_path):
    tmp_path.chmod(0o700)
    assert store.load(tmp_path) is None
    data = fixture()
    store.save(tmp_path, data)
    assert store.load(tmp_path) == data
    assert (tmp_path / store.NAME).stat().st_mode & 0o777 == 0o600
    data["saved_at"] += 1
    store.save(tmp_path, data)
    assert store.load(tmp_path) == data and sorted(p.name for p in tmp_path.iterdir()) == [
        store.NAME
    ]


@pytest.mark.parametrize("fault", ["symlink", "hardlink", "public", "fifo", "corrupt", "oversize"])
def test_unexpected_existing_cache_refused_without_altering_it(tmp_path, fault):
    tmp_path.chmod(0o700)
    p = tmp_path / store.NAME
    if fault == "symlink":
        other = tmp_path / "other"
        other.write_text("do-not-touch")
        p.symlink_to(other)
    elif fault == "fifo":
        os.mkfifo(p, 0o600)
    else:
        store.save(tmp_path, fixture())
        if fault == "hardlink":
            os.link(p, tmp_path / "alias")
        elif fault == "public":
            p.chmod(0o644)
        elif fault == "corrupt":
            p.write_bytes(b"not JSON")
        elif fault == "oversize":
            p.write_bytes(b"x" * (store.LIMIT + 1))
    before = p.lstat()
    with pytest.raises((Invalid, OSError)):
        store.load(tmp_path)
    with pytest.raises((Invalid, OSError)):
        store.save(tmp_path, fixture())
    after = p.lstat()
    assert (after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns) == (
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
    )


def test_directory_symlink_or_shared_permissions_refused(tmp_path):
    tmp_path.chmod(0o755)
    with pytest.raises(Invalid):
        store.save(tmp_path, fixture())
    tmp_path.chmod(0o700)
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(Invalid):
        store.load(link)


def test_failed_sync_preserves_previous_cache_and_removes_temporary(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    store.save(tmp_path, fixture())
    before = (tmp_path / store.NAME).read_bytes()

    def fail(_):
        raise OSError("synthetic fsync fault")

    monkeypatch.setattr(store.os, "fsync", fail)
    with pytest.raises(OSError):
        store.save(tmp_path, fixture())
    assert (tmp_path / store.NAME).read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == [store.NAME]
