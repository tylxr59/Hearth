"""Assemble/check the PRIVATE synthetic RAM storage comparison, never install it."""

import argparse
import gzip
import json
import stat
import struct
import zlib
from pathlib import Path

from firmware.settings_compat.compile import source_hashes as candidate_sources
from firmware.settings_compat_probe.compile import source_hashes
from firmware.settings_probe.abi import review as base_abi
from firmware.settings_probe.artifact import inventory, parse_cpio
from firmware.settings_probe.artifact import recipes as prior_recipes
from firmware.settings_probe.artifact import validate_entries as validate_base_entries
from firmware.tls_probe.check import FILES, split_multi, zimage_payload
from firmware.tls_probe.check import check as check_base
from firmware.tls_probe.configure import verify
from firmware.tls_probe.package import MAX_IMAGE, MAX_ROOT, cpio, multi_image, private_read, sha
from tools.elf_review import ArmElf, private_path

STATUS = "experimental-unexecuted-private-settings-compat-probe"
EXTRA = {"lib/libhearth-settings-compat.so", "lib/libhearth-settings-faults.so"}
RANGES = {
    "config_init": ("appcore", 0x1BDA4, 164),
    "config_add": ("appcore", 0x1C2F8, 372),
    "config_get": ("appcore", 0x1BE48, 28),
    "free_entry": ("appcore", 0x1BD14, 88),
    "hash_add": ("plds", 0x205C, 256),
    "compare_values": ("plds", 0x2774, 60),
}


def recipes():
    root = Path(__file__).resolve().parents[2]
    result = prior_recipes()
    for folder in ("settings_compat", "settings_compat_probe"):
        for p in (root / "firmware" / folder).iterdir():
            if p.is_file() and p.suffix in (".py", ".c", ".h", ".S", ".sh", ".json", ".map"):
                result[p.relative_to(root).as_posix()] = sha(p.read_bytes())
    return result


def validate_review(entries, record):
    blobs = {
        "appcore": next(d for n, _, _, d, _, _ in entries if n == "lib/libnlappcore.so"),
        "plds": next(d for n, _, _, d, _, _ in entries if n == "lib/libplds4.so"),
    }
    base_abi(blobs["appcore"])
    if (
        record.get("status") != "offline-storage-compat-abi-reviewed"
        or record.get("profile") != "Display-2.6/5.9.4-5"
        or record.get("object_bytes") != 48
        or record.get("field_offsets") != {"table": 4, "lock": 8, "dirty": 12, "filename": 20}
        or record.get("pointer_value_comparison") is not True
        or record.get("update_callback_does_not_free_value") is not True
    ):
        raise ValueError("separate exact-profile storage ABI review required")
    if record["source_sha256"] != {n: sha(d) for n, d in blobs.items()} or set(
        record["ranges"]
    ) != set(RANGES):
        raise ValueError("reviewed private library identity differs")
    for name, (library, address, size) in RANGES.items():
        row = record["ranges"][name]
        if (row["library"], row["address"], row["bytes"]) != (library, address, size) or row[
            "sha256"
        ] != sha(ArmElf(blobs[library]).read(address, size)):
            raise ValueError("reviewed private function range differs")


def validate_entries(entries):
    selected = {n: (m, u, d, a, b) for n, m, u, d, a, b in entries if n in EXTRA}
    if set(selected) != EXTRA:
        raise ValueError("comparison requires exactly two original test/correction libraries")
    validate_base_entries([row for row in entries if row[0] not in EXTRA])
    for mode, uid, data, major, minor in selected.values():
        ArmElf(data)
        if (mode, uid, major, minor) != (stat.S_IFREG | 0o444, 0, 0, 0) or struct.unpack_from(
            "<H", data, 16
        )[0] != 3:
            raise ValueError("read-only original ARM shared library required")
        ArmElf(data)


