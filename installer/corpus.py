"""Inspect native dependency closure after independent acquisition validation."""

from pathlib import Path

from firmware.acquisition.custody import verify
from firmware.tls_probe.package import libraries
from tools.elf_review import private_path


def inspect(root):
    decoder, record = verify(root)
    # This original passive resolver catalogs real files by filename and ELF
    # SONAME. It needs no symlink recreation and never executes a native DSO.
    selected = libraries(private_path(Path(root) / "corpus"), record)
    if not {"libc.so.6", "ld-linux-armhf.so.3"} <= selected.keys():
        raise ValueError("native libc/interpreter pair unavailable")
    return {
        "status": "private-installer-inputs-and-native-closure-verified",
        "fixed_files": len(decoder.snapshot) + len(decoder.network.records),
        "private_files": len(record["files"]),
        "native_libraries": len(selected),
        "native_code_executed": False,
        "install_kit_built": False,
    }
