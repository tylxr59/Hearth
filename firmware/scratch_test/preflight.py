"""Private archive/mask verification before any experimental USB execution."""

import hashlib
import json
import os
import stat
import tarfile
from pathlib import Path

if __package__:
    from firmware.nand_ecc_sample.reference import private_bytes
    from firmware.scratch_test.ecc import parity
else:
    from ecc_helper import parity
    from reference_helper import private_bytes

DECODE = "private/nand-analysis-20261030/bch4-decode.json"
RAW = "private/nand-capture-20261030/pass-0.raw"
DATA = "private/nand-analysis-20261030/pass-0-bch4-data.bin"


def verify_inputs(archive_directory, mask_record, private_root):
    root = Path(private_root).absolute()
    info = root.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError("owner-only private root required")
    folder = Path(archive_directory).absolute()
    record = json.loads(private_bytes(folder / "manifest.json", 65536, root))
    mask_bytes = private_bytes(mask_record, 65536, root)
    decoded = json.loads(mask_bytes)
    if (
        not isinstance(record, dict)
        or not isinstance(decoded, dict)
        or not isinstance(record.get("files"), dict)
    ):
        raise TypeError("private archive and BCH records must be mappings")
    if (
        record.get("status") != "local-recovery-archive-readback-verified"
        or record.get("archive") != "recovery.tar"
        or record.get("files", {}).get(DECODE, {}).get("sha256")
        != hashlib.sha256(mask_bytes).hexdigest()
        or decoded.get("corrected_views_equal") is not True
    ):
        raise ValueError("private archive and BCH provenance mismatch")
    try:
        mask = bytes.fromhex(decoded["mask_hex"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid private BCH4 mask record") from exc
    if len(mask) != 7:
        raise ValueError("seven-byte private BCH4 mask required")
    path = folder / "recovery.tar"
    if not path.is_relative_to(root) or path.resolve() != path:
        raise ValueError("private archive must not traverse symlinks")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or not 1 <= info.st_size <= 2 * 1024**3
            or info.st_size != record.get("archive_bytes")
            or hashlib.file_digest(stream, "sha256").hexdigest() != record.get("archive_sha256")
        ):
            raise ValueError("local recovery archive identity or permissions mismatch")
        stream.seek(0)
        with tarfile.open(fileobj=stream, mode="r:") as archive:
            raw_member, data_member = archive.getmember(RAW), archive.getmember(DATA)
            if (
                not raw_member.isfile()
                or not data_member.isfile()
                or raw_member.size != 276824064
                or data_member.size != 268435456
            ):
                raise ValueError("archive does not contain fixed original recovery inputs")
            with archive.extractfile(raw_member) as raw_stream:
                raw_stream.seek(190 * 64 * 2112)
                raw = raw_stream.read(64 * 2112)
            with archive.extractfile(data_member) as data_stream:
                data_stream.seek(190 * 131072)
                data = data_stream.read(131072)
    if len(raw) != 135168 or len(data) != 131072:
        raise ValueError("bounded recovery reference incomplete")
    checked = 0
    for page in range(64):
        for sector in range(4):
            part = data[page * 2048 + sector * 512 : page * 2048 + (sector + 1) * 512]
            pos = page * 2112 + 2048 + 36 + sector * 7
            stored = raw[pos : pos + 7]
            if stored == b"\xff" * 7 and part == b"\xff" * 512:
                continue
            protected = (int.from_bytes(stored, "big") ^ int.from_bytes(mask, "big")) & (
                (1 << 52) - 1
            )
            if parity(part) != protected:
                raise ValueError("independent BCH4 encoder does not match preserved reference")
            checked += 1
    if checked < 16:
        raise ValueError("insufficient programmed reference sectors for private mask validation")
    return mask, {"local_archive_verified": True, "private_mask_reference_sectors": checked}
