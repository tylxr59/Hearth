"""Private RAM-only file lab: no actual settings, mount, flash or physical network."""

import argparse
import gzip
import json
import stat
import zlib
from pathlib import Path

from firmware.file_install_probe.compile import source_hashes, supervisor_source
from firmware.probe.configure import initramfs
from firmware.settings_compat_probe import artifact as storage
from firmware.settings_probe.artifact import inventory, parse_cpio
from firmware.tls_probe.check import FILES, split_multi, zimage_payload
from firmware.tls_probe.check import check as check_base
from firmware.tls_probe.configure import verify
from firmware.tls_probe.package import (
    MAX_IMAGE,
    MAX_ROOT,
    cpio,
    helper_interpreter,
    multi_image,
    private_read,
    sha,
)
from tools.elf_review import private_path

STATUS = "experimental-unexecuted-private-file-commissioning-recovery-ram-lab-v2"
CASES = 91


def recipes():
    root = Path(__file__).resolve().parents[2]
    result = storage.recipes()
    for folder in ("file_install", "file_install_probe"):
        for p in (root / "firmware" / folder).iterdir():
            if p.is_file() and p.suffix in (".py", ".c", ".h", ".sh", ".json"):
                result[p.relative_to(root).as_posix()] = sha(p.read_bytes())
    result["tests/file_install_harness.c"] = sha(
        (root / "tests/file_install_harness.c").read_bytes()
    )
    result["tests/file_recovery_harness.c"] = sha(
        (root / "tests/file_recovery_harness.c").read_bytes()
    )
    return result


def validate_entries(entries):
    extra = [r for r in entries if r[0] == "file-test"]
    if len(extra) != 1:
        raise ValueError("one original file-lab helper required")
    name, mode, uid, data, major, minor = extra[0]
    if (mode, uid, major, minor) != (stat.S_IFREG | 0o555, 0, 0, 0):
        raise ValueError("file-lab helper permissions changed")
    helper_interpreter(data)
    storage.validate_entries([r for r in entries if r[0] != name])
    candidate = next(r[3] for r in entries if r[0] == "lib/libhearth-settings-compat.so")
    if b"HEARTH_STORAGE_PHASE " in candidate:
        raise ValueError("standalone settings candidate must omit lab tracing")
    initramfs(next(r[3] for r in entries if r[0] == "init"))


