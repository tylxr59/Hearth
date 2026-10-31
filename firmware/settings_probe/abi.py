"""Bounded symbol/layout gate for the reviewed private native-settings revision."""

import struct

from firmware.tls_probe.package import sha
from tools.elf_review import ArmElf

METHODS = {
    "_ZN10nlSettingsC1Ev": (0x2A630, 112),
    "_ZN10nlSettingsD1Ev": (0x2AF38, 120),
    "_ZN10nlSettings4InitEPKc": (0x2A5B8, 120),
    "_ZN10nlSettings5WriteEv": (0x2AFD4, 980),
    "_ZN10nlSettings8SetValueEPKcS1_": (0x2AA38, 100),
    "_ZNK10nlSettings8GetValueEPKc": (0x2A70C, 60),
}


def review(data):
    elf = ArmElf(data)
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    offset, stride, count = header[6], header[11], header[12]
    if stride != 40 or not 1 <= count <= 256 or offset + stride * count > len(data):
        raise ValueError("bounded native section table required")
    sections = [struct.unpack_from("<10I", data, offset + i * stride) for i in range(count)]
    found = {}
    for section in sections:
        if section[1] != 11:
            continue
        start, size, link = section[4:7]
        if (
            section[9] != 16
            or size % 16
            or size > 8192 * 16
            or start + size > len(data)
            or not 0 <= link < count
        ):
            raise ValueError("invalid bounded dynamic symbol table")
        strings = sections[link]
        begin, length = strings[4:6]
        if strings[1] != 3 or length > 1024 * 1024 or begin + length > len(data):
            raise ValueError("invalid bounded dynamic string table")
        names = data[begin : begin + length]
        for pos in range(start, start + size, 16):
            name, value, extent, info, _, index = struct.unpack_from("<IIIBBH", data, pos)
            if name >= length:
                raise ValueError("invalid dynamic name offset")
            end = names.find(b"\0", name, min(name + 257, length))
            if end < 0:
                raise ValueError("unterminated dynamic symbol")
            symbol = names[name:end].decode("ascii")
            if symbol not in METHODS:
                continue
            if (
                symbol in found
                or (value, extent) != METHODS[symbol]
                or info != 0x12
                or not index
                or not elf.executable(value)
            ):
                raise ValueError("reviewed native-settings method differs")
            found[symbol] = sha(elf.read(value, extent))
    if set(found) != set(METHODS) or elf.read(0x2A690, 8) != struct.pack("<II", 0, 1):
        raise ValueError("native-settings ABI/layout not matched")
    return {"source_sha256": sha(data), "object_bytes": 48, "method_sha256": found}
