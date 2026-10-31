import copy
import gzip
import json
import lzma
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

from firmware.probe import configure as heartbeat
from firmware.tls_probe import configure, fixtures, observe
from firmware.tls_probe.check import FILES, check, recipe_hashes, split_multi
from firmware.tls_probe.compile import compile_helpers
from firmware.tls_probe.package import cpio, helper_interpreter, multi_image, sha
from tests.test_probe import synthetic_init
from tools import elf_review


def matrix():
    rows = [{"type": "tls_setup", "loopback_stage": 3, "loopback_result": 0, "clock_result": 0}]
    for variant in ("original", "candidate"):
        for case in fixtures.CASES:
            accepted = case == "valid" or (
                variant == "original"
                and case in ("future_cert", "missing_issuer_crl", "expired_crl", "future_crl")
            )
            rows.append(
                {
                    "type": "tls_case",
                    "variant": variant,
                    "case": case,
                    "curl_code": 0 if accepted else (51 if case == "wrong_host" else 60),
                    "passed": True,
                }
            )
        rows.append({"type": "tls_process", "variant": variant, "wait_status": 0})
    return rows + [{"type": "tls_complete", "passed": True}]


def encode(rows):
    return b"\n".join(json.dumps(row).encode() for row in rows) + b"\n"


def test_tls_profile_adds_only_loopback_and_retains_heartbeat_boundaries():
    original = heartbeat.configure("CONFIG_OMAP_WATCHDOG=y\n")
    heartbeat.verify(original)
    selected = configure.configure(original)
    configure.verify(selected)
    assert configure.configure(selected) == selected
    assert "CONFIG_OMAP_WATCHDOG=y" in selected
    assert "CONFIG_NET=y" in selected and "# CONFIG_NETDEVICES is not set" in selected
    assert "# CONFIG_GENERIC_CMOS_UPDATE is not set" in selected
    with pytest.raises(ValueError):
        heartbeat.verify(selected)


@pytest.mark.parametrize(
    "name", ["MTD", "BLOCK", "NETDEVICES", "RTC_CLASS", "GENERIC_CMOS_UPDATE", "WLAN"]
)
@pytest.mark.parametrize("value", ["y", "m"])
def test_tls_kernel_rejects_storage_physical_network_or_clock_updates(name, value):
    text = configure.configure("").replace(f"# CONFIG_{name} is not set", f"CONFIG_{name}={value}")
    with pytest.raises(ValueError):
        configure.verify(text)


def test_tls_kernel_rejects_missing_required_or_duplicate_settings():
    text = configure.configure("")
    for damaged in (
        text.replace("CONFIG_INET=y", "# CONFIG_INET is not set"),
        text + "\nCONFIG_NET=y\n",
        text.replace("/work/rootfs.cpio", "other.cpio"),
    ):
        with pytest.raises(ValueError):
            configure.verify(damaged)


def test_hardware_clock_patch_is_exact_and_idempotent():
    text = "OMAP3\n\tselect GENERIC_CMOS_UPDATE\nOMAP4\n\tselect GENERIC_CMOS_UPDATE\n"
    changed = configure.disable_clock_updates(text)
    assert "select GENERIC_CMOS_UPDATE" not in changed
    assert configure.disable_clock_updates(changed) == changed
    for damaged in ("", text + "\tselect GENERIC_CMOS_UPDATE\n"):
        with pytest.raises(ValueError):
            configure.disable_clock_updates(damaged)


def test_complete_tls_matrix_requires_explicit_certificate_rejections():
    assert observe.validate(encode(matrix()))["cases"] == 18
    assert not observe.validate(encode(matrix()))["installed"]


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "duplicate",
        "timeout",
        "false",
        "bool",
        "unknown",
        "completion",
        "setup",
        "process",
    ],
)
def test_tls_results_fail_closed(damage):
    rows = copy.deepcopy(matrix())
    if damage == "missing":
        rows.pop(1)
    if damage == "duplicate":
        rows[1] = rows[2]
    if damage == "timeout":
        rows[1]["curl_code"] = 28
    if damage == "false":
        rows[1]["passed"] = False
    if damage == "bool":
        rows[1]["curl_code"] = False
    if damage == "unknown":
        rows[1]["extra"] = "unexpected"
    if damage == "completion":
        rows[-1]["passed"] = 1  # JSON numeric truthiness is not a completed test.
    if damage == "setup":
        rows[0]["loopback_result"] = -1
    if damage == "process":
        next(row for row in rows if row["type"] == "tls_process")["wait_status"] = 122 << 8
    with pytest.raises(ValueError):
        observe.validate(encode(rows))
    with pytest.raises(ValueError):
        observe.validate(b"x" * (observe.MAX_REPORT + 1))


