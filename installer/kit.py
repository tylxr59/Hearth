"""Build and revalidate private, disjoint install/restore images; no device I/O."""

import hashlib
import json

from firmware.acquisition.custody import read
from firmware.file_writer import compile as core_compile
from firmware.file_writer import prepare as core_kernel
from firmware.file_writer import profile as core_profile
from firmware.file_writer import run as core_run
from firmware.file_writer.run import encode, save
from firmware.network_writer import kernel as cleanup_kernel
from firmware.network_writer import profile as cleanup_profile
from firmware.network_writer import run as cleanup_run
from installer import build as reader_build
from installer import replacements, sources
from provisioning.time_server import DEFAULT, time_server
from tools.elf_review import private_path

FORMAT = "hearth-private-stock-kit-v1"


def check(output, *, for_restore=False):
    output = private_path(output)
    record = json.loads(read(output / "kit.json", 65536))
    if set(record) != {
        "format",
        "session",
        "bundle_sha256",
        "commissioning_plan",
        "cleanup_plan",
        "restore_order",
        "review_only",
    }:
        raise ValueError("fixed stock-kit manifest required")
    if (
        record["format"] != FORMAT
        or record["restore_order"] != ["cleanup", "commissioning"]
        or type(record["review_only"]) is not bool
    ):
        raise ValueError("fixed disjoint install/restore order required")
    session = private_path(record["session"])
    replacements.inputs(session, for_restore=for_restore)
    if (
        hashlib.sha256(read(session / "commissioning.zip", 65536)).hexdigest()
        != record["bundle_sha256"]
    ):
        raise ValueError("commissioning bundle changed since kit preparation")
    core, core_binding = core_run.checked_pair(
        output / "commissioning-install", output / "commissioning-restore"
    )
    cleanup, cleanup_binding = cleanup_run.checked_pair(
        output / "cleanup-install", output / "cleanup-restore"
    )
    if (
        core_binding.action != 1
        or cleanup_binding.action != 1
        or core_binding.plan.hex() != record["commissioning_plan"]
        or cleanup_binding.plan.hex() != record["cleanup_plan"]
        or core["capsule"] != str(output / "replacements/commissioning")
        or core["base"] != str(session / "acquisition")
        or cleanup["plan_path"] != str(output / "replacements/cleanup")
        or cleanup["backup"] != str(session / "acquisition/network-backup")
        or cleanup["libraries"] != str(session / "acquisition")
        or cleanup.get("targets", 4) != 3
    ):
        raise ValueError("kit phases must match this intake, custody and disjoint scopes")
    if not for_restore or (output / "capacity-preflight").exists():
        from installer.capacity import root_reserve

        capacity, capacity_binding = cleanup_run.checked_pair(
            output / "capacity-preflight", output / "cleanup-restore"
        )
        if (
            capacity_binding.action != 1
            or capacity.get("preflight_only") is not True
            or capacity.get("capacity_reserve")
            != root_reserve(
                output / "replacements/commissioning",
                output / "replacements/commissioning-pin.json",
            )
            or any(
                capacity.get(k) != cleanup.get(k)
                for k in ("plan_path", "backup", "libraries", "plan", "receipt", "shared_archive")
            )
        ):
            raise ValueError("combined pre-write capacity check must match both kit phases")
    replacements.check(output / "replacements", session, for_restore=for_restore)
    return {
        "status": "private-stock-install-restore-kit-checked",
        "commissioning_targets": 9,
        "cleanup_targets": 3,
        "restore_order": ["cleanup", "commissioning"],
        "device_executed": False,
        "whole_firmware_recovery": "unverified",
        "review_only": record["review_only"],
        "installation_checked": not for_restore and not record["review_only"],
    }


def build(
    session, cache, reader, build, output, *, probe_port=8123, review_only=False, ntp_server=DEFAULT
):
    ntp_server = time_server(ntp_server)
    if type(review_only) is not bool:
        raise ValueError("explicit build purpose required")
    session, output = private_path(session), private_path(output)
    replacements.inputs(session)
    reader_build.require_engine()
    sources.verify(cache)
    cache, reader, build = map(sources.build_path, (cache, reader, build))
    if build.exists() or output.exists() or output.parent.stat().st_mode & 0o077:
        raise ValueError("fresh build and private kit output required")
    # Require the verified public-source reader's two underlying kernel builds.
    reader_build.acquisition.base_check(reader / "protected")
    reader_build.probe_check.check(reader / "probe")
    build.mkdir(mode=0o700, parents=True)
    output.mkdir(mode=0o700)
    save(
        output,
        "build-started.json",
        encode({"device_executed": False, "persistent_actions": False}),
    )
    replacements.prepare(
        session,
        build / "storage-shim",
        output / "replacements",
        probe_port=probe_port,
        ntp_server=ntp_server,
    )
    capsule, pin = (
        output / "replacements/commissioning",
        output / "replacements/commissioning-pin.json",
    )
    cleanup, cleanup_pin = output / "replacements/cleanup", output / "replacements/cleanup-pin.json"
    backup = session / "acquisition/network-backup"
    libraries = session / "acquisition"
    log = build / "build.log"
    core = build / "commissioning-kernel"
    core_kernel.prepare(
        cache / "nestdfu", cache / "xloader", cache / "loader", reader / "probe", core, capsule, pin
    )
    reader_build.command(reader_build.container("podman", reader_build.IMAGE, core), log)
    core_kernel.finalize(core, reader / "probe")
    helpers = build / "commissioning-helpers"
    core_compile.compile_helpers(helpers, capsule, pin)
    for action, name in ((1, "install"), (2, "restore")):
        core_profile.package(
            core, libraries, helpers, capsule, pin, output / ("commissioning-" + name), action
        )
    network = build / "cleanup-kernel"
    cleanup_kernel.stage(
        reader / "probe", reader / "protected", cleanup, backup, cleanup_pin, network
    )
    reader_build.command(reader_build.container("podman", reader_build.IMAGE, network), log)
    cleanup_kernel.finalize(network)
    from installer.archive_discovery import discover
    from installer.capacity import root_reserve

    candidate = discover(session)
    shared_archive = None
    if candidate is not None:
        shared_archive = output / "shared-originals.json"
        save(output, shared_archive.name, candidate)
    for action, name in ((1, "install"), (2, "restore")):
        cleanup_profile.package(
            network,
            libraries,
            cleanup,
            backup,
            cleanup_pin,
            build / ("cleanup-helpers-" + name),
            output / ("cleanup-" + name),
            action=action,
            shared_archive=shared_archive,
        )
    cleanup_profile.package(
        network,
        libraries,
        cleanup,
        backup,
        cleanup_pin,
        build / "capacity-helpers",
        output / "capacity-preflight",
        action=1,
        preflight_only=True,
        shared_archive=shared_archive,
        capacity_reserve=root_reserve(capsule, pin),
    )
    core_record = json.loads(read(pin, 4096))
    cleanup_record = json.loads(read(cleanup_pin, 4096))
    save(
        output,
        "kit.json",
        encode(
            {
                "format": FORMAT,
                "session": str(session),
                "bundle_sha256": hashlib.sha256(
                    read(session / "commissioning.zip", 65536)
                ).hexdigest(),
                "commissioning_plan": core_record["plan"],
                "cleanup_plan": cleanup_record["plan"],
                "restore_order": ["cleanup", "commissioning"],
                "review_only": review_only,
            }
        ),
    )
    return check(output)
