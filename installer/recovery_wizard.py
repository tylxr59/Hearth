"""Layman entry to checked saved-file restoration, never whole-chip flashing."""

import subprocess  # nosec B404

from backend.validation import Invalid
from installer import discovery, kit, nand_backup, workflow
from tools.elf_review import PRIVATE, private_path


def select_kit(ask=input):
    choices = sorted(path.parent for path in PRIVATE.glob("setup-*/kit/kit.json"))
    if not choices:
        raise Invalid(
            "No saved installation kit found. Keep the original private/setup folder with this source version."
        )
    for i, path in enumerate(choices, 1):
        print(f"{i}. {path.parent.name}")
    answer = ask("Saved installation number [1]: ").strip() or "1"
    if not answer.isdecimal() or not 1 <= int(answer) <= len(choices):
        raise Invalid("Choose a saved installation number.")
    return private_path(choices[int(answer) - 1])


def run(*, ask=input):
    from installer.cli import inspect_disk
    from installer.wizard import prerequisites, usb_access

    print("Hearth recovery — restore saved native files and original settings")
    print(
        "This removes Hearth additions and replaces the nine commissioning and three network files."
    )
    print("It does not erase or reflash the whole NAND. Whole-chip restoration remains unverified.")
    print("Keep the display detached from its HVAC base and connected by USB.")
    try:
        prerequisites()
        root = select_kit(ask)
        status = kit.check(root, for_restore=True)
        if status["review_only"]:
            raise Invalid("A review-only kit cannot run on a device.")
        session = root.parent
        nand_backup.check(session)
        print("Full NAND archive, selected originals and restore images checked.")
        print(
            "Native settings changed since installation may cause this exact-restore preview to refuse."
        )
        print(
            "If a write was interrupted, preserve the folder for review rather than guessing recovery scope."
        )
        disk = discovery.native_disk()
        sudo_read = False
        try:
            inspect_disk(disk)
        except subprocess.CalledProcessError:
            if (
                ask("Type READ to permit a fixed read-only sudo mtype diagnostic read: ").strip()
                != "READ"
            ):
                return 0
            inspect_disk(disk, sudo_read=True)
            sudo_read = True
        usb_access(session, ask)
        print(
            "Each phase runs read-only preflight before asking for RESTORE. A restore writes NAND; power loss can leave files altered."
        )
        outcome = workflow.restore(root, disk, ask=ask, sudo_read=sudo_read)
        if not outcome["complete"]:
            print(
                "Restoration is incomplete. Keep USB connected and preserve this session; do not retry old profiles."
            )
            return 1
        print(
            "Saved-file restoration and readback passed. Follow the safe restart instruction above."
        )
        print(
            "Keep the original archive and installer source; this does not reset HA or call HVAC controls."
        )
        return 0
    except (ValueError, OSError, subprocess.SubprocessError, EOFError, KeyboardInterrupt) as exc:
        print("Recovery stopped. No automatic retry or whole-chip write.")
        if isinstance(exc, Invalid):
            print(str(exc))
        print(
            "Preserve your private installation folder. A failed post-write check requires review before native restart."
        )
        return 1
