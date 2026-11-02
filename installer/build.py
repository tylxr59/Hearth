"""Offline public-source reader build. Does not mount USB or owner material."""

import hashlib
import json
import os
import shlex
import shutil
import subprocess  # nosec B404

from firmware.acquisition import profile as acquisition
from firmware.file_snapshot import prepare as snapshot
from firmware.probe import check as probe_check
from firmware.probe import stage as probe_stage
from installer import sources

IMAGE = "localhost/hearth-installer-builder:public-v1"


def command(args, log, timeout=1200):
    with log.open("ab") as stream:
        subprocess.run(args, check=True, stdout=stream, stderr=stream, timeout=timeout)  # nosec B603


def container(engine, image, work):
    return [
        engine,
        "run",
        "--rm",
        "--network=none",
        "--cap-drop=all",
        "--security-opt=no-new-privileges",
        "--pids-limit=256",
        "--memory=4g",
        "--cpus=4",
        "-v",
        str(work) + ":/work:Z",
        image,
    ]


def loader(work, log):
    flags = subprocess.run(  # nosec B603 B607
        ["pkg-config", "--cflags", "--libs", "libusb-1.0"],
        check=True,
        capture_output=True,
        timeout=10,
        text=True,
    ).stdout
    usb = shlex.split(flags)
    out = work / "artifacts/omap_loader"
    command(
        [
            "cc",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-D_FORTIFY_SOURCE=3",
            "-fstack-protector-strong",
            "-Wl,-z,relro,-z,now",
            str(work / "loader/omap_loader.c"),
            *usb,
            "-o",
            str(out),
        ],
        log,
        60,
    )
    # Original public host-only fixture wraps every physical USB entry it uses.
    test = work / "loader/sanitizer-tests"
    command(
        [
            "cc",
            "-O1",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-I" + str(work / "loader"),
            str(sources.ROOT / "firmware/probe/test_loader.c"),
            "-Wl,--wrap=libusb_init",
            "-Wl,--wrap=libusb_bulk_transfer",
            "-Wl,--wrap=libusb_get_bus_number",
            "-Wl,--wrap=libusb_get_port_numbers",
            "-Wl,--wrap=usleep",
            *usb,
            "-o",
            str(test),
        ],
        log,
        60,
    )
    with log.open("ab") as stream:
        subprocess.run(  # nosec B603
            [str(test)],
            check=True,
            stdout=stream,
            stderr=stream,
            timeout=30,
            env=os.environ | {"ASAN_OPTIONS": "detect_leaks=0"},
        )


def build(cache, output, profile, *, engine="podman"):
    if engine not in ("podman", "docker") or shutil.which(engine) is None:
        raise ValueError("installed Podman or Docker required")
    if engine == "podman":
        info = json.loads(
            subprocess.run(  # nosec B603 B607
                [engine, "info", "--format=json"],
                check=True,
                capture_output=True,
                timeout=15,
            ).stdout
        )
        if info.get("host", {}).get("security", {}).get("rootless") is not True:
            raise ValueError("rootless Podman required")
    else:
        raise ValueError("public firmware builder currently requires rootless Podman")
    sources.verify(cache)
    cache, output = sources.build_path(cache), sources.build_path(output)
    # Check the private destination before spending time on a build.
    profile = acquisition.private_path(profile)
    if profile.exists() or profile.parent.stat().st_mode & 0o077:
        raise ValueError("fresh owner-only acquisition profile required")
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.mkdir(mode=0o700, exist_ok=False)
    context = output / "context"
    context.mkdir(mode=0o700)
    shutil.copyfile(sources.ROOT / "firmware/probe/Dockerfile", context / "Dockerfile")
    shutil.copyfile(cache / "toolchain.tar.bz2", context / "toolchain.tar.bz2")
    log = output / "build.log"
    command([engine, "build", "-t", IMAGE, str(context)], log)
    base = output / "probe"
    probe_stage.stage(cache / "nestdfu", cache / "xloader", cache / "loader", base)
    command(container(engine, IMAGE, base), log)
    loader(base, log)
    manifest = {
        "status": "experimental-unexecuted-ram-probe",
        "device_executed": False,
        "files": {
            n: hashlib.sha256((base / "artifacts" / n).read_bytes()).hexdigest()
            for n in probe_check.FILES
        },
        "host_files": {
            n: hashlib.sha256((base / n).read_bytes()).hexdigest() for n in probe_check.HOST_FILES
        },
    }
    (base / "probe-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    probe_check.check(base)
    protected = output / "protected"
    snapshot.prepare(cache / "nestdfu", cache / "xloader", cache / "loader", base, protected)
    command(container(engine, IMAGE, protected), log)
    snapshot.finalize(protected, base)
    result = acquisition.package(protected, output / "acquisition", profile)
    (output / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result
