"""One owner-guided path from USB to HACS and a checked private install kit."""

import errno
import getpass
import json
import os
import pty
import re
import select
import shutil
import subprocess  # nosec B404
import sys
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path

from backend.validation import Invalid
from firmware.file_writer.run import encode, save
from firmware.tls_probe.package import private_read
from installer import discovery, onboard, ui, workflow
from installer.bundle import device_info, read_bundle
from installer.sources import ROOT
from provisioning.time_server import DEFAULT, time_server
from tools.elf_review import PRIVATE

REPOSITORY = "https://github.com/tylxr59/Hearth"
DOCS = REPOSITORY + "/blob/main/docs/"
RESTART = "Hold the ring down for 10 seconds, let go, then press it once more."
TOTAL = 7

# Command -> package name per distribution family. Suggestions only: the
# wizard never installs system packages itself.
PACKAGES = {
    "podman": {"debian": "podman", "fedora": "podman", "arch": "podman", "suse": "podman"},
    "git": {"debian": "git", "fedora": "git", "arch": "git", "suse": "git"},
    "clang": {"debian": "clang", "fedora": "clang", "arch": "clang", "suse": "clang"},
    "ld.lld": {"debian": "lld", "fedora": "lld", "arch": "lld", "suse": "lld"},
    "cc": {"debian": "build-essential", "fedora": "gcc", "arch": "base-devel", "suse": "gcc"},
    "patch": {"debian": "patch", "fedora": "patch", "arch": "patch", "suse": "patch"},
    "pkg-config": {
        "debian": "pkg-config",
        "fedora": "pkgconf-pkg-config",
        "arch": "pkgconf",
        "suse": "pkgconf",
    },
    "mtype": {"debian": "mtools", "fedora": "mtools", "arch": "mtools", "suse": "mtools"},
    "setfacl": {"debian": "acl", "fedora": "acl", "arch": "acl", "suse": "acl"},
    "libusb": {
        "debian": "libusb-1.0-0-dev",
        "fedora": "libusb1-devel",
        "arch": "libusb",
        "suse": "libusb-1_0-devel",
    },
}
INSTALL = {
    "debian": "sudo apt install",
    "fedora": "sudo dnf install",
    "arch": "sudo pacman -S --needed",
    "suse": "sudo zypper install",
}


def os_release(path="/etc/os-release"):
    """Return (pretty name, distribution family or None) for package hints."""
    try:
        text = Path(path).read_text()
    except OSError:
        return "Linux", None
    values = {}
    for line in text.splitlines():
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"')
    ids = [values.get("ID", "")] + values.get("ID_LIKE", "").split()
    family = next(
        (
            name
            for candidate in ids
            for name, members in (
                ("debian", ("debian", "ubuntu", "linuxmint", "pop")),
                ("fedora", ("fedora", "rhel", "centos")),
                ("arch", ("arch", "cachyos", "manjaro", "endeavouros")),
                ("suse", ("suse", "opensuse", "opensuse-tumbleweed", "opensuse-leap")),
            )
            if candidate in members
        ),
        None,
    )
    return values.get("PRETTY_NAME", "Linux"), family


def install_hint(missing, family):
    """A suggested package-manager command, or None when the family is unknown."""
    if family not in INSTALL:
        return None
    packages = dict.fromkeys(PACKAGES[name][family] for name in missing)
    return INSTALL[family] + " " + " ".join(packages)


def choose_time(ask=input):
    while True:
        try:
            return time_server(
                ask(ui.prompt("Time server", f"[Enter = {DEFAULT}]")).strip() or DEFAULT
            )
        except Invalid as exc:
            ui.fail(str(exc))


