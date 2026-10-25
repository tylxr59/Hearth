"""Fetch only pinned research sources into an exclusive directory; never execute them."""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


def fetch(output):
    project = Path(__file__).resolve().parents[1]
    lock = json.loads((project / "docs/research/upstreams.json").read_text())
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for name, entry in lock.items():
        repository = entry["repository"].removeprefix("https://github.com/")
        for relative, expected in entry["files"].items():
            url = f"https://raw.githubusercontent.com/{repository}/{entry['revision']}/{relative}"
            # URLs originate in the reviewed, checked-in lockfile, never in a request.
            with urllib.request.urlopen(url, timeout=30) as response:  # nosec B310
                data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("research source digest mismatch")
            target = output / name / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    fetch(parser.parse_args().output)
