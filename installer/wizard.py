"""One owner-guided path from USB to HACS and a checked private install kit."""

import errno
import getpass
import json
import os
import pty
import select
import shutil
import subprocess  # nosec B404
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from backend.validation import Invalid
from firmware.file_writer.run import encode, save
from firmware.tls_probe.package import private_read
from installer import discovery, onboard, workflow
from installer.bundle import device_info, read_bundle
from installer.sources import ROOT
from provisioning.time_server import DEFAULT, time_server
from tools.elf_review import PRIVATE

REPOSITORY = "https://github.com/tylxr59/Hearth"
RESTART = "Hold the ring for 10 seconds, release, then press and release once."


def choose_time(ask=input):
    while True:
        try:
            return time_server(ask(f"Time server [{DEFAULT}]: ").strip() or DEFAULT)
        except Invalid as exc:
            print(str(exc))


def prerequisites():
    if sys.platform != "linux" or os.getuid() == 0:
        raise Invalid("Run this wizard as your normal user on Linux, not with sudo.")
    names = ("podman", "git", "clang", "ld.lld", "cc", "patch", "pkg-config", "mtype", "setfacl")
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        os_name = Path("/etc/os-release").read_text() if Path("/etc/os-release").exists() else ""
        system = next(
            (line for line in os_name.splitlines() if line.startswith("PRETTY_NAME=")), "Linux"
        )
        print(f"This computer: {system.removeprefix('PRETTY_NAME=').strip(chr(34))}")
        print("Install these prerequisites through your distribution: " + ", ".join(missing))
        print(
            "mtype is supplied by mtools; setfacl by acl; also install libusb development headers."
        )
        raise Invalid("Install the listed prerequisites, then launch this wizard again.")
    try:
        subprocess.run(  # nosec B603 B607
            ["pkg-config", "--exists", "libusb-1.0"], check=True, timeout=10
        )
    except subprocess.SubprocessError:
        raise Invalid(
            "Install your distribution's libusb development headers, then restart setup."
        ) from None
    from installer.build import require_engine

    require_engine()


def usb_access(folder, ask=input):
    """Explicitly install a root-managed rule for current UID and measured USB port."""
    from installer.workflow import identity

    if identity() != "native":
        raise Invalid("Connect a single Nest in its normal USB mode before starting.")
    acl = Path(shutil.which("setfacl") or "")
    if not acl.is_absolute() or any(
        c not in "/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for c in str(acl)
    ):
        raise Invalid("A standard absolute setfacl executable path is required.")
    uid = os.getuid()
    rules = (
        f'ACTION=="add", SUBSYSTEM=="usb", ENV{{DEVTYPE}}=="usb_device", KERNEL=="1-1", '
        f'ATTR{{idVendor}}=="0451", ATTR{{idProduct}}=="d00e", MODE="0600", '
        f'RUN+="{acl} -m u:{uid}:rw $env{{DEVNAME}}"\n'
        f'ACTION=="add", SUBSYSTEM=="tty", KERNEL=="ttyACM[0-9]*", KERNELS=="1-1", '
        f'ATTRS{{idVendor}}=="0525", ATTRS{{idProduct}}=="a4a7", MODE="0600", '
        f'RUN+="{acl} -m u:{uid}:rw $env{{DEVNAME}}"\n'
    ).encode()
    target = Path("/etc/udev/rules.d/70-hearth-wizard.rules")
    if target.is_symlink():
        raise Invalid("The USB rule must not be a symlink.")
    if target.exists():
        stat = target.lstat()
        if (
            target.is_symlink()
            or stat.st_uid != 0
            or stat.st_mode & 0o022
            or target.read_bytes() != rules
        ):
            raise Invalid(
                "An existing Hearth USB rule differs; review it rather than replacing it."
            )
        return
    print(
        "The wizard needs access to Nest boot USB and its temporary report interface on port 1-1."
    )
    print("This local rule grants only your account access. It grants no disk write access.")
    if (
        ask("Type USB ACCESS to install the rule with sudo, or Enter to stop: ").strip()
        != "USB ACCESS"
    ):
        raise Invalid("USB access setup cancelled; no loader started.")
    source = folder / "70-hearth-wizard.rules"
    save(folder, source.name, rules)
    subprocess.run(  # nosec B603 B607
        [
            "sudo",
            "--",
            "install",
            "-o",
            "root",
            "-g",
            "root",
            "-m",
            "0644",
            "-T",
            str(source),
            str(target),
        ],
        check=True,
        timeout=60,
    )
    subprocess.run(  # nosec B603 B607
        ["sudo", "--", "udevadm", "control", "--reload-rules"], check=True, timeout=60
    )


