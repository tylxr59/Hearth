import json
import os
import shutil
import socket
import stat
import struct
import subprocess
import time
import zlib

import pytest

from firmware.startup_diagnostic import profile
from firmware.startup_diagnostic.run import LOG_END, LOG_MAGIC, parse_logs, receive
from tests.test_file_snapshot_profile import frame


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    if shutil.which("clang") is None:
        pytest.skip("Clang needed for original read-only log-core sanitizer checks")
    output = tmp_path_factory.mktemp("startup-log-harness") / "reader"
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "tests/startup_logs_harness.c",
            "firmware/startup_diagnostic/logs.c",
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return output


def acquire(harness, root):
    result = subprocess.run([str(harness), str(root)], capture_output=True, check=True, timeout=5)
    assert result.stderr == b""
    return parse_logs(result.stdout)


def test_reader_captures_nested_log_tails_and_never_follows_symlink_or_fifo(harness, tmp_path):
    root = tmp_path / "logs"
    root.mkdir()
    (root / "app").mkdir()
    (root / "app/main.log").write_bytes(b"synthetic\0log")
    large = b"old prefix" + b"t" * 65536
    (root / "large.log").write_bytes(large)
    secret = tmp_path / "outside"
    secret.write_bytes(b"must never be acquired")
    (root / "alias").symlink_to(secret)
    os.mkfifo(root / "pipe")
    result = acquire(harness, root)
    assert result["status"] == 0
    rows = {row["path"]: row for row in result["files"]}
    assert set(rows) == {"app/main.log", "large.log"}
    assert rows["app/main.log"]["data"] == b"synthetic\0log"
    assert rows["large.log"]["original_bytes"] == len(large)
    assert rows["large.log"]["data"] == b"t" * 65536


def test_reader_explicitly_reports_file_count_limit(harness, tmp_path):
    for index in range(65):
        (tmp_path / f"{index}.log").write_bytes(b"fixture")
    result = acquire(harness, tmp_path)
    assert result["status"] == 2 and result["limit"] and len(result["files"]) == 64


def test_reader_depth_limit_prevents_recursive_unbounded_walk(harness, tmp_path):
    nested = tmp_path
    for _ in range(6):
        nested = nested / "nested"
        nested.mkdir()
    (nested / "unreachable").write_bytes(b"fixture")
    result = acquire(harness, tmp_path)
    assert result["status"] == 2 and result["files"] == []


def test_reader_empty_log_partition_is_complete(harness, tmp_path):
    assert acquire(harness, tmp_path) == {"status": 0, "scanned": 0, "limit": False, "files": []}


@pytest.mark.parametrize("path", (b"../secret", b"/absolute", b"a//b", b"a\x00b", b"a/./b"))
def test_valid_transport_cannot_substitute_log_paths(path):
    payload = (
        struct.pack("<4I", 0, 1, 1, 0)
        + struct.pack("<6I", len(path), stat.S_IFREG | 0o600, 0, 0, 1, 1)
        + path
        + b"x"
    )
    with pytest.raises(ValueError):
        parse_logs(payload)


def test_receive_preserves_both_bound_frames_and_validates_snapshot(tmp_path):
    left, right = socket.socketpair()
    logs = struct.pack("<4I", 0, 0, 0, 0)
    message = (
        LOG_MAGIC + b"s" * 32 + struct.pack("<II", len(logs), zlib.crc32(logs)) + logs + LOG_END
    )
    try:
        right.sendall(frame(session=b"x" * 32) + frame() + message)
        records, result = receive(left.fileno(), time.monotonic() + 1, b"s" * 32, tmp_path)
        assert len(records) == 9 and result["files"] == []
        assert (tmp_path / "snapshot.bin").read_bytes() == frame()
        assert (tmp_path / "logs.bin").read_bytes() == message
    finally:
        left.close()
        right.close()


def test_corrupt_log_evidence_preserved_without_acceptance(tmp_path):
    left, right = socket.socketpair()
    logs = struct.pack("<4I", 0, 0, 0, 0)
    message = LOG_MAGIC + b"s" * 32 + struct.pack("<II", len(logs), 0) + logs + LOG_END
    try:
        right.sendall(frame() + message)
        with pytest.raises(ValueError):
            receive(left.fileno(), time.monotonic() + 1, b"s" * 32, tmp_path)
        assert (tmp_path / "logs.bin").read_bytes() == message
    finally:
        left.close()
        right.close()


def test_profile_refuses_source_changes_before_any_usb_or_build_read(tmp_path, monkeypatch):
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    (tmp_path / "profile.json").write_text(
        json.dumps({"status": profile.STATUS, "device_executed": False, "recipes": {}})
    )
    (tmp_path / "profile.json").chmod(0o600)
    with pytest.raises(ValueError):
        profile.check(tmp_path)
