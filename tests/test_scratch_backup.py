import hashlib
import json
import os
import stat

import pytest

from firmware.scratch_test import backup


@pytest.fixture
def snapshot(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    data = bytearray(b"\xff" * backup.SIZE)
    data[backup.PAGE + 2 : backup.PAGE + 10] = backup.MARKER
    data = bytes(data)
    return root, data, hashlib.sha256(data).digest()


def test_ack_only_after_snapshot_manifest_and_both_directories_sync(snapshot, monkeypatch):
    root, data, digest = snapshot
    synced = []
    original = os.fsync

    def sync(fd):
        synced.append(stat.S_ISDIR(os.fstat(fd).st_mode))
        return original(fd)

    monkeypatch.setattr(os, "fsync", sync)
    output = root / "scratch"
    ack = backup.durable_snapshot(output, data, digest, root)
    assert ack == b"HSACK001" + digest
    assert synced == [False, False, True, True]
    assert (output / "original.raw-oob").read_bytes() == data
    record = json.loads((output / "original.json").read_text())
    assert record["sha256"] == digest.hex() and record["device_written"] is False
    assert record["block"] == 1312 and record["data_offset"] == 171966464
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in output.iterdir())
    with pytest.raises(ValueError, match="existing"):
        backup.durable_snapshot(output, data, digest, root)


@pytest.mark.parametrize("failure", [1, 2, 3, 4])
def test_no_ack_after_any_storage_sync_failure(snapshot, monkeypatch, failure):
    root, data, digest = snapshot
    calls = 0

    def broken_sync(fd):
        nonlocal calls
        calls += 1
        if calls == failure:
            raise OSError("injected storage failure")

    monkeypatch.setattr(os, "fsync", broken_sync)
    with pytest.raises(OSError, match="injected"):
        backup.durable_snapshot(root / "scratch", data, digest, root)
    assert (root / "scratch/original.raw-oob").exists()


@pytest.mark.parametrize("position", [0, 2048, 2049, 2050, 2057, 2058, 2111, 2112, 135167])
def test_noncanonical_data_marker_padding_or_ecc_has_no_output(snapshot, position):
    root, data, _ = snapshot
    changed = bytearray(data)
    changed[position] ^= 1
    changed = bytes(changed)
    with pytest.raises(ValueError, match="canonical"):
        backup.durable_snapshot(root / "scratch", changed, hashlib.sha256(changed).digest(), root)
    assert not list(root.iterdir())


def test_no_ack_for_target_digest_mismatch_or_truncation(snapshot):
    root, data, digest = snapshot
    with pytest.raises(ValueError, match="digest"):
        backup.durable_snapshot(root / "scratch", data, b"\0" * 32, root)
    with pytest.raises(ValueError, match="canonical"):
        backup.durable_snapshot(root / "scratch", data[:-1], digest, root)
    assert not list(root.iterdir())


def test_no_output_outside_private_or_via_symlink(snapshot, tmp_path):
    root, data, digest = snapshot
    link = tmp_path / "link"
    link.symlink_to(root, target_is_directory=True)
    for output in (tmp_path / "public", link / "scratch"):
        with pytest.raises(ValueError):
            backup.durable_snapshot(output, data, digest, root)
    root.chmod(0o755)
    with pytest.raises(ValueError, match="owner-only"):
        backup.durable_snapshot(root / "scratch", data, digest, root)
