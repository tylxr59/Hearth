"""Private RAM settings profile derived from the validated TLS kernel/library set.

No proprietary inputs execute on the host. No install, flash or filesystem mount
command exists. The diagnostic owns only a synthetic /state directory in RAM.
"""

import argparse
import gzip
import json
import stat
import zlib
from pathlib import Path

from firmware.probe.configure import initramfs
from firmware.settings_probe.abi import review as review_abi
from firmware.settings_probe.compile import source_hashes
from firmware.tls_probe.check import FILES, split_multi, zimage_payload
from firmware.tls_probe.check import check as check_base
from firmware.tls_probe.check import recipe_hashes as base_recipes
from firmware.tls_probe.configure import verify
from firmware.tls_probe.package import (
    INTERPRETER,
    MAX_IMAGE,
    MAX_ROOT,
    cpio,
    helper_interpreter,
    multi_image,
    private_read,
    sha,
)
from tools.elf_review import ArmElf, private_path

STATUS = "experimental-unexecuted-private-settings-probe"
DIRECTORIES = {".", "dev", "proc", "sys", "lib", "state"}
REQUIRED_LIBS = {
    "libnlappcore.so",
    "libnspr4.so",
    "libplc4.so",
    "libplds4.so",
    "libc.so.6",
    "libdl.so.2",
    "ld-linux-armhf.so.3",
}


def recipes():
    root = Path(__file__).resolve().parents[2]
    selected = {
        p.relative_to(root).as_posix(): sha(p.read_bytes())
        for p in Path(__file__).parent.iterdir()
        if p.is_file() and p.suffix in (".py", ".c", ".h", ".sh", ".json")
    }
    return base_recipes() | selected


def parse_cpio(data):
    if len(data) > MAX_ROOT:
        raise ValueError("RAM archive size limit")
    offset, result, seen = 0, [], set()
    while offset < len(data):
        if data[offset : offset + 6] != b"070701" or len(result) > 128:
            raise ValueError("invalid bounded newc header")
        fields = [int(data[offset + 6 + n * 8 : offset + 14 + n * 8], 16) for n in range(13)]
        name_begin = offset + 110
        name_end = name_begin + fields[11]
        if not 1 <= fields[11] <= 256 or name_end > len(data) or data[name_end - 1] != 0:
            raise ValueError("invalid newc name bounds")
        name = data[name_begin : name_end - 1].decode("ascii")
        begin = name_end + (-name_end % 4)
        end = begin + fields[6]
        if end > len(data) or name in seen or fields[3] != fields[2]:
            raise ValueError("invalid newc content or ownership")
        seen.add(name)
        result.append((name, fields[1], fields[2], data[begin:end], fields[9], fields[10]))
        offset = end + (-end % 4)
    if not result or result[-1][0] != "TRAILER!!!" or cpio(result) != data:
        raise ValueError("noncanonical RAM archive")
    return result


def inventory(entries):
    return [
        {"path": n, "mode": m, "uid": u, "bytes": len(d), "sha256": sha(d)}
        for n, m, u, d, _, _ in entries
    ]


def validate_entries(entries):
    found = {n for n, *_ in entries}
    allowed = DIRECTORIES | {"dev/console", "init", "settings-test", "TRAILER!!!"}
    libraries = set()
    for name, mode, uid, data, major, minor in entries:
        devices = (0, 0)
        expected_uid = 0
        if name == "state":
            expected_mode, expected_uid = stat.S_IFDIR | 0o700, 65534
        elif name in DIRECTORIES:
            expected_mode = stat.S_IFDIR | 0o755
        elif name == "dev/console":
            expected_mode, devices = stat.S_IFCHR | 0o600, (5, 1)
        elif name in ("init", "settings-test", INTERPRETER[1:]):
            expected_mode = stat.S_IFREG | 0o555
        elif name.startswith("lib/") and len(name.split("/")) == 2:
            expected_mode = stat.S_IFREG | 0o444
        elif name == "TRAILER!!!":
            expected_mode = 0
        else:
            raise ValueError("unexpected RAM path")
        if (mode, uid, major, minor) != (expected_mode, expected_uid, *devices):
            raise ValueError("unexpected RAM permissions/device")
        if name.startswith("lib/"):
            libraries.add(name[4:])
            ArmElf(data)
            if name == "lib/libnlappcore.so":
                review_abi(data)
            if name.endswith(".review.so"):
                raise ValueError("settings profile must contain only original libraries")
        elif name in DIRECTORIES or name in ("dev/console", "TRAILER!!!"):
            if data:
                raise ValueError("non-regular entry carries data")
        if name == "init":
            initramfs(data)  # static ARM program gate, no execution
        if name == "settings-test":
            helper_interpreter(data)
    if not allowed <= found or not REQUIRED_LIBS <= libraries or len(libraries) != 34:
        raise ValueError("incomplete reviewed diagnostic/library inventory")
    return len(libraries)


