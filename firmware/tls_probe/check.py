"""Bounded offline integrity checks, never target execution or safety certification."""

import argparse
import json
import lzma
import stat
import struct
from pathlib import Path

from firmware.probe.configure import initramfs
from firmware.tls_probe.configure import verify
from firmware.tls_probe.fixtures import TARGET_FILES
from firmware.tls_probe.package import MAX_IMAGE, MAX_ROOT, cpio, private_read, sha, unpack_image
from tools.elf_review import ArmElf, private_path

FILES = {
    "uImage",
    "rootfs.cpio",
    "kernel.config",
    "x-load-gen2.bin",
    "u-boot.bin",
    "omap_loader",
    "fallback-init",
}


def recipe_hashes():
    root = Path(__file__).resolve().parents[2]
    paths = list((root / "firmware/tls_probe").glob("*"))
    paths += [
        root / n
        for n in ("firmware/probe/configure.py", "firmware/probe/observe.py", "tools/elf_review.py")
    ]
    return {
        p.relative_to(root).as_posix(): sha(p.read_bytes())
        for p in sorted(paths)
        if p.is_file() and p.suffix in (".py", ".c", ".h", ".S", ".sh", ".json")
    }


def kernel_payload(image, fallback):
    data = unpack_image(image, 2)
    return zimage_payload(data, fallback)


def zimage_payload(data, fallback):
    if data[36:40] != b"\x18\x28\x6f\x01":
        raise ValueError("reviewed ARM zImage required")
    offset = data.find(b"\x5d\x00\x00")
    if offset < 0:
        raise ValueError("kernel LZMA stream missing")
    decoder = lzma.LZMADecompressor(lzma.FORMAT_ALONE, memlimit=128 * 1024 * 1024)
    kernel = decoder.decompress(data[offset:], max_length=8 * 1024 * 1024 + 1)
    if not decoder.eof or len(kernel) > 8 * 1024 * 1024 or kernel.count(initramfs(fallback)) != 1:
        raise ValueError("kernel or fixed fallback initramfs differs from bounded profile")
    return data


def check_kernel(root):
    root = Path(root)
    config = (root / "artifacts/kernel.config").read_text()
    verify(config)
    if config != (root / "src/Dev/linux/.config").read_text():
        raise ValueError("build config and saved config differ")
    if (root / "tls_configure.py").read_bytes() != Path(__file__).with_name(
        "configure.py"
    ).read_bytes():
        raise ValueError("staged TLS kernel recipe is stale")
    board_config = (root / "src/Dev/linux/arch/arm/mach-omap2/Kconfig").read_text()
    if (
        "\tselect GENERIC_CMOS_UPDATE" in board_config
        or board_config.count("\t# Hearth RAM TLS: no hardware clock updates") != 2
    ):
        raise ValueError("hardware clock-update selections remain")
    return kernel_payload(
        (root / "artifacts/kernel.uImage").read_bytes(),
        (root / "artifacts/fallback-init").read_bytes(),
    )


def split_multi(image):
    data = unpack_image(image, 4)
    if len(data) < 12:
        raise ValueError("missing two-component image table")
    first, second, end = struct.unpack_from(">III", data)
    offset = 12 + first + (-first % 4)
    if end or not first or not second or offset + second != len(data):
        raise ValueError("unexpected RAM image component boundaries")
    return data[12 : 12 + first], data[offset:]


