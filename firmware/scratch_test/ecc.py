"""Original independent BCH4 encoding check; no firmware execution or decoding.

The private inferred seven-byte storage mask is an explicit host-only input.
It must never be logged, committed or sent to the target.
"""

from functools import lru_cache

if __package__:
    from firmware.scratch_test.backup import OOB, PAGE, RECORD
else:
    from backup_helper import OOB, PAGE, RECORD


def multiply(a, b):
    """GF(2^13), primitive polynomial x^13+x^4+x^3+x+1."""
    result = 0
    while b:
        if b & 1:
            result ^= a
        b >>= 1
        a <<= 1
        if a & (1 << 13):
            a ^= 0x201B
    return result


@lru_cache(maxsize=1)
def generator():
    # Narrow-sense binary BCH t=4: take the union of Frobenius conjugates
    # for roots alpha^1 through alpha^8. Repeated roots are included once.
    roots = set()
    for exponent in range(1, 9):
        value = exponent
        while value not in roots:
            roots.add(value)
            value = (2 * value) % 8191
    powers = [1]
    for _ in range(max(roots)):
        powers.append(multiply(powers[-1], 2))
    coefficients = [1]
    for exponent in sorted(roots):
        updated = [0] * (len(coefficients) + 1)
        for i, coefficient in enumerate(coefficients):
            updated[i] ^= multiply(coefficient, powers[exponent])
            updated[i + 1] ^= coefficient
        coefficients = updated
    if len(coefficients) != 53 or any(c not in (0, 1) for c in coefficients):
        raise ValueError("invalid binary BCH4 generator")
    return sum(c << i for i, c in enumerate(coefficients))


def parity(data):
    """512 data bytes -> right-aligned 52 protected parity bits."""
    if len(data) != 512:
        raise ValueError("one fixed 512-byte BCH4 sector required")
    remainder = int.from_bytes(data, "big") << 52
    polynomial = generator()
    while remainder.bit_length() > 52:
        remainder ^= polynomial << (remainder.bit_length() - 53)
    return remainder


def synthetic_page():
    return bytes(((i * 73) ^ (i >> 8) ^ 0xA5) & 0xFF for i in range(PAGE))


def validate_programmed(raw, normal, storage_mask):
    if len(raw) != RECORD or len(normal) != RECORD or len(storage_mask) != 7:
        raise ValueError("fixed programmed page/OOB and private mask required")
    expected = synthetic_page()
    if raw[:PAGE] != expected or normal[:PAGE] != expected or raw[PAGE:] != normal[PAGE:]:
        raise ValueError("programmed data or physical OOB mismatch")
    oob = raw[PAGE:]
    if len(oob) != OOB or oob[:36] != b"\xff" * 36:
        raise ValueError("unexpected programmed marker/free OOB bytes")
    mask = int.from_bytes(storage_mask, "big")
    for sector in range(4):
        stored = int.from_bytes(oob[36 + sector * 7 : 43 + sector * 7], "big")
        if stored ^ mask != parity(expected[sector * 512 : (sector + 1) * 512]):
            raise ValueError("independent programmed BCH4 parity mismatch")
    return {"programmed_data_verified": True, "independent_bch4_sectors_verified": 4}