class Worker:
    def __init__(self, folder, build, *, ask=input):
        self.folder, self.build, self.ask = folder, build, ask

    def run(self, operation, *, engine=None, binding=None, **values):
        request = {
            "operation": operation,
            "session": str(self.folder),
            "build": str(self.build),
        } | values
        save(self.folder, operation + "-request.json", encode(request))
        master, slave = pty.openpty()
        process = None
        decided = False
        cancelled = False
        scan_seen = False
        pending = b""
        last = time.monotonic()
        try:
            with (self.folder / (operation + ".log")).open("xb") as log:
                os.chmod(log.name, 0o600)
                process = subprocess.Popen(  # nosec B603
                    [
                        sys.executable,
                        "-u",
                        "-m",
                        "installer.wizard_worker",
                        str(self.folder / (operation + "-request.json")),
                    ],
                    cwd=ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=slave,
                    stderr=slave,
                    start_new_session=True,
                )
                os.close(slave)
                slave = -1
                while True:
                    try:
                        ready, _, _ = select.select([master], [], [], 0.2)
                        if ready:
                            try:
                                data = os.read(master, 8192)
                            except OSError as exc:
                                if exc.errno != errno.EIO:
                                    raise
                                data = b""
                            if data:
                                log.write(data)
                                log.flush()
                                pending = (pending + data)[-16384:]
                                if not scan_seen and b"scanning for USB device" in pending:
                                    scan_seen = True
                                    print("The loader is waiting now. " + RESTART)
                                    print("Leave USB connected and the base detached afterward.")
                        if (
                            engine
                            and not decided
                            and (Path(values["output"]) / "preflight.json").exists()
                        ):
                            print(
                                "The RAM tests and original-file checks passed. The next step writes thermostat files."
                            )
                            print("Keep USB connected. Whole-firmware recovery remains unverified.")
                            commit = not cancelled and (
                                self.ask(
                                    "Type INSTALL to write this phase, or Enter to abort: "
                                ).strip()
                                == "INSTALL"
                            )
                            engine.decide(
                                Path(values["output"]),
                                commit=commit,
                                expected_action=binding.action,
                            )
                            decided = True
                        if process.poll() is not None and not ready:
                            break
                        if process.poll() is not None and ready and not data:
                            break
                        if time.monotonic() - last >= 20:
                            print("Still working; detailed output is saved privately.")
                            last = time.monotonic()
                    except (KeyboardInterrupt, EOFError):
                        cancelled = True
                        if (
                            engine
                            and not decided
                            and (Path(values["output"]) / "preflight.json").exists()
                        ):
                            engine.decide(
                                Path(values["output"]), commit=False, expected_action=binding.action
                            )
                            decided = True
                        print(
                            "Waiting for the current bounded operation to exit. Keep USB connected."
                        )
                if process.wait() != 0:
                    raise Invalid(
                        f"{operation.title()} stopped. Preserve this session; no automatic retry."
                    )
        finally:
            # Never kill a writer or boot process because the terminal was interrupted.
            if process is not None and process.poll() is None:
                process.wait()
            if slave >= 0:
                os.close(slave)
            os.close(master)
        if cancelled:
            raise Invalid(
                "Operation interrupted. It has exited; preserve the report before continuing."
            )
        return json.loads(private_read(self.folder / (operation + "-worker-result.json"), 65536))

    def writer(
        self, profile, recovery, output, *, ask=input, engine=None, entry=None, restart_after=True
    ):
        from firmware.file_writer import run as core

        engine = core if engine is None else engine
        _, binding = engine.checked_pair(profile, recovery)
        operation = (
            "cleanup" if binding.action == 1 and "cleanup" in profile.name else "commissioning"
        )
        print(
            "This phase changes "
            + (
                "three network files."
                if operation == "cleanup"
                else "nine settings, trust and startup files."
            )
        )
        print("The base must stay detached. Do not unplug USB during a write.")
        if ask("Type READY to arm this phase's checked RAM loader: ").strip() != "READY":
            return {"cancelled": True}
        result = self.run(
            operation,
            engine=engine,
            binding=binding,
            profile=str(profile),
            recovery=str(recovery),
            output=str(output),
            entry={k: str(v) for k, v in (entry or {}).items()},
        )
        if not workflow.complete(result):
            print(
                "The phase is incomplete. Keep USB connected; do not restart or retry without reviewing its report."
            )
        elif restart_after:
            print("Both file verification and restart-safety checks passed.")
        else:
            print("Phase verified. Stay connected in RAM while the next phase is prepared.")
        return result


