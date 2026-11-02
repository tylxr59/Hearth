"""Fetch only pinned public build inputs. No firmware, USB or private mounts."""

import hashlib
import json
import os
import subprocess  # nosec B404
import time
import urllib.request
from pathlib import Path

from firmware.probe.stage import verify_loader

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / "firmware/probe/inputs.json"


def build_path(value):
    path = Path(value).absolute()
    if path.resolve() != path or not path.is_relative_to(ROOT / "build") or path == ROOT / "build":
        raise ValueError("repository build path without symlinks required")
    return path


def git(directory, *args):
    return subprocess.run(  # nosec B603 B607
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "protocol.file.allow=never",
            "-C",
            str(directory),
            *args,
        ],
        check=True,
        capture_output=True,
        timeout=300,
        env=os.environ | {"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"},
    ).stdout


class HttpsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise ValueError("public compiler download must remain HTTPS")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def compiler(destination, record):
    digest, total, deadline = hashlib.sha256(), 0, time.monotonic() + 600
    opener = urllib.request.build_opener(HttpsRedirect())
    with opener.open(record["url"], timeout=60) as response, destination.open("xb") as stream:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > record["bytes"] or time.monotonic() > deadline:
                raise ValueError("public compiler download exceeded bound")
            digest.update(chunk)
            stream.write(chunk)
        stream.flush()
        os.fsync(stream.fileno())
    if total != record["bytes"] or digest.hexdigest() != record["sha256"]:
        raise ValueError("public compiler length/digest differs from pin")


def fetch(output):
    output = build_path(output)
    pins = json.loads(PINS.read_bytes())
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.mkdir(mode=0o700, exist_ok=False)
    for name in ("nestdfu", "xloader", "loader"):
        directory = output / name
        directory.mkdir(mode=0o700)
        git(directory, "init", "--quiet")
        git(directory, "remote", "add", "origin", pins[name]["repository"])
        git(directory, "fetch", "--depth=1", "--no-tags", "origin", pins[name]["revision"])
        revision = git(directory, "rev-parse", "FETCH_HEAD").decode().strip()
        if revision != pins[name]["revision"]:
            raise ValueError("public source revision differs from pin")
        # Nest/kernel staging uses git archive directly. Only three bounded,
        # hash-pinned loader source files are exported to the working tree.
        if name == "loader":
            for filename in pins[name]["files"]:
                data = git(directory, "show", revision + ":" + filename)
                if len(data) > 65536:
                    raise ValueError("bounded loader source required")
                (directory / filename).write_bytes(data)
            verify_loader(directory, pins[name]["files"])
    compiler(output / "toolchain.tar.bz2", pins["toolchain"])
    (output / "sources.json").write_text(json.dumps(pins, sort_keys=True, indent=2) + "\n")
    return verify(output)


def verify(output):
    output = build_path(output)
    pins = json.loads(PINS.read_bytes())
    if json.loads((output / "sources.json").read_bytes()) != pins:
        raise ValueError("source cache pin record differs")
    for name in ("nestdfu", "xloader", "loader"):
        directory = output / name
        if directory.resolve() != directory:
            raise ValueError("source cache symlink refused")
        revision = (
            git(directory, "rev-parse", pins[name]["revision"] + "^{commit}").decode().strip()
        )
        if revision != pins[name]["revision"]:
            raise ValueError("source commit differs")
    verify_loader(output / "loader", pins["loader"]["files"])
    archive = output / "toolchain.tar.bz2"
    if (
        archive.is_symlink()
        or not archive.is_file()
        or archive.stat().st_size != pins["toolchain"]["bytes"]
    ):
        raise ValueError("bounded compiler archive required")
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != pins["toolchain"]["sha256"]:
        raise ValueError("compiler archive differs from pin")
    return {"status": "pinned-public-sources-verified", "device_executed": False}
