"""Locate a single normal Nest disk through read-only sysfs metadata."""

from pathlib import Path

from backend.validation import Invalid


def native_disk(sysfs=Path("/sys/class/block"), devices=Path("/dev")):
    matches = []
    for node in sorted(sysfs.iterdir()):
        if (node / "partition").exists():
            continue
        resolved = node.resolve()
        for parent in (resolved, *resolved.parents):
            try:
                identity = tuple(
                    (parent / name).read_text().strip() for name in ("idVendor", "idProduct")
                )
            except (OSError, UnicodeError):
                continue
            if identity == ("2464", "0002"):
                matches.append(devices / node.name)
            break  # The closest USB identity owns this block device.
    if len(matches) != 1:
        raise Invalid("one normal-mode Nest required; choose --disk if multiple are connected")
    return matches[0]
