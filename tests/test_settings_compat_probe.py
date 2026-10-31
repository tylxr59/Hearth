import copy
import gzip
import json
import shutil
import socket
import stat
import subprocess
import threading
import time
from pathlib import Path

import pytest

from firmware.settings_compat_probe import artifact, observe, results
from firmware.settings_compat_probe.compile import compile_helpers
from firmware.tls_probe.check import split_multi
from firmware.tls_probe.package import cpio, multi_image, sha
from tests.test_settings_probe import settings_profile, synthetic_abi_library
from tools.elf_review import ArmElf


def matrix():
    rows = []
    for variant in ("original", "candidate"):
        rows.extend(results.io_expected(variant, case) for case in results.CASES)
        if variant == "candidate":
            rows.extend(results.allocation_expected(case) for case in results.ALLOCATIONS)
        rows.append(
            {
                "type": "compat_helper",
                "variant": variant,
                "bindings_verified": True,
                "suppressed_logs": 0 if variant == "original" else 40,
            }
        )
        rows.append(
            {
                "type": "compat_process",
                "variant": variant,
                "wait_status": 0,
                "synthetic_secret_log_matches": 2 if variant == "original" else 0,
                "passthrough_log_matches": 1,
            }
        )
    return rows + [{"type": "compat_complete", "passed": True}]


def encode(rows):
    return b"\n".join(json.dumps(row).encode() for row in rows) + b"\n"


def test_complete_comparison_requires_baseline_correction_allocation_and_log_evidence():
    result = results.validate(encode(matrix()))
    assert (
        result["io_cases"] == 24
        and result["allocation_alias_cases"] == 5
        and not result["installed"]
    )


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "duplicate",
        "old_entry_bug",
        "dirty_retry",
        "bool",
        "allocator_free",
        "allocator_retry",
        "binding",
        "log_scope",
        "secret_leak",
        "no_baseline_leak",
        "passthrough",
        "process",
        "complete",
    ],
)
def test_comparison_rejects_missing_or_false_security_evidence(damage):
    rows = matrix()
    candidate = next(
        r for r in rows if r.get("variant") == "candidate" and r.get("case") == "entry_error"
    )
    allocation = next(r for r in rows if r["type"] == "compat_allocation")
    process = next(r for r in rows if r["type"] == "compat_process" and r["variant"] == "candidate")
    helper = next(r for r in rows if r["type"] == "compat_helper" and r["variant"] == "candidate")
    if damage == "missing":
        rows.pop(0)
    if damage == "duplicate":
        rows[0] = copy.deepcopy(rows[1])
    if damage == "old_entry_bug":
        candidate.update(
            first_result=0,
            first_renames=1,
            first_new=1,
            first_old=0,
            retry_new=1,
            retry_file_opens=0,
            retry_renames=0,
        )
    if damage == "dirty_retry":
        next(r for r in rows if r.get("variant") == "candidate" and r.get("case") == "dir_sync")[
            "retry_file_opens"
        ] = 0
    if damage == "bool":
        candidate["first_file_opens"] = True
    if damage == "allocator_free":
        allocation["old_freed_on_failure"] = 1
    if damage == "allocator_retry":
        allocation["restored"] = False
    if damage == "binding":
        helper["bindings_verified"] = False
    if damage == "log_scope":
        helper["suppressed_logs"] = 0
    if damage == "secret_leak":
        process["synthetic_secret_log_matches"] = 1
    if damage == "no_baseline_leak":
        next(r for r in rows if r["type"] == "compat_process" and r["variant"] == "original")[
            "synthetic_secret_log_matches"
        ] = 0
    if damage == "passthrough":
        process["passthrough_log_matches"] = 0
    if damage == "process":
        process["wait_status"] = 9
    if damage == "complete":
        rows[-1]["passed"] = 1
    with pytest.raises(ValueError):
        results.validate(encode(rows))


def test_diagnostic_truncation_does_not_truncate_streamed_log_checks():
    rows = matrix()
    for _ in range(16):
        rows.insert(0, {"type": "compat_stderr", "variant": "original", "hex": "78" * 128})
    rows.insert(
        16, {"type": "compat_stderr_truncated", "variant": "original", "bytes_dropped": 9000}
    )
    assert results.validate(encode(rows))["synthetic_value_logs_removed"]
    rows.insert(0, {"type": "compat_stderr", "variant": "original", "hex": "78"})
    with pytest.raises(ValueError):
        results.validate(encode(rows))
    with pytest.raises(ValueError):
        results.validate(b"x" * 32769)


@pytest.mark.parametrize("harness", ["settings_compat_scan", "settings_compat_tail"])
def test_stream_diagnostics_under_sanitizers(tmp_path, harness):
    if not shutil.which("clang"):
        pytest.skip("Clang required for original host scanner checks")
    root = Path(__file__).resolve().parents[1]
    driver = tmp_path / "scanner"
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-g",
            "-fsanitize=address,undefined",
            str(root / f"tests/{harness}_harness.c"),
            "-o",
            str(driver),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run([str(driver)], check=True, capture_output=True, timeout=3)


