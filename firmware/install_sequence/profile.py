"""Offline composition of checked constituent profiles, with one fixed supervisor."""

import gzip
import json
import stat
from pathlib import Path

from firmware.file_writer import profile as core
from firmware.network_writer import profile as network
from firmware.probe.configure import initramfs
from firmware.settings_probe.artifact import parse_cpio
from firmware.tls_probe.compile import run
from firmware.tls_probe.package import MAX_IMAGE, MAX_ROOT, cpio, multi_image, private_read, sha
from tools.elf_review import private_path

ROOT = Path(__file__).resolve().parents[2]
FORMAT = "hearth-one-boot-install-v1"
FILES = {
    "uImage",
    "rootfs.cpio",
    "init",
    "omap_loader",
    "x-load-gen2.bin",
    "u-boot.bin",
    "kernel.config",
}


def recipes():
    return {
        p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
        for p in sorted(Path(__file__).parent.iterdir())
        if p.suffix in (".py", ".c")
    }


def constituents(kit):
    kit = private_path(kit)
    roots = [
        kit / name for name in ("sequence-capacity", "sequence-commissioning", "sequence-cleanup")
    ]
    network.check(roots[0])
    core.check(roots[1])
    network.check(roots[2])
    records = [
        json.loads(
            private_read(p / ("file-action-profile.json" if i == 1 else "profile.json"), 1048576)
        )
        for i, p in enumerate(roots)
    ]
    if (
        any(r.get("sequence_child") is not True or r["action"] != 1 for r in records)
        or records[0].get("preflight_only") is not True
        or records[2].get("preflight_only", False)
    ):
        raise ValueError("fixed child-action install profiles required")
    if (
        records[0].get("targets") != 3
        or records[2].get("targets") != 3
        or any(
            records[0].get(k) != records[2].get(k)
            for k in (
                "libraries",
                "plan",
                "receipt",
                "backup",
                "pin",
                "plan_path",
                "shared_archive",
            )
        )
    ):
        raise ValueError("same disjoint cleanup3 custody required")
    from installer.capacity import root_reserve

    if (
        records[0].get("capacity_reserve")
        != root_reserve(Path(records[1]["capsule"]), Path(records[1]["pin"]))
        or records[2]["libraries"] != records[1]["base"]
    ):
        raise ValueError("whole-install reservation and same-acquisition libraries required")
    from firmware.file_writer import run as core_run
    from firmware.network_writer import run as network_run

    # Restore images remain standalone, with no sequence terminal handshake.
    for engine, name, child in (
        (core_run, "commissioning", records[1]),
        (network_run, "cleanup", records[2]),
    ):
        restore = kit / (name + "-restore")
        if name == "commissioning":
            core.check(restore)
            row = json.loads(private_read(restore / "file-action-profile.json", 1048576))
            keys = ("capsule", "pin", "plan", "kernel", "base")
        else:
            network.check(restore)
            row = json.loads(private_read(restore / "profile.json", 65536))
            keys = (
                "plan_path",
                "backup",
                "pin",
                "plan",
                "receipt",
                "kernel",
                "shared_archive",
                "libraries",
            )
        if (
            row["action"] != 2
            or row.get("sequence_child", False)
            or any(row.get(k) != child.get(k) for k in keys)
        ):
            raise ValueError("matching standalone recovery images required")
    return roots, records


def check_scope(kit, records):
    row = json.loads(private_read(Path(kit) / "sequence-binding.json", 4096))
    if row != {
        "format": "hearth-install-sequence-binding-v1",
        "cleanup": records[2]["plan_path"],
        "backup": records[2]["backup"],
        "pin": records[2]["pin"],
    }:
        raise ValueError("combined kernel must bind the exact checked cleanup scope")


def archive(roots, init):
    initramfs(init)
    entries = [
        (n, stat.S_IFDIR | (0o755 if n == "lib" else 0o700), 0, b"", 0, 0)
        for n in ("proc", "sys", "dev", "lib", "originals")
    ]
    entries.append(("init", stat.S_IFREG | 0o500, 0, init, 0, 0))
    shared = {}
    for prefix, root in zip(("capacity", "commissioning", "cleanup"), roots, strict=True):
        entries.append((prefix, stat.S_IFDIR | 0o755, 0, b"", 0, 0))
        raw = private_read(root / "artifacts/rootfs.cpio", MAX_ROOT)
        for name, mode, uid, data, major, minor in parse_cpio(raw):
            if name in (".", "TRAILER!!!"):
                continue
            if name.startswith(("lib/", "originals/")):
                row = name, mode, uid, data, major, minor
                if name in shared and shared[name] != row:
                    raise ValueError(
                        "identical shared library/original bytes and metadata required"
                    )
                shared[name] = row
            else:
                entries.append((prefix + "/" + name, mode, uid, data, major, minor))
    entries.extend(shared.values())
    entries.append(("TRAILER!!!", 0, 0, b"", 0, 0))
    raw = cpio(entries)
    if len(raw) > MAX_ROOT:
        raise ValueError("combined archive exceeds existing RAM bound")
    return raw


