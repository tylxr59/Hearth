import struct

import pytest

from backend.validation import Invalid
from provisioning.native_network import (
    GOOGLE_PROBE,
    FixedSpan,
    connectivity_url,
    connman_time_candidate,
    probe_candidate,
    registration_candidate,
)


def image():
    data = bytearray(0x500)
    ident = b"\x7fELF\x01\x01\x01" + bytes(9)
    struct.pack_into(
        "<16sHHIIIIIHHHHHH", data, 0, ident, 2, 40, 1, 0x10000, 52, 0x400, 0, 52, 32, 1, 40, 4, 3
    )
    struct.pack_into("<8I", data, 52, 1, 0x100, 0x10000, 0, 0x200, 0x200, 5, 4)
    names = b"\0.text\0.rodata\0.shstrtab\0"
    data[0x300 : 0x300 + len(names)] = names
    struct.pack_into("<10I", data, 0x428, 1, 1, 6, 0x10000, 0x100, 16, 0, 0, 4, 0)
    struct.pack_into("<10I", data, 0x450, 7, 1, 2, 0x10080, 0x180, 0x80, 0, 0, 4, 0)
    struct.pack_into("<10I", data, 0x478, 15, 3, 0, 0, 0x300, len(names), 0, 0, 1, 0)
    data[0x180 : 0x180 + len(GOOGLE_PROBE)] = GOOGLE_PROBE
    return bytes(data)


def test_probe_candidate_changes_only_the_exact_rodata_string():
    original = image()
    span = probe_candidate(original, "192.168.50.2", 8123)
    updated = span.apply(original)
    assert len(updated) == len(original)
    assert updated[: span.offset] == original[: span.offset]
    assert updated[span.offset + len(GOOGLE_PROBE) :] == original[span.offset + len(GOOGLE_PROBE) :]
    assert span.replacement.rstrip(b"\0") == b"http://192.168.50.2:8123/api/h/204"
    assert span.replacement.endswith(b"\0")


@pytest.mark.parametrize(
    "fault", ("duplicate", "writable", "executable", "outside", "missing", "table")
)
def test_probe_refuses_ambiguous_or_unreviewed_binary_layout(fault):
    data = bytearray(image())
    if fault == "duplicate":
        data[0x1C0 : 0x1C0 + len(GOOGLE_PROBE)] = GOOGLE_PROBE
    elif fault == "writable":
        struct.pack_into("<I", data, 0x450 + 8, 3)
    elif fault == "executable":
        struct.pack_into("<I", data, 0x450 + 8, 6)
    elif fault == "outside":
        struct.pack_into("<I", data, 0x450 + 16, 0x280)
    elif fault == "missing":
        data[0x180] = ord("x")
    else:
        struct.pack_into("<H", data, 48, 4096)
    with pytest.raises((Invalid, ValueError)):
        probe_candidate(bytes(data), "192.168.50.2", 8123)


@pytest.mark.parametrize(
    "address,port",
    (
        ("8.8.8.8", 8123),
        ("127.0.0.1", 8123),
        ("example.com", 8123),
        ("192.168.50.2", True),
        ("192.168.50.2", 80),
    ),
)
def test_probe_destination_is_literal_private_and_bounded(address, port):
    with pytest.raises(Invalid):
        connectivity_url(address, port)


CONFIG = b"# opaque settings\r\n[General]\r\nFallbackTimeservers = time.nest.com  \r\nPreferFallbackTimeservers=true\r\n[Other]\r\nUntouched=yes\r\n"


def test_connman_time_edit_preserves_every_other_byte():
    span = connman_time_candidate(CONFIG)
    assert span.apply(CONFIG) == CONFIG.replace(b"time.nest.com", b"time.nist.gov")
    assert len(span.original) == len(span.replacement) == 13


@pytest.mark.parametrize(
    "data",
    (
        CONFIG + b"[General]\n",
        CONFIG.replace(b"true", b"false"),
        CONFIG.replace(b"time.nest.com", b"time.nist.gov"),
        CONFIG.replace(b"[General]", b"[Other]"),
        CONFIG.replace(b"[Other]", b"FallbackTimeservers=time.nest.com\n[Other]"),
        CONFIG.replace(b"time.nest.com", b"time.nest.com # inline"),
        b"\0",
        b"x" * 65537,
    ),
)
def test_connman_refuses_ambiguous_or_changed_source(data):
    with pytest.raises(Invalid):
        connman_time_candidate(data)


def test_registration_candidate_keeps_xml_and_file_length():
    # A one-character-longer host is offset by the authenticated /nest/init alias.
    original = b'<config><cloud><a key="cloudregisterurl" value="https://10.0.0.1:8443/nest/entry"/></cloud><a key="uploadlogs" value="0"/></config>'
    span = registration_candidate(original, "https://10.0.0.1:8443", "https://10.0.0.12:8443")
    result = span.apply(original)
    assert len(result) == len(original) and b"https://10.0.0.12:8443/nest/init" in result
    with pytest.raises(Invalid):
        registration_candidate(original, "https://10.0.0.1:8443", "https://10.0.0.123:8443")
    with pytest.raises(Invalid):
        FixedSpan(0, b"wrong", b"right").apply(original)