def test_original_comparison_helpers_cross_compile_without_firmware_input(tmp_path):
    if not shutil.which("clang") or not shutil.which("ld.lld"):
        pytest.skip("Clang/LLD required")
    output = tmp_path / "helpers"
    record = compile_helpers(output)
    assert record["link_stubs_not_for_target"]
    meta = subprocess.run(
        ["readelf", "-r", "-d", "--wide", str(output / "settings-test")],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "[libhearth-settings-faults.so]" in meta and "R_ARM_COPY" not in meta
    assert "hearth_stub_native_dependency" not in meta


def test_comparison_serial_protocol_is_fixed_and_failed_raw_reports_remain_private(
    tmp_path, monkeypatch
):
    from tools import elf_review

    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", private)
    host, peer = socket.socketpair()
    tokens = []
    payload = encode(matrix())
    output = private / "result.jsonl"

    def send():
        peer.sendall(observe.READY)
        tokens.append(peer.recv(64))
        frame = observe.BEGIN + payload + observe.END
        for i in range(0, len(frame), 19):
            peer.sendall(frame[i : i + 19])

    thread = threading.Thread(target=send)
    try:
        thread.start()
        assert observe.receive(host.fileno(), time.monotonic() + 3, output)["io_cases"] == 24
        thread.join(timeout=3)
        assert tokens == [observe.START] and output.read_bytes() == payload
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
    finally:
        host.close()
        peer.close()
        thread.join(timeout=3)


def comparison_profile(tmp_path, monkeypatch, damage=None):
    base = settings_profile(tmp_path, monkeypatch)
    entries = artifact.parse_cpio((base / "artifacts/rootfs.cpio").read_bytes())
    entries = [
        (n, m, u, synthetic_abi_library() if n == "lib/libplds4.so" else d, a, b)
        for n, m, u, d, a, b in entries
        if n != "TRAILER!!!"
    ]
    dummy = synthetic_abi_library()
    entries += [(n, stat.S_IFREG | 0o444, 0, dummy, 0, 0) for n in sorted(artifact.EXTRA)]
    entries += [("TRAILER!!!", 0, 0, b"", 0, 0)]
    files = {
        "appcore": next(d for n, m, u, d, a, b in entries if n == "lib/libnlappcore.so"),
        "plds": dummy,
    }
    review = {
        "status": "offline-storage-compat-abi-reviewed",
        "profile": "Display-2.6/5.9.4-5",
        "object_bytes": 48,
        "field_offsets": {"table": 4, "lock": 8, "dirty": 12, "filename": 20},
        "pointer_value_comparison": True,
        "update_callback_does_not_free_value": True,
        "source_sha256": {n: sha(d) for n, d in files.items()},
        "ranges": {
            n: {
                "library": lib,
                "address": address,
                "bytes": size,
                "sha256": sha(ArmElf(files[lib]).read(address, size)),
            }
            for n, (lib, address, size) in artifact.RANGES.items()
        },
    }
    if damage == "allocator_contract":
        review["update_callback_does_not_free_value"] = False
    if damage == "identity":
        review["source_sha256"]["appcore"] = "0" * 64
    if damage == "review_range":
        review["ranges"]["hash_add"]["address"] += 4
    if damage == "writable_candidate":
        entries = [
            (n, m | 0o200 if n in artifact.EXTRA else m, u, d, a, b) for n, m, u, d, a, b in entries
        ]
    if damage == "extra_app":
        entries.insert(-1, ("nlclient", stat.S_IFREG | 0o555, 0, dummy, 0, 0))
    if damage == "missing_faults":
        entries = [row for row in entries if row[0] != "lib/libhearth-settings-faults.so"]
    rootfs = cpio(entries)
    kernel, _ = split_multi((base / "artifacts/uImage").read_bytes())
    (base / "artifacts/rootfs.cpio").write_bytes(rootfs)
    (base / "artifacts/uImage").write_bytes(multi_image(kernel, gzip.compress(rootfs, mtime=0)))
    record = {
        "status": artifact.STATUS,
        "files": {n: sha((base / "artifacts" / n).read_bytes()) for n in artifact.FILES},
        "recipe_sha256": artifact.recipes(),
        "native_review": review,
        "root_inventory": artifact.inventory(entries),
    }
    (base / "compat-probe.json").write_text(json.dumps(record))
    return base


def test_private_comparison_gate_accepts_only_exact_profile_and_review_contract(
    tmp_path, monkeypatch
):
    assert artifact.check(comparison_profile(tmp_path, monkeypatch))["cases"] == 29


@pytest.mark.parametrize(
    "damage",
    [
        "allocator_contract",
        "identity",
        "review_range",
        "writable_candidate",
        "extra_app",
        "missing_faults",
    ],
)
def test_private_comparison_gate_rejects_unreviewed_or_unsafe_payloads(
    tmp_path, monkeypatch, damage
):
    with pytest.raises(ValueError):
        artifact.check(comparison_profile(tmp_path, monkeypatch, damage))


@pytest.mark.parametrize(
    "flag,existing,code",
    [
        (None, False, 0),
        ("--invalid", False, 2),
        ("--execute-experimental-settings-compat-probe", True, 2),
    ],
)
def test_comparison_boot_stops_offline_before_any_device_action(tmp_path, flag, existing, code):
    import os

    profile = tmp_path / "profile"
    profile.mkdir()
    commands = tmp_path / "commands"
    commands.mkdir()
    log = tmp_path / "calls"
    python = commands / "python3"
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$HEARTH_TEST_LOG"\nexit 0\n')
    python.chmod(0o755)
    if existing:
        (profile / "compat-result.jsonl").write_text("preserve")
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "PATH": str(commands) + os.pathsep + os.environ["PATH"],
        "HEARTH_TEST_LOG": str(log),
    }
    result = subprocess.run(
        ["sh", str(root / "firmware/settings_compat_probe/boot.sh"), str(profile)]
        + ([flag] if flag else []),
        check=False,
        env=env,
        capture_output=True,
        timeout=3,
    )
    assert result.returncode == code
    assert log.read_text().splitlines() == [
        f"-m firmware.settings_compat_probe.artifact check {profile}"
    ]
    if existing:
        assert (profile / "compat-result.jsonl").read_text() == "preserve"
