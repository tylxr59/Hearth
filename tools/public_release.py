"""Deterministic public release assets; no per-device material.

Assets published on each ``v0.x.y`` GitHub release:

- ``hearth.zip``: the Home Assistant integration. HACS downloads it by this
  exact name (see ``hacs.json``); users never need to download it by hand.
- ``hearth-nest-installer.zip``: the USB setup wizard for the thermostat,
  inside a ``hearth-nest-installer-<version>/`` folder. Its contents are
  computed by ``tools.installer_archive``.
- ``SHA256SUMS``: checksums for both.

``release.json`` and ``RELEASE-NOTES.md`` are build metadata and the release
body; they are not uploaded as assets.
"""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from tools.installer_archive import files as installer_files
from tools.installer_archive import write
from tools.package_native_ha import ROOT, package
from tools.sync_integration import sync

INTEGRATION = "hearth.zip"
INSTALLER = "hearth-nest-installer.zip"
ASSETS = (INTEGRATION, INSTALLER, "SHA256SUMS")

NOTES = """> [!WARNING]
> **Experimental preview.** Supports only the Nest Learning Thermostat 2nd gen,
> Display-2.6, software 5.9.4-5. The complete stock-device install and restore
> has not been verified on hardware yet. See the [install guide]({docs}installation.md).

### Which file do I need?

| File | What it is | Do I download it? |
| --- | --- | --- |
| `{installer}` | The USB setup wizard for your thermostat (Linux) | **Yes**, to set up a Nest: extract it and run `python3 provision.py` |
| `{integration}` | The Home Assistant integration | **No**, HACS installs it for you |
| `SHA256SUMS` | Checksums for both files | Optional, to verify downloads |

Neither file contains Nest firmware, keys or anyone's backups.
"""


def release(output):
    sync(check=True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    version = json.loads((ROOT / "custom_components/hearth/manifest.json").read_text())["version"]
    if not version.startswith("0."):
        raise ValueError(
            "stable release requires closing the public installer and hardware release gates"
        )
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "integration"
        integration = package(root)
        files = {
            p.relative_to(integration).as_posix(): p.read_bytes()
            for p in integration.rglob("*")
            if p.is_file()
        }
        write(output / INTEGRATION, files)
    write(output / INSTALLER, installer_files(ROOT), f"hearth-nest-installer-{version}/")
    (output / "SHA256SUMS").write_text(
        "".join(
            hashlib.sha256((output / name).read_bytes()).hexdigest() + "  " + name + "\n"
            for name in (INTEGRATION, INSTALLER)
        )
    )
    (output / "RELEASE-NOTES.md").write_text(
        NOTES.format(
            installer=INSTALLER,
            integration=INTEGRATION,
            docs="https://github.com/tylxr59/Hearth/blob/main/docs/",
        )
    )
    (output / "release.json").write_text(
        json.dumps(
            {
                "format": "hearth-public-release-v2",
                "version": version,
                "prerelease": False,
                "experimental": True,
                "assets": list(ASSETS),
                "integration_archive": INTEGRATION,
                "installer_archive": INSTALLER,
                "installer_folder": f"hearth-nest-installer-{version}/",
                "per_device_firmware_included": False,
                "private_keys_included": False,
                "stock_device_kit_generation": "experimental-source-builder",
                "stock_install_restore_hardware_verified": False,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    release(parser.parse_args().output)
