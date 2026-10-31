"""Separate loopback-only RAM kernel profile; never relax the heartbeat profile."""

import argparse
import re
from pathlib import Path

if __package__:
    from firmware.probe import configure as base
else:
    import probe_configure as base

DISABLED = tuple(name for name in base.DISABLED if name != "NET") + (
    "NETDEVICES",
    "WIRELESS",
    "PACKET",
    "UNIX",
    "NETFILTER",
    "NET_SCHED",
    "INET_DIAG",
    "CAN",
    "BT",
    "IRDA",
    "RFKILL",
    "RTC",
    "RTC_CLASS",
    "NFS_FS",
    "NFSD",
    "GENERIC_CMOS_UPDATE",
)
ENABLED = base.ENABLED + ("NET", "INET", "BLK_DEV_INITRD", "RD_GZIP", "AEABI", "VFP", "FUTEX")


def configure(text):
    text = base.configure(text)
    for name, value in {**dict.fromkeys(DISABLED, "n"), **dict.fromkeys(ENABLED, "y")}.items():
        line = f"# CONFIG_{name} is not set" if value == "n" else f"CONFIG_{name}=y"
        pattern = rf"^(?:CONFIG_{name}=.*|# CONFIG_{name} is not set)$"
        if re.search(pattern, text, flags=re.MULTILINE):
            text = re.sub(pattern, lambda _, value=line: value, text, flags=re.MULTILINE)
        else:
            text += "\n" + line + "\n"
    return text


def disable_clock_updates(text):
    original = "\tselect GENERIC_CMOS_UPDATE"
    replacement = "\t# Hearth RAM TLS: no hardware clock updates"
    if text.count(replacement) == 2 and original not in text:
        return text
    if text.count(original) != 2 or replacement in text:
        raise ValueError("unexpected OMAP hardware-clock selection")
    return text.replace(original, replacement)


def verify(text):
    for name, enabled in [(n, False) for n in DISABLED] + [(n, True) for n in ENABLED]:
        rows = re.findall(rf"^(?:CONFIG_{name}=.*|# CONFIG_{name} is not set)$", text, re.MULTILINE)
        expected = f"CONFIG_{name}=y" if enabled else f"# CONFIG_{name} is not set"
        # Some unavailable Kconfig symbols disappear when their parents are off.
        if rows != [expected] and (enabled or rows):
            raise ValueError("unexpected TLS kernel setting: " + name)
    if text.splitlines().count('CONFIG_INITRAMFS_SOURCE="/work/rootfs.cpio"') != 1:
        raise ValueError("unexpected fallback initramfs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    path = Path(".config")
    if args.verify:
        verify(path.read_text())
    else:
        path.write_text(configure(path.read_text()))
        kconfig = Path("arch/arm/mach-omap2/Kconfig")
        kconfig.write_text(disable_clock_updates(kconfig.read_text()))
