"""Deterministic source archive and SHA-256 manifest. No signing or publishing."""

import hashlib
import io
import json
import tarfile
from pathlib import Path


def release(output):
    root = Path(__file__).resolve().parents[1]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    allowed_dirs = (
        "backend",
        "firmware",
        "provisioning",
        "homeassistant",
        "tools",
        "tests",
        "docs",
        ".github",
    )
    paths = [
        path
        for folder in allowed_dirs
        for path in (root / folder).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    paths += [
        root / name
        for name in (
            "README.md",
            "LICENSE",
            "THIRD_PARTY.md",
            "TODO.md",
            "Makefile",
            "Dockerfile",
            "pyproject.toml",
            "requirements.lock",
            "requirements-dev.lock",
            "requirements-build.lock",
            ".gitignore",
            ".dockerignore",
        )
    ]
    archive_path = output / "hearth-0.1.0-source.tar"
    entries = {}
    with tarfile.open(archive_path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for path in sorted(paths):
            if path.is_symlink():
                raise ValueError("source symlinks are not permitted")
            relative = path.relative_to(root).as_posix()
            data = path.read_bytes()
            entries[relative] = hashlib.sha256(data).hexdigest()
            info = tarfile.TarInfo("hearth-0.1.0/" + relative)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            archive.addfile(info, io.BytesIO(data))
    (output / "source-files.json").write_text(json.dumps(entries, sort_keys=True, indent=2) + "\n")
    (output / "SHA256SUMS").write_text(
        "".join(
            hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n"
            for path in (archive_path, output / "source-files.json")
        )
    )
    return hashlib.sha256(archive_path.read_bytes()).hexdigest()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    print(release(parser.parse_args().output))
