"""Package native HA integration with the single canonical transport implementation.

Only original public source is bundled. Generated relative imports isolate the
transport package from HA and other integrations' module names. No MQTT module,
provisioning material, keys, credentials, firmware or machine configuration ships.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_FILES = (
    "__init__.py",
    "api.py",
    "core.py",
    "native.py",
    "nest.py",
    "registry.py",
    "validation.py",
)
INTEGRATION_FILES = (
    "__init__.py",
    "manifest.json",
    "const.py",
    "profile.py",
    "runtime.py",
    "config_flow.py",
    "sensor.py",
    "strings.json",
)


def isolated_source(data):
    text = data.decode()
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("backend."):
            line = lines[node.lineno - 1]
            old = "from " + node.module + " import "
            new = "from ." + node.module.removeprefix("backend.") + " import "
            if line.count(old) != 1:
                raise ValueError("unexpected canonical import layout")
            lines[node.lineno - 1] = line.replace(old, new, 1)
    output = "".join(lines)
    # The standalone CLI is excluded: HA owns startup, TLS and lifetime.
    if any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in tree.body):
        before = output.index("\ndef main():")
        output = output[:before] + "\n"
    ast.parse(output)
    return output.encode()


def package(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    destination = output / "custom_components/hearth"
    destination.mkdir(parents=True)
    source = ROOT / "homeassistant/custom_components/hearth"
    inventory = {}
    for name in INTEGRATION_FILES:
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("fixed public integration source required")
        data = path.read_bytes()
        (destination / path.name).write_bytes(data)
        inventory["custom_components/hearth/" + path.name] = hashlib.sha256(data).hexdigest()
    translations = destination / "translations"
    translations.mkdir()
    data = (source / "strings.json").read_bytes()
    (translations / "en.json").write_bytes(data)
    inventory["custom_components/hearth/translations/en.json"] = hashlib.sha256(data).hexdigest()
    backend = destination / "_backend"
    backend.mkdir()
    for name in BACKEND_FILES:
        data = isolated_source((ROOT / "backend" / name).read_bytes())
        (backend / name).write_bytes(data)
        inventory["custom_components/hearth/_backend/" + name] = hashlib.sha256(data).hexdigest()
    for name in ("LICENSE", "THIRD_PARTY.md"):
        data = (ROOT / name).read_bytes()
        (destination / name).write_bytes(data)
        inventory["custom_components/hearth/" + name] = hashlib.sha256(data).hexdigest()
    (output / "source-manifest.json").write_text(
        json.dumps(
            {"format": "hearth-native-ha-source-v1", "files": inventory}, sort_keys=True, indent=2
        )
        + "\n"
    )
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    args = parser.parse_args()
    package(args.output)
