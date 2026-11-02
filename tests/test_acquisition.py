"""Original data-only acquisition fixtures; no native firmware or device access."""

import json
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

from firmware.acquisition import codec, profile, run
from firmware.file_snapshot.run import decode as snapshot_decode
from tests.test_file_snapshot_profile import frame as snapshot_frame
from tests.test_network_snapshot import frame as network_frame
from tests.test_network_snapshot import snapshot as network_snapshot

SESSION = b"s" * 32


def payload(rows=None, **changes):
    rows = [(b"file", b"synthetic\0data", stat.S_IFREG | 0o755)] if rows is None else rows
    header = {"status": 0, "count": len(rows), "scanned": len(rows), "limited": 0} | changes
    out = bytearray(struct.pack("<4I", *header.values()))
    for path, data, mode in rows:
        out += struct.pack("<6I", len(path), mode, 0, 0, len(data), len(data)) + path + data
    return bytes(out)


def group_frame(index, data=None, session=SESSION):
    data = payload() if data is None else data
    return (
        codec.MAGIC
        + session
        + struct.pack("<3I", index, len(data), zlib.crc32(data))
        + data
        + codec.END
    )


def stream():
    snapshot = snapshot_decode(snapshot_frame(), SESSION)
    network = network_snapshot()
    network = replace(network, records=network.records[:3] + (replace(snapshot[8], target=3),))
    return (
        snapshot_frame()
        + network_frame(network)
        + b"".join(group_frame(i) for i in range(4))
        + codec.DONE
    )


def decoded(chunk_size=65536):
    frames = {}
    decoder = codec.Decoder(SESSION, lambda name, data: frames.__setitem__(name, data))
    wire = stream()
    for at in range(0, len(wire), chunk_size):
        decoder.feed(wire[at : at + chunk_size])
    return decoder, frames


@pytest.mark.parametrize("chunk_size", (1, 7, 31, 52, 65536))
def test_ordered_stream_handles_usb_fragmentation_and_coalescing(chunk_size):
    decoder, frames = decoded(chunk_size)
    assert decoder.complete and not decoder.buffer
    assert len(decoder.snapshot) == 9 and len(decoder.network.records) == 4
    assert [row.path for row in decoder.files] == [p + "/file" for p in codec.GROUPS]
    assert len(frames) == 7 and frames["capture.bin"] == snapshot_frame()
    assert frames["completion.bin"] == codec.DONE
    with pytest.raises(ValueError):
        decoder.feed(b"extra")


@pytest.mark.parametrize("fault", ("nonce", "order", "crc", "footer", "length", "done"))
def test_invalid_stream_never_reports_completion(fault):
    wire = stream()
    at = wire.index(codec.MAGIC)
    if fault == "nonce":
        wire = wire[: at + 8] + b"x" * 32 + wire[at + 40 :]
    elif fault == "order":
        wire = wire[: at + 40] + struct.pack("<I", 1) + wire[at + 44 :]
    elif fault == "crc":
        wire = wire[: at + 48] + b"\0" * 4 + wire[at + 52 :]
    elif fault == "footer":
        wire = wire.replace(codec.END, b"INVALID!", 1)
    elif fault == "length":
        wire = wire[: at + 44] + struct.pack("<I", codec.LIMIT + 1) + wire[at + 48 :]
    else:
        wire += b"extra"
    frames = {}
    decoder = codec.Decoder(SESSION, lambda name, data: frames.__setitem__(name, data))
    with pytest.raises(ValueError):
        decoder.feed(wire)
    assert not decoder.complete
    if fault in ("crc", "footer"):
        assert "group-0.bin" in frames  # Preserve bounded failed evidence.


def test_missing_completion_and_partial_group_are_not_success():
    for wire in (stream()[:-1], stream()[: stream().index(codec.MAGIC) + 53]):
        decoder = codec.Decoder(SESSION, lambda *_: None)
        decoder.feed(wire)
        assert not decoder.complete


@pytest.mark.parametrize("path", (b"../secret", b"/absolute", b"a//b", b"a/./b", b"a\\b", b"a\0b"))
def test_group_rejects_paths_outside_private_corpus(path):
    with pytest.raises(ValueError):
        codec.decode_group(payload([(path, b"x", stat.S_IFREG | 0o644)]), "lib")


@pytest.mark.parametrize(
    "fault", ("duplicate", "symlink", "short", "status", "limited", "count", "extra")
)
def test_group_requires_complete_regular_unique_files(fault):
    value = payload()
    if fault == "duplicate":
        value = payload([(b"a", b"x", stat.S_IFREG)] * 2)
    elif fault == "symlink":
        value = payload([(b"a", b"x", stat.S_IFLNK)])
    elif fault == "short":
        value = value[:32] + struct.pack("<I", 999) + value[36:]
    elif fault in ("status", "limited"):
        value = payload(**{fault: 1})
    elif fault == "count":
        value = payload(count=257, scanned=257)
    else:
        value += b"extra"
    with pytest.raises(ValueError):
        codec.decode_group(value, "lib")


