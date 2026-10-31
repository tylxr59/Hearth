"""Assemble a PRIVATE volatile TLS test image; never install or flash it."""

import argparse
import gzip
import hashlib
import json
import re
import stat
import struct

# Only fixed readelf metadata inspection; native ELF code never runs on the host.
import subprocess  # nosec B404
import zlib
from pathlib import Path

from firmware.tls_probe.fixtures import CASES, EPOCH, TARGET_FILES
from tools.elf_review import ArmElf, private_path

MAX_ROOT = 24 * 1024 * 1024
# Source buffer 0x80a00000 must remain below the reviewed 0x81000000 boundary.
MAX_IMAGE = 6 * 1024 * 1024
INTERPRETER = "/lib/ld-linux-armhf.so.3"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def helper_interpreter(data):
    """Read the actual executable's PT_INTERP, not a guessed library role."""
    ArmElf(data)
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    paths = []
    for index in range(header[10]):
        kind, offset, _, _, size, _, _, _ = struct.unpack_from(
            "<8I", data, header[5] + index * header[9]
        )
        if kind != 3:
            continue
        if not 2 <= size <= 256 or offset + size > len(data):
            raise ValueError("invalid helper interpreter bounds")
        value = data[offset : offset + size]
        if value[-1:] != b"\0" or b"\0" in value[:-1]:
            raise ValueError("invalid helper interpreter string")
        paths.append(value[:-1].decode("ascii"))
    if paths != [INTERPRETER]:
        raise ValueError("exact native ARM dynamic interpreter required")
    return paths[0]


def private_read(path, maximum=8 * 1024 * 1024):
    path = private_path(path)
    if not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("bounded private regular input required")
    return path.read_bytes()


def dynamic(path):
    result = subprocess.run(  # nosec B607
        ["readelf", "-d", "--wide", str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        shell=False,  # nosec B603
    )
    needed = re.findall(r"\(NEEDED\).*?\[(.*?)\]", result.stdout)
    names = re.findall(r"\(SONAME\).*?\[(.*?)\]", result.stdout)
    if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.+-]{0,100}", n) for n in needed + names):
        raise ValueError("unsupported shared-library identifier")
    return needed, names


def libraries(root, extraction):
    root = private_path(root)
    expected = {row["path"]: row["sha256"] for row in extraction["files"]}
    catalog = {}
    for folder in ("lib", "usr/lib", "nestlabs/lib"):
        for path in private_path(root / folder).iterdir():
            path = private_path(path)
            if not path.is_file():
                continue
            with path.open("rb") as stream:
                if stream.read(4) != b"\x7fELF":
                    continue
            relative = path.relative_to(root).as_posix()
            data = private_read(path)
            ArmElf(data)
            if expected.get(relative) != sha(data):
                raise ValueError("recovered ELF differs from private acquisition record")
            needed, names = dynamic(path)
            for name in set([path.name] + names):
                catalog.setdefault(name, []).append((data, needed))
    queue = ["libnlwebservice.so", "libcurl.so.4", "libdl.so.2"]
    selected = {}
    while queue:
        name = queue.pop()
        if name in selected:
            continue
        options = catalog.get(name, [])
        if len(options) != 1:
            raise ValueError("unresolved or ambiguous native library: " + name)
        data, needed = options[0]
        selected[name] = data
        queue.extend(needed)
    if sum(map(len, selected.values())) > MAX_ROOT:
        raise ValueError("native dependency closure exceeds reviewed RAM budget")
    return selected


