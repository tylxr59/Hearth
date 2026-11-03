"""Bounded read-only encoding frames, original-file agreement and ARM helper."""

import json
import socket
import struct
import threading
import time
import zlib
from dataclasses import replace
from pathlib import Path

import pytest

from firmware.encoding_audit import profile
from firmware.encoding_audit.run import AUDIT_END, AUDIT_MAGIC, audit_report, receive, same
from firmware.file_snapshot.run import decode
from firmware.startup_diagnostic.profile import expected_archive
from tests.test_acquisition import SESSION
from tests.test_file_snapshot_profile import frame


@pytest.fixture
def originals():
    return decode(frame(), SESSION)


def payload(originals, *, version=1, count=19, selected=None, archive=None):
    expected = [0 if row.existed else -2 for row in originals]
    return struct.pack(
        "<II19i",
        version,
        count,
        *(expected if selected is None else selected),
        *(expected + [0] if archive is None else archive),
    )


def test_archive_encoding_failure_does_not_hide_selected_file_result(originals):
    raw = payload(originals, archive=[-95] * 10)
    result = audit_report(raw, originals)
    assert result["selected_encoding_verified"] and not result["archive_encoding_verified"]
    assert result["flash_writes"] is False
    assert not audit_report(payload(originals, selected=[-95] * 9), originals)[
        "selected_encoding_verified"
    ]
    assert not same(originals, (replace(originals[0], data=b"changed"),) + originals[1:])


@pytest.mark.parametrize(
    "fault", ("short", "long", "version", "count", "positive", "unknown-error")
)
def test_malformed_encoding_report_is_refused(originals, fault):
    raw = payload(originals)
    if fault == "short":
        raw = raw[:-1]
    if fault == "long":
        raw += b"x"
    if fault in ("version", "count"):
        raw = payload(originals, **{fault: 2})
    if fault in ("positive", "unknown-error"):
        raw = payload(originals, selected=([1] if fault == "positive" else [-10001]) + [0] * 8)
    with pytest.raises(ValueError):
        audit_report(raw, originals)


def test_fragmented_frames_preserve_originals_and_encoding_results(tmp_path, originals):
    raw = payload(originals)
    audit = AUDIT_MAGIC + SESSION + struct.pack("<II", len(raw), zlib.crc32(raw)) + raw + AUDIT_END
    wire = frame() + audit
    left, right = socket.socketpair()

    def send():
        for at in range(0, len(wire), 13):
            right.sendall(wire[at : at + 13])

    thread = threading.Thread(target=send)
    thread.start()
    try:
        records, encoded = receive(left.fileno(), time.monotonic() + 5, SESSION, tmp_path)
        assert records == originals and encoded == raw
        assert (tmp_path / "encoding.bin").read_bytes() == audit
    finally:
        thread.join()
        left.close()
        right.close()


def test_original_static_arm_audit_has_no_linked_native_code(tmp_path, monkeypatch):
    import tempfile

    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    tmp_path.chmod(0o700)
    blobs = {
        n: b"public synthetic kernel fixture"
        for n in ("kernel.config", "x-load-gen2.bin", "u-boot.bin", "omap_loader", "probe-init")
    }
    monkeypatch.setattr(
        profile, "kernel_check", lambda _: (blobs, b"public kernel fixture", "d" * 64)
    )
    with tempfile.TemporaryDirectory(
        prefix="encoding-audit-test-", dir=profile.ROOT / "build"
    ) as directory:
        build = Path(directory) / "helper"
        output = tmp_path / "profile"
        result = profile.package(profile.ROOT / "build/fixture", build, output)
        assert result["flash_writes"] is False
        program = (output / "artifacts/init").read_bytes()
        assert program[:7] == b"\x7fELF\x01\x01\x01"
        assert (output / "artifacts/rootfs.cpio").read_bytes() == expected_archive(program)
        assert b"/sys/bus/platform/devices/omap2-nand.0/hearth_file_control" not in program
        assert (
            json.loads((output / "profile.json").read_bytes())["status"]
            == "protected-readonly-encoding-audit-unexecuted"
        )
