import json
import shutil
import socket
import struct
import subprocess
import threading
import time
import zlib
from pathlib import Path

import pytest

from firmware.nand_capture import receiver, stage


def frame(pass_id, page, payload=None):
    payload = bytes([page % 256]) * receiver.RECORD if payload is None else payload
    header = struct.pack(
        "<8s5I", receiver.MAGIC, 1, pass_id, page, len(payload), zlib.crc32(payload)
    )
    return header + struct.pack("<I", zlib.crc32(header)) + payload


def wire():
    return (
        b"".join(frame(p, i) for p in range(2) for i in range(receiver.PAGES)) + receiver.footer()
    )


def capture(tmp_path, data):
    host, device = socket.socketpair()
    tokens = []

    def produce():
        try:
            token = b""
            while len(token) < len(receiver.START):
                chunk = device.recv(len(receiver.START) - len(token))
                if not chunk:
                    return
                token += chunk
            tokens.append(token)
            device.sendall(data)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            device.close()

    thread = threading.Thread(target=produce, daemon=True)
    thread.start()
    try:
        result = receiver.collect(
            host.fileno(),
            time.monotonic() + 2,
            tmp_path / "private/fullcapture",
            tmp_path / "private",
        )
    finally:
        host.close()
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert tokens == [receiver.START]
    return result


def test_full_physical_bounds_and_specific_magic():
    good = frame(1, 131071)
    assert receiver.header_fields(good[:32])[:2] == (1, 131071)
    with pytest.raises(ValueError):
        receiver.header_fields(frame(1, 131072)[:32])
    assert receiver.PAGES * receiver.RECORD == 276824064
    assert "#define HEARTH_SAMPLE_PAGES 131072U" in stage.raw_header()
    assert '"hearth_raw"' in stage.raw_header()
    assert "os.O_RDWR | os.O_NOCTTY" in stage.serial_helper()
    assert "1 <= seconds <= 1800" in stage.serial_helper()


def test_two_pass_capture_requires_start_and_completion(tmp_path, monkeypatch):
    monkeypatch.setattr(receiver, "PAGES", 3)
    result = capture(tmp_path, wire())
    assert result["status"] == "raw-nand-capture-matched" and result["whole_chip_read"]
    assert result["firmware_backup"] is False
    record = json.loads((tmp_path / "private/fullcapture/capture.json").read_text())
    assert record["records_received"] == 6 and record["passes_match"]
    assert (tmp_path / "private/fullcapture/pass-1.raw").stat().st_size == 3 * 2112


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d[:-1],
        lambda d: d[:-32],
        lambda d: d[:-1] + bytes([d[-1] ^ 1]),
        lambda d: d[:2144] + d[4288:],
        lambda d: d[:2144] + d[:2144] + d[2144:],
        lambda d: d[: 2144 + 33] + bytes([d[2144 + 33] ^ 1]) + d[2144 + 34 :],
    ],
)
def test_corruption_or_missing_footer_never_completes(tmp_path, monkeypatch, mutation):
    monkeypatch.setattr(receiver, "PAGES", 3)
    with pytest.raises((OSError, ValueError)):
        capture(tmp_path, mutation(wire()))
    record = json.loads((tmp_path / "private/fullcapture/capture.json").read_text())
    assert record["status"] == "incomplete"


def test_full_capture_rejects_differing_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(receiver, "PAGES", 3)
    data = wire().replace(frame(1, 2), frame(1, 2, b"x" * receiver.RECORD))
    with pytest.raises(ValueError, match="passes differ"):
        capture(tmp_path, data)
    record = json.loads((tmp_path / "private/fullcapture/capture.json").read_text())
    assert record["status"] == "raw-nand-capture-mismatch"


def test_capture_preflight_checks_disk_before_start(tmp_path, monkeypatch):
    monkeypatch.setattr(
        receiver.shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(100, 99, 1)
    )
    with pytest.raises(ValueError, match="disk space"):
        receiver.validate_output(tmp_path / "private/capture", tmp_path / "private")
    assert not (tmp_path / "private").exists()


def compile_c(tmp_path, source, include):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("gcc required for synthetic capture safeguards")
    exe = tmp_path / "check"
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
            str(include),
            str(source),
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
    )
    return subprocess.run([str(exe)], check=True, capture_output=True).stdout


def test_actual_exporter_with_mocked_syscalls(tmp_path, monkeypatch):
    assets = Path(__file__).resolve().parents[1] / "firmware/nand_capture"
    (tmp_path / "sample-protocol.h").write_text(stage.protocol_header().replace("131072U", "3U"))
    (tmp_path / "capture-init.c").write_bytes((assets / "init.c").read_bytes())
    actual = compile_c(tmp_path, assets / "test_producer.c", assets)
    monkeypatch.setattr(receiver, "PAGES", 3)
    assert actual == wire()


def test_actual_whole_chip_reader_bounds_with_mocked_nand(tmp_path):
    assets = Path(__file__).resolve().parents[1] / "firmware/nand_sample"
    (tmp_path / "sample.h").write_text(stage.raw_header())
    (tmp_path / "protocol.h").write_text(stage.protocol_header())
    (tmp_path / "linux").mkdir()
    (tmp_path / "linux/sysfs.h").write_text("/* types supplied by synthetic harness */\n")
    text = (assets / "test_sample.c").read_text()
    text = text.replace("63 * 2112", "131071 * 2112").replace("63 * 2048", "131071 * 2048")
    text = text.replace("64 * 2112", "131072 * 2112").replace("65 * 2112", "131073 * 2112")
    text = text.replace(
        "sample_header(header, 1, 63, payload)", "sample_header(header, 1, 131071, payload)"
    )
    source = tmp_path / "bounds.c"
    source.write_text(text)
    assert compile_c(tmp_path, source, tmp_path) == frame(1, 131071, bytes(receiver.RECORD))[:32]
