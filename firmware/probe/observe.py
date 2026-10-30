"""Observe only the fixed USB heartbeat on the previously identified USB port.

No commands or payload bytes are written to the serial device. Host tty settings
are temporarily made raw, then restored. Unknown received bytes are not printed.
"""

import argparse
import contextlib
import json
import os
import re
import select
import stat
import termios
import time
from pathlib import Path

HEARTBEAT = (
    b"HEARTH_RAM_PROBE_V1\n"
    b"mtd=disabled\n"
    b"stock_userspace=absent\n"
    b"commands=none\n"
    b"END_HEARTH_RAM_PROBE\n"
)


def require_native(port, sysfs=Path("/sys/bus/usb/devices")):
    """Reject a stale ROM handshake before starting a fresh controlled attempt."""
    if not re.fullmatch(r"[0-9]+-[0-9]+(?:\.[0-9]+)*", port):
        raise ValueError("known USB port required")
    usb = Path(sysfs) / port
    identity = ((usb / "idVendor").read_text().strip(), (usb / "idProduct").read_text().strip())
    if identity == ("0451", "d00e"):
        raise ValueError(
            "ROM already active; restart to native startup with the loader exited first"
        )
    if identity != ("2464", "0002"):
        raise ValueError("expected normal Nest USB mode on the known port before a new attempt")
    return {"status": "native-usb-mode-observed", "port": port}


def receive(fd, deadline):
    data = b""
    while (remaining := deadline - time.monotonic()) > 0:
        if not select.select([fd], [], [], min(remaining, 0.5))[0]:
            continue
        chunk = os.read(fd, 1024)
        if not chunk:
            raise OSError("serial device disconnected")
        data = (data + chunk)[-4096:]
        if HEARTBEAT in data.replace(b"\r\n", b"\n"):
            return {
                "status": "probe-heartbeat-observed",
                "flash_access": "disabled-in-probe-kernel",
                "recovery": "unverified",
            }
    raise TimeoutError("probe heartbeat was not observed")


def observe(port, seconds):
    if not re.fullmatch(r"[0-9]+-[0-9]+(?:\.[0-9]+)*", port) or not 1 <= seconds <= 60:
        raise ValueError("known USB port and 1..60 second duration required")
    usb = Path("/sys/bus/usb/devices") / port
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            identity = (
                (usb / "idVendor").read_text().strip(),
                (usb / "idProduct").read_text().strip(),
            )
        except OSError:
            time.sleep(0.1)
            continue
        # These are the reviewed kernel serial gadget's default identities,
        # not globally unique Nest IDs. Bind them to the observed physical port.
        if identity not in (("0525", "a4a7"), ("0525", "a4a6")):
            time.sleep(0.1)
            continue
        for tty in Path("/sys/class/tty").glob("tty*"):
            if not re.fullmatch(r"tty(?:ACM|USB)[0-9]+", tty.name):
                continue
            if not (tty / "device").resolve().is_relative_to(usb.resolve()):
                continue
            fd = os.open(
                "/dev/" + tty.name, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK | os.O_NOFOLLOW
            )
            previous = None
            try:
                if not stat.S_ISCHR(os.fstat(fd).st_mode):
                    raise ValueError("expected a serial character device")
                previous = termios.tcgetattr(fd)
                raw = termios.tcgetattr(fd)
                raw[0] = raw[1] = raw[3] = 0
                raw[2] |= termios.CLOCAL | termios.CREAD
                raw[6][termios.VMIN] = raw[6][termios.VTIME] = 0
                termios.tcsetattr(fd, termios.TCSANOW, raw)
                return receive(fd, deadline)
            finally:
                if previous is not None:
                    with contextlib.suppress(OSError):
                        termios.tcsetattr(fd, termios.TCSANOW, previous)
                os.close(fd)
        time.sleep(0.1)
    raise TimeoutError("probe serial interface was not observed on the known USB port")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="1-1")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--require-native", action="store_true")
    args = parser.parse_args()
    try:
        result = (
            require_native(args.port) if args.require_native else observe(args.port, args.seconds)
        )
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, "Probe observation failed: " + str(exc) + "\n")
