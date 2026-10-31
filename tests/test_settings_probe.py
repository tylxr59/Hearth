import copy
import gzip
import json
import os
import shutil
import socket
import stat
import struct
import subprocess
import threading
import time
from pathlib import Path

import pytest

from firmware.settings_probe import abi, artifact, observe, results
from firmware.settings_probe.compile import compile_helpers
from firmware.tls_probe.check import split_multi
from firmware.tls_probe.package import cpio, helper_interpreter, multi_image, sha
from tests.test_tls_probe import synthetic_profile


def matrix():
    rows = []
    for case in results.CASES:
        rows.append(
            {
                "type": "settings_case",
                "case": case,
                "injected": int(case != "normal"),
                "first_result": 0,
                "first_file_opens": 1,
                "first_renames": 1,
                "first_reload_result": 0,
                "first_new": 3,
                "first_old": 0,
                "retry_result": 0,
                "retry_file_opens": 0,
                "retry_renames": 0,
                "retry_reload_result": 0,
                "retry_new": 3,
                "retry_old": 0,
                "canary_ok": True,
            }
        )
    return rows + [
        {"type": "settings_process", "wait_status": 0},
        {"type": "settings_complete", "passed": True},
    ]


def encode(rows):
    return b"\n".join(json.dumps(row).encode() for row in rows) + b"\n"


def test_result_is_an_observation_and_does_not_assert_a_storage_fix():
    data = matrix()
    # A zero result despite partial readback and no retry is a measured bug,
    # not a collector failure or a claim that persistence is secure.
    data[3].update(first_new=1, first_old=0, retry_new=1, retry_old=0)
    result = results.validate(encode(data))
    assert result["cases"] == 12 and result["native_writer_fixed"] is False
    assert result["observations"][3]["retry_new"] == 1


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "duplicate",
        "fault",
        "bool",
        "baseline",
        "mask",
        "canary",
        "process",
        "complete",
        "extra",
    ],
)
def test_results_require_complete_fault_and_normal_baseline_evidence(damage):
    rows = matrix()
    if damage == "missing":
        rows.pop(1)
    if damage == "duplicate":
        rows[1] = copy.deepcopy(rows[2])
    if damage == "fault":
        rows[1]["injected"] = 0
    if damage == "bool":
        rows[1]["first_result"] = False
    if damage == "baseline":
        rows[0]["first_new"] = 1
    if damage == "mask":
        rows[1]["first_old"] = 1
    if damage == "canary":
        rows[1]["canary_ok"] = False
    if damage == "process":
        rows[-2]["wait_status"] = 9
    if damage == "complete":
        rows[-1]["passed"] = 1
    if damage == "extra":
        rows[1]["unreviewed"] = 1
    with pytest.raises(ValueError):
        results.validate(encode(rows))


def test_bounded_private_stderr_is_not_decoded_or_echoed():
    rows = matrix()
    rows.insert(3, {"type": "settings_stderr", "hex": "74657374"})
    assert results.validate(encode(rows))["cases"] == 12
    rows[3]["hex"] = "plaintext"
    with pytest.raises(ValueError):
        results.validate(encode(rows))
    with pytest.raises(ValueError):
        results.validate(b"x" * 16385)


def test_settings_receiver_uses_fixed_token_and_preserves_fragmented_result(tmp_path, monkeypatch):
    from tools import elf_review

    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", private)
    output = private / "result.jsonl"
    host, peer = socket.socketpair()
    tokens = []

    def send():
        peer.sendall(observe.READY)
        tokens.append(peer.recv(64))
        frame = observe.BEGIN + encode(matrix()) + observe.END
        for n in range(0, len(frame), 27):
            peer.sendall(frame[n : n + 27])

    thread = threading.Thread(target=send)
    try:
        thread.start()
        assert observe.receive(host.fileno(), time.monotonic() + 3, output)["cases"] == 12
        thread.join(timeout=3)
        assert tokens == [observe.START] and output.read_bytes() == encode(matrix())
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
        with pytest.raises(FileExistsError):
            observe.capture_private(output, b"replacement")
    finally:
        host.close()
        peer.close()
        thread.join(timeout=3)


