"""Protected-kernel packaging regression: external initramfs must be raw newc."""

import shutil
from pathlib import Path

import pytest

from firmware.rom_restart import profile
from firmware.tls_probe.check import split_multi


def test_profile_uses_raw_newc_when_protected_kernel_disables_gzip(tmp_path, monkeypatch):
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    if not shutil.which("clang") or not shutil.which("ld.lld"):
        pytest.skip("clang/lld unavailable")
    monkeypatch.setattr(profile, "ROOT", tmp_path)
    monkeypatch.setattr(profile, "private_path", lambda p: Path(p))
    monkeypatch.setattr(profile, "recipes", lambda: {"synthetic-source": "pinned"})
    kernel = b"synthetic opaque kernel"
    blobs = {
        name: b"synthetic bootstrap" for name in ("omap_loader", "x-load-gen2.bin", "u-boot.bin")
    }
    blobs["kernel.config"] = b"CONFIG_BLK_DEV_INITRD=y\n# CONFIG_RD_GZIP is not set\n"
    monkeypatch.setattr(profile, "base_check", lambda _: (blobs, kernel, "synthetic-manifest"))
    (tmp_path / "build").mkdir()
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    # read_build ordinarily enforces the real repository build root; this test
    # keeps generated artifacts entirely inside its isolated temporary tree.
    monkeypatch.setattr(profile, "read_build", lambda p, limit: p.read_bytes())
    output = private / "profile"
    result = profile.build(tmp_path / "base", tmp_path / "build/experiment", output)
    assert result["device_executed"] is False
    payload, ramdisk = split_multi((output / "artifacts/uImage").read_bytes())
    assert payload == kernel
    assert ramdisk.startswith(b"070701")
    assert ramdisk == (output / "artifacts/rootfs.cpio").read_bytes()
    assert profile.check(output)["rom_restart_measured"] is False
