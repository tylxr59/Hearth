"""Independent synthetic ELF/ARM instruction data, never vendor bytes or execution."""

import struct

import pytest

from provisioning.native_tls import strict_tls

PROFILE = {"model": "Display-2.6", "software_version": "5.9.4-5"}


def synthetic():
    data = bytearray(2048)
    ident = b"\x7fELF\x01\x01\x01" + b"\0" * 9
    data[:52] = struct.pack(
        "<16sHHIIIIIHHHHHH", ident, 3, 40, 1, 0x1100, 52, 1536, 0, 52, 32, 2, 40, 7, 0
    )
    data[52:84] = struct.pack("<8I", 1, 0, 0x1000, 0x1000, 768, 768, 5, 4096)
    data[84:116] = struct.pack("<8I", 1, 768, 0x1300, 0x1300, 768, 768, 6, 4096)
    # Original synthetic A32 data instructions. This is not a runnable app.
    body = [0xE1A00000] * 14
    body[5] = 0xE3A01001  # mov r1,#SSL_VERIFY_PEER
    body[6] = 0xE92DD800  # save frame registers without writing r1
    body[7] = 0xE24CB004  # sub fp,ip,#4
    body[8] = 0xE7932002  # ldr r2,[r3,r2]
    body[9] = 0xEB000035  # bl the synthetic PLT stub at0x1200
    body[10] = 0xE3A00000  # mov r0,#0
    data[256:312] = struct.pack("<14I", *body)
    data[512:524] = struct.pack("<3I", 0xE28FC000, 0xE28CC000, 0xE5BCF0F8)
    strings = b"\0_Z9sslctxfunPvS_S_\0SSL_CTX_set_verify\0"
    data[1088 : 1088 + len(strings)] = strings
    data[1024:1072] = (
        b"\0" * 16
        + struct.pack("<IIIBBH", 1, 0x1100, 56, 0x12, 0, 1)
        + struct.pack("<IIIBBH", strings.index(b"SSL_"), 0, 0, 0x12, 0, 0)
    )
    data[1280:1288] = struct.pack("<2I", 0x1300, 2 << 8 | 22)
    sections = (
        (0,) * 10,
        (0, 1, 6, 0x1100, 256, 56, 0, 0, 4, 0),
        (0, 11, 2, 0x1400, 1024, 48, 3, 1, 4, 16),
        (0, 3, 2, 0x1440, 1088, len(strings), 0, 0, 1, 0),
        (0, 9, 2, 0x1500, 1280, 8, 2, 5, 4, 8),
        (0, 1, 3, 0x1300, 768, 4, 0, 0, 4, 0),
        (0, 1, 6, 0x1200, 512, 12, 0, 0, 4, 0),
    )
    for i, row in enumerate(sections):
        struct.pack_into("<10I", data, 1536 + i * 40, *row)
    opaque = b"opaque\0\xffdataXYZ!"
    data[800 : 800 + len(opaque)] = opaque
    return bytes(data)


def test_one_original_instruction_is_replaced_and_every_other_byte_survives():
    original = synthetic()
    replacement = strict_tls(original, **PROFILE)
    at = 256 + 32
    assert replacement[:at] == original[:at] and replacement[at + 4 :] == original[at + 4 :]
    assert struct.unpack_from("<I", replacement, at)[0] == 0xE3A02000
    assert replacement != original and len(replacement) == len(original)
    assert strict_tls(replacement, **PROFILE) == replacement


@pytest.mark.parametrize(
    "fault",
    (
        "peer",
        "hook_size",
        "callback_register",
        "call",
        "relocation_type",
        "relocation_symbol",
        "got",
        "hook_type",
        "section",
        "frame_r1",
        "frame_load",
        "frame_setup",
        "return",
        "sections_outside_file",
        "string_outside_table",
        "plt_operation",
    ),
)
def test_unknown_hook_call_or_elf_shape_refuses_before_any_output(fault):
    data = bytearray(synthetic())
    changes = {
        "peer": (256 + 20, 0xE3A01000),
        "hook_size": (1024 + 16 + 8, 52),
        "callback_register": (256 + 32, 0xE7933002),
        "call": (256 + 36, 0xEB000000),
        "relocation_type": (1284, 2 << 8 | 23),
        "relocation_symbol": (1284, 1 << 8 | 22),
        "got": (1280, 0x1304),
        "hook_type": (1024 + 16 + 12, 1 << 16 | 0x11),
        "section": (1536 + 40 + 8, 2),
        "frame_r1": (256 + 24, 0xE92DD802),
        "frame_load": (256 + 24, 0xE93DD800),
        "frame_setup": (256 + 28, 0xE24C1004),
        "return": (256 + 40, 0xE3A00001),
        "sections_outside_file": (32, 2**32 - 40),
        "string_outside_table": (1024 + 16, 2**32 - 1),
        "plt_operation": (512, 0xE24FC000),
    }
    struct.pack_into("<I", data, *changes[fault])
    with pytest.raises(ValueError):
        strict_tls(bytes(data), **PROFILE)


@pytest.mark.parametrize("changes", ({"model": "Display-1.0"}, {"software_version": "other"}))
def test_unmeasured_device_profile_is_not_inferred(changes):
    with pytest.raises(ValueError, match="measured"):
        strict_tls(synthetic(), **(PROFILE | changes))


def test_strict_input_still_requires_valid_peer_mode_and_import_binding():
    data = bytearray(strict_tls(synthetic(), **PROFILE))
    struct.pack_into("<I", data, 256 + 20, 0xE3A01000)
    with pytest.raises(ValueError):
        strict_tls(bytes(data), **PROFILE)
