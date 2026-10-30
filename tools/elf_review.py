"""Bounded offline ARM ELF dispatch-table inspection; never execute image code."""

import argparse
import hashlib
import json
import os
import re
import stat
import struct
from pathlib import Path

MAX_BYTES = 64 * 1024 * 1024
PRIVATE = Path(__file__).resolve().parents[1] / "private"


class ArmElf:
    def __init__(self, data):
        if not 52 <= len(data) <= MAX_BYTES or data[:7] != b"\x7fELF\x01\x01\x01":
            raise ValueError("bounded little-endian ELF32 required")
        header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
        if header[1] not in (2, 3) or header[2] != 40 or header[3] != 1:
            raise ValueError("ARM executable/shared-object ELF required")
        offset, stride, count = header[5], header[9], header[10]
        if (
            stride != 32
            or not 1 <= count <= 64
            or offset < 52
            or offset + stride * count > len(data)
        ):
            raise ValueError("invalid program-header bounds")
        self.data, self.segments = data, []
        for index in range(count):
            kind, start, address, _, size, memory, flags, _ = struct.unpack_from(
                "<8I", data, offset + stride * index
            )
            if kind != 1:
                continue
            if size > memory or start + size > len(data) or address + memory > 2**32:
                raise ValueError("invalid load-segment bounds")
            if not size:
                continue
            self.segments.append((address, address + size, start, flags))
        self.segments.sort()
        if not self.segments or any(
            left[1] > right[0] for left, right in zip(self.segments, self.segments[1:])
        ):
            raise ValueError("missing or ambiguous file-backed mappings")

    def read(self, address, size):
        if not 0 <= address < 2**32 or not 0 < size <= 65536 or address + size > 2**32:
            raise ValueError("bounded virtual address range required")
        for begin, end, offset, _ in self.segments:
            if begin <= address and address + size <= end:
                start = offset + address - begin
                return self.data[start : start + size]
        raise ValueError("address is not entirely file-backed")

    def executable(self, address):
        address &= ~1  # ARM/Thumb function pointers; no instruction is executed.
        return any(begin <= address < end and flags & 1 for begin, end, _, flags in self.segments)

    def identifier(self, address, interface=False):
        value = bytearray()
        for index in range(129):
            byte = self.read(address + index, 1)[0]
            if not byte:
                break
            value.append(byte)
        else:
            raise ValueError("unterminated or oversized dispatch identifier")
        pattern = (
            rb"(?:[A-Za-z_][A-Za-z0-9_]*\.)+[A-Za-z_][A-Za-z0-9_]*"
            if interface
            else rb"[A-Za-z_][A-Za-z0-9_]*"
        )
        if not re.fullmatch(pattern, value):
            raise ValueError("invalid dispatch identifier")
        return value.decode("ascii")

    def dispatch(self, address, limit=64):
        if address % 4 or not 1 <= limit <= 128:
            raise ValueError("aligned dispatch table and bounded record limit required")
        result = []
        for index in range(limit + 1):
            interface, method, handler = struct.unpack("<III", self.read(address + index * 12, 12))
            if not (interface or method or handler):
                return result
            if index == limit or not interface or not method or not self.executable(handler):
                raise ValueError("invalid or unterminated dispatch table")
            result.append(
                {
                    "interface": self.identifier(interface, interface=True),
                    "method": self.identifier(method),
                    "handler": handler,
                }
            )
        raise ValueError("dispatch table limit exceeded")

    def commands(self, address, count):
        """Read fixed-count name/handler/metadata triples identified in disassembly."""
        if address % 4 or not 1 <= count <= 128:
            raise ValueError("aligned command table and bounded count required")
        result, names = [], set()
        for index in range(count):
            name, handler, metadata = struct.unpack("<III", self.read(address + index * 12, 12))
            if not self.executable(handler):
                raise ValueError("command handler is not file-backed executable code")
            name = self.identifier(name)
            if name in names:
                raise ValueError("ambiguous duplicate command name")
            names.add(name)
            result.append({"name": name, "handler": handler, "metadata_word": metadata})
        return result


def private_path(path):
    path = Path(path).absolute()
    if not path.is_relative_to(PRIVATE) or path.resolve() != path:
        raise ValueError("path must remain below the private directory without symlinks")
    return path


def review(source, addresses, output, command_tables=()):
    source, output = private_path(source), private_path(output)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("fresh output in an existing private directory required")
    if stat.S_IMODE(output.parent.stat().st_mode) & 0o077:
        raise ValueError("output directory must be restricted to its owner")
    with source.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("regular ELF source required")
        data = stream.read(MAX_BYTES + 1)
    elf = ArmElf(data)
    if not 1 <= len(addresses) + len(command_tables) <= 16:
        raise ValueError("one to sixteen reviewed tables required")
    tables = [{"address": address, "entries": elf.dispatch(address)} for address in addresses]
    commands = [
        {"address": address, "entries": elf.commands(address, count)}
        for address, count in command_tables
    ]
    report = {
        "status": "offline-dispatch-review",
        "runtime_verified": False,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "tables": tables,
        "command_tables": commands,
    }
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    summary = {
        "status": report["status"],
        "tables": len(tables),
        "methods": sum(len(table["entries"]) for table in tables),
        "runtime_verified": False,
    }
    if commands:
        summary["commands"] = sum(len(table["entries"]) for table in commands)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--table", action="append", default=[], type=lambda value: int(value, 0))
    parser.add_argument(
        "--commands",
        nargs=2,
        action="append",
        default=[],
        metavar=("ADDRESS", "COUNT"),
        type=lambda value: int(value, 0),
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(review(args.source, args.table, args.output, args.commands), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, "Offline review failed: " + str(exc) + "\n")
