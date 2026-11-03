"""Layman entry to checked saved-file restoration, never whole-chip flashing."""

import subprocess  # nosec B404

from backend.validation import Invalid
from installer import discovery, kit, nand_backup, ui, workflow
from tools.elf_review import PRIVATE, private_path


def select_kit(ask=input):
    choices = sorted(path.parent for path in PRIVATE.glob("setup-*/kit/kit.json"))
    if not choices:
        raise Invalid(
            "No saved installation found in the private folder. Run this from the same "
            "Hearth folder you used for setup, with its private/setup-... folder intact."
        )
    ui.section("Saved installations")
    ui.numbered([path.parent.name for path in choices])
    answer = ask(ui.prompt("Which one", "[Enter = 1]")).strip() or "1"
    if not answer.isdecimal() or not 1 <= int(answer) <= len(choices):
        raise Invalid("Choose a saved installation number.")
    return private_path(choices[int(answer) - 1])


def run(*, ask=input):
    from installer.cli import inspect_disk
    from installer.wizard import prerequisites, usb_access

    ui.banner(
        "Hearth restore",
        "Put back the original thermostat files that Hearth changed.",
        "Experimental preview  ·  Nest Gen 2 (Display-2.6), firmware 5.9.4-5 only",
    )
    ui.section("What this does")
    ui.bullets(
        [
            (
                "Removes Hearth's changes and restores the nine settings/startup files and "
                "three network files saved during setup."
            ),
            "Checks everything first, and asks before each write.",
            (
                "Does not erase or rewrite the whole flash chip. Full-chip restore has not "
                "been verified yet."
            ),
        ]
    )
    ui.section("Before you start")
    ui.bullets(
        ["Take the display off its wall base and plug it into this computer by USB (port 1-1)."]
    )
    try:
        prerequisites()
        root = select_kit(ask)
        status = kit.check(root, for_restore=True)
        if status["review_only"]:
            raise Invalid("A review-only kit cannot run on a device.")
        session = root.parent
        nand_backup.check(session)
        ui.ok("Full backup, saved originals and restore images all check out.")
        ui.muted(
            "If you changed thermostat settings since installing, the restore may refuse "
            "to protect them. If an earlier write was interrupted, stop here and ask for "
            "help instead of guessing."
        )
        disk = discovery.native_disk()
        sudo_read = False
        try:
            inspect_disk(disk)
        except subprocess.CalledProcessError:
            ui.info(
                "Your account can't read the Nest's info file directly. One read-only "
                "sudo command (mtype) can read it for you."
            )
            if ask(ui.prompt("Type READ to allow it", "[Enter = cancel]")).strip() != "READ":
                return 0
            inspect_disk(disk, sudo_read=True)
            sudo_read = True
        usb_access(session, ask)
        ui.say(
            "Each part runs read-only checks first, then asks you to type RESTORE. "
            "Restoring writes to flash, so keep USB connected until it finishes."
        )
        outcome = workflow.restore(root, disk, ask=ask, sudo_read=sudo_read)
        if not outcome["complete"]:
            ui.box(
                "Restore did not finish",
                [
                    "Keep USB connected and don't restart the Nest.",
                    "Keep your private folder. Nothing is retried automatically.",
                ],
                "red",
            )
            return 1
        ui.box(
            "Original files restored",
            [
                "Every restored file was read back and verified.",
                (
                    "Restart the Nest as shown above. Hold the ring for 10 seconds, let go, then "
                    "press it once more."
                ),
                "Remove the Hearth integration in Home Assistant if you no longer need it.",
                "Keep your private folder and this Hearth source folder.",
            ],
            "green",
        )
        return 0
    except (ValueError, OSError, subprocess.SubprocessError, EOFError, KeyboardInterrupt) as exc:
        ui.blank()
        ui.fail("Restore stopped. Nothing is retried automatically.")
        if isinstance(exc, Invalid):
            ui.say(str(exc))
        ui.box(
            "What to do now",
            [
                "Keep your private folder.",
                (
                    "If a write had started, keep USB connected and don't restart the Nest "
                    "until its report has been reviewed."
                ),
                "Help: https://github.com/tylxr59/Hearth/issues",
            ],
            "red",
        )
        return 1
