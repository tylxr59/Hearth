import hashlib
import json
import os
import tarfile

import pytest

from firmware.scratch_test import preflight
from tests.test_scratch_ecc import MASK, programmed


def write_json(path, record):
    path.write_text(json.dumps(record))
    path.chmod(0o600)


@pytest.fixture
def recovery(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    folder = root / "archive"
    folder.mkdir(mode=0o700)
    mask = root / "mask.json"
    write_json(mask, {"mask_hex": MASK.hex(), "corrected_views_equal": True})
    archive = folder / "recovery.tar"
    # Sparse synthetic archive: exercise exact real member sizes/offsets without
    # allocating half a gigabyte or including any native firmware contents.
    with archive.open("xb") as stream:
        for name, size, offset, payload in (
            (preflight.RAW, 276824064, 190 * 64 * 2112, programmed() * 64),
            (preflight.DATA, 268435456, 190 * 131072, programmed()[:2048] * 64),
        ):
            info = tarfile.TarInfo(name)
            info.size = size
            stream.write(info.tobuf(format=tarfile.USTAR_FORMAT))
            start = stream.tell()
            stream.seek(start + offset)
            stream.write(payload)
            stream.seek(start + ((size + 511) // 512) * 512)
        stream.write(bytes(1024))
    archive.chmod(0o600)
    record = {
        "status": "local-recovery-archive-readback-verified",
        "archive": "recovery.tar",
        "archive_bytes": archive.stat().st_size,
        "files": {preflight.DECODE: {"sha256": hashlib.sha256(mask.read_bytes()).hexdigest()}},
    }
    with archive.open("rb") as stream:
        record["archive_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    write_json(folder / "manifest.json", record)
    return root, folder, mask, record


def test_archive_hash_and_independent_private_mask_reference(recovery):
    root, folder, mask, _ = recovery
    value, result = preflight.verify_inputs(folder, mask, root)
    assert value == MASK
    assert result == {"local_archive_verified": True, "private_mask_reference_sectors": 256}


@pytest.mark.parametrize("fault", ["archive-bytes", "archive-link", "mask-changed", "public-mask"])
def test_archive_or_provenance_failure_stops_before_usb(recovery, fault):
    root, folder, mask, _ = recovery
    archive = folder / "recovery.tar"
    if fault == "archive-bytes":
        with archive.open("r+b") as stream:
            stream.seek(2048)
            stream.write(b"broken")
    elif fault == "archive-link":
        actual = folder / "preserved.tar"
        archive.rename(actual)
        archive.symlink_to(actual)
    elif fault == "mask-changed":
        write_json(mask, {"mask_hex": "00" * 7, "corrected_views_equal": True})
    else:
        mask.chmod(0o644)
    with pytest.raises(ValueError):
        preflight.verify_inputs(folder, mask, root)


def test_independent_parity_mismatch_even_with_updated_archive_hash(recovery):
    root, folder, mask, record = recovery
    archive = folder / "recovery.tar"
    with archive.open("r+b") as stream:
        pos = 512 + 190 * 64 * 2112 + 2048 + 36
        stream.seek(pos)
        original = stream.read(1)
        stream.seek(pos)
        stream.write(bytes([original[0] ^ 1]))
    with archive.open("rb") as stream:
        record["archive_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    write_json(folder / "manifest.json", record)
    with pytest.raises(ValueError, match="encoder does not match"):
        preflight.verify_inputs(folder, mask, root)
    assert os.stat(archive).st_blocks * 512 < 2 * 1024**2