def cpio(entries):
    """Deterministic newc; no links, arbitrary paths, settings, apps or devices."""
    result = bytearray()
    for ino, (name, mode, uid, content, major, minor) in enumerate(entries, 1):
        if name not in (".", "TRAILER!!!") and (
            name.startswith("/") or any(p in ("", ".", "..") for p in name.split("/"))
        ):
            raise ValueError("unsafe RAM archive path")
        encoded = name.encode("ascii") + b"\0"
        fields = (ino, mode, uid, uid, 1, 0, len(content), 0, 0, major, minor, len(encoded), 0)
        result += b"070701" + "".join(f"{n:08x}" for n in fields).encode()
        result += encoded
        result += b"\0" * (-len(result) % 4)
        result += content
        result += b"\0" * (-len(result) % 4)
    return bytes(result)


def unpack_image(data, kind):
    if not 64 <= len(data) <= MAX_IMAGE:
        raise ValueError("bounded uImage required")
    header = struct.unpack_from(">7I4B32s", data)
    if (
        header[0] != 0x27051956
        or zlib.crc32(data[:4] + b"\0" * 4 + data[8:64]) != header[1]
        or header[3] != len(data) - 64
        or zlib.crc32(data[64:]) != header[6]
        or header[4:6] != (0x80008000, 0x80008000)
        or header[7:11] != (5, 2, kind, 0)
    ):
        raise ValueError("unexpected ARM Linux uImage header or CRC")
    return data[64:]


def multi_image(kernel, root):
    payload = struct.pack(">III", len(kernel), len(root), 0)
    payload += kernel + b"\0" * (-len(kernel) % 4) + root
    header = struct.pack(
        ">7I4B32s",
        0x27051956,
        0,
        1793318400,
        len(payload),
        0x80008000,
        0x80008000,
        zlib.crc32(payload),
        5,
        2,
        4,
        0,
        b"Hearth volatile TLS test",
    )
    data = header[:4] + struct.pack(">I", zlib.crc32(header)) + header[8:] + payload
    unpack_image(data, 4)
    return data


