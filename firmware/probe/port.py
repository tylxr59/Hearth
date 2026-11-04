"""Find the one USB port the Nest is plugged into, then keep using only that port.

Discovery reads sysfs only. The first port found is pinned for the rest of the
process: the udev rule, the ROM loader (``-P``) and every serial observer are
scoped to it, and a Nest that reappears anywhere else is refused.

Only port 1-1 has been measured on hardware. Other ports, including ports
behind a hub, use the same loader pacing but are not yet hardware-tested.
"""

import re
from pathlib import Path

SYSFS = Path("/sys/bus/usb/devices")
MEASURED = "1-1"
NATIVE = ("2464", "0002")
ROM = ("0451", "d00e")
# The reviewed RAM kernels use the serial gadget's default IDs. They are not
# unique to a Nest, so a RAM-mode match is only accepted when it is the sole
# candidate, and the serial handshakes still check the Hearth payload.
RAM = (("0525", "a4a7"), ("0525", "a4a6"))
# Linux names a USB device <bus>-<port>[.<port>]..., at most seven tiers deep.
PATTERN = re.compile(r"[1-9][0-9]{0,2}-[1-9][0-9]{0,2}(?:\.[1-9][0-9]{0,2}){0,6}")

_pinned = None


class NotFound(ValueError):
    """No Nest is visible over USB."""


class Ambiguous(ValueError):
    """More than one possible Nest is connected, so none is chosen."""


def valid(port):
    return (
        isinstance(port, str)
        and PATTERN.fullmatch(port) is not None
        and all(int(part) <= 255 for part in re.split(r"[-.]", port))
    )


def require_valid(port):
    if not valid(port):
        raise ValueError("known USB port required")
    return port


def mode(identity):
    if identity == NATIVE:
        return "native"
    if identity in RAM:
        return "ram"
    if identity == ROM:
        return "rom"
    return None


def candidates(sysfs=SYSFS):
    """Map each USB port showing a Nest-related identity to its mode."""
    found = {}
    try:
        entries = sorted(Path(sysfs).iterdir())
    except OSError:
        return found
    for entry in entries:
        if not valid(entry.name):
            continue  # Skips root hubs (usb1) and interfaces (1-1:1.0).
        try:
            identity = tuple(
                (entry / name).read_text().strip() for name in ("idVendor", "idProduct")
            )
        except (OSError, UnicodeError):
            continue
        if (kind := mode(identity)) is not None:
            found[entry.name] = kind
    return found


def discover(sysfs=SYSFS, *, modes=("native", "ram")):
    """Return the single port with a Nest in one of ``modes``; refuse otherwise."""
    found = candidates(sysfs)
    if "rom" not in modes and "rom" in found.values():
        raise ValueError(
            "ROM already active; restart to native startup with the loader exited first"
        )
    matches = sorted(port for port, kind in found.items() if kind in modes)
    if not matches:
        raise NotFound("no Nest found on any USB port")
    if len(matches) > 1:
        raise Ambiguous(
            "more than one possible Nest is connected (USB ports "
            + ", ".join(matches)
            + "); unplug all but one"
        )
    return matches[0]


def pin(port):
    """Scope this process to ``port``. Refuse a different port once pinned."""
    global _pinned
    require_valid(port)
    if _pinned is not None and _pinned != port:
        raise ValueError(
            f"the Nest moved from USB port {_pinned} to {port}; "
            "this session only uses the port it started on"
        )
    _pinned = port
    return port


def current(sysfs=SYSFS):
    """The pinned port, discovering and pinning it on first use."""
    if _pinned is not None:
        return _pinned
    return pin(discover(sysfs))


def pinned():
    return _pinned


def measured(port):
    return port == MEASURED
