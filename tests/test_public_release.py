import json
import os
import subprocess
import sys
import zipfile

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
        assert json.loads(z.read("manifest.json"))["version"] == "0.7.0"
    with zipfile.ZipFile(a / "hearth-installer-source.zip") as z:
        names = set(z.namelist())
        assert {
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
    result = subprocess.run(
        [sys.executable, "-m", "installer.cli", "--help"],
        cwd=extracted,
        env={**os.environ, "PYTHONPATH": str(extracted)},
        capture_output=True,
        text=True,
        check=True,
    )
    assert all(name in result.stdout for name in ("build-kit", "install-kit", "restore-kit"))
    assert (
        json.loads((a / "release.json").read_bytes())["stock_device_kit_generation"]
        == "experimental-source-builder"
    )
    assert not json.loads((a / "release.json").read_bytes())[
        "stock_install_restore_hardware_verified"
    ]
