import json
import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

from firmware.acquisition.profile import recipes as acquisition_recipes
from firmware.file_writer.profile import recipes as commissioning_recipes
from firmware.network_writer.profile import recipes as cleanup_recipes
from tools.public_release import release
from tools.sync_integration import sync


def test_hacs_and_installer_archives_reproduce_without_private_material(tmp_path):
    sync(check=True)
    a, b = tmp_path / "a", tmp_path / "b"
    release(a)
    release(b)
    assert {p.name: p.read_bytes() for p in a.iterdir()} == {
        p.name: p.read_bytes() for p in b.iterdir()
    }
    with zipfile.ZipFile(a / "hearth.zip") as z:
        names = set(z.namelist())
        assert {
            "manifest.json",
            "config_flow.py",
            "_backend/native_controls.py",
            "commissioning_view.py",
            "switch.py",
            "translations/en.json",
        } <= names
        assert not any(
            name.startswith(("private/", "build/")) or name.endswith((".key", ".pem", ".crl"))
            for name in names
        )
        version = json.loads(z.read("manifest.json"))["version"]
        project = tomllib.loads(Path("pyproject.toml").read_text())
        assert version == project["project"]["version"]
    with zipfile.ZipFile(a / "hearth-installer-source.zip") as z:
        names = set(z.namelist())
        assert {
            "provision.py",
            "installer/wizard.py",
            "installer/recovery_wizard.py",
            "installer/nand_backup.py",
            "tools/nand_archive/bch-input.json",
            "tools/nand_archive/verify.py",
            "firmware/nand_capture/profile.py",
            "installer/wizard_worker.py",
            "provisioning/time_server.py",
            "installer/cli.py",
            "installer/kit.py",
            "installer/replacements.py",
            "installer/workflow.py",
            "provisioning/native_tls.py",
            "firmware/file_writer/chain.py",
            "firmware/file_writer/run.py",
        } <= names
        assert "firmware/probe/omap-loader.patch" in names
        assert "firmware/probe/COPYING.GPL-2.0" in names
        assert "firmware/probe/Dockerfile" in names
        assert {
            "tests/file_install_harness.c",
            "tests/file_recovery_harness.c",
            "tests/file_reencode_harness.c",
            "tests/network_memory.h",
            "tests/network_transaction_harness.c",
        } <= names
        assert not any(
            name.startswith(("private/", "build/"))
            or name.endswith((".key", ".pem", ".crl", ".bin", ".so"))
            for name in names
        )
        assert (
            set(acquisition_recipes()) | set(commissioning_recipes()) | set(cleanup_recipes())
        ) <= names
        extracted = tmp_path / "source"
        z.extractall(extracted)
    launch = subprocess.run(
        [sys.executable, "-S", "provision.py"],
        input=b"QUIT\n",
        check=False,
        cwd=extracted,
        capture_output=True,
        timeout=15,
        env={**os.environ, "PYTHONPATH": str(extracted)},
    )
    assert launch.returncode == 0 and b"Hearth setup" in launch.stdout
    result = subprocess.run(
        [sys.executable, "-S", "-m", "installer.cli", "--help"],
        cwd=extracted,
        env={**os.environ, "PYTHONPATH": str(extracted)},
        capture_output=True,
        text=True,
        check=True,
    )
    # The installed archive must be able to snapshot itself without HA sources.
    assert not (extracted / "custom_components").exists()
    subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "from tools.public_release import installer_archive; installer_archive('recovery-source.zip')",
        ],
        cwd=extracted,
        env={**os.environ, "PYTHONPATH": str(extracted)},
        check=True,
        capture_output=True,
    )
    with (
        zipfile.ZipFile(extracted / "recovery-source.zip") as snapshot,
        zipfile.ZipFile(a / "hearth-installer-source.zip") as original,
    ):
        assert snapshot.namelist() == original.namelist()
        assert all(snapshot.read(n) == original.read(n) for n in original.namelist())
    assert all(name in result.stdout for name in ("build-kit", "install-kit", "restore-kit"))
    assert (
        json.loads((a / "release.json").read_bytes())["stock_device_kit_generation"]
        == "experimental-source-builder"
    )
    assert not json.loads((a / "release.json").read_bytes())[
        "stock_install_restore_hardware_verified"
    ]
    metadata = json.loads((a / "release.json").read_bytes())
    # Default HACS release filtering must have an ordinary GitHub release to
    # select; otherwise zip_release falls back to a nonexistent commit asset.
    assert metadata["prerelease"] is False and metadata["experimental"] is True
    workflow = Path(".github/workflows/release.yml").read_text()
    publish = next(line for line in workflow.splitlines() if "run: gh release create " in line)
    assert "--prerelease" not in publish and "--latest" in publish
    assert "Experimental preview" in publish
    assert "needs: [package, hassfest]" in workflow
