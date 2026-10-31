"""Inspect a user-owned unpacked root without executing or shipping its contents.

Produces a reproducible inert change plan, NOT a flashable firmware image.
"""

import argparse
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

from backend.validation import Invalid
from provisioning.cli import endpoint

FILES = ("etc/init.d/rcS", "etc/nestlabs/client.config", "etc/shadow", "etc/monitrc")


def read_regular(root, relative):
    path = root / relative
    # No symlinks in any component; never follow a firmware link onto the host.
    current = root
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink():
            raise Invalid("symlink in input")
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise Invalid("missing or oversized input file: " + relative)
    return path.read_bytes()


def build(root, output, expected, origin):
    root, output = Path(root), Path(output)
    if root.is_symlink() or not root.is_dir():
        raise Invalid("unpacked root directory required")
    origin = endpoint(origin)
    inputs = {name: read_regular(root, name) for name in FILES}
    actual = {name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()}
    if actual != expected:
        raise Invalid("input digest mismatch; explicitly review and pin the root first")
    config = inputs["etc/nestlabs/client.config"].decode("utf-8")
    pattern = r'(<a\s+key="cloudregisterurl"\s+value=")[^"]*(")'
    config, count = re.subn(pattern, lambda m: m[1] + origin + "/nest/entry" + m[2], config)
    if count != 1:
        raise Invalid("expected exactly one known cloudregisterurl")
    # Candidate diff only, never include proprietary input file contents in archive.
    lines = inputs["etc/init.d/rcS"].decode().splitlines()
    unsafe = [
        {"line": index, "service": match.group(0)}
        for index, line in enumerate(lines, 1)
        if not line.lstrip().startswith("#")
        and (match := re.search(r"\b(nleapi|dropbear|sshconnect|rootme)\b", line))
    ]
    plan = {
        "format": 1,
        "status": "inert-review-only",
        "input_sha256": actual,
        "candidate_edits": [
            {
                "path": "etc/nestlabs/client.config",
                "key": "cloudregisterurl",
                "value": origin + "/nest/entry",
            },
            {"path": "etc/nestlabs/client.config", "key": "uploadlogs", "value": "0"},
            {"path": "etc/shadow", "operation": "lock root password"},
        ],
        "candidate_rcS_lines_to_disable": unsafe,
        "candidate_paths_to_disable": [
            "etc/init.d/nleapi",
            "etc/monit.d/httpd.monitrc",
            "var/www/cgi-bin",
            "etc/init.d/sshconnect",
        ],
        "preserve": ["nlclient", "osm", "nlscpmd", "backplate firmware", "watchdog", "drivers"],
        "blockers": [
            "no hardware profile verified",
            "no complete cloud protocol adapter",
            "no credential install API verified",
            "no kernel isolation verified",
            "no apply, flash or executable update interface provided",
        ],
    }
    payloads = {
        "plan.json": (json.dumps(plan, sort_keys=True, indent=2) + "\n").encode(),
        "DO-NOT-FLASH.txt": b"Inert review bundle. No bootloader, kernel, secrets or firmware.\n",
    }
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}
    payloads["SHA256SUMS"] = "".join(
        f"{value}  {name}\n" for name, value in sorted(hashes.items())
    ).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with (
        output.open("xb") as stream,
        tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive,
    ):
        for name, data in sorted(payloads.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o600, 0
            info.uid = info.gid = 0
            archive.addfile(info, io.BytesIO(data))
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(
        build(
            args.root, args.output, json.loads(Path(args.input_manifest).read_text()), args.endpoint
        )
    )


if __name__ == "__main__":
    main()
