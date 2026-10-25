"""Generate private, offline replacement files for manual review; never apply to a device."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from backend.validation import Invalid
from firmware.prepare import FILES, read_regular
from provisioning.cli import endpoint

DISABLE = re.compile(
    r"(?:\$\{INITDIR\}|/etc/init.d)/(?:nleapi|rootme|sshconnect)(?: start)?|"
    r"/bin/(?:dropbear|sshconnect)"
)


def stage(root, output, expected, origin):
    root, output = Path(root), Path(output)
    if root.is_symlink() or not root.is_dir():
        raise Invalid("input directory required")
    origin = endpoint(origin)
    inputs = {name: read_regular(root, name) for name in FILES}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()}
    if hashes != expected:
        raise Invalid("input digest mismatch")
    changed = {}
    removed = []
    lines = []
    for line in inputs[FILES[0]].decode().splitlines():
        if DISABLE.fullmatch(line.strip()):
            removed.append(line)
        else:
            # Refuse ambiguous shell constructs rather than disabling unknown services.
            if not line.lstrip().startswith("#") and re.search(
                r"\b(nleapi|dropbear|sshconnect|rootme)\b", line
            ):
                raise Invalid("unrecognized service invocation; manual analysis required")
            lines.append(line)
    changed[FILES[0]] = "\n".join(lines) + "\n"
    config = inputs[FILES[1]].decode()
    changed[FILES[1]], count = re.subn(
        r'(<a\s+key="cloudregisterurl"\s+value=")[^"]*(")',
        lambda match: match[1] + origin + "/nest/entry" + match[2],
        config,
    )
    if count != 1:
        raise Invalid("exactly one cloudregisterurl required")
    shadow, count = re.subn(
        r"^root:[^:\n]*:", "root:!:", inputs[FILES[2]].decode(), flags=re.MULTILINE
    )
    if count != 1:
        raise Invalid("exactly one root account required")
    changed[FILES[2]] = shadow
    changed[FILES[3]] = (
        "\n".join(
            line
            for line in inputs[FILES[3]].decode().splitlines()
            if line.strip() != "include /etc/monit.d/httpd.monitrc"
        )
        + "\n"
    )
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, content in changed.items():
        target = output / "replacement-files" / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with target.open("x") as stream:
            target.chmod(0o600)
            stream.write(content)
    manifest = {
        "status": "offline-review-only-not-bootable",
        "input_sha256": hashes,
        "intended_target_modes": {
            FILES[0]: "0755",
            FILES[1]: "0600",
            FILES[2]: "0600",
            FILES[3]: "0644",
        },
        "replacement_sha256": {
            name: hashlib.sha256(content.encode()).hexdigest() for name, content in changed.items()
        },
        "disabled_rcS_lines": removed,
        "remove_before_any_deployment": [
            "etc/init.d/nleapi",
            "etc/monit.d/httpd.monitrc",
            "var/www/cgi-bin",
        ],
        "warning": "Not a complete runtime lockdown. No credential/TLS install or flash support.",
    }
    (output / "changes.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    (output / "DO-NOT-FLASH").write_text(
        "Review partial replacements only. See docs/hardware.md.\n"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    stage(args.root, args.output, json.loads(Path(args.input_manifest).read_text()), args.endpoint)


if __name__ == "__main__":
    main()
