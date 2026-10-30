import hashlib
import json
import os
import pty
import select
import shutil
import stat
import struct
import subprocess
import tempfile
import termios
import time
import zlib
from pathlib import Path

import pytest

from firmware.nand_metadata import configure as metadata
from firmware.nand_sample import configure, receiver
from firmware.probe import configure as probe


def frame(pass_id, page, payload=None):
    payload = bytes([page]) * receiver.RECORD if payload is None else payload
    header = struct.pack(
        "<8s5I", receiver.MAGIC, 1, pass_id, page, len(payload), zlib.crc32(payload)
    )
    return header + struct.pack("<I", zlib.crc32(header)) + payload


def wire(change=None):
    frames = [frame(p, i) for p in range(2) for i in range(64)]
    if change:
        frames = change(frames)
    return b"".join(frames)


def collect(data, tmp_path):
    with tempfile.TemporaryFile() as stream:
        stream.write(data)
        stream.seek(0)
        return receiver.collect(
            stream.fileno(), time.monotonic() + 2, tmp_path / "private/sample", tmp_path / "private"
        )


def test_sample_retains_geometry_and_no_character_device_constraints():
    text = metadata.configure(probe.configure(""))
    configure.verify(text)
    for forbidden in ("MTD_CHAR", "MTD_PARTITIONS", "MTD_BLKDEVS", "NET"):
        with pytest.raises(ValueError):
            configure.verify(text + f"\nCONFIG_{forbidden}=y\n")


def test_binary_tty_patch_requires_reviewed_source(monkeypatch):
    with pytest.raises(ValueError, match="unreviewed"):
        configure.patch_serial("unexpected source")
    original = "\tgs_tty_driver->init_termios = tty_std_termios;\n"
    monkeypatch.setattr(configure, "SERIAL_SHA256", hashlib.sha256(original.encode()).hexdigest())
    patched = configure.patch_serial(original)
    for field in ("c_iflag", "c_oflag", "c_lflag"):
        assert f"init_termios.{field} = 0;" in patched
    assert patched.index("= tty_std_termios;") < patched.index(".c_oflag = 0;")


@pytest.mark.parametrize("translate", [True, False])
def test_binary_framing_through_real_tty_output_processing(translate):
    master, slave = pty.openpty()
    try:
        attrs = termios.tcgetattr(slave)
        attrs[0] = attrs[3] = 0
        attrs[1] = termios.OPOST | termios.ONLCR if translate else 0
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        payload = (bytes(range(256)) * 9)[: receiver.RECORD]
        original = frame(0, 0, payload)
        expected = original.replace(b"\n", b"\r\n") if translate else original
        assert os.write(slave, original) == len(original)
        received = b""
        deadline = time.monotonic() + 1
        while len(received) < len(expected) and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                received += os.read(master, 4096)
        assert received == expected
        if translate:
            assert received != original
        else:
            _, _, crc = receiver.header_fields(received[:32])
            assert zlib.crc32(received[32:]) == crc
    finally:
        os.close(master)
        os.close(slave)


def test_private_two_pass_capture_and_permissions(tmp_path):
    result = collect(b"ignored identifying bytes\n" + wire(), tmp_path)
    assert result["status"] == "raw-sample-matched"
    assert result["firmware_backup"] is False
    root = tmp_path / "private/sample"
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    expected = b"".join(bytes([i]) * receiver.RECORD for i in range(64))
    for p in root.iterdir():
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert (root / "pass-0.raw").read_bytes() == expected
    assert (root / "pass-1.raw").read_bytes() == expected
    record = json.loads((root / "capture.json").read_text())
    assert record["passes_match"] and record["records_received"] == 128
    assert "identifying" not in json.dumps(record) + str(result)
    with pytest.raises(ValueError, match="existing"):
        collect(wire(), tmp_path)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda f: f[:5] + f[6:],
        lambda f: f[:5] + [f[4]] + f[5:],
        lambda f: f[:5] + [f[5][:-1] + bytes([f[5][-1] ^ 1])] + f[6:],
        lambda f: f[:5] + [bytes([f[5][0] ^ 1]) + f[5][1:]] + f[6:],
        lambda f: f[:-1],
        lambda f: f[:5] + [f[5][:10]],
    ],
)
def test_incomplete_or_corrupt_stream_preserved_without_success(tmp_path, mutate):
    with pytest.raises((OSError, ValueError)) as error:
        collect(wire(mutate), tmp_path)
    assert "identifying" not in str(error.value)
    record = json.loads((tmp_path / "private/sample/capture.json").read_text())
    assert record["status"] == "incomplete"
    assert record["records_received"] < 128


