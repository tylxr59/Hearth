"""Whole-chip read-only profile, retaining the reviewed sample driver guards."""

if __package__:
    from firmware.nand_sample.configure import initramfs, main, verify
else:
    from sample_configure import initramfs, main, verify

__all__ = ["initramfs", "verify"]

if __name__ == "__main__":
    main()