def package(base, helpers, review, output):
    base, output = private_path(base), private_path(output)
    if output.exists():
        raise ValueError("fresh private comparison output required")
    check_base(base)
    base_record = private_read(base / "tls-probe.json")
    original = parse_cpio(private_read(base / "artifacts/rootfs.cpio", MAX_ROOT))
    original = [
        row
        for row in original
        if row[0].startswith("lib/") and row[0] != "lib/libnlwebservice.review.so"
    ]
    review_bytes = private_read(review)
    abi_record = json.loads(review_bytes)
    validate_review(original, abi_record)
    helpers = Path(helpers)
    record = json.loads((helpers / "helpers.json").read_text())
    candidate_record = json.loads((helpers / "candidate/compat.json").read_text())
    if (
        record["source_sha256"] != source_hashes()
        or candidate_record["source_sha256"] != candidate_sources()
        or candidate_record.get("fixed_phase_trace") is not True
        or set(record["files"])
        != {"settings-init", "settings-test", "libhearth-settings-faults.so"}
    ):
        raise ValueError("compiled original helper/candidate sources stale")
    blobs = {n: (helpers / n).read_bytes() for n in record["files"]}
    if any(sha(d) != record["files"][n] for n, d in blobs.items()):
        raise ValueError("compiled helper changed")
    candidate = (helpers / "candidate/libhearth-settings-compat.so").read_bytes()
    if sha(candidate) != record["candidate_sha256"] or candidate_record["files"] != {
        "libhearth-settings-compat.so": sha(candidate)
    }:
        raise ValueError("compiled original correction library changed")
    entries = [
        (
            n,
            stat.S_IFDIR | (0o700 if n == "state" else 0o755),
            65534 if n == "state" else 0,
            b"",
            0,
            0,
        )
        for n in (".", "dev", "lib", "proc", "state", "sys")
    ]
    entries += [
        ("dev/console", stat.S_IFCHR | 0o600, 0, b"", 5, 1),
        ("init", stat.S_IFREG | 0o555, 0, blobs["settings-init"], 0, 0),
        ("settings-test", stat.S_IFREG | 0o555, 0, blobs["settings-test"], 0, 0),
    ] + original
    entries += [
        ("lib/libhearth-settings-compat.so", stat.S_IFREG | 0o444, 0, candidate, 0, 0),
        (
            "lib/libhearth-settings-faults.so",
            stat.S_IFREG | 0o444,
            0,
            blobs["libhearth-settings-faults.so"],
            0,
            0,
        ),
        ("TRAILER!!!", 0, 0, b"", 0, 0),
    ]
    validate_entries(entries)
    rootfs = cpio(entries)
    if len(rootfs) > MAX_ROOT:
        raise ValueError("bounded RAM archive required")
    kernel, _ = split_multi(private_read(base / "artifacts/uImage", MAX_IMAGE))
    files = {
        n: private_read(base / "artifacts" / n, MAX_ROOT) for n in FILES - {"uImage", "rootfs.cpio"}
    }
    files |= {"uImage": multi_image(kernel, gzip.compress(rootfs, mtime=0)), "rootfs.cpio": rootfs}
    if len(files["uImage"]) > MAX_IMAGE:
        raise ValueError("RAM upload address window exceeded")
    manifest = {
        "status": STATUS,
        "device_executed": False,
        "persistent_storage": False,
        "native_application": False,
        "whole_boot_chain_write_free": "unverified",
        "cases": 29,
        "files": {n: sha(d) for n, d in files.items()},
        "recipe_sha256": recipes(),
        "base_manifest_sha256": sha(base_record),
        "native_review_sha256": sha(review_bytes),
        "native_review": abi_record,
        "root_inventory": inventory(entries),
    }
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / "artifacts").mkdir(mode=0o700)
    for name, data in files.items():
        p = output / "artifacts" / name
        with p.open("xb") as stream:
            p.chmod(0o700 if name == "omap_loader" else 0o600)
            stream.write(data)
    path = output / "compat-probe.json"
    with path.open("x") as stream:
        path.chmod(0o600)
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    return check(output)


def check(root):
    root = private_path(root)
    record = json.loads(private_read(root / "compat-probe.json", 1024 * 1024))
    if (
        record.get("status") != STATUS
        or record["recipe_sha256"] != recipes()
        or set(record["files"]) != FILES
    ):
        raise ValueError("comparison recipe/artifact inventory changed")
    files = {n: private_read(root / "artifacts" / n, MAX_ROOT) for n in FILES}
    if any(sha(d) != record["files"][n] for n, d in files.items()):
        raise ValueError("comparison artifact changed")
    if (
        len(files["uImage"]) > MAX_IMAGE
        or len(files["x-load-gen2.bin"]) > 65536
        or len(files["u-boot.bin"]) > 1048576
    ):
        raise ValueError("boot artifacts exceed reviewed RAM bounds")
    verify(files["kernel.config"].decode())
    kernel, compressed = split_multi(files["uImage"])
    zimage_payload(kernel, files["fallback-init"])
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    rootfs = decoder.decompress(compressed, MAX_ROOT + 1)
    if (
        not decoder.eof
        or decoder.unused_data
        or len(rootfs) > MAX_ROOT
        or rootfs != files["rootfs.cpio"]
    ):
        raise ValueError("comparison archive mismatch/decompression limit")
    entries = parse_cpio(rootfs)
    validate_entries(entries)
    validate_review(entries, record["native_review"])
    if inventory(entries) != record["root_inventory"]:
        raise ValueError("comparison inventory changed")
    return {
        "status": "settings-compat-offline-integrity-passed",
        "device_executed": False,
        "hardware_safe": "unverified",
        "restoration": "unverified",
        "cases": 29,
        "baseline_libraries": 34,
        "original_test_libraries": 2,
        "rootfs_bytes": len(rootfs),
        "image_bytes": len(files["uImage"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("package")
    for key in ("base", "helpers", "review", "output"):
        prepare.add_argument("--" + key, required=True)
    sub.add_parser("check").add_argument("profile")
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(package(**args) if command == "package" else check(args["profile"]), indent=2))
