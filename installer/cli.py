"""Guided install/restore frontend. No downloaded scripts or automatic retry."""

import argparse
import getpass
import json
import shutil
import subprocess  # nosec B404
import sys
import threading
from pathlib import Path

from backend.validation import Invalid
from firmware.file_writer import run as writer
from firmware.harden import client_config
from firmware.tls_probe.package import private_read
from installer.bundle import device_info, read_bundle
from provisioning.intake import MAX_INFO_BYTES, usb_inventory
from provisioning.native_settings import assigned_credentials
from tools.elf_review import PRIVATE, private_path


def inspect_disk(disk):
    path = Path(disk)
    if (
        path.parent != Path("/dev")
        or not path.name
        or path.is_symlink()
        or not path.is_block_device()
    ):
        raise Invalid("direct /dev block-device path required")
    result = subprocess.run(  # nosec B603 B607
        ["mtype", "-i", str(path), "::/Technical Info.plist"],
        capture_output=True,
        timeout=10,
        check=True,
    )
    if len(result.stdout) > MAX_INFO_BYTES:
        raise Invalid("diagnostic plist too large")
    return result.stdout


def supported_kit(profile, recovery, bundle):
    record, binding = writer.checked_pair(profile, recovery)
    if binding.action != 1:
        raise Invalid("install action and matching restore image required")
    capsule = Path(record["capsule"])
    settings = private_read(capsule / "7.replacement", 1024 * 1024)
    # The prepared image must ALREADY contain exactly this user's credential.
    if assigned_credentials(settings, bundle["serial"], bundle["credential"]) != settings:
        raise Invalid("prepared installer credentials do not match commissioning bundle")
    if (
        private_read(capsule / "1.replacement", 65536) != bundle["_ca"]
        or private_read(capsule / "2.replacement", 65536) != bundle["_crl"]
    ):
        raise Invalid("prepared installer trust differs from commissioning bundle")
    client = private_read(capsule / "8.replacement", 1024 * 1024)
    if client_config(client.decode("utf-8"), bundle["origin"]).encode("utf-8") != client:
        raise Invalid("prepared local endpoint or log setting differs from commissioning bundle")
    return record, binding


