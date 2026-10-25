"""Create synthetic inputs and inspectable artifacts. Contains no Nest firmware."""

import hashlib
import json
from pathlib import Path

from firmware.harden import stage
from firmware.prepare import build


def demo(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    root = output / "synthetic-root"
    files = {
        "etc/init.d/rcS": "#!/bin/sh\n${INITDIR}/nestlabs start\n${INITDIR}/nleapi start\n/bin/dropbear\n",
        "etc/nestlabs/client.config": '<config><a key="cloudregisterurl" value="https://invalid.example/entry"/></config>\n',
        "etc/shadow": "root:synthetic-placeholder:1:0:99999:7:::\n",
        "etc/monitrc": "include /etc/monit.d/*\ninclude /etc/monit.d/httpd.monitrc\n",
    }
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
    hashes = {name: hashlib.sha256(data.encode()).hexdigest() for name, data in files.items()}
    (output / "input-manifest.json").write_text(json.dumps(hashes, sort_keys=True, indent=2) + "\n")
    origin = "https://192.168.50.2:8443"
    digest = build(root, output / "review.tar", hashes, origin)
    stage(root, output / "offline-replacements", hashes, origin)
    (output / "SHA256SUMS").write_text(f"{digest}  review.tar\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    demo(parser.parse_args().output)