def package(kit, kernel, build, output):
    kit, output = private_path(kit), private_path(output)
    roots, records = constituents(kit)
    check_scope(kit, records)
    _, provenance, blobs, payload = core.kernel_check(kernel)
    if (
        provenance.get("sequence") != str(kit / "sequence-binding.json")
        or provenance["capsule"] != records[1]["capsule"]
        or provenance["pin"] != records[1]["pin"]
    ):
        raise ValueError("exact three-slot combined kernel binding required")
    from firmware.install_sequence.binding import header

    expected = header(kit / "sequence-binding.json", records[1]["capsule"], records[1]["pin"])
    build = Path(build).absolute()
    if build.resolve() != build or not build.is_relative_to(ROOT / "build"):
        raise ValueError("literal build path required")
    build.mkdir(mode=0o700, exist_ok=False)
    (build / "sequence-binding.h").write_text(expected)
    run(
        [
            "clang",
            "--target=arm-linux-gnueabihf",
            "-marm",
            "-march=armv7-a",
            "-Os",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-ffreestanding",
            "-fno-builtin",
            "-fno-stack-protector",
            "-fomit-frame-pointer",
            "-fuse-ld=lld",
            "-nostdlib",
            "-static",
            "-Wl,-e,_start,--build-id=none,-z,noexecstack",
            "-I" + str(build),
            str(Path(__file__).with_name("init.c")),
            "-o",
            str(build / "init"),
        ]
    )
    init = core.read_build(build / "init", 65536)
    raw = archive(roots, init)
    files = {
        name: blobs[name]
        for name in ("omap_loader", "x-load-gen2.bin", "u-boot.bin", "kernel.config")
    }
    files |= {
        "init": init,
        "rootfs.cpio": raw,
        "uImage": multi_image(payload, gzip.compress(raw, mtime=0)),
    }
    if len(files["uImage"]) > MAX_IMAGE:
        raise ValueError("combined image exceeds existing USB load bound")
    output.mkdir(mode=0o700)
    (output / "artifacts").mkdir(mode=0o700)
    from firmware.file_writer.run import encode, save

    for name, data in files.items():
        save(output / "artifacts", name, data)
    (output / "artifacts/omap_loader").chmod(0o700)
    save(
        output,
        "profile.json",
        encode(
            {
                "format": FORMAT,
                "kit": str(kit),
                "kernel": str(Path(kernel).absolute()),
                "build": str(build),
                "recipes": recipes(),
                "files": {n: sha(d) for n, d in files.items()},
                "device_executed": False,
            }
        ),
    )
    return check(output)


def check(output):
    output = private_path(output)
    row = json.loads(private_read(output / "profile.json", 65536))
    if (
        row.get("format") != FORMAT
        or row.get("device_executed") is not False
        or row["recipes"] != recipes()
        or set(row["files"]) != FILES
    ):
        raise ValueError("fixed original one-boot profile required")
    roots, records = constituents(row["kit"])
    check_scope(row["kit"], records)
    _, provenance, blobs, payload = core.kernel_check(row["kernel"])
    if (
        provenance.get("sequence") != str(Path(row["kit"]) / "sequence-binding.json")
        or provenance["capsule"] != records[1]["capsule"]
        or provenance["pin"] != records[1]["pin"]
    ):
        raise ValueError("matching fixed sequence kernel required")
    files = {n: private_read(output / "artifacts" / n, MAX_ROOT) for n in FILES}
    if any(sha(d) != row["files"][n] for n, d in files.items()) or files["init"] != core.read_build(
        Path(row["build"]) / "init", 65536
    ):
        raise ValueError("combined profile artifact changed")
    raw = archive(roots, files["init"])
    if (
        raw != files["rootfs.cpio"]
        or files["uImage"] != multi_image(payload, gzip.compress(raw, mtime=0))
        or len(files["uImage"]) > MAX_IMAGE
        or any(
            files[n] != blobs[n]
            for n in ("kernel.config", "omap_loader", "x-load-gen2.bin", "u-boot.bin")
        )
    ):
        raise ValueError("combined RAM/kernel/bootstrap bounds or contents differ")
    return {"status": "one-boot-install-offline-checked", "device_executed": False, "targets": 12}
