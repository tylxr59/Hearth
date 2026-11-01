"""Offline fixed-width network candidates. No device access or installation.

Candidates preserve file length and all bytes outside the reviewed span. The
large native client is never executed or repackaged as a deployable image here.
Target acquisition, write protection, transactional application and restoration
remain separate gates; preparing these DATA objects grants none of them.
"""

import ipaddress
import re
import struct
from dataclasses import dataclass
from urllib.parse import urlsplit

from backend.validation import Invalid, endpoint
from firmware.harden import client_config
from tools.elf_review import ArmElf

GOOGLE_PROBE = b"http://clients3.google.com/generate_204\0"
PROBE_PATH = "/api/h/204"


@dataclass(frozen=True)
class FixedSpan:
    offset: int
    original: bytes
    replacement: bytes

    def apply(self, data):
        if (
            type(data) is not bytes
            or type(self.original) is not bytes
            or type(self.replacement) is not bytes
            or type(self.offset) is not int
            or self.offset < 0
            or not self.original
            or len(self.original) > 64
            or len(self.original) != len(self.replacement)
            or data[self.offset : self.offset + len(self.original)] != self.original
        ):
            raise Invalid("exact original and equal-width reviewed span required")
        return data[: self.offset] + self.replacement + data[self.offset + len(self.original) :]


def connectivity_url(address, port):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise Invalid("explicit unprivileged probe port required")
    parsed = urlsplit(endpoint(f"https://{address}:{port}"))
    destination = ipaddress.ip_address(parsed.hostname)
    if destination.is_loopback or destination.is_link_local:
        raise Invalid("reachable private HA address required")
    value = ("http://" + parsed.netloc + PROBE_PATH).encode("ascii")
    if len(value) >= len(GOOGLE_PROBE):
        raise Invalid("local probe URL exceeds reviewed string slot")
    return value


def probe_candidate(data, address, port):
    """Replace one exact terminated probe string inside an allocated RO data section."""
    elf = ArmElf(data)
    if data.count(GOOGLE_PROBE) != 1:
        raise Invalid("one exact terminated Google probe string required")
    offset = data.index(GOOGLE_PROBE)
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    table, stride, count, names_index = header[6], header[11], header[12], header[13]
    if (
        stride != 40
        or not 1 <= count <= 4096
        or not 0 < names_index < count
        or table < 52
        or table + stride * count > len(data)
    ):
        raise Invalid("bounded ELF section table required")
    sections = [struct.unpack_from("<10I", data, table + stride * i) for i in range(count)]
    strings = sections[names_index]
    if strings[1] != 3 or strings[5] > 1024 * 1024 or strings[4] + strings[5] > len(data):
        raise Invalid("bounded ELF section-name table required")
    names = data[strings[4] : strings[4] + strings[5]]
    matched = []
    for section in sections:
        if section[0] >= len(names):
            raise Invalid("invalid section name index")
        end = names.find(b"\0", section[0])
        if end < 0:
            raise Invalid("unterminated section name")
        name = names[section[0] : end]
        if section[4] <= offset and offset + len(GOOGLE_PROBE) <= section[4] + section[5]:
            matched.append(section)
            if (
                name != b".rodata"
                or section[1] != 1
                or section[2] & 7 != 2
                or section[4] + section[5] > len(data)
            ):
                raise Invalid("probe string must be allocated non-writable non-code rodata")
            if elf.read(section[3] + offset - section[4], len(GOOGLE_PROBE)) != GOOGLE_PROBE:
                raise Invalid("probe section differs from loaded image")
    if len(matched) != 1:
        raise Invalid("one unambiguous probe section required")
    url = connectivity_url(address, port)
    return FixedSpan(offset, GOOGLE_PROBE, url + bytes(len(GOOGLE_PROBE) - len(url)))


def connman_time_candidate(data):
    if type(data) is not bytes or len(data) > 65536 or b"\0" in data:
        raise Invalid("bounded ConnMan configuration required")
    section, general_count, seen, offset, selected = None, 0, set(), 0, None
    for line in data.splitlines(keepends=True):
        header = re.fullmatch(rb"[ \t]*\[([^\]\r\n]+)\][ \t]*(?:\r?\n)?", line)
        if header:
            section = header[1]
            general_count += section == b"General"
        elif not line.lstrip().startswith((b"#", b";")):
            possible = re.match(rb"[ \t]*(FallbackTimeservers|PreferFallbackTimeservers)\b", line)
            if possible:
                match = re.fullmatch(
                    rb"[ \t]*(FallbackTimeservers|PreferFallbackTimeservers)[ \t]*=[ \t]*"
                    rb"(?P<value>[^ \t\r\n#;]+)[ \t]*(?:\r?\n)?",
                    line,
                )
                if not match or section != b"General" or match[1] in seen:
                    raise Invalid("ambiguous ConnMan time setting")
                seen.add(match[1])
                expected = b"time.nest.com" if match[1] == b"FallbackTimeservers" else b"true"
                if match["value"] != expected:
                    raise Invalid("reviewed preferred Nest fallback time source required")
                if match[1] == b"FallbackTimeservers":
                    selected = FixedSpan(offset + match.start("value"), expected, b"time.nist.gov")
        offset += len(line)
    if general_count != 1 or seen != {b"FallbackTimeservers", b"PreferFallbackTimeservers"}:
        raise Invalid("one General section and both time settings required")
    return selected


def registration_candidate(data, old_origin, new_origin):
    if type(data) is not bytes:
        raise Invalid("native client configuration bytes required")
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise Invalid("UTF-8 client configuration required") from exc
    if client_config(text, old_origin).encode("utf-8") != data:
        raise Invalid("reviewed current registration URL and logs-off required")
    old = (endpoint(old_origin) + "/nest/entry").encode("ascii")
    new = (endpoint(new_origin) + "/nest/init").encode("ascii")
    if len(old) != len(new) or data.count(old) != 1:
        raise Invalid("one equal-width registration URL transition required")
    return FixedSpan(data.index(old), old, new)