def run(*, ask=input, secret=getpass.getpass):
    print("Hearth setup — experimental Gen 2 / Display-2.6 / primary 5.9.4-5 only")
    print(
        "This guides you through HACS, original-file backup and a checked local-service installation."
    )
    print("Selected-file recovery is supported; whole-firmware restoration is unverified.")
    print(
        "Start with the display detached from its HVAC base and connected to this computer by USB."
    )
    if ask("Press Enter to begin, or type QUIT: ").strip().upper() == "QUIT":
        return 0
    folder = None
    phase = "requirements"
    try:
        prerequisites()
        disk = discovery.native_disk()
        try:
            mode = workflow.identity()
        except (OSError, ValueError):
            raise Invalid(
                "The supported USB port is 1-1. Connect the Nest there in normal mode."
            ) from None
        if mode != "native":
            raise Invalid("The supported USB port is 1-1. Connect the Nest there in normal mode.")
        from installer.cli import inspect_disk

        try:
            info = inspect_disk(disk)
        except subprocess.CalledProcessError:
            print("Your account cannot read the Nest diagnostic file directly.")
            if ask("Type READ to allow one read-only sudo mtype command: ").strip() != "READ":
                raise Invalid("Diagnostic read cancelled.")
            info = inspect_disk(disk, sudo_read=True)
        device_info(info)
        print("A supported thermostat is connected. Its identifier will stay private.")
        ntp = choose_time(ask)
        PRIVATE.mkdir(mode=0o700, exist_ok=True)
        if PRIVATE.is_symlink() or PRIVATE.stat().st_mode & 0o077:
            raise Invalid("The private folder must be owner-only and must not be a symlink.")
        name = "setup-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
        folder = PRIVATE / name
        build = ROOT / "build" / name
        build.mkdir(mode=0o700, parents=True)
        print("1/6 Install Hearth in Home Assistant")
        print("Open HACS → three-dot menu → Custom repositories.")
        print(f"Add {REPOSITORY} with category Integration; download the latest tagged release.")
        print("Restart HA Core yourself, then return here. Do not manually add a Hearth entry.")
        if (
            ask("Type HA READY when HACS installation and the Core restart are complete: ").strip()
            != "HA READY"
        ):
            return 0
        ha_url = ask("Home Assistant address (the URL you use to open HA): ").strip()
        print(
            "In your HA profile → Security, create a temporary long-lived access token as an administrator."
        )
        print("Paste it at the hidden prompt. It is used only for setup and is never saved.")
        token = secret("Temporary HA administrator token (hidden): ")
        phase = "ha-setup"
        result = onboard.onboard(ha_url, token, folder, info, ask=ask)
        del token
        if result.get("cancelled"):
            return 0
        save(folder, "wizard-settings.json", encode({"ntp_server": ntp, "ha_url": ha_url}))
        save(
            folder,
            "READ-ME-FIRST.txt",
            (
                "Private Hearth setup and recovery files. Do not publish this folder.\n"
                "Keep this folder and the matching installer source version. No complete firmware backup is claimed.\n"
                "Never rerun an attempted loader/profile. A failed or interrupted write requires report review.\n"
                "If installation finishes, selected originals may be restored with the checked kit's reverse-order restore.\n"
                "Do not run restore-kit blindly after a failure or native settings changes; its strict checks may refuse.\n"
                f"Kit: {folder / 'kit'}\nLogs and progress: this folder.\n"
            ).encode(),
        )
        print(f"Private setup and recovery folder: {folder}")
        usb_access(folder, ask)
        worker = Worker(folder, build, ask=ask)
        phase = "prepare"
        print("2/6 Download and build the protected reader. This can take several minutes.")
        worker.run("prepare")
        phase = "acquire"
        print("3/6 Save the original files. This RAM reader cannot write flash.")
        device_info(
            inspect_disk(disk, sudo_read=True),
            read_bundle(private_read(folder / "commissioning.zip", 65536))[0],
        )
        if ask("Type READY to arm one read-only loader: ").strip() != "READY":
            return 0
        worker.run("acquire")
        phase = "kit"
        print(
            "4/6 Build and verify your private install and restore kit. Keep USB connected; do not reboot."
        )
        # The connectivity check uses HA's plain HTTP frontend, not its TLS listener.
        probe = ask("HA's local plain HTTP port for connectivity checks [8123]: ").strip() or "8123"
        if not probe.isdecimal() or not 1 <= int(probe) <= 65535:
            raise Invalid("A reachable plain HTTP frontend port is required.")
        worker.run("kit", ntp_server=ntp, probe_port=int(probe))
        phase = "install"
        print("5/6 Install the checked files in two separately confirmed phases.")
        result = workflow.install(folder / "kit", disk, ask=ask, runner=worker.writer)
        save(folder, "wizard-install-result.json", encode(result))
        if not result.get("complete"):
            raise Invalid(
                "Installation did not finish. Preserve the folder; do not retry old profiles."
            )
        phase = "verify"
        print("6/6 Return to the normal Nest UI. " + RESTART)
        ask("Press Enter when the home/attach-to-base screen is back: ")
        print(
            "Disconnect USB, refit the display to its base, and use normal Wi-Fi setup if needed."
        )
        print(
            "Enter the Wi-Fi password only on the Nest. Existing HVAC wiring must remain unchanged."
        )
        print(
            "In HA → Settings → Devices & services → Hearth, check for fresh temperature and humidity."
        )
        answer = ask(
            "Do fresh readings appear in HA? Type YES when verified, or Enter if not: "
        ).strip()
        result = {
            "files_verified": True,
            "fresh_readings_owner_verified": answer == "YES",
            "control_tested": False,
        }
        save(folder, "wizard-complete.json", encode(result))
        print(
            "Setup files are verified."
            + (
                " Fresh readings confirmed."
                if answer == "YES"
                else " Live connection still needs checking."
            )
        )
        print("Revoke the temporary HA access token and keep your private recovery folder.")
        return 0 if answer == "YES" else 1
    except (
        ValueError,
        OSError,
        subprocess.SubprocessError,
        RuntimeError,
        EOFError,
        KeyboardInterrupt,
    ) as exc:
        print(f"Setup stopped during {phase}. No automatic retry.")
        if isinstance(exc, Invalid):
            print(str(exc))
        if folder and folder.exists():
            save(
                folder,
                "wizard-stopped.json",
                encode(
                    {"phase": phase, "error_type": type(exc).__name__, "automatic_retry": False}
                ),
            )
            print(f"Preserve this private folder: {folder}")
            if phase in ("install", "acquire", "kit"):
                print(
                    "Keep USB connected. Check the private report before restarting or trying anything again."
                )
        return 1
