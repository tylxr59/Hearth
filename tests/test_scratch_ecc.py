import pytest

from firmware.scratch_test import ecc

# Synthetic fixed vectors independently compared with pinned public bchlib 2.1.3,
# never extracted from native firmware. The storage mask below is also synthetic.
MASK = bytes.fromhex("00112233445566")


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (bytes(512), 0),
        (b"\xff" * 512, 0xD7EC33C669538),
        (bytes(range(256)) * 2, 0xECD0E0A751C49),
    ],
)
def test_independent_bch4_vectors(data, expected):
    assert ecc.generator().bit_length() == 53
    assert ecc.parity(data) == expected


def programmed():
    data = ecc.synthetic_page()
    oob = bytearray(b"\xff" * 64)
    for i in range(4):
        encoded = ecc.parity(data[i * 512 : (i + 1) * 512]) ^ int.from_bytes(MASK, "big")
        oob[36 + i * 7 : 43 + i * 7] = encoded.to_bytes(7, "big")
    return data + oob


def test_independent_programmed_page_validation():
    page = programmed()
    assert ecc.validate_programmed(page, page, MASK) == {
        "programmed_data_verified": True,
        "independent_bch4_sectors_verified": 4,
    }


def test_every_parity_or_padding_bit_failure_detected_even_if_driver_accepts():
    page = programmed()
    for bit in range(28 * 8):
        bad = bytearray(page)
        bad[2048 + 36 + bit // 8] ^= 1 << (bit % 8)
        with pytest.raises(ValueError, match="parity"):
            ecc.validate_programmed(bad, bad, MASK)


@pytest.mark.parametrize("position", [0, 511, 512, 1024, 1536, 2047, 2048, 2049, 2083])
def test_data_and_non_parity_oob_changes_detected(position):
    page = programmed()
    bad = bytearray(page)
    bad[position] ^= 1
    with pytest.raises(ValueError):
        ecc.validate_programmed(bad, bad, MASK)


def test_raw_normal_disagreement_and_wrong_private_mask_detected():
    page = programmed()
    bad = bytearray(page)
    bad[2048 + 40] ^= 1
    with pytest.raises(ValueError, match="OOB mismatch"):
        ecc.validate_programmed(page, bad, MASK)
    with pytest.raises(ValueError, match="parity"):
        ecc.validate_programmed(page, page, b"\x00" * 7)
    for raw, normal, mask in [(page[:-1], page, MASK), (page, page, MASK[:-1])]:
        with pytest.raises(ValueError, match="fixed"):
            ecc.validate_programmed(raw, normal, mask)
