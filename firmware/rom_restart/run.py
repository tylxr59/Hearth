"""Explicit supervised experiment; never imported or enabled by the setup wizard."""

import argparse
import json
import os
import select
import subprocess  # nosec B404
import time

from firmware.file_writer.run import encode, save, write_token
from firmware.probe import port as usb_port
from firmware.probe.observe import require_native
from firmware.rom_restart import profile
from firmware.settings_compat_probe.observe import observe
from firmware.tls_probe.package import private_read
from installer import ui
from tools.elf_review import private_path


def run(root, output, *, ask=input):
    root, output = private_path(root), private_path(output)
    profile.check(root)
    if not os.isatty(0) or not os.isatty(1):
        raise ValueError("owner-supervised PTY required")
    if output.exists() or (root / "execution-started.json").exists():
        raise ValueError("fresh one-use profile and private output required")
    require_native(usb_port.current())
    ui.say(
        "This experiment boots a read-only RAM image, then tries one normal Linux warm restart without a ring press. It may return to stock startup instead of USB boot mode. Stock startup can write its usual settings/logs; whole-firmware and power-loss recovery remain unverified. Keep the display detached from its wired HVAC base and USB connected."
    )
    if not ui.confirm(ask, "Ready to arm the loader for one owner-timed boot?"):
        return {"cancelled": True}
    output.mkdir(mode=0o700)
    row = json.loads(private_read(root / "profile.json", 65536))
    execution = {"profile": str(root), "session": row["session"], "once": True}
    save(root, "execution-started.json", encode(execution))
    save(output, "execution.json", encode(execution))
    a = root / "artifacts"
    ui.action(
        "The loader is starting. When it reports scanning for USB device, hold the ring for 10 seconds, release it, then press it once. Do not press the ring after the RAM image connects."
    )
    try:
        subprocess.run(
            [
                str(a / "omap_loader"),
                "-P",
                usb_port.current(),
                "-f",
                str(a / "x-load-gen2.bin"),
                "-f",
                str(a / "u-boot.bin"),
                "-a",
                "0x80100000",
                "-f",
                str(a / "uImage"),
                "-a",
                "0x80a00000",
                "-j",
                "0x80100000",
            ],
            check=True,
            timeout=90,
        )  # nosec B603

        def collect(fd, deadline, _capture):
            nonce = bytes.fromhex(row["session"])
            buffer = b""
            while time.monotonic() < deadline:
                if not select.select([fd], [], [], 0.1)[0]:
                    continue
                chunk = os.read(fd, 4096)
                if not chunk:
                    raise OSError("RAM experiment disconnected before readiness")
                buffer = (buffer + chunk)[-8192:]
                if b"HROMRDY1" + nonce in buffer:
                    break
            else:
                raise TimeoutError("no nonce-bound RAM readiness; no retry")
            save(output, "ram-ready.json", encode({"nonce_verified": True}))
            if not ui.confirm(
                ask,
                "RAM image is ready. Trigger the single warm restart now, without touching the ring?",
            ):
                return {"cancelled": True, "restart_sent": False}
            profile.check(root)
            save(output, "restart-sending.json", encode({"once": True}))
            write_token(fd, b"HROMRST1" + nonce)
            save(output, "restart-sent.json", encode({"once": True}))
            end = time.monotonic() + 30
            saw_disconnect = False
            usb = usb_port.SYSFS / usb_port.current()
            while time.monotonic() < end:
                try:
                    identity = tuple(
                        (usb / n).read_text().strip() for n in ("idVendor", "idProduct")
                    )
                except OSError:
                    saw_disconnect = True
                    time.sleep(0.02)
                    continue
                if identity == ("0451", "d00e"):
                    return {
                        "restart_sent": True,
                        "rom_usb_observed": True,
                        "native_usb_observed": False,
                        "second_image_loaded": False,
                    }
                if identity == ("2464", "0002"):
                    return {
                        "restart_sent": True,
                        "rom_usb_observed": False,
                        "native_usb_observed": True,
                        "second_image_loaded": False,
                    }
                time.sleep(0.02)
            return {
                "restart_sent": True,
                "rom_usb_observed": False,
                "native_usb_observed": False,
                "usb_disconnected": saw_disconnect,
                "second_image_loaded": False,
            }

        def collect_and_preserve(fd, deadline, capture):
            result = collect(fd, deadline, capture)
            # Preserve the observation before serial cleanup, which can race
            # the expected USB disconnect during a successful warm reset.
            save(output, "device-observation.json", encode(result))
            return result

        result = observe(usb_port.current(), 120, receive_fn=collect_and_preserve)
        save(output, "observed.json", encode(result))
        return result
    finally:
        save(output, "finished.json", encode({"host_command_exited": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    parser.add_argument("output")
    args = parser.parse_args()
    run(args.profile, args.output)
