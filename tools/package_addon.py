"""Assemble a local HA add-on repository without maintaining a second backend copy."""

import shutil
from pathlib import Path


def package(output):
    root = Path(__file__).resolve().parents[1]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(root / "homeassistant/repository.yaml", output / "repository.yaml")
    addon = output / "hearth"
    addon.mkdir()
    shutil.copyfile(root / "homeassistant/hearth/config.yaml", addon / "config.yaml")
    shutil.copyfile(root / "homeassistant/DOCS.md", addon / "DOCS.md")
    for name in ("Dockerfile", "requirements.lock", "LICENSE", "THIRD_PARTY.md"):
        shutil.copyfile(root / name, addon / name)
    for name in ("backend", "provisioning"):
        shutil.copytree(root / name, addon / name, ignore=shutil.ignore_patterns("__pycache__"))
    return addon


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    package(parser.parse_args().output)
