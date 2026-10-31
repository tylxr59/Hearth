"""Bounded same-port receiver for the fixed RAM file/standalone-settings lab."""

import argparse
import json
import os
import select
import time

from firmware.file_install_probe.results import MAX_REPORT, validate
from firmware.probe.observe import HEARTBEAT
from firmware.settings_compat_probe.observe import observe
from tools.elf_review import private_path

START = b"BEGIN_FILE_COMMISSIONING_V1\n"
READY = b"HEARTH_FILE_COMMISSIONING_READY_V1\n"
BEGIN = b"HEARTH_FILE_COMMISSIONING_V1\n"
END = b"END_HEARTH_FILE_COMMISSIONING\n"


def capture_private(path, data):
    path = private_path(path)
    if path.parent.stat().st_mode & 0o077 or len(data) > MAX_REPORT:
        raise ValueError("bounded owner-only capture required")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def receive(fd, deadline, capture=None):
    data, started = b"", False
    while (remaining := deadline - time.monotonic()) > 0:
        if not select.select([fd], [], [], min(remaining, 0.5))[0]:
            continue
        chunk = os.read(fd, 4096)
        if not chunk:
            raise OSError("file lab serial disconnected")
        data = (data + chunk)[-2 * MAX_REPORT :]
        if HEARTBEAT in data:
            if capture is not None:
                capture_private(capture, data[-MAX_REPORT:])
            raise ValueError("fallback heartbeat booted instead of the file lab")
        if READY in data and not started:
            if os.write(fd, START) != len(START):
                raise OSError("fixed file lab token transfer incomplete")
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
    raise TimeoutError("bounded file lab report not received")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(observe("1-1", 300, args.output, receive_fn=receive), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, "File RAM lab not confirmed: " + str(exc) + "\n")
