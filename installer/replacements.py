"""Prepare private stock-unit replacement DATA and disjoint custody-bound plans.

No USB, target execution, installer image or persistent action exists here.
Already commissioned units require their existing upgrade/recovery workflow.
"""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from firmware.acquisition.custody import read, verify
from firmware.file_snapshot.run import MAX_PAYLOAD
from firmware.file_writer.profile import read_build
from firmware.file_writer.run import encode, save
from firmware.harden import client_config
from firmware.settings_compat.compile import compile_library, source_hashes
from installer.build import IMAGE
from installer.bundle import read_bundle
from installer.sources import build_path
from provisioning import file_backup, file_capsule, network_backup, network_plan
from provisioning.native_network import connectivity_url
from provisioning.native_settings import assigned_credentials, nist_time_config
from provisioning.native_startup import LAUNCHER, native_startup
from provisioning.native_tls import strict_tls
from provisioning.time_server import DEFAULT, time_server
from tools.elf_review import private_path


def inputs(session, *, for_restore=False):
    session = private_path(session)
    raw = read(session / "commissioning.zip", 65536)
    bundle, ca, crl = read_bundle(raw, for_restore=True) if for_restore else read_bundle(raw)
    identity = json.loads(read(session / "identity.json", 65536))
    if identity != {
        "serial": bundle["serial"],
        "model": "Display-2.6",
        "software": "5.9.4-5",
        "partition": "primary",
    }:
        raise ValueError("matching supported intake identity required")
    acquired = session / "acquisition"
    decoder, _ = verify(acquired)
    binding = json.loads(read(acquired / "intake-binding.json", 65536))
    if binding != {
        "format": "hearth-acquisition-session-v1",
        "identity": identity,
        "bundle_sha256": hashlib.sha256(raw).hexdigest(),
        "session": decoder.session.hex(),
    }:
        raise ValueError("acquisition must match this intake and commissioning bundle")
    if decoder.snapshot[4].existed or decoder.snapshot[5].existed:
        raise ValueError("existing Hearth installation requires its upgrade/recovery path")
    return decoder, bundle, ca, crl


def recipes():
    root = Path(__file__).resolve().parents[1]
    names = (
        "installer/replacements.py",
        "provisioning/native_tls.py",
        "provisioning/native_settings.py",
        "provisioning/native_startup.py",
        "firmware/harden.py",
        "provisioning/network_plan.py",
        "provisioning/native_network.py",
        "provisioning/time_server.py",
    )
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def check(output, session, *, for_restore=False):
    output, session = private_path(output), private_path(session)
    decoder, bundle, ca, crl = inputs(session, for_restore=for_restore)
    source = json.loads(read(output / "source-review.json", 16384))
    if (
        set(source) != {"recipes", "storage_sources", "shim_sha256"}
        or source["recipes"] != recipes()
        or source["storage_sources"] != source_hashes()
    ):
        raise ValueError("replacement source recipe changed; use its pinned source version")
    shim = read(output / "commissioning/4.replacement", 1024 * 1024)
    if hashlib.sha256(shim).hexdigest() != source["shim_sha256"]:
        raise ValueError("prepared storage shim changed")
    if read(output / "commissioning/capture.bin", MAX_PAYLOAD + 56) != read(
        session / "acquisition/capture.bin", MAX_PAYLOAD + 56
    ):
        raise ValueError("commissioning originals differ from this acquisition")
    manifest = json.loads(read(output / "commissioning/plan.json", 32768))
    selection = json.loads(read(output / "time-server.json", 1024))
    if set(selection) != {"server"} or selection["server"] != time_server(selection["server"]):
        raise ValueError("canonical time server selection required")
    network = json.loads(read(output / "cleanup/plan.json", 16384))
    if network.get("ntp_server", DEFAULT) != selection["server"]:
        raise ValueError("primary and fallback time servers must match")
    for row in candidates(decoder.snapshot, bundle, ca, crl, shim, selection["server"]):
        if (
            manifest["files"][row.target]["replacement_mode"] != row.mode
            or read(output / f"commissioning/{row.target}.replacement", 1024 * 1024) != row.data
        ):
            raise ValueError("prepared replacement differs from the verified bundle/stock recipe")
    return True