def prerequisites():
    if sys.platform != "linux" or os.getuid() == 0:
        raise Invalid("Run this wizard as your normal user on Linux, not with sudo.")
    names = ("podman", "git", "clang", "ld.lld", "cc", "patch", "pkg-config", "mtype", "setfacl")
    missing = [name for name in names if shutil.which(name) is None]
    try:
        subprocess.run(  # nosec B603 B607
            ["pkg-config", "--exists", "libusb-1.0"], check=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        missing.append("libusb")
    if missing:
        system, family = os_release()
        ui.fail(f"Some tools this wizard needs are missing on {system}:")
        ui.bullets(("libusb development headers" if name == "libusb" else name) for name in missing)
        hint = install_hint(missing, family)
        if hint:
            ui.say("You can probably install them with:")
            print("      " + ui.style(hint, "bold"))
        else:
            ui.say(
                "Install them with your package manager. mtype comes from mtools, "
                "setfacl from acl, and ld.lld from lld."
            )
        raise Invalid("Install the missing tools, then run this wizard again.")
    from installer.build import require_engine

    require_engine()


def usb_access(folder, ask=input):
    """Explicitly install a root-managed rule for current UID and measured USB port."""
    from installer.workflow import identity

    if identity() != "native":
        raise Invalid("Connect a single Nest in its normal USB mode before starting.")
    # udev executes RUN as root: never trust a user-controlled PATH executable.
    acl = Path("/usr/bin/setfacl")
    if (
        not acl.is_file()
        or acl.is_symlink()
        or acl.stat().st_uid != 0
        or acl.stat().st_mode & 0o022
    ):
        raise Invalid("The USB rule requires the root-managed /usr/bin/setfacl executable.")
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
    ui.box(
        "One-time USB permission",
        [
            (
                "To talk to the Nest while it is in boot mode, Linux needs a permission "
                "rule for USB port 1-1."
            ),
            f"It is saved to {target} and applies to your user account only.",
            (
                "It does not give anything write access to your disks. sudo will ask "
                "for your computer's password."
            ),
        ],
        "cyan",
    )
    if not ui.confirm(ask, "Add the USB rule now?"):
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


WORK_LABELS = {
    "prepare": "Building the USB reader",
    "nand": "Preparing the backup loader",
    "acquire": "Preparing the file reader",
    "kit": "Building your install kit",
    "capacity": "Preparing the space check",
    "commissioning": "Preparing phase 1",
    "cleanup": "Preparing phase 2",
}
# Shown once the loader reports that the Nest's boot ROM answered.
CONNECTED_LABELS = {
    "nand": "Nest connected, starting the backup",
    "acquire": "Nest connected, reading the original files",
    "capacity": "Nest connected, checking free space",
    "commissioning": "Nest connected, running safety checks",
    "cleanup": "Nest connected, running safety checks",
}


class Worker:
    def __init__(self, folder, build, *, ask=input):
        self.folder, self.build, self.ask = folder, build, ask

    RECORDS = re.compile(rb'"records": (\d+), "total_records": 262144')

    def _confirm_write(self, values, binding, engine, cancelled):
        ui.box(
            "Ready to write",
            [
                (
                    "All checks passed: the test boot worked and the files on the Nest "
                    "exactly match your saved originals."
                ),
                (
                    "The next step writes to the thermostat's flash. Do not unplug USB "
                    "until the wizard says it is finished."
                ),
                (
                    "Your saved files can be restored later, but a full-chip restore has "
                    "not been verified yet."
                ),
            ],
        )
        commit = not cancelled and (
            self.ask(ui.prompt("Type INSTALL to write", "[Enter = cancel]")).strip() == "INSTALL"
        )
        if commit and values.get("backup_session"):
            from installer.nand_backup import check as check_backup

            try:
                check_backup(Path(values["backup_session"]))
            except (ValueError, OSError):
                ui.fail(
                    "Rechecking the full flash backup failed. Cancelled before writing anything."
                )
                commit = False
        engine.decide(Path(values["output"]), commit=commit, expected_action=binding.action)

    def run(self, operation, *, engine=None, binding=None, **values):
        request = {
            "operation": operation,
            "session": str(self.folder),
            "build": str(self.build),
        } | values
        save(self.folder, operation + "-request.json", encode(request))
        log_name = self.folder / (operation + ".log")
        status = ui.Live(WORK_LABELS.get(operation, "Working"))
        master, slave = pty.openpty()
        process = None
        log = None
        decided = cancelled = scan_seen = connected = False
        pending = b""

        def pump(timeout):
            """Read and log worker output; False once the stream has ended."""
            ready, _, _ = select.select([master], [], [], timeout)
            if not ready:
                return True
            try:
                data = os.read(master, 8192)
            except OSError as exc:
                if exc.errno != errno.EIO:
                    raise
                return False
            if not data:
                return False
            if log is not None and not log.closed:
                log.write(data)
                log.flush()
            nonlocal pending
            pending = (pending + data)[-16384:]
            return True

        def preflight_ready():
            return (
                engine is not None
                and not decided
                and (Path(values["output"]) / "preflight.json").exists()
            )

        try:
            log = log_name.open("xb")
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
            open_stream = True
            while True:
                try:
                    if open_stream:
                        open_stream = pump(0.2)
                    else:
                        time.sleep(0.2)
                    stages = list(ui.STAGE.finditer(pending))
                    if stages:
                        number, total, label = stages[-1].groups()
                        status.set_stage(int(number), int(total), label.decode(errors="replace"))
                    if operation == "nand":
                        records = list(self.RECORDS.finditer(pending))
                        if records:
                            count = int(records[-1][1])
                            if 0 < count <= 262144:
                                status.set_percent(count * 100 // 262144)
                                status.set_label(
                                    "Reading flash (two passes)"
                                    if count < 262144
                                    else "Verifying the backup"
                                )
                    if not scan_seen and b"scanning for USB device" in pending:
                        scan_seen = True
                        status.clear()
                        ui.blank()
                        ui.action("The loader is waiting now. " + RESTART)
                        ui.muted(
                            "Keep USB plugged in and the display off its base. The wizard "
                            "continues by itself once the Nest connects (within 90 seconds)."
                        )
                        status.set_label("Waiting for the Nest to restart")
                    if not connected and b"ROM boot command transferred" in pending:
                        connected = True
                        status.set_label(CONNECTED_LABELS.get(operation, "Nest connected"))
                    if preflight_ready():
                        status.clear()
                        self._confirm_write(values, binding, engine, cancelled)
                        decided = True
                    if process.poll() is not None and not open_stream:
                        break
                    if process.poll() is not None and not select.select([master], [], [], 0)[0]:
                        break
                    status.refresh()
                except (KeyboardInterrupt, EOFError):
                    cancelled = True
                    if preflight_ready():
                        engine.decide(
                            Path(values["output"]), commit=False, expected_action=binding.action
                        )
                        decided = True
                    status.clear()
                    ui.warn(
                        "Stopping safely: waiting for the current operation to finish. "
                        "Keep USB connected."
                    )
            status.clear()
            if process.wait() != 0:
                raise Invalid(
                    f"The {operation} step stopped with an error. "
                    f"Details are in {log_name}. Nothing is retried automatically."
                )
        finally:
            status.clear()
            # Never kill a writer or boot process because the wizard stopped, and
            # keep draining its output so it can never block on a full terminal.
            while process is not None and process.poll() is None:
                try:
                    if not pump(0.2):
                        time.sleep(0.2)
                except (KeyboardInterrupt, EOFError):
                    ui.warn("Still waiting for the current operation to finish safely.")
                except OSError:
                    time.sleep(0.2)
            if log is not None:
                log.close()
            if slave >= 0:
                os.close(slave)
            os.close(master)
        if cancelled:
            raise Invalid(
                "Operation interrupted. It has exited safely; keep its report before "
                "doing anything else."
            )
        return json.loads(private_read(self.folder / (operation + "-worker-result.json"), 65536))

    def writer(
        self,
        profile,
        recovery,
        output,
        *,
        ask=input,
        engine=None,
        entry=None,
        restart_after=True,
        backup_session=None,
    ):
        from firmware.file_writer import run as core

        engine = core if engine is None else engine
        _, binding = engine.checked_pair(profile, recovery)
        capacity = profile.name == "capacity-preflight"
        operation = (
            "capacity"
            if capacity
            else "cleanup"
            if binding.action == 1 and "cleanup" in profile.name
            else "commissioning"
        )
        if capacity:
            ui.say(
                "First, a read-only check that there is enough free flash space for "
                "the whole install. Nothing is written in this check."
            )
        else:
            ui.say(
                "This phase changes "
                + (
                    "three network files (connectivity check and time server)."
                    if operation == "cleanup"
                    else "nine settings, trust and startup files."
                )
            )
        ui.muted("Keep the display off its base, and don't unplug USB during a write.")
        if not ui.confirm(ask, "Run the space check?" if capacity else "Start this phase?"):
            return {"cancelled": True}
        result = self.run(
            operation,
            engine=engine,
            binding=binding,
            profile=str(profile),
            recovery=str(recovery),
            output=str(output),
            entry={k: str(v) for k, v in (entry or {}).items()},
            **({"backup_session": str(backup_session)} if backup_session is not None else {}),
        )
        if capacity:
            if result.get("preflight_passed") is True and result.get("safe_to_restart") is True:
                ui.ok("There is enough space. Stay connected; the first phase is next.")
            else:
                ui.fail("Not enough space, or the check refused. Nothing was installed or written.")
            return result
        if not workflow.complete(result):
            ui.fail(
                "This phase did not finish. Keep USB connected and do not restart the Nest "
                "until its report has been reviewed."
            )
        elif restart_after:
            ui.ok("Files verified, and the Nest is safe to restart.")
        else:
            ui.ok("Phase verified. Stay connected while the next phase is prepared.")
        return result


PHASES = {
    "requirements": "the computer and thermostat checks",
    "ha-setup": "Home Assistant setup",
    "prepare": "building the reader",
    "nand": "the full flash backup",
    "acquire": "saving the original files",
    "kit": "building your install kit",
    "install": "installation",
    "verify": "the final check",
}

README = """HEARTH PRIVATE SETUP FOLDER
===========================

Keep this folder. Do not share or publish it: it contains your thermostat's
credential, a full copy of its flash memory and its original files.

What is in here
---------------
  kit/                Your install kit and the matching restore images.
  nand-backup/        Full flash backup: two raw passes plus checked data views.
  acquisition/        The thermostat's original files, read before any change.
  installer-source.zip  The exact Hearth source used. Restores need it.
  *.log, *.json       Progress logs and results for each step.

Also keep the matching build folder:
  {build}
Restoring currently needs it on this same computer.

If something went wrong
-----------------------
  * Do not run setup again on the same thermostat. Each step runs only once.
  * After a failed or interrupted write, keep USB connected and do not restart
    the Nest until the reports in this folder have been reviewed.
  * Ask for help at https://github.com/tylxr59/Hearth/issues. Never attach
    this folder or its files; they contain private keys and device data.

Undoing the installation
------------------------
If setup finished, run this from the same Hearth folder:

    python3 provision.py --restore

That puts back the original files that Hearth changed. It can refuse if the
thermostat's settings changed afterwards. Restoring the whole flash chip has not
been verified yet.
"""


def overview():
    ui.banner(
        "Hearth setup",
        "Connect your Nest Learning Thermostat to Home Assistant, with no cloud.",
        "Experimental preview  ·  Nest Gen 2 (Display-2.6), firmware 5.9.4-5 only",
    )
    ui.section("What this wizard does")
    ui.numbered(
        [
            "Installs the Hearth integration in Home Assistant (you click, it guides).",
            "Builds a small read-only tool that runs on the Nest over USB.",
            "Backs up the Nest's entire flash memory to this computer.",
            "Saves the original files that Hearth will change.",
            "Builds an install kit and a matching undo kit for your unit only.",
            "Installs in two phases, asking you before each write.",
            "Checks that readings appear in Home Assistant.",
        ]
    )
    ui.section("Before you start")
    ui.bullets(
        [
            (
                "Take the display off its wall base and plug it into this computer by USB "
                "(port 1-1). Use a data cable, not a charge-only one."
            ),
            "Have Home Assistant open in a browser, with an admin account.",
            "Allow about 7 GB of free disk space, and roughly an hour. Most of it runs unattended.",
        ]
    )
    ui.muted(
        "Your saved files can be put back with python3 provision.py --restore. "
        "A full-chip restore has not been verified yet, so this is still experimental."
    )


def run(*, ask=input, secret=getpass.getpass):
    overview()
    choice = (
        ask(ui.prompt("Press Enter to begin", "[RESTORE = undo a previous install, QUIT = exit]"))
        .strip()
        .upper()
    )
    if choice == "QUIT":
        return 0
    if choice == "RESTORE":
        from installer.recovery_wizard import run as recover

        return recover(ask=ask)
    folder = None
    phase = "requirements"
    try:
        ui.section("Checking this computer and your thermostat")
        prerequisites()
        ui.ok("All required tools are installed.")
        disk = discovery.native_disk()
        try:
            mode = workflow.identity()
        except (OSError, ValueError):
            raise Invalid(
                "No Nest found in normal mode on USB port 1-1. Plug it into that port "
                "and wait for it to finish starting up."
            ) from None
        if mode != "native":
            raise Invalid(
                "No Nest found in normal mode on USB port 1-1. Plug it into that port "
                "and wait for it to finish starting up."
            )
        from installer.cli import inspect_disk

        sudo_read = False
        try:
            info = inspect_disk(disk)
        except subprocess.CalledProcessError:
            ui.info(
                "Your account can't read the Nest's info file directly. One read-only "
                "sudo command (mtype) can read it for you."
            )
            if not ui.confirm(ask, "Allow this one read-only sudo command?"):
                raise Invalid("Reading the thermostat's info file was cancelled.")
            info = inspect_disk(disk, sudo_read=True)
            sudo_read = True
        device_info(info)
        ui.ok("Found a supported Nest. Its serial number stays private.")
        ui.section("Time server")
        ui.say(
            "Hearth points the Nest's clock at a time server you choose. Press Enter "
            f"for {DEFAULT}, or type the hostname or IPv4 address of your own."
        )
        ntp = choose_time(ask)
        ui.ok(f"Time server: {ntp}")
        PRIVATE.mkdir(mode=0o700, exist_ok=True)
        if PRIVATE.is_symlink() or PRIVATE.stat().st_mode & 0o077:
            raise Invalid("The private folder must be owner-only and must not be a symlink.")
        name = "setup-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
        folder = PRIVATE / name
        build = ROOT / "build" / name
        build.mkdir(mode=0o700, parents=True)

        phase = "ha-setup"
        ui.step(1, TOTAL, "Install Hearth in Home Assistant")
        ui.numbered(
            [
                (
                    "In Home Assistant, open HACS, then the three-dot menu (top right), then "
                    "Custom repositories."
                ),
                f"Add {REPOSITORY} and choose the type Integration.",
                "Search HACS for Hearth and download it.",
                "Restart Home Assistant: Settings, then System, then Restart.",
            ]
        )
        ui.warn("Don't add the Hearth integration yourself. This wizard does it next.")
        done = ask(ui.prompt("Press Enter once Home Assistant has restarted", "[q = quit]"))
        if done.strip().lower() in ("q", "quit"):
            return 0
        ui.say("Enter the address you use to open Home Assistant in your browser.")
        ha_url = ask(ui.prompt("Home Assistant address", "(e.g. http://192.168.1.10:8123)")).strip()
        ui.say("Now create a temporary access token so the wizard can set up the integration:")
        ui.numbered(
            [
                "Click your profile picture (bottom left), then open the Security tab.",
                'Under Long-lived access tokens, choose Create token and name it "Hearth setup".',
                "Copy the token and paste it below. You won't see it as you paste.",
            ]
        )
        ui.muted("The token is used once and never saved. Delete it after setup.")
        token = secret(ui.prompt("Access token", "(hidden)"))
        result = onboard.onboard(ha_url, token, folder, info, ask=ask)
        del token
        if result.get("cancelled"):
            return 0
        save(folder, "wizard-settings.json", encode({"ntp_server": ntp, "ha_url": ha_url}))
        save(folder, "READ-ME-FIRST.txt", README.format(build=build).encode())
        ui.ok("Hearth was added to Home Assistant.")
        ui.info(f"Your private setup folder is {folder}. Keep it; see READ-ME-FIRST.txt inside.")
        usb_access(folder, ask)
        worker = Worker(folder, build, ask=ask)

        phase = "prepare"
        ui.step(2, TOTAL, "Build the USB reader")
        ui.say(
            "Downloading pinned sources and building a small read-only boot image in a "
            "Podman container. This takes several minutes and doesn't touch the Nest."
        )
        worker.run("prepare")
        ui.ok("Reader built.")

        phase = "nand"
        ui.step(3, TOTAL, "Back up the whole thermostat")
        ui.say(
            "Hearth now copies the Nest's entire flash memory to this computer, twice. "
            "Flash has normal bit-level noise, so the two copies are cross-checked after "
            "error correction: that is how the wizard knows the backup is genuine. The "
            "read takes up to 20 minutes, then a few minutes to verify."
        )
        device_info(
            inspect_disk(disk, sudo_read=sudo_read),
            read_bundle(private_read(folder / "commissioning.zip", 65536))[0],
        )
        ui.say(
            "Once you say yes, the wizard waits for the Nest. It will tell you when to "
            "press the ring."
        )
        if not ui.confirm(ask, "Start the backup?"):
            return 0
        worker.run("nand")
        ui.ok("Full backup saved and verified.")

        phase = "acquire"
        ui.step(4, TOTAL, "Save the original files")
        ui.say(
            "Next, Hearth reads the individual files it will change, so they can be "
            "checked and put back later. Don't restart the Nest yourself; wait for the "
            "ring prompt."
        )
        if not ui.confirm(ask, "Read the original files now?"):
            ui.warn(
                "Stopped. Your full backup is saved. Keep USB connected until this "
                "window has closed, then restart the Nest normally."
            )
            return 0
        worker.run("acquire")
        ui.ok("Original files saved.")

        phase = "kit"
        ui.step(5, TOTAL, "Build your install kit")
        ui.say(
            "The Nest checks its internet connection by loading a page from Home "
            "Assistant over plain HTTP. Most setups use port 8123."
        )
        # The connectivity check uses HA's plain HTTP frontend, not its TLS listener.
        probe = ask(ui.prompt("Home Assistant HTTP port", "[Enter = 8123]")).strip() or "8123"
        if not probe.isdecimal() or not 1 <= int(probe) <= 65535:
            raise Invalid("Enter the port number Home Assistant serves plain HTTP on.")
        ui.say(
            "Building the install and undo kits for this thermostat. This takes a few "
            "minutes. Keep USB connected and don't restart the Nest."
        )
        worker.run("kit", ntp_server=ntp, probe_port=int(probe))
        ui.ok("Install kit built and checked.")

        phase = "install"
        ui.step(6, TOTAL, "Install")
        ui.say(
            "There are three parts: a read-only space check, then two install phases. "
            "Each one asks you first, and nothing is written until you type INSTALL."
        )
        result = workflow.install(folder / "kit", disk, ask=ask, runner=worker.writer)
        save(folder, "wizard-install-result.json", encode(result))
        if not result.get("complete"):
            raise Invalid("Installation did not finish.")

        phase = "verify"
        ui.step(7, TOTAL, "Finish up")
        ui.action("Restart the Nest: " + RESTART)
        ask(ui.prompt("Press Enter when the Nest shows its home screen"))
        ui.numbered(
            [
                "Unplug USB and put the display back on its wall base. Leave the wiring as it is.",
                "If the Nest asks, join your Wi-Fi on the Nest itself.",
                (
                    "In Home Assistant, open Settings, then Devices & services, then Hearth. "
                    "Check that temperature and humidity are updating."
                ),
            ]
        )
        readings = ui.confirm(ask, "Are fresh readings showing in Home Assistant?")
        result = {
            "files_verified": True,
            "fresh_readings_owner_verified": readings,
            "control_tested": False,
        }
        save(folder, "wizard-complete.json", encode(result))
        if readings:
            ui.box(
                "Hearth is set up",
                [
                    "Your Nest now reports to Home Assistant locally.",
                    "Delete the temporary access token in your Home Assistant profile.",
                    f"Keep your private folder somewhere safe: {folder}",
                    f"Next: controls and schedules, {DOCS}usage.md",
                ],
                "green",
            )
            return 0
        ui.box(
            "Files installed, but no readings yet",
            [
                (
                    "Give the Nest a few minutes after joining Wi-Fi, and wake it by pressing "
                    "the ring."
                ),
                (
                    "Make sure the Nest can reach Home Assistant on your network (same "
                    "network or VLAN routing, port 8443)."
                ),
                f"Troubleshooting: {DOCS}troubleshooting.md",
                f"Delete the temporary access token, and keep your private folder: {folder}",
            ],
        )
        return 1
    except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 - always record the stop
        # Expected refusals explain themselves; anything else is a wizard bug, but
        # the stop must still be recorded and the same safety guidance shown.
        expected = isinstance(
            exc,
            (ValueError, OSError, subprocess.SubprocessError, RuntimeError, KeyboardInterrupt),
        )
        ui.blank()
        ui.fail(f"Setup stopped during {PHASES.get(phase, phase)}.")
        if isinstance(exc, Invalid):
            ui.say(str(exc))
        elif not expected:
            ui.say(f"Unexpected error ({type(exc).__name__}). This is a bug in the wizard.")
        lines = ["Nothing is retried automatically."]
        if folder and folder.exists():
            try:
                save(
                    folder,
                    "wizard-stopped.json",
                    encode(
                        {
                            "phase": phase,
                            "error_type": type(exc).__name__,
                            "unexpected": not expected,
                            "automatic_retry": False,
                        }
                    ),
                )
                if not expected:
                    save(folder, "wizard-error.log", traceback.format_exc().encode())
            except (OSError, ValueError):
                pass
            lines.append(f"Keep your private folder: {folder}")
        if phase in ("install", "nand", "acquire", "kit"):
            lines.append(
                "Keep USB connected, and don't restart the Nest or run setup again until "
                "the report in that folder has been reviewed."
            )
        if not expected:
            lines.append(
                "Please report it at https://github.com/tylxr59/Hearth/issues with the "
                "message above. wizard-error.log has the details; check it for private "
                "paths before sharing."
            )
        lines.append(f"Help: {DOCS}troubleshooting.md")
        ui.box("What to do now", lines, "red")
        return 1