def execute(profile, recovery, output, *, restore=False, ask=input, engine=writer):
    """Run one checked preflight, then ask separately before one scoped commit."""
    profile, recovery, output = map(private_path, (profile, recovery, output))
    _record, binding = engine.checked_pair(profile, recovery)
    if binding.action != (2 if restore else 1):
        raise Invalid("requested action differs from image")
    if output.exists():
        raise Invalid("fresh output session required")
    print(
        "Detach the display from its base; keep USB connected. Whole-firmware recovery is unverified."
    )
    if ask("Type READY to arm one RAM preflight: ").strip() != "READY":
        return {"cancelled": True, "device_executed": False}
    result, failures = [], []

    def worker():
        try:
            result.append(engine.run(profile, recovery, output, execute=True))
        except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
            failures.append(type(exc).__name__)

    thread = threading.Thread(target=worker, daemon=False)
    thread.start()
    print(
        "When the loader says scanning: hold the ring for 10 seconds, release, then press/release once."
    )
    decided = False
    try:
        while thread.is_alive():
            if not decided and (output / "preflight.json").exists():
                phrase = "RESTORE" if restore else "INSTALL"
                print(
                    "RAM checks and real-file preflight passed. The next decision writes NAND. Keep USB connected."
                )
                answer = ask(f"Type {phrase} to write, or press Enter to abort: ").strip()
                engine.decide(output, commit=answer == phrase, expected_action=binding.action)
                decided = True
            thread.join(0.2)
    except (KeyboardInterrupt, EOFError):
        if not decided and (output / "preflight.json").exists():
            engine.decide(output, commit=False, expected_action=binding.action)
        print("Waiting for the bounded device session to exit; keep USB connected.")
        thread.join()
    if failures or not result:
        print(
            "Session incomplete. Preserve this private session and keep USB connected; do not retry or assume restart is safe."
        )
        return {
            "complete": False,
            "safe_to_restart": False,
            "error_type": failures[0] if failures else "interrupted",
        }
    outcome = result[0]
    if outcome.get("safe_to_restart"):
        print(
            "Device report says safe to restart. Hold 10 seconds, release, then press/release once."
        )
    else:
        print(
            "Restart safety is unconfirmed. Keep USB connected and preserve the session for recovery review."
        )
    return outcome


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hearth", description="Hearth guided Linux USB installer")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    fetch_sources = commands.add_parser("sources")
    fetch_sources.add_argument("--output", type=Path, required=True)
    build_reader = commands.add_parser("build-reader")
    build_reader.add_argument("--sources", type=Path, required=True)
    build_reader.add_argument("--output", type=Path, required=True)
    build_reader.add_argument("--profile", type=Path, required=True)
    fetch = commands.add_parser("download")
    fetch.add_argument("--ha-url", required=True)
    fetch.add_argument("--output", type=Path, required=True)
    identify = commands.add_parser("identify")
    identify.add_argument("--disk")
    identify.add_argument("--info", type=Path)
    identify.add_argument("--show-device-id", action="store_true")
    setup = commands.add_parser("setup")
    setup.add_argument("--bundle", type=Path, required=True)
    setup.add_argument("--info", type=Path, required=True)
    setup.add_argument("--session", type=Path, required=True)
    install = commands.add_parser("install")
    install.add_argument("--session", type=Path, required=True)
    install.add_argument("--profile", type=Path, required=True)
    install.add_argument("--restore-profile", type=Path, required=True)
    install.add_argument("--disk", required=True)
    acquire = commands.add_parser("acquire")
    acquire.add_argument("--session", type=Path, required=True)
    acquire.add_argument("--profile", type=Path, required=True)
    acquire.add_argument("--disk", required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--profile", type=Path, required=True)
    restore.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            print(
                json.dumps(
                    {
                        "platform": sys.platform,
                        "commands": {
                            name: shutil.which(name) is not None
                            for name in (
                                "mtype",
                                "podman",
                                "openssl",
                                "cc",
                                "clang",
                                "git",
                                "patch",
                                "pkg-config",
                            )
                        },
                        "usb": usb_inventory(),
                        "supported_host": sys.platform.startswith("linux"),
                    },
                    indent=2,
                )
            )
        elif args.command == "sources":
            from installer.sources import fetch

            print(json.dumps(fetch(args.output), indent=2))
        elif args.command == "build-reader":
            from installer.build import build

            print(json.dumps(build(args.sources, args.output, args.profile), indent=2))
        elif args.command == "download":
            from installer.download import download

            token = getpass.getpass("HA administrator access token (hidden): ")
            download(args.ha_url, token, args.output.absolute())
            print("Private commissioning bundle downloaded and validated.")
        elif args.command == "identify":
            raw = args.info.read_bytes() if args.info else inspect_disk(args.disk or "")
            value = device_info(raw)
            if not args.show_device_id:
                value.pop("serial")
            print(json.dumps(value, indent=2))
        elif args.command == "setup":
            bundle, ca, crl = read_bundle(args.bundle.read_bytes())
            info = device_info(args.info.read_bytes(), bundle)
            session = private_path(args.session)
            PRIVATE.mkdir(mode=0o700, exist_ok=True)
            if PRIVATE.stat().st_mode & 0o077:
                raise Invalid("private session parent permissions required")
            session.mkdir(mode=0o700)
            writer.save(session, "commissioning.zip", args.bundle.read_bytes())
            writer.save(session, "identity.json", writer.encode(info))
            print(
                "Device and commissioning bundle match. Session prepared; no USB opened or firmware written."
            )
        elif args.command in ("install", "acquire"):
            session = private_path(args.session)
            bundle, ca, crl = read_bundle(private_read(session / "commissioning.zip", 65536))
            info = json.loads(private_read(session / "identity.json", MAX_INFO_BYTES))
            if info["serial"] != bundle["serial"]:
                raise Invalid("session identity differs from commissioning bundle")
            device_info(inspect_disk(args.disk), bundle)
            if args.command == "acquire":
                from firmware.acquisition import profile as acquisition_profile
                from firmware.acquisition.run import run as acquire_inputs

                acquisition_profile.check(args.profile)
                print(
                    "Detach the display from its base; keep USB connected. This RAM reader cannot write flash."
                )
                if input("Type READY to arm one read-only acquisition: ").strip() != "READY":
                    print("Cancelled; no loader started.")
                    return 0
                print(
                    "When the loader says scanning: hold the ring for 10 seconds, release, then press/release once."
                )
                result = acquire_inputs(args.profile, session / "acquisition", execute=True)
                print(json.dumps(result, indent=2))
                print(
                    "Acquisition exited. Hold 10 seconds, release, then press/release once to return to native startup."
                )
                return 0
            supported_kit(args.profile, args.restore_profile, bundle | {"_ca": ca, "_crl": crl})
            outcome = execute(args.profile, args.restore_profile, session / "install-attempt")
            if not outcome.get("complete"):
                return 1
        else:
            outcome = execute(args.profile, args.profile, args.output, restore=True)
            if not outcome.get("complete"):
                return 1
    except (Invalid, ValueError, OSError, subprocess.SubprocessError):
        print(
            "Hearth refused this operation. Check supported device/version, private inputs, permissions and matching backup/restore profiles. No automatic retry.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
