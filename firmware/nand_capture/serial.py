"""Fixed long capture window; same measured physical-port/gadget guards."""

import contextlib
import os
import re
import stat
import termios
import time
from pathlib import Path


def observe(receive):
    usb = Path("/sys/bus/usb/devices/1-1")
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        try:
            identity = tuple((usb / n).read_text().strip() for n in ("idVendor", "idProduct"))
        except OSError:
            time.sleep(0.1)
            continue
        if identity not in (("0525", "a4a7"), ("0525", "a4a6")):
            time.sleep(0.1)
            continue
        for tty in Path("/sys/class/tty").glob("tty*"):
            if not re.fullmatch(r"tty(?:ACM|USB)[0-9]+", tty.name) or not (
                tty / "device"
            ).resolve().is_relative_to(usb.resolve()):
                continue
            fd = os.open(
                "/dev/" + tty.name, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK | os.O_NOFOLLOW
            )
            previous = None
            try:
                if not stat.S_ISCHR(os.fstat(fd).st_mode):
                    raise ValueError("serial character device required")
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
    raise TimeoutError("full raw capture interface not observed on port 1-1")