def test_overlapping_snapshot_client_configuration_must_match():
    decoder = codec.Decoder(SESSION, lambda *_: None)
    with pytest.raises(ValueError, match="overlapping"):
        decoder.feed(snapshot_frame() + network_frame())
    assert not decoder.complete


def test_preserved_corpus_is_private_data_and_both_backups_validate(tmp_path):
    tmp_path.chmod(0o700)
    decoder, _ = decoded()
    result = run.preserve_inputs(tmp_path, decoder)
    assert result["flash_writes"] is False and result["firmware_backup"] is False
    record = json.loads((tmp_path / "extraction.json").read_bytes())
    rows = {row["path"]: row for row in record["files"]}
    assert rows["media/user-config/settings.config"]["source"] == "user-config"
    assert rows["lib/file"]["mode"] == 0o755
    assert "settings.config" not in rows
    for path in tmp_path.rglob("*"):
        assert not path.is_symlink()
        assert stat.S_IMODE(path.stat().st_mode) == (0o700 if path.is_dir() else 0o600)
    assert (tmp_path / "corpus/lib/file").read_bytes() == b"synthetic\0data"
    with pytest.raises(FileExistsError):
        run.preserve_inputs(tmp_path, decoder)


def test_conflicting_group_and_fixed_file_refuse_preservation(tmp_path):
    decoder, _ = decoded()
    decoder.files.append(
        codec.AcquiredFile("nestlabs/sbin/nlclient", stat.S_IFREG | 0o644, 0, 0, b"different")
    )
    with pytest.raises(ValueError, match="overlapping"):
        run.preserve_inputs(tmp_path, decoder)
    assert not (tmp_path / "corpus").exists()


def test_receiver_sends_one_start_token_and_preserves_complete_private_frames(tmp_path):
    left, right = socket.socketpair()
    observed = []

    def device():
        observed.append(right.recv(32))
        right.sendall(stream())

    worker = threading.Thread(target=device)
    worker.start()
    try:
        result = run.receive(left.fileno(), time.monotonic() + 3, SESSION, tmp_path)
        assert result["library_groups"] == 4
        assert observed == [SESSION]
    finally:
        left.close()
        right.close()
        worker.join(3)


def test_offline_check_does_not_inventory_or_open_usb(monkeypatch):
    monkeypatch.setattr(run, "private_path", lambda value: value)
    monkeypatch.setattr(profile, "check", lambda _: {"offline": True})
    monkeypatch.setattr(run, "require_native", lambda _: pytest.fail("must not open USB"))
    assert run.run("unused") == {"offline": True}


def test_disconnected_stream_preserves_bounded_partial_frame(tmp_path):
    left, right = socket.socketpair()
    partial = snapshot_frame()[:60]
    right.sendall(partial)
    right.shutdown(socket.SHUT_WR)
    try:
        with pytest.raises(OSError, match="disconnected"):
            run.receive(left.fileno(), time.monotonic() + 1, SESSION, tmp_path)
        assert (tmp_path / "incomplete-frame.bin").read_bytes() == partial
        assert not (tmp_path / "extraction.json").exists()
    finally:
        left.close()
        right.close()


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    if shutil.which("clang") is None:
        pytest.skip("Clang needed for original acquisition sanitizer fixture")
    directory = tmp_path_factory.mktemp("acquisition-harness")
    output = directory / "reader"
    subprocess.run(
        [
            "clang",
            "-DHEARTH_CAPTURE_CAPACITY=16777216",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "tests/startup_logs_harness.c",
            "firmware/acquisition/core.c",
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return output


def test_original_walker_acquires_full_files_larger_than_log_tail(harness, tmp_path):
    data = b"prefix\0" + b"x" * 131072
    (tmp_path / "large").write_bytes(data)
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested/file").write_bytes(b"small")
    (tmp_path / "link").symlink_to(tmp_path / "large")
    os.mkfifo(tmp_path / "pipe")
    result = subprocess.run(
        [str(harness), str(tmp_path)], check=True, capture_output=True, timeout=5
    )
    assert not result.stderr
    rows = {row.path: row for row in codec.decode_group(result.stdout, "lib")}
    assert rows["lib/large"].data == data
    assert set(rows) == {"lib/large", "lib/nested/file"}


def test_original_walker_limit_is_not_accepted_as_complete(harness, tmp_path):
    for index in range(257):
        (tmp_path / str(index)).write_bytes(b"x")
    result = subprocess.run(
        [str(harness), str(tmp_path)], check=True, capture_output=True, timeout=5
    )
    assert struct.unpack_from("<I", result.stdout)[0] == 2
    with pytest.raises(ValueError):
        codec.decode_group(result.stdout, "lib")