def test_original_arm_helpers_build_without_linking_or_executing_firmware(tmp_path):
    if not shutil.which("clang") or not shutil.which("ld.lld"):
        pytest.skip("Clang/LLD required for original ARM source compilation")
    output = tmp_path / "helpers"
    record = compile_helpers(output)
    assert record["link_stubs_not_for_target"]
    assert helper_interpreter((output / "settings-test").read_bytes()) == "/lib/ld-linux-armhf.so.3"
    meta = subprocess.run(
        ["readelf", "--dyn-syms", "--wide", str(output / "settings-test")],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert all(name in meta for name in ("PR_Open", "PR_Write", "PR_Close", "PR_Sync", "rename"))
    with pytest.raises(FileExistsError):
        compile_helpers(output)


def test_original_host_fault_instrumentation_under_sanitizers(tmp_path):
    if not shutil.which("clang"):
        pytest.skip("Clang required for original host instrumentation checks")
    root = Path(__file__).resolve().parents[1]
    flags = [
        "clang",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-g",
        "-fsanitize=address,undefined",
        "-fno-omit-frame-pointer",
    ]
    library, driver = tmp_path / "libfake-nspr.so", tmp_path / "fault-driver"
    subprocess.run(
        flags + ["-shared", "-fPIC", str(root / "tests/settings_fake_nspr.c"), "-o", str(library)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        flags
        + [
            "-Wl,--export-dynamic",
            str(root / "tests/settings_fault_harness.c"),
            str(root / "firmware/settings_probe/faults.c"),
            "-ldl",
            "-o",
            str(driver),
        ],
        check=True,
        capture_output=True,
    )
    state = tmp_path / "state"
    state.mkdir()
    subprocess.run(
        [str(driver), str(library), str(state)], check=True, capture_output=True, timeout=10
    )


def synthetic_abi_library():
    from tests.test_probe import synthetic_init

    data = bytearray(0x30100)
    header = synthetic_init()
    data[: len(header)] = header
    struct.pack_into("<H", data, 16, 3)
    struct.pack_into("<II", data, 60, 0, 0)
    struct.pack_into("<II", data, 68, len(data), len(data))
    struct.pack_into("<I", data, 32, 0x30000)
    struct.pack_into("<HH", data, 46, 40, 3)
    strings = b"\0"
    for i, (name, (value, size)) in enumerate(abi.METHODS.items(), 1):
        struct.pack_into("<IIIBBH", data, 0x2F000 + i * 16, len(strings), value, size, 0x12, 0, 1)
        strings += name.encode() + b"\0"
    data[0x2F100 : 0x2F100 + len(strings)] = strings
    struct.pack_into("<10I", data, 0x30000 + 40, 0, 11, 0, 0, 0x2F000, 7 * 16, 2, 0, 4, 16)
    struct.pack_into("<10I", data, 0x30000 + 80, 0, 3, 0, 0, 0x2F100, len(strings), 0, 0, 1, 0)
    struct.pack_into("<II", data, 0x2A690, 0, 1)
    return bytes(data)


def test_bounded_settings_abi_gate_requires_all_reviewed_exports_and_layout():
    data = synthetic_abi_library()
    assert abi.review(data)["object_bytes"] == 48
    for offset in (0x2A690, 0x2F000 + 16 + 4, 0x30000 + 40 + 36):
        corrupt = bytearray(data)
        corrupt[offset] ^= 1
        with pytest.raises(ValueError):
            abi.review(bytes(corrupt))


def settings_profile(tmp_path, monkeypatch, damage=None):
    base = synthetic_profile(tmp_path, monkeypatch)
    rootfs = (base / "artifacts/rootfs.cpio").read_bytes()
    entries = artifact.parse_cpio(rootfs)
    original_library = next(d for n, m, u, d, a, b in entries if n == "lib/libc.so.6")
    selected = [
        (n, m, u, d, a, b)
        for n, m, u, d, a, b in entries
        if n not in {"fixtures", "tls-test", "TRAILER!!!"}
        and not n.startswith("fixtures/")
        and not n.endswith(".review.so")
    ]
    helper = next(d for n, m, u, d, a, b in entries if n == "tls-test")
    selected += [
        ("settings-test", stat.S_IFREG | 0o555, 0, helper, 0, 0),
        ("state", stat.S_IFDIR | 0o700, 65534, b"", 0, 0),
    ]
    present = {n[4:] for n, *_ in selected if n.startswith("lib/")}
    needed = artifact.REQUIRED_LIBS - present
    needed |= {f"libsynthetic{i}.so" for i in range(34 - len(present) - len(needed))}
    selected += [
        ("lib/" + n, stat.S_IFREG | 0o444, 0, original_library, 0, 0) for n in sorted(needed)
    ]
    selected = [
        (n, m, u, synthetic_abi_library() if n == "lib/libnlappcore.so" else d, a, b)
        for n, m, u, d, a, b in selected
    ]
    if damage == "state-owner":
        selected = [(n, m, 0 if n == "state" else u, d, a, b) for n, m, u, d, a, b in selected]
    if damage == "real-settings":
        selected.append(
            ("settings.config", stat.S_IFREG | 0o600, 0, b"should never be included", 0, 0)
        )
    if damage == "device":
        selected.append(("dev/mtd0", stat.S_IFCHR | 0o600, 0, b"", 90, 0))
    if damage == "review-library":
        selected.append(("lib/private.review.so", stat.S_IFREG | 0o444, 0, original_library, 0, 0))
    if damage == "loader-mode":
        selected = [
            (n, m & ~0o111 if n == "lib/ld-linux-armhf.so.3" else m, u, d, a, b)
            for n, m, u, d, a, b in selected
        ]
    selected.append(("TRAILER!!!", 0, 0, b"", 0, 0))
    rootfs = cpio(selected)
    kernel, _ = split_multi((base / "artifacts/uImage").read_bytes())
    (base / "artifacts/rootfs.cpio").write_bytes(rootfs)
    (base / "artifacts/uImage").write_bytes(multi_image(kernel, gzip.compress(rootfs, mtime=0)))
    if damage == "network":
        path = base / "artifacts/kernel.config"
        path.write_text(
            path.read_text().replace("# CONFIG_NETDEVICES is not set", "CONFIG_NETDEVICES=y")
        )
    manifest = {
        "status": artifact.STATUS,
        "files": {n: sha((base / "artifacts" / n).read_bytes()) for n in artifact.FILES},
        "recipe_sha256": artifact.recipes(),
        "root_inventory": artifact.inventory(selected),
        "library_count": 34,
        "settings_abi": abi.review(synthetic_abi_library()),
    }
    (base / "settings-probe.json").write_text(json.dumps(manifest))
    if damage == "corrupt":
        (base / "artifacts/rootfs.cpio").write_bytes(rootfs + b"extra")
    return base


def test_settings_integrity_gate_checks_exact_private_ram_archive(tmp_path, monkeypatch):
    assert artifact.check(settings_profile(tmp_path, monkeypatch))["device_executed"] is False


@pytest.mark.parametrize(
    "damage",
    [
        "state-owner",
        "real-settings",
        "device",
        "review-library",
        "loader-mode",
        "network",
        "corrupt",
    ],
)
def test_settings_gate_rejects_unsafe_extra_or_corrupt_content(tmp_path, monkeypatch, damage):
    with pytest.raises(ValueError):
        artifact.check(settings_profile(tmp_path, monkeypatch, damage))


@pytest.mark.parametrize(
    "flag,existing,code",
    [(None, False, 0), ("--invalid", False, 2), ("--execute-experimental-settings-probe", True, 2)],
)
def test_boot_defaults_to_offline_and_never_overwrites_or_retries(tmp_path, flag, existing, code):
    profile, commands = tmp_path / "profile", tmp_path / "commands"
    profile.mkdir()
    commands.mkdir()
    log = tmp_path / "calls"
    python = commands / "python3"
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$HEARTH_TEST_LOG"\nexit 0\n')
    python.chmod(0o755)
    if existing:
        (profile / "settings-result.jsonl").write_text("preserve")
    wrapper = Path(__file__).resolve().parents[1] / "firmware/settings_probe/boot.sh"
    env = {
        **os.environ,
        "PATH": str(commands) + os.pathsep + os.environ["PATH"],
        "HEARTH_TEST_LOG": str(log),
    }
    run = subprocess.run(
        ["sh", str(wrapper), str(profile)] + ([flag] if flag else []),
        env=env,
        check=False,
        capture_output=True,
        timeout=3,
    )
    assert run.returncode == code
    assert log.read_text().splitlines() == [f"-m firmware.settings_probe.artifact check {profile}"]
    if existing:
        assert (profile / "settings-result.jsonl").read_text() == "preserve"


def test_diagnostic_flood_cannot_consume_the_shared_target_result_cache(tmp_path):
    if not shutil.which("clang"):
        pytest.skip("Clang required for original shared cache sanitizer checks")
    root = Path(__file__).resolve().parents[1]
    driver = tmp_path / "capture-driver"
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            str(root / "tests/settings_capture_harness.c"),
            "-o",
            str(driver),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run([str(driver)], check=True, capture_output=True, timeout=3)


def test_explicit_bounded_diagnostic_truncation_preserves_complete_measurements():
    rows = matrix()
    rows.insert(1, {"type": "settings_stderr_truncated", "bytes_dropped": 20000})
    assert results.validate(encode(rows))["cases"] == 12
    for invalid in (False, 0, -1, 1048577):
        rows[1]["bytes_dropped"] = invalid
        with pytest.raises(ValueError):
            results.validate(encode(rows))
    rows[1]["bytes_dropped"] = 1
    rows.insert(2, copy.deepcopy(rows[1]))
    with pytest.raises(ValueError):
        results.validate(encode(rows))