def package(
    kernel_build,
    helpers,
    recovered,
    extraction_report,
    candidate,
    candidate_record,
    fixtures,
    output,
):
    from firmware.tls_probe.check import check_kernel, recipe_hashes

    output = private_path(output)
    if output.exists():
        raise ValueError("fresh private TLS profile required")
    kernel_build, helpers = Path(kernel_build), Path(helpers)
    check_kernel(kernel_build)
    extraction = json.loads(private_read(extraction_report, 16 * 1024 * 1024))
    selected = libraries(recovered, extraction)
    original = selected["libnlwebservice.so"]
    changed = private_read(candidate)
    review = json.loads(private_read(candidate_record))
    offset = review["file_offset"]
    if (
        review["source_sha256"] != sha(original)
        or review["review_sha256"] != sha(changed)
        or review["words_replaced"] != 1
        or type(offset) is not int
        or offset < 0
        or offset + 4 > len(original)
        or len(original) != len(changed)
        or original[:offset] != changed[:offset]
        or original[offset + 4 :] != changed[offset + 4 :]
        or original[offset : offset + 4] == changed[offset : offset + 4]
    ):
        raise ValueError("candidate does not match the separate private one-word review")
    selected["libnlwebservice.review.so"] = changed
    helper_record = json.loads((helpers / "helpers.json").read_text())
    if helper_record["source_sha256"] != {
        name: sha((Path(__file__).parent / name).read_bytes())
        for name in ("init.c", "client.c", "abi.h", "start.S")
    }:
        raise ValueError("compiled helper sources are stale")
    helper_data = {}
    for name in ("tls-init", "tls-test"):
        data = (helpers / name).read_bytes()
        ArmElf(data)
        if helper_record["files"][name] != sha(data):
            raise ValueError("original helper digest mismatch")
        helper_data[name] = data
    interpreter = helper_interpreter(helper_data["tls-test"])
    if interpreter.removeprefix("/lib/") not in selected:
        raise ValueError("helper interpreter missing from recovered libraries")
    entries = [
        (d, stat.S_IFDIR | 0o755, 0, b"", 0, 0)
        for d in (".", "dev", "proc", "sys", "lib", "fixtures")
    ]
    entries += [
        ("dev/console", stat.S_IFCHR | 0o600, 0, b"", 5, 1),
        ("init", stat.S_IFREG | 0o555, 0, helper_data["tls-init"], 0, 0),
        ("tls-test", stat.S_IFREG | 0o555, 0, helper_data["tls-test"], 0, 0),
    ]
    entries += [
        (
            "lib/" + name,
            stat.S_IFREG | (0o555 if "/lib/" + name == interpreter else 0o444),
            0,
            data,
            0,
            0,
        )
        for name, data in sorted(selected.items())
    ]
    fixture_record = json.loads(private_read(Path(fixtures) / "fixtures.json"))
    if (
        fixture_record["status"] != "synthetic-fixtures-host-verified"
        or fixture_record["epoch"] != EPOCH
        or fixture_record["cases"] != list(CASES)
        or set(fixture_record["target_sha256"]) != TARGET_FILES
    ):
        raise ValueError("host-verified synthetic fixture inventory required")
    for name in sorted(TARGET_FILES):
        data = private_read(Path(fixtures) / name, 65536)
        if sha(data) != fixture_record["target_sha256"][name]:
            raise ValueError("synthetic fixture changed after host verification")
        entries.append(
            (
                "fixtures/" + name,
                stat.S_IFREG | (0o400 if name == "server.key" else 0o444),
                65534 if name == "server.key" else 0,
                data,
                0,
                0,
            )
        )
    entries.append(("TRAILER!!!", 0, 0, b"", 0, 0))
    root = cpio(entries)
    if len(root) > MAX_ROOT:
        raise ValueError("RAM filesystem exceeds bounded budget")
    kernel = unpack_image((kernel_build / "artifacts/kernel.uImage").read_bytes(), 2)
    image = multi_image(kernel, gzip.compress(root, mtime=0))
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / "artifacts").mkdir(mode=0o700)
    files = {
        "uImage": image,
        "rootfs.cpio": root,
        "kernel.config": (kernel_build / "artifacts/kernel.config").read_bytes(),
        "fallback-init": (kernel_build / "artifacts/fallback-init").read_bytes(),
    }
    source_record = json.loads((kernel_build / "tls-kernel-sources.json").read_text())
    for name in ("x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        data = (kernel_build / "artifacts" / name).read_bytes()
        if source_record["bootstrap_sha256"][name] != sha(data):
            raise ValueError("bootstrap artifact changed")
        files[name] = data
    for name, data in files.items():
        path = output / "artifacts" / name
        with path.open("xb") as stream:
            path.chmod(0o700 if name == "omap_loader" else 0o600)
            stream.write(data)
    manifest = {
        "status": "experimental-unexecuted-private-tls-probe",
        "device_executed": False,
        "kernel_flash_support": False,
        "whole_boot_chain_write_free": "unverified",
        "physical_network": False,
        "synthetic_fixture_epoch": 1893456000,
        "files": {name: sha(data) for name, data in files.items()},
        "recipe_sha256": recipe_hashes(),
        "root_inventory": [
            {"path": n, "mode": m, "uid": u, "bytes": len(d), "sha256": sha(d)}
            for n, m, u, d, _, _ in entries
        ],
        "library_count": len(selected),
        "rootfs_bytes": len(root),
        "kernel_source_sha256": source_record["kernel_source_archive_sha256"],
        "candidate_review_sha256": sha(private_read(candidate_record)),
        "remaining_gates": [
            "first target execution",
            "full native fetch path",
            "restoration",
            "HVAC",
        ],
    }
    with (output / "tls-probe.json").open("x") as stream:
        (output / "tls-probe.json").chmod(0o600)
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in (
        "kernel-build",
        "helpers",
        "recovered",
        "extraction-report",
        "candidate",
        "candidate-record",
        "fixtures",
        "output",
    ):
        parser.add_argument("--" + name, required=True)
    package(**vars(parser.parse_args()))
