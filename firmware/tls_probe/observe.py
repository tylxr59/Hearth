"""Receive only bounded TLS results; USB input is one fixed start token."""

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

from backend.validation import loads
from firmware.probe.observe import HEARTBEAT
from firmware.tls_probe.fixtures import CASES
from tools.elf_review import private_path

START = b"BEGIN_TLS_TEST_V1\n"
READY = b"HEARTH_TLS_READY_V1\n"
BEGIN = b"HEARTH_TLS_PROBE_V1\n"
END = b"END_HEARTH_TLS_PROBE\n"
MAX_REPORT = 16384


def validate(data):
    if len(data) > MAX_REPORT:
        raise ValueError("TLS report limit exceeded")
    rows = [loads(line) for line in data.splitlines()]
    clean = []
    for row in rows:
        if isinstance(row, dict) and row.get("type") == "tls_stderr":
            if (
                set(row) != {"type", "variant", "hex"}
                or row["variant"] not in ("original", "candidate")
                or not isinstance(row["hex"], str)
                or not re.fullmatch(r"(?:[0-9a-f]{2}){1,128}", row["hex"])
            ):
                raise ValueError("invalid private diagnostic row")
            continue  # kept privately; never echo decoded library output
        clean.append(row)
    rows = clean
    if (
        len(rows) != 22
        or not isinstance(rows[-1], dict)
        or set(rows[-1]) != {"type", "passed"}
        or rows[-1]["type"] != "tls_complete"
        or rows[-1]["passed"] is not True
    ):
        raise ValueError("TLS run incomplete or helper failed")
    setup = rows[0]
    expected_setup = {
        "type": "tls_setup",
        "loopback_stage": 3,
        "loopback_result": 0,
        "clock_result": 0,
    }
    if setup != expected_setup or any(
        type(setup.get(k)) is not int for k in ("loopback_stage", "loopback_result", "clock_result")
    ):
        raise ValueError("TLS setup was not confirmed")
    seen = set()
    processes = set()
    for row in rows[1:-1]:
        if isinstance(row, dict) and row.get("type") == "tls_process":
            if (
                set(row) != {"type", "variant", "wait_status"}
                or row["variant"] not in ("original", "candidate")
                or row["variant"] in processes
                or type(row["wait_status"]) is not int
                or row["wait_status"] != 0
            ):
                raise ValueError("TLS helper did not exit successfully")
            processes.add(row["variant"])
            continue
        if not isinstance(row, dict) or set(row) != {
            "type",
            "variant",
            "case",
            "curl_code",
            "passed",
        }:
            raise ValueError("unexpected TLS result shape")
        variant, case = row["variant"], row["case"]
        if (
            row["type"] != "tls_case"
            or variant not in ("original", "candidate")
            or case not in CASES
            or (variant, case) in seen
            or type(row["curl_code"]) is not int
        ):
            raise ValueError("unexpected or duplicate TLS case")
        accepts = case == "valid" or (
            variant == "original"
            and case in ("future_cert", "missing_issuer_crl", "expired_crl", "future_crl")
        )
        expected = 0 if accepts else (51 if case == "wrong_host" else 60)
        if row["curl_code"] != expected or row["passed"] is not True:
            raise ValueError("native TLS behavior differed from the test expectation")
        seen.add((variant, case))
    if seen != {(v, c) for v in ("original", "candidate") for c in CASES} or processes != {
        "original",
        "candidate",
    }:
        raise ValueError("missing TLS case")
    return {
        "status": "native-tls-callback-matrix-observed",
        "cases": 18,
        "network": "device loopback only",
        "installed": False,
        "full_native_transport_verified": False,
        "recovery": "unverified",
    }


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
            raise OSError("TLS serial interface disconnected")
        data = (data + chunk)[-2 * MAX_REPORT :]
        if HEARTBEAT in data:
            if capture is not None:
                capture_private(capture, data[-MAX_REPORT:])
            raise ValueError("fallback heartbeat booted; external TLS filesystem was not started")
        if READY in data and not started:
            if os.write(fd, START) != len(START):
                raise OSError("fixed TLS start token was not transferred completely")
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
    raise TimeoutError("bounded TLS result was not received")


def observe(port="1-1", seconds=240, capture=None):
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
    raise TimeoutError("TLS serial interface was not observed on the known port")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="1-1")
    parser.add_argument("--seconds", type=int, default=240)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        print(json.dumps(observe(args.port, args.seconds, args.output), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, "TLS observation failed: " + str(exc) + "\n")
