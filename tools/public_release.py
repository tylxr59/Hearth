"""Deterministic public integration/installer archives; no per-device material."""

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

from tools.package_native_ha import ROOT, package
from tools.sync_integration import sync


def archive(path, files):
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, data)


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
        archive(output / "hearth.zip", files)
    public = {}
    for folder in ("installer", "backend", "provisioning", "firmware", "tools"):
        for p in (ROOT / folder).rglob("*"):
            if (
                p.is_file()
                and not p.is_symlink()
                and "__pycache__" not in p.parts
                and (
                    p.suffix
                    in {
                        ".py",
                        ".c",
                        ".h",
                        ".S",
                        ".map",
                        ".json",
                        ".sh",
                        ".md",
                        ".patch",
                        ".txt",
                        ".config",
                        ".lds",
                    }
                    or p.name in {"Dockerfile", "LICENSE", "Makefile"}
                )
            ):
                public[p.relative_to(ROOT).as_posix()] = p.read_bytes()
    for name in (
        "LICENSE",
        "THIRD_PARTY.md",
        "pyproject.toml",
        "requirements.lock",
        "requirements-dev.lock",
        "requirements-build.lock",
        "docs/installation.md",
        "docs/recovery.md",
        "docs/development/firmware-kit.md",
    ):
        public[name] = (ROOT / name).read_bytes()
    archive(output / "hearth-installer-source.zip", public)
    (output / "SHA256SUMS").write_text(
        "".join(
            hashlib.sha256((output / name).read_bytes()).hexdigest() + "  " + name + "\n"
            for name in ("hearth.zip", "hearth-installer-source.zip")
        )
    )
    (output / "release.json").write_text(
        json.dumps(
            {
                "format": "hearth-public-release-v1",
                "version": version,
                "prerelease": True,
                "integration_archive": "hearth.zip",
                "installer_archive": "hearth-installer-source.zip",
                "per_device_firmware_included": False,
                "private_keys_included": False,
                "stock_device_kit_generation": "developer-prepared",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    release(parser.parse_args().output)