def package(base, helpers, output):
    base, output = private_path(base), private_path(output)
    if output.exists():
        raise ValueError("fresh private output required")
    check_base(base)
    base_manifest = private_read(base / "tls-probe.json")
    original = parse_cpio(private_read(base / "artifacts/rootfs.cpio", MAX_ROOT))
    entries = [
        (n, m, u, d, a, b)
        for n, m, u, d, a, b in original
        if n.startswith("lib/") and n != "lib/libnlwebservice.review.so"
    ]
    # This ABI inspection is additional to the recorded acquisition hashes.
    appcore = next(d for n, _, _, d, _, _ in entries if n == "lib/libnlappcore.so")
    abi = review_abi(appcore)
    helpers = Path(helpers)
    record = json.loads((helpers / "helpers.json").read_text())
    if record["source_sha256"] != source_hashes():
        raise ValueError("settings helper sources changed")
    compiled = {}
    for name in ("settings-init", "settings-test"):
        data = (helpers / name).read_bytes()
        ArmElf(data)
        if sha(data) != record["files"][name]:
            raise ValueError("compiled helper changed")
        compiled[name] = data
    entries = (
        [
            (
                n,
                stat.S_IFDIR | (0o700 if n == "state" else 0o755),
                65534 if n == "state" else 0,
                b"",
                0,
                0,
            )
            for n in sorted(DIRECTORIES)
        ]
        + [
            ("dev/console", stat.S_IFCHR | 0o600, 0, b"", 5, 1),
            ("init", stat.S_IFREG | 0o555, 0, compiled["settings-init"], 0, 0),
            ("settings-test", stat.S_IFREG | 0o555, 0, compiled["settings-test"], 0, 0),
        ]
        + entries
        + [("TRAILER!!!", 0, 0, b"", 0, 0)]
    )
    count = validate_entries(entries)
    rootfs = cpio(entries)
    if len(rootfs) > MAX_ROOT:
        raise ValueError("RAM filesystem limit")
    kernel, _ = split_multi(private_read(base / "artifacts/uImage", MAX_IMAGE))
    files = {
        n: private_read(base / "artifacts" / n, MAX_ROOT) for n in FILES - {"uImage", "rootfs.cpio"}
    }
    files |= {"uImage": multi_image(kernel, gzip.compress(rootfs, mtime=0)), "rootfs.cpio": rootfs}
    if len(files["uImage"]) > MAX_IMAGE:
        raise ValueError("RAM upload exceeds reviewed address window")
    manifest = {
        "status": STATUS,
        "device_executed": False,
        "whole_boot_chain_write_free": "unverified",
        "persistent_storage": False,
        "physical_network": False,
        "real_credentials": False,
        "files": {n: sha(d) for n, d in files.items()},
        "recipe_sha256": recipes(),
        "base_manifest_sha256": sha(base_manifest),
        "root_inventory": inventory(entries),
        "library_count": count,
        "cases": 12,
        "settings_abi": abi,
        "remaining_gates": ["target measurement", "native commissioning", "restoration", "HVAC"],
    }
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / "artifacts").mkdir(mode=0o700)
    for name, data in files.items():
        path = output / "artifacts" / name
        with path.open("xb") as stream:
            path.chmod(0o700 if name == "omap_loader" else 0o600)
            stream.write(data)
    path = output / "settings-probe.json"
    with path.open("x") as stream:
        path.chmod(0o600)
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    return check(output)


def check(root):
    root = private_path(root)
    manifest = json.loads(private_read(root / "settings-probe.json", 1024 * 1024))
    if (
        manifest.get("status") != STATUS
        or manifest["recipe_sha256"] != recipes()
        or set(manifest["files"]) != FILES
    ):
        raise ValueError("settings recipe/inventory differs")
    files = {n: private_read(root / "artifacts" / n, MAX_ROOT) for n in FILES}
    if any(sha(d) != manifest["files"][n] for n, d in files.items()):
        raise ValueError("settings artifact changed")
    if (
        len(files["uImage"]) > MAX_IMAGE
        or len(files["x-load-gen2.bin"]) > 65536
        or len(files["u-boot.bin"]) > 1048576
    ):
        raise ValueError("boot artifacts exceed reviewed bounds")
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
        raise ValueError("RAM filesystem mismatch/decompression limit")
    entries = parse_cpio(rootfs)
    count = validate_entries(entries)
    appcore = next(d for n, _, _, d, _, _ in entries if n == "lib/libnlappcore.so")
    if manifest["settings_abi"] != review_abi(appcore):
        raise ValueError("native ABI record differs")
    if inventory(entries) != manifest["root_inventory"] or count != manifest["library_count"]:
        raise ValueError("settings inventory mismatch")
    return {
        "status": "settings-probe-offline-integrity-passed",
        "device_executed": False,
        "hardware_safe": "unverified",
        "recovery": "unverified",
        "cases": 12,
        "library_count": count,
        "rootfs_bytes": len(rootfs),
        "image_bytes": len(files["uImage"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("package")
    for key in ("base", "helpers", "output"):
        prepare.add_argument("--" + key, required=True)
    sub.add_parser("check").add_argument("profile")
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(package(**args) if command == "package" else check(args["profile"]), indent=2))
