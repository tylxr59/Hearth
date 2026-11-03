# SPDX-License-Identifier: GPL-2.0-only
"""Standalone offline BCH verifier using pinned public GPL-2.0 BCH code.

This component is invoked as a separate analysis process by the installer. NAND
bytes are DATA only. No proprietary executable is loaded or linked on the host.
"""

import ctypes
import hashlib
import json
import os
from pathlib import Path

PINS = Path(__file__).with_name("bch-input.json")
PAGE, OOB, RECORD, PAGES = 2048, 64, 2112, 131072


class BCH:
    def __init__(self, library):
        self.lib = ctypes.CDLL(str(Path(library).absolute()))
        self.lib.bch_init.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_bool]
        self.lib.bch_init.restype = ctypes.c_void_p
        self.lib.bch_free.argtypes = [ctypes.c_void_p]
        self.lib.bch_encode.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
        ]
        self.lib.bch_decode.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self.lib.bch_decode.restype = ctypes.c_int
        self.context = self.lib.bch_init(13, 4, 0x201B, False)
        if not self.context or list(
            ctypes.cast(self.context, ctypes.POINTER(ctypes.c_uint * 5)).contents
        ) != [13, 8191, 4, 52, 7]:
            raise ValueError("fixed BCH13/4 ABI required")
        self.selftest()

    def close(self):
        if self.context:
            self.lib.bch_free(self.context)
            self.context = None

    def encode(self, data):
        if type(data) is not bytes or len(data) != 512:
            raise ValueError("one 512-byte ECC chunk required")
        source, out = ctypes.create_string_buffer(data), ctypes.create_string_buffer(7)
        self.lib.bch_encode(self.context, source, 512, out)
        return out.raw

    def correct(self, data, parity):
        if len(parity) != 7:
            raise ValueError("seven parity bytes required")
        if self.encode(data) == parity:
            return data, 0, 0, True
        source, stored = ctypes.create_string_buffer(data), ctypes.create_string_buffer(parity)
        locations = (ctypes.c_uint * 4)()
        count = self.lib.bch_decode(self.context, source, 512, stored, None, None, locations)
        if not 0 <= count <= 4:
            return data, 0, 0, False
        fixed, code, d, e = bytearray(data), bytearray(parity), 0, 0
        for bit in locations[:count]:
            if bit < 4096:
                fixed[bit // 8] ^= 1 << (bit % 8)
                d += 1
            elif bit < 4152:
                bit -= 4096
                code[bit // 8] ^= 1 << (bit % 8)
                e += 1
            else:
                return data, 0, 0, False
        return bytes(fixed), d, e, self.encode(bytes(fixed)) == bytes(code)

    def selftest(self):
        original = bytes(range(256)) * 2
        parity = self.encode(original)
        for count in range(1, 5):
            damaged = bytearray(original)
            for bit in (0, 17, 900, 4095)[:count]:
                damaged[bit // 8] ^= 1 << (bit % 8)
            fixed, data_errors, ecc_errors, valid = self.correct(bytes(damaged), parity)
            if (fixed, data_errors, ecc_errors, valid) != (original, count, 0, True):
                raise ValueError("BCH synthetic data correction selftest failed")
        bad = bytes([parity[0] ^ 1]) + parity[1:]
        if self.correct(original, bad) != (original, 0, 1, True):
            raise ValueError("BCH synthetic parity correction selftest failed")


def infer_mask(source, bch, *, pages=PAGES):
    from collections import Counter

    candidates, distinct = Counter(), set()
    # Evenly sample physical pages; erased/all-FF parity does not identify a mask.
    with source.open("rb") as stream:
        for page in range(0, pages, max(1, pages // 8192)):
            stream.seek(page * RECORD)
            raw = stream.read(RECORD)
            if len(raw) != RECORD:
                raise ValueError("complete raw NAND page required")
            for chunk in range(4):
                data = raw[512 * chunk : 512 * (chunk + 1)]
                stored = raw[PAGE + 36 + 7 * chunk : PAGE + 43 + 7 * chunk]
                if stored == b"\xff" * 7 or data == b"\xff" * 512:
                    continue
                encoded = (int.from_bytes(bch.encode(data), "big") >> 4).to_bytes(7, "big")
                candidates[bytes(a ^ b for a, b in zip(encoded, stored, strict=True))] += 1
                distinct.add(hashlib.sha256(data).digest())
            if sum(candidates.values()) >= 4096:
                break
    if not candidates:
        raise ValueError("no programmed BCH samples available")
    mask, count = candidates.most_common(1)[0]
    if count < 64 or count * 100 < sum(candidates.values()) * 90 or len(distinct) < 16:
        raise ValueError("unambiguous independently sampled OMAP parity mask required")
    return mask


def decode_chunk(data, stored, mask, bch):
    if data == b"\xff" * 512 and stored == b"\xff" * 7:
        return data, "erased", 0, 0
    encoded = int.from_bytes(bytes(a ^ b for a, b in zip(stored, mask, strict=True)), "big")
    if stored == b"\xff" * 7 or encoded >> 52:
        return data, "unclassified", 0, 0
    fixed, d, e, valid = bch.correct(data, (encoded << 4).to_bytes(7, "big"))
    return fixed, "verified" if valid else "uncorrectable", d, e


def exclusive(path):
    return os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    )


def analyze(raw0, raw1, output, bch):
    from collections import Counter

    paths = (Path(raw0), Path(raw1))
    output = Path(output)
    for path in paths:
        meta = path.lstat()
        if (
            path.is_symlink()
            or not path.is_file()
            or meta.st_size != PAGES * RECORD
            or meta.st_mode & 0o077
            or meta.st_nlink != 1
        ):
            raise ValueError("complete private regular raw files required")
    mask = infer_mask(paths[0], bch, pages=PAGES)
    output.mkdir(mode=0o700, exist_ok=False)
    counters = [Counter() for _ in paths]
    raw_hash = [hashlib.sha256(), hashlib.sha256()]
    data_hash = [hashlib.sha256(), hashlib.sha256()]
    oob_equal = True
    unknown_equal = True
    marker_pages = []
    with (
        paths[0].open("rb") as a,
        paths[1].open("rb") as b,
        exclusive(output / "pass-0-data.bin") as x,
        exclusive(output / "pass-1-data.bin") as y,
    ):
        for page in range(PAGES):
            records = (a.read(RECORD), b.read(RECORD))
            dest = (x, y)
            if any(len(row) != RECORD for row in records):
                raise ValueError("raw input changed during analysis")
            oob_equal &= records[0][PAGE:] == records[1][PAGE:]
            if page % 64 in (0, 1) and records[0][PAGE : PAGE + 2] != b"\xff\xff":
                marker_pages.append(page)
            for chunk in range(4):
                decoded = []
                for pass_id, row in enumerate(records):
                    data = row[512 * chunk : 512 * (chunk + 1)]
                    parity = row[PAGE + 36 + 7 * chunk : PAGE + 43 + 7 * chunk]
                    fixed, status, d, e = decode_chunk(data, parity, mask, bch)
                    counters[pass_id][status] += 1
                    counters[pass_id]["corrected_data_bits"] += d
                    counters[pass_id]["corrected_ecc_bits"] += e
                    decoded.append((fixed, status))
                    dest[pass_id].write(fixed)
                    data_hash[pass_id].update(fixed)
                if any(status == "unclassified" for _, status in decoded):
                    unknown_equal &= (
                        records[0][512 * chunk : 512 * (chunk + 1)]
                        == records[1][512 * chunk : 512 * (chunk + 1)]
                        and decoded[0][1] == decoded[1][1]
                    )
            for i, row in enumerate(records):
                raw_hash[i].update(row)
        for stream in (x, y):
            stream.flush()
            os.fsync(stream.fileno())
    raw_digests = [h.hexdigest() for h in raw_hash]
    views = [h.hexdigest() for h in data_hash]
    for counter in counters:
        for name in (
            "verified",
            "erased",
            "unclassified",
            "uncorrectable",
            "corrected_data_bits",
            "corrected_ecc_bits",
        ):
            counter.setdefault(name, 0)
    report = {
        "format": "hearth-full-nand-quality-v1",
        "raw_sha256": raw_digests,
        "data_sha256": views,
        "raw_passes_equal": raw_digests[0] == raw_digests[1],
        "corrected_views_equal": views[0] == views[1],
        "oob_equal": bool(oob_equal),
        "unclassified_chunks_equal": bool(unknown_equal),
        "passes": [dict(c) for c in counters],
        "ecc_mask_hex": mask.hex(),
        "ecc": {
            "field_order": 13,
            "strength": 4,
            "polynomial": 0x201B,
            "chunk_bytes": 512,
            "parity_bytes": 7,
            "oob_offset": 36,
            "alignment": "right-aligned52",
        },
        "bad_blocks_skipped": False,
        "geometry": {"pages": PAGES, "page_bytes": PAGE, "oob_bytes": OOB, "passes": 2},
        "raw_marker_pages": marker_pages,
        "bad_block_interpretation": "first-two-page marker summary only; every physical OOB preserved; no remapping plan",
        "whole_chip_restoration_verified": False,
    }
    report["archive_quality_accepted"] = (
        report["corrected_views_equal"]
        and report["oob_equal"]
        and report["unclassified_chunks_equal"]
        and all(c["uncorrectable"] == 0 for c in counters)
    )
    report["all_chunks_ecc_verified"] = all(
        c["unclassified"] == 0 and c["uncorrectable"] == 0 for c in counters
    )
    with exclusive(output / "quality.json") as stream:
        stream.write((json.dumps(report, sort_keys=True, indent=2) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())
    for folder in (output, output.parent):
        directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return report