def package(base, helpers, review, output):
    base, output = private_path(base), private_path(output)
    check_base(base)
    helpers = Path(helpers)
    compiled = json.loads((helpers / "helpers.json").read_text())
    if (
        compiled["source_sha256"] != source_hashes()
        or compiled.get("ram_only_file_adapter") is not True
        or compiled.get("candidate_phase_trace") is not False
        or compiled["generated_supervisor_sha256"] != sha(supervisor_source().encode())
        or compiled["settings_helpers_manifest_sha256"]
        != sha((helpers / "settings/helpers.json").read_bytes())
    ):
        raise ValueError("file lab sources/mode changed")
    settings = json.loads((helpers / "settings/helpers.json").read_text())
    candidate = json.loads((helpers / "settings/candidate/compat.json").read_text())
    if (
        candidate.get("fixed_phase_trace") is not False
        or candidate["linker"]["profile"] != "gnu-2008q3-container"
    ):
        raise ValueError("exact standalone GNU candidate required")
    blobs = {n: (helpers / n).read_bytes() for n in ("file-init", "file-test")}
    if compiled["files"] != {n: sha(d) for n, d in blobs.items()}:
        raise ValueError("file lab helpers changed")
    for n, digest in settings["files"].items():
        if sha((helpers / "settings" / n).read_bytes()) != digest:
            raise ValueError("settings helper changed")
    original = parse_cpio(private_read(base / "artifacts/rootfs.cpio", MAX_ROOT))
    original = [r for r in original if r[0].startswith("lib/") and not r[0].endswith(".review.so")]
    review_bytes = private_read(review)
    abi = json.loads(review_bytes)
    storage.validate_review(original, abi)
    shim = (helpers / "settings/candidate/libhearth-settings-compat.so").read_bytes()
    if sha(shim) != settings["candidate_sha256"] or candidate["files"] != {
        "libhearth-settings-compat.so": sha(shim)
    }:
        raise ValueError("standalone correction changed")
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
        ("init", stat.S_IFREG | 0o555, 0, blobs["file-init"], 0, 0),
        ("file-test", stat.S_IFREG | 0o555, 0, blobs["file-test"], 0, 0),
        (
            "settings-test",
            stat.S_IFREG | 0o555,
            0,
            (helpers / "settings/settings-test").read_bytes(),
            0,
            0,
        ),
    ]
    entries += original + [
        ("lib/libhearth-settings-compat.so", stat.S_IFREG | 0o444, 0, shim, 0, 0),
        (
            "lib/libhearth-settings-faults.so",
            stat.S_IFREG | 0o444,
            0,
            (helpers / "settings/libhearth-settings-faults.so").read_bytes(),
            0,
            0,
        ),
        ("TRAILER!!!", 0, 0, b"", 0, 0),
    ]
    validate_entries(entries)
    rootfs = cpio(entries)
    if len(rootfs) > MAX_ROOT:
        raise ValueError("RAM archive bound exceeded")
    kernel, _ = split_multi(private_read(base / "artifacts/uImage", MAX_IMAGE))
    files = {
        n: private_read(base / "artifacts" / n, MAX_ROOT) for n in FILES - {"uImage", "rootfs.cpio"}
    }
    files |= {"rootfs.cpio": rootfs, "uImage": multi_image(kernel, gzip.compress(rootfs, mtime=0))}
    if len(files["uImage"]) > MAX_IMAGE:
        raise ValueError("RAM upload bound exceeded")
    record = {
        "status": STATUS,
        "device_executed": False,
        "ram_only": True,
        "actual_settings": False,
        "cases": CASES,
        "candidate_phase_trace": False,
        "files": {n: sha(d) for n, d in files.items()},
        "recipe_sha256": recipes(),
        "native_review": abi,
        "root_inventory": inventory(entries),
    }
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / "artifacts").mkdir(mode=0o700)
    for n, data in files.items():
        p = output / "artifacts" / n
        with p.open("xb") as stream:
            p.chmod(0o700 if n == "omap_loader" else 0o600)
            stream.write(data)
    with (output / "file-lab.json").open("x") as stream:
        (output / "file-lab.json").chmod(0o600)
        json.dump(record, stream, indent=2)
    return check(output)


def check(root):
    root = private_path(root)
    record = json.loads(private_read(root / "file-lab.json", 1024 * 1024))
    if (
        record.get("status") != STATUS
        or record.get("cases") != CASES
        or record.get("ram_only") is not True
        or record.get("actual_settings") is not False
        or record.get("candidate_phase_trace") is not False
        or record["recipe_sha256"] != recipes()
        or set(record["files"]) != FILES
    ):
        raise ValueError("file lab recipe/scope changed")
    files = {n: private_read(root / "artifacts" / n, MAX_ROOT) for n in FILES}
    if any(sha(d) != record["files"][n] for n, d in files.items()):
        raise ValueError("file lab artifact changed")
    if (
        len(files["uImage"]) > MAX_IMAGE
        or len(files["x-load-gen2.bin"]) > 65536
        or len(files["u-boot.bin"]) > 1048576
    ):
        raise ValueError("file lab boot bounds exceeded")
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
        raise ValueError("file lab archive mismatch")
    entries = parse_cpio(rootfs)
    validate_entries(entries)
    storage.validate_review(entries, record["native_review"])
    if inventory(entries) != record["root_inventory"]:
        raise ValueError("file lab inventory changed")
    return {
        "status": "file-commissioning-ram-offline-integrity-passed",
        "device_executed": False,
        "cases": CASES,
        "persistent_storage": False,
        "native_application": False,
        "rootfs_bytes": len(rootfs),
        "image_bytes": len(files["uImage"]),
        "restoration": "unverified",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("package")
    for key in ("base", "helpers", "review", "output"):
        prepare.add_argument("--" + key, required=True)
    sub.add_parser("check").add_argument("root")
    args = vars(parser.parse_args())
    cmd = args.pop("command")
    print(json.dumps(package(**args) if cmd == "package" else check(args["root"]), indent=2))
