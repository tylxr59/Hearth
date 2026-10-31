import copy
import gzip
import json
import shutil
import socket
import stat
import threading
import time

import pytest

from firmware.file_install_probe import artifact, observe, results
from firmware.file_install_probe.compile import compile_helpers, supervisor_source
from firmware.settings_probe.artifact import parse_cpio
from firmware.tls_probe.check import split_multi
from firmware.tls_probe.package import cpio, multi_image, sha
from tests.test_settings_compat_probe import comparison_profile
from tests.test_settings_compat_probe import matrix as settings_matrix


def matrix():
    rows = settings_matrix()
    rows[-1:-1] = [{"type": "file_case", "case": i, "passed": True} for i in range(32)] + [
        {
            "type": "compat_process",
            "variant": "files",
            "wait_status": 0,
            "synthetic_secret_log_matches": 0,
            "passthrough_log_matches": 0,
        }
    ]
    return rows


def encode(rows):
    return b"\n".join(json.dumps(r).encode() for r in rows) + b"\n"


def test_complete_ram_evidence_does_not_claim_flash_or_native_application():
    report = results.validate(encode(matrix()))
    assert report["settings_cases"] == 36 and report["file_cases"] == 32
    assert not report["installed"] and not report["flash_filesystem_verified"]
    assert not report["full_native_application_verified"]


@pytest.mark.parametrize(
    "fault",
    ["missing", "duplicate", "bool", "failed", "process", "stderr", "extra", "old_settings"],
)
def test_incomplete_or_ambiguous_matrix_is_rejected(fault):
    rows = copy.deepcopy(matrix())
    start = next(i for i, r in enumerate(rows) if r["type"] == "file_case")
    if fault == "missing":
        rows.pop(start)
    if fault == "duplicate":
        rows[start + 1] = copy.deepcopy(rows[start])
    if fault == "bool":
        rows[start]["case"] = False
    if fault == "failed":
        rows[start]["passed"] = False
    if fault == "process":
        rows[-2]["wait_status"] = 9
    if fault == "stderr":
        rows.insert(0, {"type": "compat_stderr", "variant": "files", "hex": "78"})
    if fault == "extra":
        rows[start]["unknown"] = 1
    if fault == "old_settings":
        rows = [r for r in rows if r.get("type") != "compat_permissions"]
    with pytest.raises(ValueError):
        results.validate(encode(rows))


def test_fixed_protocol_preserves_fragmented_private_result_and_refuses_overwrite(
    tmp_path, monkeypatch
):
    from tools import elf_review

    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", private)
    host, peer = socket.socketpair()
    output = private / "result.jsonl"
    payload = encode(matrix())
    tokens = []

    def sender():
        peer.sendall(observe.READY)
        tokens.append(peer.recv(64))
        frame = observe.BEGIN + payload + observe.END
        for i in range(0, len(frame), 23):
            peer.sendall(frame[i : i + 23])

    thread = threading.Thread(target=sender)
    try:
        thread.start()
        assert observe.receive(host.fileno(), time.monotonic() + 3, output)["file_cases"] == 32
        thread.join(timeout=3)
        assert tokens == [observe.START] and output.read_bytes() == payload
        assert output.stat().st_mode & 0o077 == 0
        with pytest.raises(FileExistsError):
            observe.capture_private(output, b"replace")
    finally:
        host.close()
        peer.close()
        thread.join(timeout=3)


def profile(tmp_path, monkeypatch, fault=None):
    base = comparison_profile(tmp_path, monkeypatch)
    entries = parse_cpio((base / "artifacts/rootfs.cpio").read_bytes())
    helper = next(r[3] for r in entries if r[0] == "settings-test")
    entries.insert(-1, ("file-test", stat.S_IFREG | 0o555, 0, helper, 0, 0))
    if fault == "writable_helper":
        entries = [
            (n, m | 0o200 if n == "file-test" else m, u, d, a, b) for n, m, u, d, a, b in entries
        ]
    if fault == "settings":
        entries.insert(-1, ("settings.config", stat.S_IFREG | 0o600, 0, b"forbidden", 0, 0))
    if fault == "native_app":
        entries.insert(-1, ("nlclient", stat.S_IFREG | 0o555, 0, helper, 0, 0))
    if fault == "trace":
        entries = [
            (
                n,
                m,
                u,
                d + b"HEARTH_STORAGE_PHASE x" if n == "lib/libhearth-settings-compat.so" else d,
                a,
                b,
            )
            for n, m, u, d, a, b in entries
        ]
    if fault == "flash":
        config = base / "artifacts/kernel.config"
        config.write_text(config.read_text().replace("# CONFIG_MTD is not set", "CONFIG_MTD=y"))
    rootfs = cpio(entries)
    kernel, _ = split_multi((base / "artifacts/uImage").read_bytes())
    (base / "artifacts/rootfs.cpio").write_bytes(rootfs)
    (base / "artifacts/uImage").write_bytes(multi_image(kernel, gzip.compress(rootfs, mtime=0)))
    review = json.loads((base / "compat-probe.json").read_text())["native_review"]
    record = {
        "status": artifact.STATUS,
        "cases": artifact.CASES,
        "ram_only": True,
        "actual_settings": False,
        "candidate_phase_trace": False,
        "recipe_sha256": artifact.recipes(),
        "native_review": review,
        "files": {n: sha((base / "artifacts" / n).read_bytes()) for n in artifact.FILES},
        "root_inventory": artifact.inventory(entries),
    }
    if fault == "scope":
        record["actual_settings"] = True
    (base / "file-lab.json").write_text(json.dumps(record))
    return base


def test_exact_ram_archive_accepts_only_bounded_lab_scope(tmp_path, monkeypatch):
    assert artifact.check(profile(tmp_path, monkeypatch))["cases"] == 68


@pytest.mark.parametrize(
    "fault", ["writable_helper", "settings", "native_app", "trace", "flash", "scope"]
)
def test_ram_archive_rejects_production_or_expanded_scope(tmp_path, monkeypatch, fault):
    with pytest.raises(ValueError):
        artifact.check(profile(tmp_path, monkeypatch, fault))


def test_original_helpers_cross_compile_without_firmware_or_container_requirement(tmp_path):
    if not shutil.which("clang") or not shutil.which("ld.lld"):
        pytest.skip("Clang/LLD required")
    record = compile_helpers(tmp_path / "helpers", legacy_linker=False)
    assert record["ram_only_file_adapter"] and record["candidate_phase_trace"] is False
    assert 'files = run("files",2)' in supervisor_source()
    assert "static char report[49152]" in supervisor_source()
