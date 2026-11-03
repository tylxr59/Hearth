"""Whole-chip read-only profile with reproducible build metadata."""

import sys
from pathlib import Path

if __package__:
    from firmware.nand_contract.configure import patch_build_metadata
    from firmware.nand_sample.configure import initramfs, verify
    from firmware.nand_sample.configure import main as sample_main
else:
    from contract_configure import patch_build_metadata
    from sample_configure import initramfs, verify
    from sample_configure import main as sample_main

__all__ = ["initramfs", "verify"]


def main():
    sample_main()
    path = Path("scripts/mkcompile_h")
    saved = path.with_suffix(".hearth-capture-original")
    if "--verify" in sys.argv:
        if not saved.exists() or path.read_text() != patch_build_metadata(saved.read_text()):
            raise ValueError("reproducible raw-reader metadata patch required")
        return
    if not saved.exists():
        saved.write_bytes(path.read_bytes())
    desired = patch_build_metadata(saved.read_text())
    if path.read_text() not in (saved.read_text(), desired):
        raise ValueError("unexpected compile metadata edits")
    path.write_text(desired)


if __name__ == "__main__":
    main()
