"""Explicit continuation of one failed host prepare; never rerun a device attempt."""

import hashlib
import json

from firmware.acquisition import profile as acquisition
from firmware.file_writer.run import encode, save
from firmware.nand_capture import profile as nand
from firmware.tls_probe.package import private_read
from installer.bundle import device_info, read_bundle
from installer.sources import ROOT
from provisioning.time_server import time_server
from tools.elf_review import private_path
from tools.nand_archive.build import checked_library
from tools.public_release import installer_archive


def load(folder, info):
    folder = private_path(folder)
    stopped = json.loads(private_read(folder / "wizard-stopped.json", 65536))
    request = json.loads(private_read(folder / "prepare-request.json", 16384))
    build = ROOT / "build" / folder.name
    if (
        stopped.get("phase") != "prepare"
        or request != {"operation": "prepare", "session": str(folder), "build": str(build)}
        or build.resolve() != build
    ):
        raise ValueError("Only a matching failed host prepare may be continued.")
    for path in (
        folder / "prepared-continuation-started.json",
        folder / "prepare-worker-result.json",
        folder / "nand-request.json",
        folder / "nand-reader-executed.json",
        folder / "nand",
        folder / "acquire-request.json",
        folder / "acquisition",
        folder / "kit",
        folder / "installer-source.zip",
        folder / "reader/execution-started.json",
        build / "nand-reader/execution-started.json",
    ):
        if path.exists() or path.is_symlink():
            raise ValueError(
                "Fresh pre-device preparation required; no attempted operation may resume."
            )
    bundle, _, _ = read_bundle(private_read(folder / "commissioning.zip", 65536))
    identity = device_info(info, bundle)
    if identity != json.loads(private_read(folder / "identity.json", 65536)):
        raise ValueError("Connected thermostat differs from the prepared session.")
    ntp = time_server(
        json.loads(private_read(folder / "wizard-settings.json", 65536))["ntp_server"]
    )
    acquisition.check(folder / "reader")
    nand.check(build / "nand-reader")
    checked_library(build / "nand-bch/compiled/libbch.so")
    # A fresh receipt and output preserve the original failed request/log.
    save(folder, "prepared-continuation-started.json", encode({"host_prepare_only": True}))
    output = build / "continued-recovery-source"
    output.mkdir(mode=0o700)
    installer_archive(output / "hearth-installer-source.zip")
    source = (output / "hearth-installer-source.zip").read_bytes()
    save(folder, "installer-source.zip", source)
    save(
        folder,
        "prepared-continuation-checked.json",
        encode({"source_sha256": hashlib.sha256(source).hexdigest(), "device_executed": False}),
    )
    return folder, build, ntp
