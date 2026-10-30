import hashlib
import json
import lzma
import os
import shutil
import struct
import subprocess
import time
import zlib

import pytest

from firmware.probe.check import FILES, HOST_FILES, check
from firmware.probe.configure import DISABLED, configure, initramfs, verify
from firmware.probe.observe import HEARTBEAT, receive
from firmware.probe.stage import patch_model, verify_loader


def synthetic_init():
    ident = b"\x7fELF\x01\x01\x01" + b"\0" * 9
    return (
        struct.pack("<16sHHIIIIIHHHHHH", ident, 2, 40, 1, 0x8054, 52, 0, 0, 52, 32, 1, 0, 0, 0)
        + struct.pack("<8I", 1, 0, 0x8000, 0x8000, 88, 88, 5, 0x1000)
        + b"\0" * 4
    )


def test_probe_configuration_disables_flash_and_network():
    stock = "CONFIG_MTD=y\nCONFIG_NET=y\nCONFIG_USB_DYNAMIC=y\nCONFIG_OMAP_WATCHDOG=y\n"
    selected = configure(stock)
    verify(selected)
    assert "CONFIG_OMAP_WATCHDOG=y" in selected
    assert configure(selected) == selected


@pytest.mark.parametrize("name", DISABLED)
@pytest.mark.parametrize("value", ["y", "m"])
def test_probe_gate_rejects_enabled_storage_or_network(name, value):
    text = configure("").replace(f"# CONFIG_{name} is not set", f"CONFIG_{name}={value}")
    with pytest.raises(ValueError, match="forbidden"):
        verify(text)


def test_probe_gate_requires_own_initramfs_and_serial():
    text = configure("")
    with pytest.raises(ValueError):
        verify(text.replace("/work/rootfs.cpio", "../initramfs_data.cpio"))
    with pytest.raises(ValueError):
        verify(text.replace("CONFIG_USB_G_SERIAL=y", "# CONFIG_USB_G_SERIAL is not set"))


def test_probe_initramfs_is_deterministic_and_contains_only_our_payload():
    if not shutil.which("cpio"):
        pytest.skip("cpio required for independent archive format validation")
    source = synthetic_init()
    archive = initramfs(source)
    assert archive == initramfs(source)
    listing = (
        subprocess.run(
            ["cpio", "--list", "--quiet"], input=archive, capture_output=True, check=True
        )
        .stdout.decode()
        .splitlines()
    )
    assert listing == [".", "dev", "proc", "sys", "dev/console", "init"]
    actual = subprocess.run(
        ["cpio", "--extract", "--to-stdout", "--quiet", "init"],
        input=archive,
        capture_output=True,
        check=True,
    ).stdout
    assert actual == source


@pytest.mark.parametrize("mode", ["script", "wrong-arch", "dynamic", "invalid-entry", "truncated"])
def test_probe_rejects_unexpected_init(mode):
    source = bytearray(synthetic_init())
    if mode == "script":
        source = b"#!/bin/sh\n" + b"x" * 64
    elif mode == "wrong-arch":
        source[18:20] = b"\x03\x00"
    elif mode == "dynamic":
        struct.pack_into("<I", source, 52, 3)
    elif mode == "invalid-entry":
        struct.pack_into("<I", source, 24, 0x1000)
    else:
        source = source[:55]
    with pytest.raises(ValueError):
        initramfs(source)


def test_model_patch_rejects_unrecognized_or_already_patched_source():
    known = (
        '#define\tDIAMOND_DEFAULT_MODEL_INDEX\t\t\tJ49_BOARD_PROTOTYPE_MODEL_INDEX\n"Display-2.0"'
    )
    patched = patch_model(known)
    assert "J49_BOARD_PVT_MODEL_INDEX" in patched and '"Display-2.6"' in patched
    for text in ("unknown", patched, known + known):
        with pytest.raises(ValueError):
            patch_model(text)


def test_loader_sources_must_match_reviewed_bytes(tmp_path):
    path = tmp_path / "omap_loader.c"
    path.write_text("unexpected source")
    with pytest.raises(ValueError, match="digest"):
        verify_loader(tmp_path, {"omap_loader.c": "0" * 64})
    path.unlink()
    path.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="regular"):
        verify_loader(tmp_path, {"omap_loader.c": "0" * 64})


def synthetic_image(kernel):
    payload = bytearray(40)
    payload[36:40] = b"\x18\x28\x6f\x01"
    payload += lzma.compress(kernel, format=lzma.FORMAT_ALONE)
    header = struct.pack(
        ">7I4B32s",
        0x27051956,
        0,
        0,
        len(payload),
        0x80008000,
        0x80008000,
        zlib.crc32(payload),
        5,
        2,
        2,
        0,
        b"synthetic probe",
    )
    header = header[:4] + struct.pack(">I", zlib.crc32(header)) + header[8:]
    return header + payload


def synthetic_build(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    blobs = {name: b"synthetic" for name in FILES}
    blobs["probe-init"] = synthetic_init()
    blobs["kernel.config"] = configure("").encode()
    blobs["uImage"] = synthetic_image(b"\0" * 128 + initramfs(synthetic_init()))
    for name, value in blobs.items():
        (artifacts / name).write_bytes(value)
    manifest = {
        "status": "experimental-unexecuted-ram-probe",
        "files": {name: hashlib.sha256(b).hexdigest() for name, b in blobs.items()},
        "host_files": {
            name: hashlib.sha256(b"synthetic helper").hexdigest() for name in HOST_FILES
        },
    }
    for name in HOST_FILES:
        (tmp_path / name).write_bytes(b"synthetic helper")
    (tmp_path / "probe-manifest.json").write_text(json.dumps(manifest))
    return manifest


def test_compiled_kernel_gate_checks_exact_initramfs_without_claiming_hardware_safety(tmp_path):
    synthetic_build(tmp_path)
    result = check(tmp_path)
    assert result["status"] == "offline-integrity-checks-passed"
    assert result["device_executed"] is False
    assert result["hardware_safe"] == "unverified"


@pytest.mark.parametrize("fault", ["digest", "header", "payload", "rootfs", "decompression-limit"])
def test_probe_image_gate_fails_closed(tmp_path, fault):
    manifest = synthetic_build(tmp_path)
    path = tmp_path / "artifacts/uImage"
    image = bytearray(path.read_bytes())
    if fault == "digest":
        image[-1] ^= 1
    elif fault == "header":
        image[8] ^= 1
    elif fault == "payload":
        image[-1] ^= 1
    elif fault == "rootfs":
        image = synthetic_image(b"unrelated initramfs")
    else:
        image = synthetic_image(b"\0" * (8 * 1024 * 1024 + 1))
    path.write_bytes(image)
    if fault != "digest":
        manifest["files"]["uImage"] = hashlib.sha256(image).hexdigest()
        (tmp_path / "probe-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        check(tmp_path)


def test_probe_heartbeat_receiver_does_not_echo_other_device_bytes():
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"PRIVATE_DEVICE_DATA\n" + HEARTBEAT.replace(b"\n", b"\r\n"))
        result = receive(read_fd, time.monotonic() + 1)
        assert result["status"] == "probe-heartbeat-observed"
        assert "PRIVATE" not in json.dumps(result)
    finally:
        os.close(read_fd)
        os.close(write_fd)
