import os
import shutil
import socket
import stat
import struct
import subprocess
import threading
import time
import zlib
from dataclasses import replace

import pytest

from firmware.network_snapshot.protocol import END, MAGIC, MAX_PAYLOAD, decode
from firmware.network_snapshot.run import receive_frame
from provisioning import file_backup, network_backup


def snapshot():
    return network_backup.Snapshot(
        b"s" * 32,
        (4096, 11776, 8000, 7500, 0x72B6, 0),
        tuple(file_backup.CapturedFile(i, True, 0o644, 0, 0, b"synthetic\0file") for i in range(4)),
    )


def frame(value=None):
    value = snapshot() if value is None else value
    payload = bytearray(struct.pack("<8I", 0, 4, *value.filesystem))
    for row in value.records:
        payload += struct.pack(
            "<6I", row.target, row.existed, row.mode, row.owner, row.group, len(row.data)
        )
        payload += row.data
    return (
        MAGIC
        + value.session
        + struct.pack("<II", len(payload), zlib.crc32(payload))
        + payload
        + END
    )


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    if shutil.which("clang") is None:
        pytest.skip("Clang required for original read-only capture sanitizer checks")
    path = tmp_path_factory.mktemp("network-reader-build") / "reader"
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-DHEARTH_HOST_LAB",
            "-fsanitize=address,undefined",
            "-Wl,--wrap=read",
            "tests/network_snapshot_harness.c",
            "firmware/network_snapshot/reader.c",
            "-o",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


@pytest.mark.parametrize("scenario", range(22))
def test_original_reader_faults_and_file_larger_than_legacy_limit(harness, tmp_path, scenario):
    result = subprocess.run(
        [str(harness), str(scenario), str(tmp_path)], check=False, capture_output=True, timeout=10
    )
    if result.returncode == 77:
        pytest.skip("Fixture filesystem lacks xattrs")
    assert result.returncode == 0, result.stderr.decode()
    assert not result.stdout and not result.stderr


def test_decode_preserves_binary_data_and_readonly_filesystem_evidence():
    assert decode(frame(), b"s" * 32) == snapshot()
    assert MAX_PAYLOAD == 7471232


@pytest.mark.parametrize("fault", ("crc", "session", "footer", "truncated", "extra", "bound"))
def test_transport_refuses_corruption_replay_and_missing_completion(fault):
    data = bytearray(frame())
    if fault == "crc":
        data[60] ^= 1
    elif fault == "session":
        data[8] ^= 1
    elif fault == "footer":
        data[-1] ^= 1
    elif fault == "truncated":
        data = data[:-1]
    elif fault == "extra":
        data += b"extra"
    else:
        struct.pack_into("<I", data, 40, MAX_PAYLOAD + 1)
    with pytest.raises(ValueError):
        decode(bytes(data), b"s" * 32)


@pytest.mark.parametrize(
    "fields",
    (
        {"target": 1},
        {"existed": False},
        {"owner": 1},
        {"group": 1},
        {"mode": 0o666},
        {"mode": 0o4755},
        {"data": b""},
        {"data": b"x" * 65537},
    ),
)
def test_metadata_and_per_target_limits_are_enforced(fields):
    value = snapshot()
    records = list(value.records)
    records[2] = replace(records[2], **fields)
    with pytest.raises(ValueError):
        decode(frame(replace(value, records=tuple(records))), value.session)


@pytest.mark.parametrize(
    "filesystem",
    ((4096, 1, 0, 0, 0x72B6, 0), (4096, 11776, 1, 2, 0x72B6, 0), (4096, 11776, 8000, 7500, 0, 0)),
)
def test_source_geometry_and_filesystem_identity_are_not_arbitrary(filesystem):
    with pytest.raises(ValueError):
        decode(frame(replace(snapshot(), filesystem=filesystem)), b"s" * 32)


def test_custody_reads_back_every_file_and_refuses_reuse_or_changed_data(tmp_path):
    tmp_path.chmod(0o700)
    output = tmp_path / "backup"
    receipt = network_backup.preserve(output, snapshot())
    assert network_backup.verify(output, snapshot()) == receipt
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in output.iterdir())
    with pytest.raises(FileExistsError):
        network_backup.preserve(output, snapshot())
    (output / "0.original").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        network_backup.verify(output, snapshot())


@pytest.mark.parametrize("fault", ("symlink", "hardlink", "mode", "extra"))
def test_custody_rejects_unsafe_files_and_unexpected_inventory(tmp_path, fault):
    tmp_path.chmod(0o700)
    output = tmp_path / "backup"
    network_backup.preserve(output, snapshot())
    target = output / "0.original"
    if fault == "symlink":
        target.unlink()
        target.symlink_to(output / "1.original")
    elif fault == "hardlink":
        os.link(target, tmp_path / "alias")
    elif fault == "mode":
        target.chmod(0o644)
    else:
        (output / "unexpected").touch()
    with pytest.raises((ValueError, OSError)):
        network_backup.verify(output, snapshot())


def test_no_receipt_if_original_readback_fails(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    original = file_backup._read

    def changed(directory, name, limit):
        return b"wrong" if name == "0.original" else original(directory, name, limit)

    monkeypatch.setattr(file_backup, "_read", changed)
    with pytest.raises(ValueError):
        network_backup.preserve(tmp_path / "backup", snapshot())
    assert not (tmp_path / "backup/receipt.json").exists()


def test_receiver_preserves_first_complete_bad_frame_without_accepting_retry(tmp_path):
    a, b = socket.socketpair()
    try:
        data = bytearray(frame())
        data[-9] ^= 1
        b.sendall(data + frame())
        target = tmp_path / "capture.bin"
        with pytest.raises(ValueError):
            receive_frame(a.fileno(), time.monotonic() + 1, b"s" * 32, target)
        assert target.read_bytes() == data
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
    finally:
        a.close()
        b.close()


def test_receiver_handles_file_above_legacy_limit_and_split_binary_chunks(tmp_path):
    value = snapshot()
    records = list(value.records)
    records[0] = replace(records[0], data=b"\0\xffsynthetic" * 110000)
    value = replace(value, records=tuple(records))
    data = frame(value)
    a, b = socket.socketpair()

    def produce():
        try:
            b.sendall(b"bounded startup noise" + data[:17])
            b.sendall(data[17:])
        finally:
            b.close()

    thread = threading.Thread(target=produce)
    thread.start()
    try:
        target = tmp_path / "capture.bin"
        assert receive_frame(a.fileno(), time.monotonic() + 5, value.session, target) == value
        assert target.read_bytes() == data
    finally:
        a.close()
        thread.join(timeout=5)


def test_receiver_retains_incomplete_frame_without_backup_receipt(tmp_path):
    a, b = socket.socketpair()
    data = frame()[:-10]
    b.sendall(data)
    b.close()
    try:
        target = tmp_path / "capture.bin"
        with pytest.raises(OSError):
            receive_frame(a.fileno(), time.monotonic() + 1, b"s" * 32, target)
        assert not target.exists()
        assert target.with_name("capture.bin.partial").read_bytes() == data
        assert not (tmp_path / "backup/receipt.json").exists()
    finally:
        a.close()