def check(root):
    root = private_path(root)
    manifest = json.loads(private_read(root / "tls-probe.json", 1024 * 1024))
    if manifest.get("status") != "experimental-unexecuted-private-tls-probe":
        raise ValueError("unexpected TLS profile status")
    if manifest["recipe_sha256"] != recipe_hashes() or set(manifest["files"]) != FILES:
        raise ValueError("TLS recipe or artifact inventory changed")
    blobs = {}
    for name in FILES:
        data = private_read(root / "artifacts" / name, MAX_ROOT)
        if sha(data) != manifest["files"][name]:
            raise ValueError("TLS artifact digest mismatch")
        blobs[name] = data
    if (
        len(blobs["uImage"]) > MAX_IMAGE
        or len(blobs["x-load-gen2.bin"]) > 65536
        or len(blobs["u-boot.bin"]) > 1048576
    ):
        raise ValueError("boot artifacts exceed reviewed RAM bounds")
    verify(blobs["kernel.config"].decode())
    kernel, compressed = split_multi(blobs["uImage"])
    # Bounded decompression; gzip.decompress itself does not impose an output cap.
    import zlib

    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    rootfs = decoder.decompress(compressed, MAX_ROOT + 1)
    if (
        not decoder.eof
        or decoder.unused_data
        or len(rootfs) > MAX_ROOT
        or rootfs != blobs["rootfs.cpio"]
    ):
        raise ValueError("external RAM filesystem mismatch or decompression limit")
    allowed = {
        ".",
        "dev",
        "proc",
        "sys",
        "lib",
        "fixtures",
        "dev/console",
        "init",
        "tls-test",
        "TRAILER!!!",
    }
    allowed.update("fixtures/" + n for n in TARGET_FILES)
    inventory = manifest["root_inventory"]
    entries, offset, found = [], 0, set()
    for row in inventory:
        if rootfs[offset : offset + 6] != b"070701":
            raise ValueError("invalid newc header")
        numbers = [int(rootfs[offset + 6 + n * 8 : offset + 14 + n * 8], 16) for n in range(13)]
        name_begin = offset + 110
        name_end = name_begin + numbers[11]
        if not 1 <= numbers[11] <= 256 or name_end > len(rootfs) or rootfs[name_end - 1] != 0:
            raise ValueError("invalid newc name bounds")
        name = rootfs[name_begin : name_end - 1].decode("ascii")
        begin = name_end + (-name_end % 4)
        end = begin + numbers[6]
        if end > len(rootfs):
            raise ValueError("newc file exceeds archive")
        content = rootfs[begin:end]
        offset = end + (-end % 4)
        if (
            name in found
            or name != row["path"]
            or len(content) != row["bytes"]
            or sha(content) != row["sha256"]
        ):
            raise ValueError("RAM inventory mismatch")
        found.add(name)
        mode, uid = numbers[1], numbers[2]
        if mode != row["mode"] or uid != row["uid"] or numbers[3] != uid:
            raise ValueError("RAM ownership/mode differs")
        library = name.startswith("lib/") and len(name.split("/")) == 2
        if name not in allowed and not library:
            raise ValueError("unexpected RAM filesystem path")
        if name in (".", "dev", "proc", "sys", "lib", "fixtures"):
            expected_mode, expected_uid, devices = stat.S_IFDIR | 0o755, 0, (0, 0)
        elif name == "dev/console":
            expected_mode, expected_uid, devices = stat.S_IFCHR | 0o600, 0, (5, 1)
        elif name in ("init", "tls-test"):
            expected_mode, expected_uid, devices = stat.S_IFREG | 0o555, 0, (0, 0)
        elif name == "fixtures/server.key":
            expected_mode, expected_uid, devices = stat.S_IFREG | 0o400, 65534, (0, 0)
        elif name == "TRAILER!!!":
            expected_mode, expected_uid, devices = 0, 0, (0, 0)
        else:
            expected_mode, expected_uid, devices = stat.S_IFREG | 0o444, 0, (0, 0)
        if (mode, uid, numbers[9], numbers[10]) != (expected_mode, expected_uid, *devices):
            raise ValueError("RAM permissions, ownership or device nodes exceed the fixed profile")
        if library:
            ArmElf(content)
            if mode != stat.S_IFREG | 0o444 or uid:
                raise ValueError("unexpected library permissions")
        if name == "init":
            initramfs(content)  # static ARM ELF bounds; its archive is not used here
        entries.append((name, mode, uid, content, numbers[9], numbers[10]))
    if offset != len(rootfs) or not allowed <= found or cpio(entries) != rootfs:
        raise ValueError("RAM archive is not the exact deterministic inventory")
    library_count = sum(name.startswith("lib/") for name in found)
    required = {
        "lib/libnlwebservice.so",
        "lib/libnlwebservice.review.so",
        "lib/libssl.so.1.0.0",
        "lib/libcurl.so.4",
        "lib/libc.so.6",
        "lib/ld-linux-armhf.so.3",
    }
    if (
        not required <= found
        or not 6 <= library_count <= 64
        or library_count != manifest["library_count"]
    ):
        raise ValueError("native library inventory is incomplete or inconsistent")
    zimage_payload(kernel, blobs["fallback-init"])
    return {
        "status": "tls-probe-offline-integrity-passed",
        "device_executed": False,
        "hardware_safe": "unverified",
        "recovery": "unverified",
        "library_count": manifest["library_count"],
        "rootfs_bytes": len(rootfs),
        "image_bytes": len(blobs["uImage"]),
        "network": "loopback-only",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    print(json.dumps(check(parser.parse_args().profile), indent=2))
