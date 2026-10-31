"""Fixed normal-ECC reads; retain all sample-profile write restrictions."""

import argparse
from pathlib import Path

if __package__:
    from firmware.nand_contract.configure import patch_build_metadata
    from firmware.nand_sample import configure as sample
else:
    import raw_sample_configure as sample
    from contract_configure import patch_build_metadata

initramfs = sample.initramfs
verify = sample.verify
patch_driver = sample.patch_driver
patch_serial = sample.patch_serial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    if parser.parse_args().verify:
        verify(Path(".config").read_text())
        return
    sample.main()
    path = Path("scripts/mkcompile_h")
    original = path.with_suffix(".hearth-original")
    if not original.exists():
        original.write_bytes(path.read_bytes())
    path.write_text(patch_build_metadata(original.read_text()))


if __name__ == "__main__":
    main()
