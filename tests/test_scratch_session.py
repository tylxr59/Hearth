import concurrent.futures
import hashlib
import json
import shutil
import socket
import struct
import subprocess
import time
import zlib
from pathlib import Path

import pytest

from firmware.scratch_test import backup, session
from tests.test_scratch_ecc import MASK, programmed


def snapshots():
    original = bytearray(b"\xff" * backup.SIZE)
    original[backup.PAGE + 2 : backup.PAGE + 10] = backup.MARKER
    original = bytes(original)
    digest = hashlib.sha256(original).digest()
    ready = (
        session.META.pack(
            b"HRTHSCR1",
            1,
            2,
            0,
            0,
            0,
            0,
            0,
            0,
            1,
            0,
            0,
            0,
            backup.BLOCK,
            backup.SIZE,
            digest,
            bytes(32),
        )
        + original
        + bytes(2 * backup.RECORD + backup.SIZE)
    )
    final = (
        session.META.pack(
            b"HRTHSCR1",
            1,
            5,
            0,
            1,
            1,
            1,
            1,
            1,
            1,
            0,
            0,
            0,
            backup.BLOCK,
            backup.SIZE,
            digest,
            digest,
        )
        + original
        + programmed() * 2
        + original
    )
    return ready, final, digest


def frame(stage, data):
    prefix = struct.pack("<8s5I", session.MAGIC, 1, stage, len(data), zlib.crc32(data), 0)
    return prefix + struct.pack("<I", zlib.crc32(prefix)) + data


def run_peer(peer, ready, final, digest):
    deadline = time.monotonic() + 3
    assert session.read_exact(peer.fileno(), 8, deadline) == b"HSBEGIN1"
    session.send_exact(peer.fileno(), b"startup\n" + frame(1, ready), deadline)
    try:
        ack = session.read_exact(peer.fileno(), 40, deadline)
    except OSError:
        return False
    assert ack == backup.ACK_PREFIX + digest
    session.send_exact(peer.fileno(), frame(2, final), deadline)
    return True


def transaction(tmp_path, monkeypatch=None, final_change=None, ready_change=None, mask=MASK):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    ready, final, digest = snapshots()
    ready = ready_change(ready) if ready_change else ready
    final = final_change(final) if final_change else final
    client, peer = socket.socketpair()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(run_peer, peer, ready, final, digest)
        try:
            result = session.transact(
                client.fileno(), time.monotonic() + 3, root / "test", root, mask
            )
        finally:
            client.close()
        acked = future.result(timeout=4)
        peer.close()
    return result, acked, root / "test"


def test_complete_duplex_transaction_preserves_and_independently_checks(tmp_path):
    result, acked, output = transaction(tmp_path)
    assert acked and result["status"] == "scratch-transaction-validated"
    assert result["independent_bch4_sectors_verified"] == 4
    assert result["restoration"] == "exact fixed block only"
    assert (output / "result.bin").stat().st_size == session.WIRE_BYTES
    assert (output / "original.raw-oob").stat().st_size == backup.SIZE
    assert json.loads((output / "original.json").read_text())["device_written"] is False
    assert json.loads((output / "attempt.json").read_text())["write_may_have_executed"] is True


def test_storage_failure_never_sends_ack(tmp_path, monkeypatch):
    def fail(fd):
        raise OSError("injected disk failure")

    monkeypatch.setattr(backup.os, "fsync", fail)
    with pytest.raises(OSError, match="injected"):
        transaction(tmp_path)
    record = json.loads((tmp_path / "private/test/attempt.json").read_text())
    assert record["write_may_have_executed"] is False


def change_field(data, offset, value):
    data = bytearray(data)
    struct.pack_into("<I", data, offset, value)
    return bytes(data)


@pytest.mark.parametrize("offset,value", [(12, 4), (16, 1), (36, 0), (40, 0), (44, 1)])
def test_terminal_failure_never_promoted(tmp_path, offset, value):
    with pytest.raises(ValueError, match="complete protected"):
        transaction(tmp_path, final_change=lambda b: change_field(b, offset, value))
    root = tmp_path / "private/test"
    assert (root / "result.bin").exists()
    record = json.loads((root / "attempt.json").read_text())
    assert record["status"] == "incomplete" and record["write_may_have_executed"] is True


def test_ecc_failure_after_restoration_is_not_a_pass(tmp_path):
    with pytest.raises(ValueError, match="parity"):
        transaction(tmp_path, mask=b"\0" * 7)
    record = json.loads((tmp_path / "private/test/attempt.json").read_text())
    assert record["status"] == "incomplete" and record["restoration"] == "unverified"


def test_changed_final_contents_not_a_pass(tmp_path):
    def changed(data):
        data = bytearray(data)
        data[-1] ^= 1
        return bytes(data)

    with pytest.raises(ValueError, match="differs"):
        transaction(tmp_path, final_change=changed)


@pytest.mark.parametrize("offset,value", [(12, 5), (20, 1), (36, 1), (40, 0), (56, 1313)])
def test_bad_ready_state_or_scope_prevents_ack_and_storage(tmp_path, offset, value):
    with pytest.raises(ValueError):
        transaction(tmp_path, ready_change=lambda b: change_field(b, offset, value))
    assert not (tmp_path / "private/test").exists()


def test_unbounded_frame_and_crc_damage_rejected_before_payload_read():
    ready, _, _ = snapshots()
    for wire in (
        frame(2, ready),
        frame(1, ready[:-1]),
        frame(1, ready)[:24] + b"\x01" + frame(1, ready)[25:],
    ):
        client, peer = socket.socketpair()
        # Only the header is needed: rejection must not wait for payload bytes.
        peer.sendall(wire[: session.HEADER.size])
        try:
            with pytest.raises(ValueError, match="header"):
                session.receive(client.fileno(), 1, time.monotonic() + 1)
        finally:
            client.close()
            peer.close()


def test_original_c_framing_matches_python_wire_schema(tmp_path):
    compiler = shutil.which("clang")
    if not compiler:
        pytest.skip("host clang required for original framing sanitizer check")
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "frame.c"
    source.write_text(
        '#include <stdio.h>\n#include "protocol.h"\n'
        "static unsigned char payload[HS_WIRE_BYTES];\n"
        "int main(void) { unsigned char header[32]; unsigned int i;\n"
        "for(i=0;i<HS_WIRE_BYTES;i++) payload[i]=(unsigned char)(i*17u);\n"
        "hs_wire_header(header,2,payload);\n"
        "return fwrite(header,1,32,stdout)==32 ? 0 : 1; }\n"
    )
    exe = tmp_path / "frame"
    subprocess.run(
        [
            compiler,
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-I",
            str(root / "firmware/scratch_test"),
            str(source),
            "-o",
            str(exe),
        ],
        check=True,
        capture_output=True,
    )
    result = subprocess.run([str(exe)], check=True, capture_output=True, timeout=3)
    payload = bytes((i * 17) & 255 for i in range(session.WIRE_BYTES))
    assert result.stdout == frame(2, payload)[:32]
