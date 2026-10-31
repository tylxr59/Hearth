"""Offline Linux provisioning preparation. Intentionally no flash/apply operation."""

import argparse
import json
import secrets
import sys
from pathlib import Path

from backend.registry import Registry, private_json
from backend.validation import Invalid, endpoint, serial
from provisioning.intake import MAX_INFO_BYTES, inspect_info, usb_events, usb_inventory


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


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init")
    init.add_argument("--registry", required=True)
    init.add_argument("--admin-file", required=True)
    rotate_admin = sub.add_parser("rotate-admin")
    rotate_admin.add_argument("--registry", required=True)
    rotate_admin.add_argument("--output", required=True)
    detect = sub.add_parser("detect")
    detect.add_argument("--watch", type=int, choices=range(1, 301), metavar="SECONDS")
    sub.add_parser("inspect-info", help="read a plist from stdin; emit allowlisted metadata only")
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
        elif args.action == "inspect-info":
            print(json.dumps(inspect_info(sys.stdin.buffer.read(MAX_INFO_BYTES + 1)), indent=2))
        elif args.watch:
            for event in usb_events(args.watch):
                print(json.dumps(event), flush=True)
        else:
            print(json.dumps(usb_inventory(), indent=2))
    except (Invalid, OSError) as exc:
        parser.exit(1, f"Preparation failed: {exc}\n")


if __name__ == "__main__":
    main()
