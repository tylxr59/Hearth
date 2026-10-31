import hashlib
import json
import shutil
import stat
import struct
import subprocess
import tempfile
import time
import zlib
from pathlib import Path

import pytest

from firmware.nand_ecc_sample import receiver, reference


def payload(page):
    return bytes([page]) * receiver.RECORD


def frame(pass_id, page, data=None):
    data = payload(page) if data is None else data
    header = struct.pack(
        "<8s5I", receiver.MAGIC, 1, pass_id, receiver.FIRST_PAGE + page, len(data), zlib.crc32(data)
    )
    return header + struct.pack("<I", zlib.crc32(header)) + data


def failure(stage=2, pass_id=1, page=49, code=-74):
    h = struct.pack(
        "<8s5I", receiver.FAILED, 1, stage, pass_id, receiver.FIRST_PAGE + page, code & 0xFFFFFFFF
    )
    return h + struct.pack("<I", zlib.crc32(h))


def make_reference(tmp_path, data=None):
    root = tmp_path / "private"
    root.mkdir(mode=0o700, exist_ok=True)
    folder = root / "reference"
    folder.mkdir(mode=0o700)
    data = b"".join(payload(p) for p in range(64)) if data is None else data
    path = folder / "expected.ecc-oob"
    path.write_bytes(data)
    path.chmod(0o600)
    record = {
        "status": "preserved-bch4-data-and-raw-oob-reference",
        "file": path.name,
        "flash_data_offset": 190 * 131072,
        "pages": 64,
        "record_bytes": 2112,
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    meta = folder / "reference.json"
    meta.write_text(json.dumps(record))
    meta.chmod(0o600)
    return root, path


def collect(tmp_path, wire, expected=None):
    root, path = make_reference(tmp_path, expected)
    with tempfile.TemporaryFile() as stream:
        stream.write(wire)
        stream.seek(0)
        return receiver.collect(stream.fileno(), time.monotonic() + 2, root / "capture", path, root)


def wire():
    return b"".join(frame(p, i) for p in range(2) for i in range(64))


def test_corrected_data_and_oob_must_match_private_reference(tmp_path):
    result = collect(tmp_path, b"prefix noise\n" + wire())
    assert (
        result["status"] == "normal-ecc-reference-matched" and result["reference_matched"] is True
    )
    assert result["write_path_verified"] is False and result["ecc_fault_injection_tested"] is False
    out = tmp_path / "private/capture"
    for p in out.iterdir():
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert stat.S_IMODE(out.stat().st_mode) == 0o700
    record = json.loads((out / "capture.json").read_text())
    assert record["records_received"] == 128 and record["reference_matches"] is True
    assert record["flash_data_offset"] == 190 * 131072
    for i in range(2):
        assert (out / f"pass-{i}.ecc-oob").stat().st_size == 135168


def test_two_matching_passes_are_insufficient_without_reference_match(tmp_path):
    wrong = b"x" * 135168
    with pytest.raises(ValueError, match="preserved reference"):
        collect(tmp_path, wire(), wrong)
    record = json.loads((tmp_path / "private/capture/capture.json").read_text())
    assert record["status"] == "normal-ecc-reference-mismatch" and record["passes_match"] is True


def test_failure_retains_bounded_numeric_diagnosis(tmp_path):
    with pytest.raises(receiver.AcquisitionFailed):
        collect(tmp_path, failure())
    record = json.loads((tmp_path / "private/capture/capture.json").read_text())
    assert record["device_failure"] == {"stage": "read", "pass": 1, "page": 12209, "result": -74}
    assert record["records_received"] == 0 and record["status"] == "normal-ecc-device-failed"


def test_fragmented_stream_and_payload_corruption(tmp_path, monkeypatch):
    real_read = receiver.os.read
    monkeypatch.setattr(receiver.os, "read", lambda fd, size: real_read(fd, min(size, 17)))
    assert collect(tmp_path, wire())["reference_matched"] is True
    other = tmp_path / "second"
    other.mkdir()
    data = bytearray(wire())
    data[32 + 2112 + 32 + 5] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        collect(other, bytes(data))
    record = json.loads((other / "private/capture/capture.json").read_text())
    assert record["records_received"] == 1 and record["status"] == "incomplete"


def test_storage_sync_failure_cannot_report_success(tmp_path, monkeypatch):
    real_sync = receiver.os.fsync
    calls = 0

    def fail_once(fd):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("synthetic disk failure")
        return real_sync(fd)

    monkeypatch.setattr(receiver.os, "fsync", fail_once)
    with pytest.raises(OSError, match="did not sync"):
        collect(tmp_path, wire())
    record = json.loads((tmp_path / "private/capture/capture.json").read_text())
    assert record["status"] == "storage-failed"


@pytest.mark.parametrize(
    "data",
    [
        failure(stage=3),
        failure(pass_id=2),
        failure(page=64),
        failure(code=2112),
        failure(stage=1, code=1),
        failure()[:-1] + b"x",
    ],
)
def test_invalid_failure_metadata_rejected(data):
    with pytest.raises(ValueError):
        receiver.failure_fields(data)


def test_absolute_range_magic_crc_and_order_are_required(tmp_path):
    with pytest.raises(ValueError):
        receiver.header_fields(frame(0, 64)[:32])
    with pytest.raises(ValueError):
        receiver.header_fields(frame(0, 0)[:16] + b"\x00" * 16)
    frames = [frame(p, i) for p in range(2) for i in range(64)]
    frames[1] = frame(0, 2)
    with pytest.raises(ValueError, match="order"):
        collect(tmp_path, b"".join(frames))


@pytest.mark.parametrize("mutate", ["scope", "hash", "permissions", "symlink", "size"])
def test_reference_scope_identity_and_privacy_are_required(tmp_path, mutate):
    root, path = make_reference(tmp_path)
    meta = path.parent / "reference.json"
    record = json.loads(meta.read_text())
    if mutate == "scope":
        record["flash_data_offset"] = 0
        meta.write_text(json.dumps(record))
    if mutate == "hash":
        path.write_bytes(b"z" * 135168)
    if mutate == "permissions":
        path.chmod(0o644)
    if mutate == "symlink":
        other = path.with_name("actual")
        path.rename(other)
        path.symlink_to(other)
    if mutate == "size":
        path.write_bytes(b"x")
    with pytest.raises(ValueError):
        reference.read_reference(path, root)


def test_c_normal_read_scope_cleaned_error_and_failure_framing(tmp_path):
    compiler = shutil.which("clang")
    if not compiler:
        pytest.skip("Clang required for original host-only sysfs fixture")
    assets = Path(__file__).resolve().parents[1] / "firmware/nand_ecc_sample"
    include = tmp_path / "linux"
    include.mkdir()
    (include / "sysfs.h").write_text("/* original fixture types */\n")
    executable = tmp_path / "normal-read"
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
    result = subprocess.run([str(executable)], check=True, capture_output=True, timeout=3)
    assert result.stdout[:32] == frame(1, 63, bytes(receiver.RECORD))[:32]
    assert result.stdout[32:] == failure()


@pytest.mark.parametrize("mode", ["offline", "missing-argument", "missing-reference"])
def test_boot_wrapper_stops_before_usb_without_valid_explicit_inputs(tmp_path, mode):
    root = tmp_path / "workspace"
    work = root / "build/probe"
    work.mkdir(parents=True)
    (root / "private").mkdir(mode=0o700)
    assets = Path(__file__).resolve().parents[1] / "firmware/nand_ecc_sample"
    for name, target in [
        ("boot.sh", "boot.sh"),
        ("observe.py", "observe.py"),
        ("receiver.py", "sample_receiver.py"),
        ("reference.py", "reference_helper.py"),
    ]:
        shutil.copyfile(assets / name, work / target)
    (work / "check.py").write_text('print("synthetic integrity preflight")\n')
    (work / "serial_observe.py").write_text(
        "from pathlib import Path\n"
        'def observe(*args): raise AssertionError("unexpected USB access")\n'
        'if __name__ == "__main__":\n'
        '    Path(__file__).with_name("usb-opened").touch()\n'
        "    raise SystemExit(93)\n"
    )
    (work / "artifacts").mkdir()
    loader = work / "artifacts/omap_loader"
    loader.write_text("#!/bin/sh\nexit 99\n")
    loader.chmod(0o700)
    args = (
        []
        if mode == "offline"
        else ["--execute-read-only-nand-ecc-sample", str(root / "private/output")]
    )
    if mode == "missing-reference":
        args.append(str(root / "private/missing"))
    result = subprocess.run(
        ["sh", str(work / "boot.sh"), *args], check=False, capture_output=True, text=True, timeout=3
    )
    assert result.returncode == (0 if mode == "offline" else 2 if mode == "missing-argument" else 1)
    assert not (work / "usb-opened").exists()
