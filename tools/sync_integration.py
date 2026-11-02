"""Keep HACS's self-contained transport generated from canonical public source."""

import argparse

from tools.package_native_ha import BACKEND_FILES, ROOT, isolated_source


def sync(check=False):
    destination = ROOT / "custom_components/hearth/_backend"
    expected = {
        name: isolated_source((ROOT / "backend" / name).read_bytes()) for name in BACKEND_FILES
    }
    actual = (
        {p.name: p.read_bytes() for p in destination.glob("*.py")} if destination.exists() else {}
    )
    translation = ROOT / "custom_components/hearth/translations/en.json"
    english = (ROOT / "custom_components/hearth/strings.json").read_bytes()
    if check:
        if not translation.is_file() or translation.read_bytes() != english:
            raise ValueError("English translation differs from canonical strings")
        if actual != expected:
            raise ValueError(
                "generated HACS transport differs; run python -m tools.sync_integration"
            )
        return
    translation.parent.mkdir(exist_ok=True)
    translation.write_bytes(english)
    destination.mkdir(exist_ok=True)
    for path in destination.glob("*.py"):
        if path.name not in expected:
            path.unlink()
    for name, data in expected.items():
        (destination / name).write_bytes(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    sync(parser.parse_args().check)