def test_serial_receiver_sends_only_fixed_token_and_handles_fragmentation():
    host, peer = socket.socketpair()
    token = []

    def send():
        peer.sendall(observe.READY)
        token.append(peer.recv(64))
        frame = observe.BEGIN + encode(matrix()) + observe.END
        for offset in range(0, len(frame), 31):
            peer.sendall(frame[offset : offset + 31])

    thread = threading.Thread(target=send)
    try:
        thread.start()
        result = observe.receive(host.fileno(), time.monotonic() + 3)
        thread.join(timeout=3)
        assert result["cases"] == 18 and token == [observe.START]
    finally:
        host.close()
        peer.close()
        thread.join(timeout=3)


def test_multi_image_has_exact_bounded_components_and_crcs():
    kernel, root = b"kernel" * 5, b"compressed-ram-filesystem"
    image = multi_image(kernel, root)
    assert image == multi_image(kernel, root)
    assert split_multi(image) == (kernel, root)
    for damaged in (image[:-1], image[:30] + bytes([image[30] ^ 1]) + image[31:], image + b"extra"):
        with pytest.raises(ValueError):
            split_multi(damaged)


@pytest.mark.parametrize("name", ["../settings", "/init", "lib/../../etc/shadow", "lib//bad"])
def test_ram_archive_rejects_escape_paths(name):
    with pytest.raises(ValueError):
        cpio([(name, 0o100444, 0, b"data", 0, 0)])


