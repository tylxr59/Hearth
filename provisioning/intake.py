"""Read-only USB inventory and allowlisted thermostat diagnostic metadata.

No device nodes are opened, USB transfers sent, or firmware commands executed.
"""

import math
import plistlib
import re
import time
from pathlib import Path
from xml.parsers.expat import ExpatError

from backend.validation import Invalid

MAX_INFO_BYTES = 16 * 1024
INFO_FIELDS = {
    "Base": ("Model", "SoftwareVersion"),
    "Display": ("Model", "SoftwareVersion", "ActivePartition", "SoftwareUpdateState"),
}


class UniqueKeys(dict):
    def __setitem__(self, key, value):
        if key in self:
            raise Invalid("duplicate diagnostic key")
        super().__setitem__(key, value)


def inspect_info(data):
    """Return only known non-identifying fields; never echo malformed input."""
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_INFO_BYTES:
        raise Invalid("diagnostic input must contain 1..16384 bytes")
    try:
        source = plistlib.loads(data, fmt=plistlib.FMT_XML, dict_type=UniqueKeys)
    except (ValueError, TypeError, OverflowError, RecursionError, ExpatError) as exc:
        raise Invalid("invalid diagnostic plist") from exc
    if not isinstance(source, dict):
        raise Invalid("diagnostic dictionary required")
    result = {}
    for section, fields in INFO_FIELDS.items():
        if section not in source:
            continue
        values = source[section]
        if not isinstance(values, dict):
            raise Invalid("invalid diagnostic section")
        selected = {}
        for field in fields:
            if field not in values:
                continue
            value = values[field]
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9 ._:+/()-]{1,96}", value):
                raise Invalid("invalid diagnostic metadata")
            selected[field] = value
        if selected:
            result[section] = selected
    if not result:
        raise Invalid("no recognized diagnostic metadata")
    return {"status": "device-reported-metadata-only", "metadata": result}


def usb_inventory(sysfs=Path("/sys/bus/usb/devices")):
    result = []
    for path in sorted(Path(sysfs).glob("*")):
        try:
            vendor, product = (
                (path / "idVendor").read_text().strip().lower(),
                (path / "idProduct").read_text().strip().lower(),
            )
        except (OSError, UnicodeError):
            continue
        if not re.fullmatch(r"[0-9a-f]{4}", vendor) or not re.fullmatch(r"[0-9a-f]{4}", product):
            continue
        if (vendor, product) == ("2464", "0002"):
            mode = "nest-mass-storage"
            note = "Observed normal-mode identity; not a firmware backup or control interface"
        elif (vendor, product) == ("0451", "d00e"):
            mode = "omap-rom-candidate"
            note = "ROM identity does not establish payload compatibility or recovery"
        elif vendor == "0451":
            mode = "ti-candidate"
            note = "TI USB identity alone cannot establish Nest compatibility"
        else:
            continue
        result.append(
            {
                "bus_path": path.name,
                "vendor": vendor,
                "product": product,
                "mode": mode,
                "generation": "unknown",
                "compatible": False,
                "note": note,
            }
        )
    return result


def usb_events(duration, sysfs=Path("/sys/bus/usb/devices")):
    """Yield changed sysfs snapshots only; short ROM windows can still be missed."""
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or not 1 <= duration <= 300
    ):
        raise Invalid("watch duration must be between 1 and 300 seconds")
    start = time.monotonic()
    previous = None
    while (elapsed := time.monotonic() - start) < duration:
        current = usb_inventory(sysfs)
        if current != previous:
            yield {"elapsed_seconds": round(elapsed, 3), "devices": current}
            previous = current
        time.sleep(0.05)
