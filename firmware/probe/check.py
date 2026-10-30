"""Offline integrity checks for the experimental diagnostic RAM-probe build.

Passing this gate is not hardware safety, authenticity or recovery verification.
"""

import argparse
import hashlib
import json
import lzma
import struct
import zlib
from pathlib import Path

if __package__:
    from .configure import initramfs, verify
else:
    from configure import initramfs, verify

FILES = {"x-load-gen2.bin", "u-boot.bin", "uImage", "kernel.config", "probe-init", "omap_loader"}
HOST_FILES = {"boot.sh", "check.py", "configure.py", "observe.py"}


def check(root):
    root = Path(root)
    artifacts = root / "artifacts"
    manifest = json.loads((root / "probe-manifest.json").read_text())
    if manifest.get("status") != "experimental-unexecuted-ram-probe":
        raise ValueError("unexpected artifact status")
    if set(manifest["files"]) != FILES:
        raise ValueError("unexpected artifact inventory")
    if set(manifest["host_files"]) != HOST_FILES:
        raise ValueError("unexpected host helper inventory")
    for name in sorted(HOST_FILES):
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            raise ValueError("regular bounded host helper required")
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["host_files"][name]:
            raise ValueError("host helper digest mismatch: " + name)
    blobs = {}
    for name in sorted(FILES):
        path = artifacts / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("regular bounded artifact required")
        blobs[name] = path.read_bytes()
        if hashlib.sha256(blobs[name]).hexdigest() != manifest["files"][name]:
            raise ValueError("artifact digest mismatch: " + name)
    verify(blobs["kernel.config"].decode())
    if (
        not 0 < len(blobs["x-load-gen2.bin"]) <= 65536
        or not 0 < len(blobs["u-boot.bin"]) <= 1048576
    ):
        raise ValueError("bootloader exceeds reviewed RAM region")
    cpio = initramfs(blobs["probe-init"])
    image = blobs["uImage"]
    if len(image) < 64:
        raise ValueError("missing uImage header")
    fields = struct.unpack_from(">7I4B32s", image)
    magic, crc, _, size, load, entry, data_crc = fields[:7]
    header = image[:4] + b"\0" * 4 + image[8:64]
    if magic != 0x27051956 or zlib.crc32(header) != crc:
        raise ValueError("uImage header CRC mismatch")
    payload = image[64:]
    if len(payload) != size or zlib.crc32(payload) != data_crc:
        raise ValueError("uImage payload CRC mismatch")
    if fields[7:11] != (5, 2, 2, 0) or load != 0x80008000 or entry != load:
        raise ValueError("unexpected Linux ARM image parameters")
    if payload[36:40] != b"\x18\x28\x6f\x01":
        raise ValueError("ARM zImage required")
    # This deliberately supports only the reviewed kernel's LZMA stream. No
    # external decompressor or executable from the image is invoked.
    offset = payload.find(b"\x5d\x00\x00")
    if offset < 0:
        raise ValueError("expected LZMA stream missing")
    decoder = lzma.LZMADecompressor(lzma.FORMAT_ALONE, memlimit=128 * 1024 * 1024)
    kernel = decoder.decompress(payload[offset:], max_length=8 * 1024 * 1024 + 1)
    if not decoder.eof or len(kernel) > 8 * 1024 * 1024:
        raise ValueError("unsupported or oversized probe kernel")
    if kernel.count(cpio) != 1:
        raise ValueError("compiled kernel does not contain the exact minimal initramfs")
    return {
        "status": "offline-integrity-checks-passed",
        "device_executed": False,
        "hardware_safe": "unverified",
        "recovery": "unverified",
        "initramfs_bytes": len(cpio),
        "kernel_uncompressed_bytes": len(kernel),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build_directory")
    args = parser.parse_args()
    print(json.dumps(check(args.build_directory), indent=2))
