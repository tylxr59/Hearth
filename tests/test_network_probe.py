import hashlib
import json
import socket
import stat
import struct
import time
import zlib

import pytest

from firmware.network_probe import profile, run
from firmware.settings_probe.artifact import parse_cpio
from provisioning import network_backup, network_plan
from tests.test_native_network import image
from tests.test_network_stream import plan_snapshot


def row():
    return {
        "type": "network_ram_preflight",
        "stream_cases": 41,
        "transaction_cases": 20,
        "child_status": 0,
        "child_output_bytes": 0,
        "real_files_checked": 4,
        "real_preflight": True,
        "phase": 0,
        "flash_writes": False,
        "diagnostic_hex": "",
    }


def frame(value=None, session=b"s" * 32):
    payload = json.dumps(row() if value is None else value).encode()
    return (
        run.MAGIC
        + session
        + struct.pack("<II", len(payload), zlib.crc32(payload))
        + payload
        + run.END
    )


def test_complete_report_and_failure_report_have_separate_meanings():
    assert run.successful(run.decode(frame(), b"s" * 32))
    value = row()
    value.update(real_preflight=False, real_files_checked=2, phase=62)
    assert not run.successful(run.decode(frame(value), b"s" * 32))


@pytest.mark.parametrize(
    "field,value",
    (
        ("stream_cases", True),
        ("stream_cases", 42),
        ("transaction_cases", 21),
        ("flash_writes", True),
        ("real_files_checked", 5),
        ("child_output_bytes", 1025),
        ("diagnostic_hex", "not hex"),
        ("phase", 99),
    ),
)
def test_report_schema_and_evidence_bounds_are_strict(field, value):
    value_row = row()
    value_row[field] = value
    with pytest.raises(ValueError):
        run.decode(frame(value_row), b"s" * 32)


@pytest.mark.parametrize("fault", ("crc", "session", "extra", "footer", "bound"))
def test_frame_corruption_and_replay_are_refused(fault):
    data = bytearray(frame())
    if fault == "crc":
        data[60] ^= 1
    elif fault == "session":
        data[8] ^= 1
    elif fault == "extra":
        data += b"extra"
    elif fault == "footer":
        data[-1] ^= 1
    else:
        struct.pack_into("<I", data, 40, run.LIMIT + 1)
    with pytest.raises(ValueError):
        run.decode(bytes(data), b"s" * 32)


def test_first_complete_bad_frame_is_preserved_without_retry(tmp_path):
    a, b = socket.socketpair()
    try:
        data = bytearray(frame())
        data[-9] ^= 1
        b.sendall(data + frame())
        with pytest.raises(ValueError):
            run.receive(a.fileno(), time.monotonic() + 1, b"s" * 32, tmp_path)
        assert (tmp_path / "report.bin").read_bytes() == data
        assert stat.S_IMODE((tmp_path / "report.bin").stat().st_mode) == 0o600
    finally:
        a.close()
        b.close()


def test_no_execution_without_flag_or_with_reused_output(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "private_path", lambda p: p)
    monkeypatch.setattr(run, "check", lambda root: {"checked": True})

    def forbidden(_port):
        raise AssertionError("USB must not be opened")

    monkeypatch.setattr(run, "require_native", forbidden)
    assert run.run(tmp_path) == {"checked": True}
    with pytest.raises(ValueError):
        run.run(tmp_path, tmp_path, execute=True)


def test_execution_marker_prevents_second_loader_attempt(tmp_path, monkeypatch):
    root = tmp_path / "profile"
    root.mkdir()
    tmp_path.chmod(0o700)
    (root / "profile.json").write_text(json.dumps({"session": "73" * 32}))
    (root / "execution-started.json").write_bytes(b"already used")
    monkeypatch.setattr(run, "private_path", lambda p: p)
    monkeypatch.setattr(run, "check", lambda root: {"checked": True})
    monkeypatch.setattr(run, "require_native", lambda port: None)
    monkeypatch.setattr(run, "private_read", lambda path, limit: path.read_bytes())

    def forbidden(*args, **kwargs):
        raise AssertionError("loader must not start")

    monkeypatch.setattr(run.subprocess, "run", forbidden)
    with pytest.raises(FileExistsError):
        run.run(root, tmp_path / "new-output", execute=True)


def test_archive_has_only_fixed_programs_and_unprivileged_synthetic_roots(monkeypatch):
    monkeypatch.setattr(profile, "elf_metadata", lambda blob: ({"libc.so.6"}, set(), set()))
    libs = [
        ("lib/libc.so.6", stat.S_IFREG | 0o444, 0, b"synthetic libc DATA", 0, 0),
        ("lib/ld-linux-armhf.so.3", stat.S_IFREG | 0o555, 0, b"synthetic loader DATA", 0, 0),
    ]
    entries = parse_cpio(profile.archive(image(), b"original harness DATA", libs))
    by_name = {r[0]: r for r in entries}
    assert len(entries) == 32
    assert by_name["init"][1:3] == (stat.S_IFREG | 0o700, 0)
    assert by_name["network-transaction"][1:3] == (stat.S_IFREG | 0o555, 0)
    assert all(
        by_name[f"state/transaction-{i:02d}"][1:3] == (stat.S_IFDIR | 0o700, 65534)
        for i in range(20)
    )
    assert not {"file-action", "nlclient", "osm", "settings.config", "network-writer"} & set(
        by_name
    )


@pytest.mark.parametrize("fault", ("pin", "header", "candidate", "extra"))
def test_pinned_plan_rejects_tampering_before_packaging(tmp_path, fault):
    tmp_path.chmod(0o700)
    value = plan_snapshot()
    backup = tmp_path / "backup"
    plan = tmp_path / "plan"
    network_backup.preserve(backup, value)
    network_plan.prepare(plan, value, backup, "https://10.0.0.1:8443", "https://10.0.0.12:8443")
    pin = hashlib.sha256(
        b"hearth-network-offline-plan-v1\n" + (plan / "plan.json").read_bytes()
    ).digest()
    assert network_plan.check(plan, backup, pin)["snapshot"] == value
    if fault == "pin":
        pin = b"x" * 32
    elif fault == "header":
        (plan / "plan.h").write_bytes(b"unreviewed header")
    elif fault == "candidate":
        (plan / "0.replacement").write_bytes(b"changed outside span")
    else:
        (plan / "extra").touch()
    with pytest.raises(ValueError):
        network_plan.check(plan, backup, pin)