def test_distinct_raw_passes_are_preserved_and_rejected(tmp_path):
    data = wire(lambda f: f[:64] + [frame(1, 0, b"x" * receiver.RECORD)] + f[65:])
    with pytest.raises(ValueError, match="passes differ"):
        collect(data, tmp_path)
    root = tmp_path / "private/sample"
    record = json.loads((root / "capture.json").read_text())
    assert record["status"] == "raw-sample-mismatch" and not record["passes_match"]
    assert (root / "pass-0.raw").stat().st_size == 135168
    assert (root / "pass-1.raw").stat().st_size == 135168


def test_storage_sync_failure_cannot_report_success(tmp_path, monkeypatch):
    real_sync = os.fsync
    calls = 0

    def fail_first(fd):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated storage fault")
        real_sync(fd)

    monkeypatch.setattr(receiver.os, "fsync", fail_first)
    with pytest.raises(OSError, match="did not sync"):
        collect(wire(), tmp_path)
    record = json.loads((tmp_path / "private/sample/capture.json").read_text())
    assert record["status"] == "storage-failed"


def test_sync_recovers_only_before_first_accepted_page(tmp_path):
    first = bytearray(frame(0, 0))
    first[-1] ^= 1
    result = collect(bytes(first) + wire(), tmp_path)
    assert result["status"] == "raw-sample-matched"


def test_device_error_timeout_and_sync_bounds(tmp_path):
    for data in (receiver.FAILED, b"x" * (1024 * 1024 + 100)):
        with tempfile.TemporaryFile() as stream:
            stream.write(data)
            stream.seek(0)
            with pytest.raises(ValueError):
                list(receiver.frames(stream.fileno(), time.monotonic() + 2))
    with pytest.raises(TimeoutError):
        list(receiver.frames(-1, time.monotonic() - 1))


def test_private_path_policy_rejects_symlinks_and_existing(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    for path in (tmp_path / "outside", root / "nested/sample", root / "..", root / "bad name"):
        with pytest.raises(ValueError):
            receiver.validate_output(path, root)
    (root / "existing").symlink_to(tmp_path / "absent")
    with pytest.raises(ValueError):
        receiver.validate_output(root / "existing", root)
    alias = tmp_path / "alias"
    alias.symlink_to(root)
    with pytest.raises(ValueError):
        receiver.validate_output(alias / "fresh", alias)


def test_native_sample_guard_and_framing_harness(tmp_path):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("gcc is required for host-only C safeguards")
    assets = Path(__file__).resolve().parents[1] / "firmware/nand_sample"
    include = tmp_path / "linux"
    include.mkdir()
    (include / "sysfs.h").write_text("/* host test types are defined in the harness */\n")
    executable = tmp_path / "sample-test"
    subprocess.run(
        [
            compiler,
            "-std=gnu11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-unused-parameter",
            "-fsanitize=address,undefined",
            "-g",
            "-I",
            str(tmp_path),
            "-I",
            str(assets),
            str(assets / "test_sample.c"),
            "-o",
            str(executable),
        ],
        check=True,
        capture_output=True,
    )
    result = subprocess.run([str(executable)], check=True, capture_output=True)
    assert result.stdout == frame(1, 63, bytes(receiver.RECORD))[:32]
