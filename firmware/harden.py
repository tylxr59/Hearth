"""Generate private, offline replacement files for manual review; never apply to a device."""

import argparse
import hashlib
import json
import re
from pathlib import Path

# Input is bounded and DTD/entity handlers reject declarations before expansion.
from xml.parsers import expat  # nosec B407

from backend.validation import Invalid
from firmware.prepare import FILES, read_regular
from provisioning.cli import endpoint

DISABLE = re.compile(
    r"(?:\$\{INITDIR\}|/etc/init.d)/(?:nleapi|rootme|sshconnect)(?: start)?|"
    r"/bin/(?:dropbear|sshconnect)"
)


def client_config(config, origin):
    """Edit only reviewed XML value spans; preserve all other source bytes."""
    origin = endpoint(origin)
    data = config.encode("utf-8")
    if len(data) > 1024 * 1024:
        raise Invalid("oversized client config")
    targets = {
        "cloudregisterurl": (("config", "cloud", "a"), origin + "/nest/entry"),
        "uploadlogs": (("config", "a"), "0"),
    }
    parser = expat.ParserCreate("UTF-8")
    stack, edits, seen = [], [], set()

    def reject(*args):
        raise Invalid("client config DTDs and entities are unsupported")

    def declaration(version, encoding, standalone):
        if version != "1.0" or (encoding and encoding.lower() != "utf-8"):
            raise Invalid("client config must use XML 1.0 and UTF-8")

    def start(name, attrs):
        stack.append(name)
        if len(stack) > 64:
            raise Invalid("client config nesting limit exceeded")
        key = attrs.get("key")
        if key not in targets:
            return
        path, value = targets[key]
        if key in seen or tuple(stack) != path or set(attrs) != {"key", "value"}:
            raise Invalid("ambiguous client config setting: " + key)
        if key == "uploadlogs" and attrs["value"] not in ("0", "1"):
            raise Invalid("unsupported uploadlogs value")
        seen.add(key)
        offset = parser.CurrentByteIndex
        tag = re.match(rb"""<a\b(?:[^"'<>]|"[^"]*"|'[^']*')*/>""", data[offset:])
        if tag is None:
            raise Invalid("reviewed self-closing config entry required")
        match = re.search(rb"""\bvalue\s*=\s*(["'])(.*?)\1""", tag[0], re.DOTALL)
        if match is None:
            raise Invalid("literal config value attribute required")
        edits.append((offset + match.start(2), offset + match.end(2), value.encode()))

    parser.StartDoctypeDeclHandler = reject
    parser.XmlDeclHandler = declaration
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.StartElementHandler = start
    parser.EndElementHandler = lambda name: stack.pop()
    try:
        parser.Parse(data, True)
    except expat.ExpatError as exc:
        raise Invalid("invalid client config XML") from exc
    if seen != targets.keys():
        raise Invalid("cloudregisterurl and uploadlogs entries required")
    for begin, end, value in sorted(edits, reverse=True):
        data = data[:begin] + value + data[end:]
    return data.decode("utf-8")


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
    changed[FILES[1]] = client_config(inputs[FILES[1]].decode(), origin)
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
        "disabled_config_keys": ["uploadlogs"],
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