def test_helpers_cross_compile_without_any_firmware_input(tmp_path):
    if not shutil.which("clang") or not shutil.which("ld.lld") or not shutil.which("readelf"):
        pytest.skip("Clang, LLD and readelf required for offline ARM cross-compilation")
    output = tmp_path / "helpers"
    record = compile_helpers(output)
    assert record["link_stubs_not_for_target"]
    for name in ("tls-init", "tls-test"):
        data = (output / name).read_bytes()
        assert data[:7] == b"\x7fELF\x01\x01\x01"
        assert struct.unpack_from("<H", data, 18)[0] == 40
    meta = subprocess.run(
        ["readelf", "-l", "-d", str(output / "tls-test")],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "/lib/ld-linux-armhf.so.3" in meta
    assert "[libc.so.6]" in meta and "[libdl.so.2]" in meta
    with pytest.raises(FileExistsError):
        compile_helpers(output)


def test_fixture_generator_uses_only_synthetic_private_keys(tmp_path, monkeypatch):
    if not shutil.which("openssl"):
        pytest.skip("OpenSSL required for synthetic fixture baseline")
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", private)
    output = private / "fixtures"
    record = fixtures.generate(output)
    assert record["cases"] == list(fixtures.CASES)
    assert set(record["target_sha256"]) == fixtures.TARGET_FILES
    assert "ca.key" not in fixtures.TARGET_FILES and "other-ca.key" not in fixtures.TARGET_FILES
    assert not record["native_execution"] and not record["real_device_credentials"]
    assert all(p.stat().st_mode & 0o077 == 0 for p in output.rglob("*") if p.is_file())


def synthetic_profile(tmp_path, monkeypatch, damage=None):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", private)
    profile = private / "profile"
    (profile / "artifacts").mkdir(parents=True)
    init = synthetic_init()
    helper = bytearray(256)
    helper[: len(init)] = init
    struct.pack_into("<H", helper, 44, 2)
    struct.pack_into("<II", helper, 68, 256, 256)
    interpreter = b"/lib/ld-linux-armhf.so.3\0"
    helper[128 : 128 + len(interpreter)] = interpreter
    struct.pack_into("<8I", helper, 84, 3, 128, 0, 0, len(interpreter), len(interpreter), 4, 1)
    library = bytearray(init)
    struct.pack_into("<H", library, 16, 3)
    entries = [
        (d, stat.S_IFDIR | 0o755, 0, b"", 0, 0)
        for d in (".", "dev", "proc", "sys", "lib", "fixtures")
    ]
    entries += [
        ("dev/console", stat.S_IFCHR | 0o600, 0, b"", 5, 1),
        ("init", stat.S_IFREG | 0o555, 0, init, 0, 0),
        ("tls-test", stat.S_IFREG | 0o555, 0, bytes(helper), 0, 0),
    ]
    for name in (
        "libnlwebservice.so",
        "libnlwebservice.review.so",
        "libssl.so.1.0.0",
        "libcurl.so.4",
        "libc.so.6",
        "ld-linux-armhf.so.3",
    ):
        mode = 0o555 if name == "ld-linux-armhf.so.3" else 0o444
        if damage == "interpreter-permission" and name == "ld-linux-armhf.so.3":
            mode = 0o444
        entries.append(("lib/" + name, stat.S_IFREG | mode, 0, bytes(library), 0, 0))
    for name in sorted(fixtures.TARGET_FILES):
        entries.append(
            (
                "fixtures/" + name,
                stat.S_IFREG | (0o400 if name == "server.key" else 0o444),
                65534 if name == "server.key" else 0,
                b"synthetic fixture only",
                0,
                0,
            )
        )
    if damage == "extra-key":
        entries.append(("fixtures/ca.key", stat.S_IFREG | 0o400, 0, b"not-for-target", 0, 0))
    if damage == "key-owner":
        entries = [
            (n, m, 0 if n == "fixtures/server.key" else u, d, a, b) for n, m, u, d, a, b in entries
        ]
    if damage == "device":
        entries = [(n, m, u, d, a, 2 if n == "dev/console" else b) for n, m, u, d, a, b in entries]
    if damage == "writable-lib":
        entries = [
            (n, m | 0o200 if n.startswith("lib/") else m, u, d, a, b)
            for n, m, u, d, a, b in entries
        ]
    entries.append(("TRAILER!!!", 0, 0, b"", 0, 0))
    rootfs = cpio(entries)
    zimage = bytearray(64)
    zimage[36:40] = b"\x18\x28\x6f\x01"
    zimage += lzma.compress(
        b"synthetic kernel" + heartbeat.initramfs(init), format=lzma.FORMAT_ALONE
    )
    config = configure.configure("")
    if damage == "network":
        config = config.replace("# CONFIG_NETDEVICES is not set", "CONFIG_NETDEVICES=y")
    data = {
        "uImage": multi_image(bytes(zimage), gzip.compress(rootfs, mtime=0)),
        "rootfs.cpio": rootfs,
        "kernel.config": config.encode(),
        "fallback-init": init,
        "x-load-gen2.bin": b"synthetic xloader",
        "u-boot.bin": b"synthetic uboot",
        "omap_loader": b"synthetic host loader never executed",
    }
    assert set(data) == FILES
    for name, blob in data.items():
        (profile / "artifacts" / name).write_bytes(blob)
    record = {
        "status": "experimental-unexecuted-private-tls-probe",
        "recipe_sha256": recipe_hashes(),
        "files": {n: sha(d) for n, d in data.items()},
        "library_count": 7 if damage == "count" else 6,
        "root_inventory": [
            {"path": n, "mode": m, "uid": u, "bytes": len(d), "sha256": sha(d)}
            for n, m, u, d, _, _ in entries
        ],
    }
    (profile / "tls-probe.json").write_text(json.dumps(record))
    if damage == "corruption":
        (profile / "artifacts/uImage").write_bytes(data["uImage"] + b"corrupt")
    return profile


def test_private_profile_gate_accepts_synthetic_complete_inventory(tmp_path, monkeypatch):
    result = check(synthetic_profile(tmp_path, monkeypatch))
    assert result["status"] == "tls-probe-offline-integrity-passed"
    assert result["device_executed"] is False


@pytest.mark.parametrize(
    "damage",
    [
        "extra-key",
        "key-owner",
        "device",
        "writable-lib",
        "network",
        "count",
        "corruption",
        "interpreter-permission",
    ],
)
def test_private_profile_gate_rejects_unsafe_or_corrupt_content(tmp_path, monkeypatch, damage):
    with pytest.raises(ValueError):
        check(synthetic_profile(tmp_path, monkeypatch, damage))


def test_failed_reports_are_preserved_privately_without_overwrite(tmp_path, monkeypatch):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", private)
    host, peer = socket.socketpair()
    output = private / "result.jsonl"
    rows = matrix()
    rows[-1]["passed"] = False
    payload = encode(rows)
    peer.sendall(observe.BEGIN + payload + observe.END)
    try:
        with pytest.raises(ValueError):
            observe.receive(host.fileno(), time.monotonic() + 1, output)
        assert output.read_bytes() == payload and output.stat().st_mode & 0o077 == 0
        with pytest.raises(FileExistsError):
            observe.capture_private(output, b"replacement")
        assert output.read_bytes() == payload
    finally:
        host.close()
        peer.close()


def test_receiver_detects_fallback_without_waiting_for_tls_deadline():
    host, peer = socket.socketpair()
    peer.sendall(observe.HEARTBEAT)
    try:
        with pytest.raises(ValueError, match="fallback heartbeat"):
            observe.receive(host.fileno(), time.monotonic() + 1)
    finally:
        host.close()
        peer.close()


@pytest.mark.parametrize(
    "flag,existing,code",
    [(None, False, 0), ("--invalid", False, 2), ("--execute-experimental-tls-probe", True, 2)],
)
def test_boot_wrapper_stops_before_native_preflight_or_loader(tmp_path, flag, existing, code):
    profile, commands = tmp_path / "profile", tmp_path / "commands"
    profile.mkdir()
    commands.mkdir()
    log = tmp_path / "calls"
    # Replace host Python with a recorder to isolate shell execution gating.
    python = commands / "python3"
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$HEARTH_TEST_LOG"\nexit 0\n')
    python.chmod(0o755)
    if existing:
        (profile / "tls-result.jsonl").write_text("preserve")
    wrapper = Path(__file__).resolve().parents[1] / "firmware/tls_probe/boot.sh"
    argv = ["sh", str(wrapper), str(profile)] + ([flag] if flag else [])
    env = {
        **os.environ,
        "PATH": str(commands) + os.pathsep + os.environ["PATH"],
        "HEARTH_TEST_LOG": str(log),
    }
    result = subprocess.run(argv, check=False, capture_output=True, env=env, timeout=3)
    assert result.returncode == code
    calls = log.read_text().splitlines()
    assert len(calls) == 1 and calls[0].startswith("-m firmware.tls_probe.check ")
    if existing:
        assert (profile / "tls-result.jsonl").read_text() == "preserve"


def test_setup_and_process_evidence_are_required_even_with_all_cases_passing():
    rows = matrix()
    rows.insert(2, {"type": "tls_stderr", "variant": "original", "hex": "74657374"})
    assert observe.validate(encode(rows))["cases"] == 18
    rows[2]["hex"] = "untrusted plaintext"
    with pytest.raises(ValueError, match="diagnostic"):
        observe.validate(encode(rows))


def test_helper_interpreter_is_read_from_elf_and_static_helpers_are_rejected():
    with pytest.raises(ValueError, match="interpreter"):
        helper_interpreter(synthetic_init())


def test_host_kernel_requires_execute_permission_on_dynamic_interpreter(tmp_path):
    # Reproduce Linux open_exec semantics using trusted HOST true/ld binaries.
    # This test never executes device firmware or an ARM cross-compiled helper.
    source = shutil.which("true")
    if not source:
        pytest.skip("trusted host true executable required")
    data = bytearray(Path(source).read_bytes())
    if data[:6] != b"\x7fELF\x02\x01":
        pytest.skip("dynamic little-endian ELF64 host required")
    offset = struct.unpack_from("<Q", data, 32)[0]
    stride, count = struct.unpack_from("<HH", data, 54)
    slot = next(
        (
            offset + i * stride
            for i in range(count)
            if struct.unpack_from("<I", data, offset + i * stride)[0] == 3
        ),
        None,
    )
    if slot is None:
        pytest.skip("host true has no dynamic interpreter")
    begin = struct.unpack_from("<Q", data, slot + 8)[0]
    size = struct.unpack_from("<Q", data, slot + 32)[0]
    host_loader = Path(bytes(data[begin : begin + size - 1]).decode())
    binary, loader = tmp_path / "host-true", tmp_path / "host-loader"
    binary.write_bytes(data)
    binary.chmod(0o755)
    try:
        subprocess.run([str(binary)], check=True, capture_output=True, timeout=3)
    except PermissionError:
        pytest.skip("test filesystem is mounted noexec")
    loader.write_bytes(host_loader.read_bytes())
    interpreter = str(loader).encode() + b"\0"
    struct.pack_into("<Q", data, slot + 8, len(data))
    struct.pack_into("<QQ", data, slot + 32, len(interpreter), len(interpreter))
    data.extend(interpreter)
    binary.write_bytes(data)
    loader.chmod(0o444)
    with pytest.raises(PermissionError):
        subprocess.run([str(binary)], check=True, capture_output=True, timeout=3)
    loader.chmod(0o555)
    assert (
        subprocess.run([str(binary)], check=False, capture_output=True, timeout=3).returncode == 0
    )
