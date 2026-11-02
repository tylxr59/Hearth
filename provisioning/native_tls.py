"""Original one-instruction TLS correction from bounded ELF/ABI observations.

No proprietary byte patterns, input hashes, execution, network or device API.
Only the measured Gen2/5.9.4-5 hook shape is supported. All other bytes survive
unchanged. This is replacement DATA preparation, not installation permission.
"""

import struct

from tools.elf_review import ArmElf

HOOK = "_Z9sslctxfunPvS_S_"
VERIFY = "SSL_CTX_set_verify"


def word(data, at=0):
    return struct.unpack_from("<I", data, at)[0]


def mov(register, value):
    """Encode our own A32 `mov register, #imm8`, without changing flags."""
    if not 0 <= register <= 15 or not 0 <= value <= 255:
        raise ValueError("bounded original MOV instruction required")
    return 0xE3A00000 | register << 12 | value


class Metadata:
    def __init__(self, data):
        self.elf = ArmElf(data)
        h = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
        at, stride, count = h[6], h[11], h[12]
        if stride != 40 or not 1 <= count <= 4096 or at < 52 or at + count * stride > len(data):
            raise ValueError("bounded ELF32 section table required")
        self.sections = [struct.unpack_from("<10I", data, at + i * stride) for i in range(count)]
        for row in self.sections:
            if row[1] != 8 and row[4] + row[5] > len(data):
                raise ValueError("section outside original ELF")
        self.data = data
        self.symbols = {}
        self.relocations = []
        symbols_left, relocations_left = 32768, 32768
        for index, row in enumerate(self.sections):
            if row[1] != 11:
                continue
            if row[9] != 16 or row[5] % 16 or row[5] // 16 > 32768 or row[6] >= count:
                raise ValueError("bounded dynamic symbol table required")
            symbols_left -= row[5] // 16
            if symbols_left < 0:
                raise ValueError("total dynamic symbol budget exceeded")
            strings = self.sections[row[6]]
            if strings[1] != 3 or strings[5] > 2 * 1024 * 1024:
                raise ValueError("dynamic symbol string table required")
            text = data[strings[4] : strings[4] + strings[5]]
            for i in range(row[5] // 16):
                name, value, size, info, _, section = struct.unpack_from(
                    "<IIIBBH", data, row[4] + i * 16
                )
                if name >= len(text):
                    raise ValueError("symbol name outside string table")
                end = text.find(b"\0", name, min(name + 256, len(text)))
                if end < 0:
                    raise ValueError("bounded terminated symbol name required")
                label = text[name:end]
                self.symbols[index, i] = (label, value, size, info, section)
        for row in self.sections:
            if row[1] != 9:
                continue
            if row[9] != 8 or row[5] % 8 or row[5] // 8 > 32768:
                raise ValueError("bounded ARM dynamic relocations required")
            relocations_left -= row[5] // 8
            if relocations_left < 0:
                raise ValueError("total dynamic relocation budget exceeded")
            for i in range(row[5] // 8):
                address, info = struct.unpack_from("<2I", data, row[4] + i * 8)
                if info & 255 != 22:  # R_ARM_JUMP_SLOT, not a guessed PLT position.
                    continue
                symbol = self.symbols.get((row[6], info >> 8))
                if symbol is None:
                    raise ValueError("dynamic relocation has no symbol")
                self.relocations.append((address, symbol))

    def function(self, name):
        found = [row for row in self.symbols.values() if row[0] == name.encode() and row[4] != 0]
        if len(found) != 1:
            raise ValueError("one measured native hook export required")
        _, address, size, info, section = found[0]
        if (
            info & 15 != 2
            or info >> 4 not in (1, 2)
            or address & 3
            or section >= len(self.sections)
            or not self.sections[section][2] & 4
            or not self.elf.executable(address)
            or not self.sections[section][3] <= address
            or address + size > self.sections[section][3] + self.sections[section][5]
        ):
            raise ValueError("file-backed exported ARM function required")
        return address, size

    def file_offset(self, address):
        matches = [
            offset + address - start
            for start, end, offset, flags in self.elf.segments
            if start <= address and address + 4 <= end and flags & 1
        ]
        if len(matches) != 1:
            raise ValueError("one executable word mapping required")
        return matches[0]


def immediate(instruction):
    amount = ((instruction >> 8) & 15) * 2
    value = instruction & 255
    return ((value >> amount) | (value << ((32 - amount) & 31))) & 0xFFFFFFFF


def add(instruction, destination, base):
    if (
        instruction >> 28 != 14
        or (instruction >> 25) & 7 != 1
        or (instruction >> 21) & 15 != 4
        or instruction & (1 << 20)
        or (instruction >> 16) & 15 != base
        or (instruction >> 12) & 15 != destination
    ):
        raise ValueError("measured A32 ADD-immediate PLT form required")
    return immediate(instruction)


def verify_call(metadata, address, instruction):
    if instruction >> 24 != 0xEB:
        raise ValueError("unconditional ARM BL required")
    relative = instruction & 0xFFFFFF
    if relative & 0x800000:
        relative -= 1 << 24
    target = address + 8 + 4 * relative
    if not metadata.elf.executable(target):
        raise ValueError("file-backed PLT call required")
    first, second, load = struct.unpack("<3I", metadata.elf.read(target, 12))
    got = (target + 8 + add(first, 12, 15) + add(second, 12, 12)) & 0xFFFFFFFF
    if (
        load >> 28 != 14
        or (load >> 26) & 3 != 1
        or load & (1 << 25)
        or not load & (1 << 24)
        or load & (1 << 22)
        or not load & (1 << 21)
        or not load & (1 << 20)
        or (load >> 16) & 15 != 12
        or (load >> 12) & 15 != 15
    ):
        raise ValueError("measured ARM PLT indirect jump required")
    got = (got + (load & 4095) * (1 if load & (1 << 23) else -1)) & 0xFFFFFFFF
    if not any(
        start <= got and got + 4 <= end and flags & 2
        for start, end, _, flags in metadata.elf.segments
    ):
        raise ValueError("file-backed writable PLT relocation slot required")
    entries = [symbol for address, symbol in metadata.relocations if address == got]
    if (
        len(entries) != 1
        or entries[0][0] != VERIFY.encode()
        or entries[0][4] != 0
        or entries[0][3] & 15 != 2
        or entries[0][3] >> 4 not in (1, 2)
    ):
        raise ValueError("hook call must resolve to imported SSL_CTX_set_verify")


def strict_tls(data, *, model, software_version):
    if model != "Display-2.6" or software_version != "5.9.4-5":
        raise ValueError("measured Gen2 native software profile required")
    if type(data) is not bytes or len(data) > 1024 * 1024:
        raise ValueError("bounded original native web-service ELF required")
    metadata = Metadata(data)
    address, size = metadata.function(HOOK)
    if size != 56:
        raise ValueError("measured native TLS hook size required")
    body = metadata.elf.read(address, size)
    if word(body, 20) != mov(1, 1) or word(body, 40) != mov(0, 0):
        raise ValueError("SSL_VERIFY_PEER and native return contract required")
    # Between the mode assignment and call, only the measured frame-save/frame
    # setup and callback argument may occur. Neither can overwrite r1.
    frame, setup = word(body, 24), word(body, 28)
    if (
        frame >> 28 != 14
        or (frame >> 25) & 7 != 4
        or (frame >> 16) & 15 != 13
        or frame & (1 << 20)
        or frame & 2
        or setup >> 28 != 14
        or (setup >> 25) & 7 != 1
        or (setup >> 21) & 15 != 2
        or setup & (1 << 20)
        or (setup >> 16) & 15 != 12
        or (setup >> 12) & 15 != 11
        or immediate(setup) != 4
    ):
        raise ValueError("measured native hook frame shape required")
    verify_call(metadata, address + 36, word(body, 36))
    old = word(body, 32)
    if old == mov(2, 0):
        return data
    if (
        old >> 28 != 14
        or (old >> 25) & 7 != 3
        or not old & (1 << 24)
        or not old & (1 << 23)
        or old & (1 << 22)
        or old & (1 << 21)
        or not old & (1 << 20)
        or (old >> 16) & 15 != 3
        or (old >> 12) & 15 != 2
        or old & 4095 != 2
    ):
        raise ValueError("measured native callback pointer load required")
    offset = metadata.file_offset(address + 32)
    return data[:offset] + struct.pack("<I", mov(2, 0)) + data[offset + 4 :]
