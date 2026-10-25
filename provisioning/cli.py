"""Offline Linux provisioning preparation. Intentionally no flash/apply operation."""

import argparse
import ipaddress
import json
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from backend.registry import Registry, private_json
from backend.validation import Invalid, serial


def endpoint(value):
    parsed = urlsplit(value)
    try:
        port = parsed.port
        address = ipaddress.ip_address(parsed.hostname or "")
    except ValueError as exc:
        raise Invalid("endpoint must use a literal private IPv4 address") from exc
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or not port
        or address.version != 4
        or not (address.is_private and not address.is_unspecified and not address.is_multicast)
    ):
        raise Invalid("HTTPS endpoint with explicit port and private IPv4 required")
    return f"https://{address}:{port}"


def prepare(registry_path, output, ident, generation, origin, modes, fan=False, rotate=False):
    serial(ident)
    if generation not in (1, 2):
        raise Invalid("unsupported generation")
    origin = endpoint(origin)
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    token = secrets.token_hex(32)
    registry = Registry(registry_path)
    caps = {"modes": modes, "fan": fan}
    # Export recovery-sensitive material only into this private, exclusive directory.
    private_json(
        output / "device.json",
        {"serial": ident, "credential": token, "endpoint": origin, "capabilities": caps},
    )
    registry.register(ident, token, caps, rotate=rotate)
    report = {
        "serial": ident,
        "generation_claim": generation,
        "endpoint": origin,
        "status": "prepared-only",
        "hardware_detected": False,
        "credential_registered": True,
        "credential_installed": False,
        "services_verified": False,
        "flashed": False,
        "blockers": [
            "USB ROM identity does not prove generation",
            "client credential installation and TLS compatibility unverified",
            "verified backup, recovery and physical authorization required",
        ],
    }
    private_json(output / "report.json", report)
    return report


def usb_inventory(sysfs=Path("/sys/bus/usb/devices")):
    result = []
    for path in sorted(Path(sysfs).glob("*")):
        try:
            vendor, product = (
                (path / "idVendor").read_text().strip(),
                (path / "idProduct").read_text().strip(),
            )
        except (OSError, UnicodeError):
            continue
        if vendor == "0451":
            result.append(
                {
                    "bus_path": path.name,
                    "vendor": vendor,
                    "product": product,
                    "generation": "unknown",
                    "compatible": False,
                    "note": "TI USB identity alone cannot establish Nest compatibility",
                }
            )
    return result


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init")
    init.add_argument("--registry", required=True)
    init.add_argument("--admin-file", required=True)
    rotate_admin = sub.add_parser("rotate-admin")
    rotate_admin.add_argument("--registry", required=True)
    rotate_admin.add_argument("--output", required=True)
    sub.add_parser("detect")
    prep = sub.add_parser("prepare")
    prep.add_argument("--registry", required=True)
    prep.add_argument("--output", required=True)
    prep.add_argument("--serial", required=True)
    prep.add_argument("--generation", type=int, choices=[1, 2], required=True)
    prep.add_argument("--endpoint", required=True)
    prep.add_argument(
        "--modes", nargs="+", choices=["off", "heat", "cool"], default=["off", "heat"]
    )
    prep.add_argument("--fan", action="store_true")
    prep.add_argument("--rotate", action="store_true")
    revoke = sub.add_parser("revoke")
    revoke.add_argument("--registry", required=True)
    revoke.add_argument("--serial", required=True)
    args = parser.parse_args()
    try:
        if args.action == "init":
            Registry.initialize(args.registry, args.admin_file)
        elif args.action == "prepare":
            prepare(
                args.registry,
                args.output,
                args.serial,
                args.generation,
                args.endpoint,
                args.modes,
                args.fan,
                args.rotate,
            )
        elif args.action == "rotate-admin":
            Registry(args.registry).rotate_admin(args.output)
        elif args.action == "revoke":
            Registry(args.registry).revoke(serial(args.serial))
        else:
            print(json.dumps(usb_inventory(), indent=2))
    except (Invalid, OSError) as exc:
        parser.exit(1, f"Preparation failed: {exc}\n")


if __name__ == "__main__":
    main()
