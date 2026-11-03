"""Fetch hash-pinned public BCH source and compile a separate offline GPL tool."""

import hashlib
import json
import os
import subprocess  # nosec B404
import tarfile
import urllib.request
from pathlib import Path

from installer.sources import HttpsRedirect, build_path

PINS = Path(__file__).with_name("bch-input.json")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1048576), b""):
            h.update(data)
    return h.hexdigest()


def compile_source(output, source):
    output = build_path(output)
    source = Path(source).absolute()
    pins = json.loads(PINS.read_bytes())
    for name, expected in pins["files"].items():
        path = source / Path(name).name
        if path.is_symlink() or digest(path) != expected:
            raise ValueError("pinned public BCH source required")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    import shutil

    for name in pins["files"]:
        shutil.copyfile(source / Path(name).name, output / Path(name).name)
    library = output / "libbch.so"
    subprocess.run(  # nosec B603 B607
        [
            "cc",
            "-O2",
            "-shared",
            "-fPIC",
            "-fno-strict-aliasing",
            "-Wl,--build-id=none,-z,relro,-z,now",
            "-I" + str(output),
            str(output / "bch.c"),
            "-o",
            str(library),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    record = {
        "format": "hearth-public-offline-bch-library-v1",
        "pins": pins,
        "library_sha256": digest(library),
    }
    (output / "library.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    for path in output.iterdir():
        path.chmod(0o600)
    return library


def fetch(output):
    output = build_path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    pins = json.loads(PINS.read_bytes())
    archive = output / "public-source.tar.gz"
    opener = urllib.request.build_opener(HttpsRedirect())
    with opener.open(pins["sdist_url"], timeout=30) as response, archive.open("xb") as stream:  # nosec B310
        data = response.read(2 * 1048576 + 1)
        if len(data) > 2 * 1048576:
            raise ValueError("bounded public BCH archive required")
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if digest(archive) != pins["sdist_sha256"]:
        raise ValueError("public BCH source archive pin mismatch")
    source = output / "source"
    source.mkdir(mode=0o700)
    with tarfile.open(archive, "r:gz") as tar:
        for name, expected in pins["files"].items():
            members = [m for m in tar.getmembers() if m.name == f"bchlib-{pins['version']}/{name}"]
            if len(members) != 1 or not members[0].isfile() or members[0].size > 262144:
                raise ValueError("fixed public source members required")
            handle = tar.extractfile(members[0])
            if handle is None:
                raise ValueError("public source unavailable")
            raw = handle.read(262145)
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("BCH source member differs from pin")
            path = source / Path(name).name
            path.write_bytes(raw)
            path.chmod(0o600)
    return compile_source(output / "compiled", source)


def checked_library(path):
    path = build_path(path)
    root = path.parent
    if path.name != "libbch.so" or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("private compiled public library required")
    record = json.loads((root / "library.json").read_bytes())
    pins = json.loads(PINS.read_bytes())
    if record != {
        "format": "hearth-public-offline-bch-library-v1",
        "pins": pins,
        "library_sha256": digest(path),
    }:
        raise ValueError("compiled public library changed")
    for name, expected in pins["files"].items():
        if digest(root / Path(name).name) != expected:
            raise ValueError("BCH source provenance changed")
    return path
