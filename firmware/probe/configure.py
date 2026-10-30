"""Configure a diagnostic-only kernel, with no flash or network subsystem.

This runs inside the isolated build container, never on the thermostat.
"""

import argparse
import re
import stat
import struct
from pathlib import Path

DISABLED = ("MTD", "BLOCK", "JFFS2_FS", "USB_DYNAMIC", "NET", "WLAN", "MMC", "PCMCIA", "LOGO")
ENABLED = ("DEVTMPFS", "DEVTMPFS_MOUNT", "USB_G_SERIAL", "PROC_FS", "SYSFS")


def configure(text):
    settings = {name: "n" for name in DISABLED}
    settings.update({name: "y" for name in ENABLED})
    settings["INITRAMFS_SOURCE"] = '"/work/rootfs.cpio"'
    for name, value in settings.items():
        line = f"# CONFIG_{name} is not set" if value == "n" else f"CONFIG_{name}={value}"
        pattern = rf"^(?:CONFIG_{name}=.*|# CONFIG_{name} is not set)$"
        if re.search(pattern, text, flags=re.MULTILINE):
            text = re.sub(pattern, lambda _, value=line: value, text, flags=re.MULTILINE)
        else:
            text += "\n" + line + "\n"
    return text


def verify(text):
    for name in DISABLED:
        if re.search(rf"^CONFIG_{name}=[ym]$", text, flags=re.MULTILINE):
            raise ValueError("forbidden probe subsystem: " + name)
    for name in ENABLED:
        if not re.search(rf"^CONFIG_{name}=y$", text, flags=re.MULTILINE):
            raise ValueError("missing required probe subsystem: " + name)
    if 'CONFIG_INITRAMFS_SOURCE="/work/rootfs.cpio"' not in text.splitlines():
        raise ValueError("unexpected initramfs source")


def initramfs(init):
    """Construct only our fixed directories, console node and ARM init ELF.

    No stock files, symlinks, shell, credentials or install scripts are accepted.
    newc metadata is fixed so identical init binaries produce identical archives.
    """
    if not 52 <= len(init) <= 65536 or init[:6] != b"\x7fELF\x01\x01":
        raise ValueError("small little-endian ELF32 init required")
    if init[16:20] != b"\x02\x00\x28\x00":
        raise ValueError("ARM executable init required")
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", init)
    entry, offset, stride, count = header[4], header[5], header[9], header[10]
    if stride != 32 or not 1 <= count <= 16 or offset < 52 or offset + stride * count > len(init):
        raise ValueError("invalid init ELF program headers")
    executable = False
    for i in range(count):
        segment = struct.unpack_from("<8I", init, offset + i * stride)
        kind, start, address, _, size, memory, flags, _ = segment
        if kind in (2, 3):
            raise ValueError("dynamic init dependencies are forbidden")
        if kind == 1:
            if start + size > len(init) or size > memory:
                raise ValueError("invalid init ELF load segment")
            executable |= bool(flags & 1 and address <= entry < address + size)
    if not executable:
        raise ValueError("init entry point must be in an executable load segment")
    result = bytearray()
    entries = [
        (".", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("dev", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("proc", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("sys", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("dev/console", stat.S_IFCHR | 0o600, b"", 5, 1),
        ("init", stat.S_IFREG | 0o755, init, 0, 0),
        ("TRAILER!!!", 0, b"", 0, 0),
    ]
    for ino, (name, mode, content, major, minor) in enumerate(entries, 1):
        encoded = name.encode("ascii") + b"\0"
        fields = (ino, mode, 0, 0, 1, 0, len(content), 0, 0, major, minor, len(encoded), 0)
        result += b"070701" + "".join(f"{value:08x}" for value in fields).encode("ascii")
        result += encoded
        result += b"\0" * (-len(result) % 4)
        result += content
        result += b"\0" * (-len(result) % 4)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    path = Path(".config")
    if args.verify:
        verify(path.read_text())
    else:
        path.write_text(configure(path.read_text()))
        Path("/work/rootfs.cpio").write_bytes(initramfs(Path("/work/root/init").read_bytes()))
        # Original 2.6.37 script uses defined(@array), removed by newer Perl.
        script = Path("kernel/timeconst.pl")
        text = script.read_text()
        script.write_text(text.replace("defined(@val)", "@val"))
        # The board's development Ethernet init calls a conditionally compiled
        # function without a matching guard. NET=n exposes that upstream bug.
        board = Path("arch/arm/mach-omap2/board-diamond.c")
        text = board.read_text()
        call = "\tdiamond_smsc911x_init();"
        guarded = (
            "#if defined(CONFIG_SMSC911X) || defined(CONFIG_SMSC911X_MODULE)\n"
            + call
            + "\n#endif /* Hearth network-disabled probe */"
        )
        if guarded not in text:
            if text.count(call) != 1:
                raise ValueError("unexpected development Ethernet init")
            board.write_text(text.replace(call, guarded))
        # The previously unused serial gadget includes composite.c, whose
        # msleep call needs the normal kernel delay declaration.
        serial = Path("drivers/usb/gadget/serial.c")
        text = serial.read_text()
        if "#include <linux/delay.h>" not in text:
            serial.write_text("#include <linux/delay.h>\n" + text)


if __name__ == "__main__":
    main()