def candidates(records, bundle, ca, crl, shim, ntp_server=DEFAULT):
    data = (
        strict_tls(records[0].data, model="Display-2.6", software_version="5.9.4-5"),
        ca,
        crl,
        nist_time_config(records[3].data, ntp_server),
        shim,
        LAUNCHER,
        native_startup(records[6].data),
        assigned_credentials(records[7].data, bundle["serial"], bundle["credential"]),
        client_config(records[8].data.decode("utf-8"), bundle["origin"]).encode("utf-8"),
    )
    modes = {1: 0o644, 2: 0o644, 4: 0o444, 5: 0o750, 7: 0o600, 8: 0o600}
    return tuple(
        file_capsule.Replacement(i, modes.get(i, records[i].mode), value)
        for i, value in enumerate(data)
    )


def prepare(session, build, output, *, probe_port=8123, ntp_server=DEFAULT):
    ntp_server = time_server(ntp_server)
    session = private_path(session)
    decoder, bundle, ca, crl = inputs(session)
    connectivity_url(urlsplit(bundle["origin"]).hostname, probe_port)
    build, output = build_path(build), private_path(output)
    if build.exists() or output.exists() or output.parent.stat().st_mode & 0o077:
        raise ValueError("fresh build and owner-only replacement output required")
    if set(file_backup.TARGETS) & set(network_backup.TARGETS[:3]):
        raise ValueError("commissioning and cleanup targets must be disjoint")
    build.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    save(
        output,
        "preparation-started.json",
        encode({"device_executed": False, "flash_writes": False}),
    )
    compile_library(build, legacy_linker=True, builder_image=IMAGE)
    replacements = candidates(
        decoder.snapshot,
        bundle,
        ca,
        crl,
        read_build(build / "libhearth-settings-compat.so", 1024 * 1024),
        ntp_server,
    )
    save(
        output,
        "source-review.json",
        encode(
            {
                "recipes": recipes(),
                "storage_sources": source_hashes(),
                "shim_sha256": hashlib.sha256(replacements[4].data).hexdigest(),
            }
        ),
    )
    core = file_capsule.prepare(
        session / "acquisition",
        replacements,
        output / "commissioning",
        session=decoder.session,
        native_partition="primary",
        software_version="5.9.4-5",
        archive_layout=1,
    )
    save(
        output,
        "commissioning-pin.json",
        encode({"format": "hearth-local-file-plan-pin-v1", "plan": core.hex()}),
    )
    network_plan.prepare(
        output / "cleanup",
        decoder.network,
        session / "acquisition/network-backup",
        None,
        bundle["origin"],
        probe_port=probe_port,
        target_count=3,
        ntp_server=ntp_server,
    )
    manifest = read(output / "cleanup/plan.json", 16384)
    cleanup = hashlib.sha256((json.loads(manifest)["format"] + "\n").encode() + manifest).digest()
    save(output, "time-server.json", encode({"server": ntp_server}))
    network_plan.check(output / "cleanup", session / "acquisition/network-backup", cleanup)
    save(
        output,
        "cleanup-pin.json",
        encode({"format": "hearth-network-reviewed-pin-v1", "plan": cleanup.hex()}),
    )
    save(
        output,
        "replacements.json",
        encode(
            {
                "format": "hearth-stock-replacements-v1",
                "session": str(session),
                "commissioning_plan": core.hex(),
                "cleanup_plan": cleanup.hex(),
                "commissioning_targets": 9,
                "cleanup_targets": 3,
                "disjoint": True,
                "probe_port": probe_port,
                "device_executed": False,
                "write_profiles_ready": False,
            }
        ),
    )
    return {
        "status": "private-stock-replacements-prepared",
        "commissioning_targets": 9,
        "cleanup_targets": 3,
        "disjoint": True,
        "write_profiles_ready": False,
        "device_executed": False,
        "flash_writes": False,
    }
