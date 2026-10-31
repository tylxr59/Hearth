"""Receive only bounded SETTINGS results; USB input is one fixed start token."""

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

from firmware.probe.observe import HEARTBEAT
from firmware.settings_compat_probe.results import validate
from tools.elf_review import private_path

START = b"BEGIN_SETTINGS_COMPAT_V1\n"
READY = b"HEARTH_SETTINGS_COMPAT_READY_V1\n"
BEGIN = b"HEARTH_SETTINGS_COMPAT_V1\n"
END = b"END_HEARTH_SETTINGS_COMPAT\n"
MAX_REPORT = 32768


def capture_private(path, data):
    path = private_path(path)
    if path.parent.stat().st_mode & 0o077 or len(data) > MAX_REPORT:
        raise ValueError("bounded capture in an owner-only directory required")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def receive(fd, deadline, capture=None):
    data, started = b"", False
    while (remaining := deadline - time.monotonic()) > 0:
        if not select.select([fd], [], [], min(remaining, 0.5))[0]:
            continue
        chunk = os.read(fd, 4096)
        if not chunk:
            raise OSError("SETTINGS serial interface disconnected")
        data = (data + chunk)[-2 * MAX_REPORT :]
        if HEARTBEAT in data:
            if capture is not None:
                capture_private(capture, data[-MAX_REPORT:])
            raise ValueError(
                "fallback heartbeat booted; external SETTINGS filesystem was not started"
            )
        if READY in data and not started:
            if os.write(fd, START) != len(START):
                raise OSError("fixed SETTINGS start token was not transferred completely")
            started = True
        begin = data.find(BEGIN)
        end = data.find(END, begin + len(BEGIN)) if begin >= 0 else -1
        if end >= 0:
            payload = data[begin + len(BEGIN) : end]
            if capture is not None:
                capture_private(capture, payload)
            return validate(payload)
    if capture is not None and data:
        capture_private(capture, data[-MAX_REPORT:])
    raise TimeoutError("bounded SETTINGS result was not received")


def observe(port="1-1", seconds=300, capture=None):
    if not re.fullmatch(r"[0-9]+-[0-9]+(?:\.[0-9]+)*", port) or not 1 <= seconds <= 300:
        raise ValueError("known port and bounded duration required")
    usb = Path("/sys/bus/usb/devices") / port
    if capture is not None:
        capture = private_path(capture)
        if capture.exists() or capture.is_symlink() or capture.parent.stat().st_mode & 0o077:
            raise ValueError("fresh capture in an owner-only private directory required")
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
        if identity not in (("0525", "a4a7"), ("0525", "a4a6")):
            time.sleep(0.1)
            continue
        for tty in Path("/sys/class/tty").glob("tty*"):
            if not re.fullmatch(r"tty(?:ACM|USB)[0-9]+", tty.name):
                continue
            if not (tty / "device").resolve().is_relative_to(usb.resolve()):
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
                return receive(fd, deadline, capture)
            finally:
                if previous is not None:
                    with contextlib.suppress(OSError):
                        termios.tcsetattr(fd, termios.TCSANOW, previous)
                os.close(fd)
        time.sleep(0.1)
    raise TimeoutError("SETTINGS serial interface was not observed on the known port")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="1-1")
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        print(json.dumps(observe(args.port, args.seconds, args.output), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, "SETTINGS observation failed: " + str(exc) + "\n")
