"""Original BCH fixtures and full-archive gates; never device or native firmware."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from installer import nand_backup, workflow
from tools.nand_archive import bch as module
from tools.nand_archive.bch import BCH, analyze, decode_chunk, infer_mask
from tools.nand_archive.build import checked_library


@pytest.fixture(scope="module")
def decoder():
    library = os.environ.get("HEARTH_BCH_LIBRARY")
    if not library:
        pytest.skip("explicit pinned public BCH library required for native verifier checks")
    instance = BCH(checked_library(Path(library)))
    yield instance
    instance.close()


def test_public_bch_decoder_corrects_parity_bit_order_at_both_ends(decoder):
    data = bytes(range(256)) * 2
    parity = decoder.encode(data)
    for bit in range(56):
        if 48 <= bit < 52:
            continue  # BCH52 is left-aligned, with four zero padding bits.
        damaged = bytearray(parity)
        damaged[bit // 8] ^= 1 << (bit % 8)
        assert decoder.correct(data, bytes(damaged)) == (data, 0, 1, True)


def raw_pages(decoder, pages, mask, *, errors=False):
    for page in range(pages):
        contents = []
        codes = []
        for chunk in range(4):
            seed = hashlib.sha256(f"original synthetic page{page}chunk{chunk}".encode()).digest()
            data = seed * 16
            ecc = (int.from_bytes(decoder.encode(data), "big") >> 4).to_bytes(7, "big")
            codes.append(bytes(a ^ b for a, b in zip(ecc, mask, strict=True)))
            if errors and page % 5 == 0 and chunk == 0:
                data = bytes([data[0] ^ 1]) + data[1:]
            contents.append(data)
        yield b"".join(contents) + b"\xff" * 36 + b"".join(codes)


def test_sampled_mask_and_ecc_views_match_with_independent_raw_errors(
    decoder, tmp_path, monkeypatch
):
    monkeypatch.setattr(module, "PAGES", 64)
    mask = b"\xa3\x22\x11\x45\x67\x89\xab"
    paths = []
    for i in range(2):
        path = tmp_path / f"raw{i}"
        path.write_bytes(b"".join(raw_pages(decoder, 64, mask, errors=bool(i))))
        path.chmod(0o600)
        paths.append(path)
    assert infer_mask(paths[0], decoder, pages=64) == mask
    report = analyze(*paths, tmp_path / "analysis", decoder)
    assert report["archive_quality_accepted"] and report["all_chunks_ecc_verified"]
    assert (
        not report["raw_passes_equal"] and report["corrected_views_equal"] and report["oob_equal"]
    )
    assert report["passes"][1]["corrected_data_bits"] == 13
    assert report["whole_chip_restoration_verified"] is False


def test_erased_and_unclassified_chunks_are_preserved_without_claiming_ecc():
    class Never:
        def correct(self, *a):
            pytest.fail("unclassified chunks must not be guessed")

    assert decode_chunk(b"\xff" * 512, b"\xff" * 7, b"\0" * 7, Never()) == (
        b"\xff" * 512,
        "erased",
        0,
        0,
    )
    assert decode_chunk(b"a" * 512, b"\xff" * 7, b"\0" * 7, Never()) == (
        b"a" * 512,
        "unclassified",
        0,
        0,
    )


@pytest.fixture
def archive(tmp_path, monkeypatch):
    from firmware.file_writer.run import encode, save
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    tmp_path.chmod(0o700)
    session = tmp_path / "session"
    session.mkdir(mode=0o700)
    save(
        session,
        "identity.json",
        encode(
            {
                "model": "Display-2.6",
                "software": "5.9.4-5",
                "partition": "primary",
                "serial": "synthetic-unit",
            }
        ),
    )
    save(session, "installer-source.zip", b"public source fixture")
    root = session / "nand"
    root.mkdir(mode=0o700)
    for name in ("raw", "analysis"):
        (root / name).mkdir(mode=0o700)
    monkeypatch.setattr(nand_backup.profile, "check", lambda _: {})
    for i in range(2):
        for path, size in (
            (root / f"raw/pass-{i}.raw", 276824064),
            (root / f"analysis/pass-{i}-data.bin", 268435456),
        ):
            with path.open("wb") as stream:
                stream.truncate(size)
            path.chmod(0o600)
    real_digest = nand_backup.digest
    monkeypatch.setattr(
        nand_backup,
        "digest",
        lambda path: (
            "r" + Path(path).name
            if str(path).endswith(".raw")
            else "d" * 64
            if str(path).endswith("-data.bin")
            else real_digest(path)
        ),
    )
    profile = tmp_path / "profile"
    profile.mkdir(mode=0o700)
    save(profile, "probe-manifest.json", b"public profile fixture")
    execution = {
        "profile": str(profile),
        "binding": nand_backup.binding(session),
        "profile_manifest_sha256": nand_backup.digest(profile / "probe-manifest.json"),
        "analysis_recipes": nand_backup.analysis_recipes(),
        "source_sha256": nand_backup.digest(session / "installer-source.zip"),
    }
    save(root, "execution.json", encode(execution))
    save(root, "finished.json", encode({"host_command_exited": True}))
    capture = {
        "records_received": 262144,
        "status": "raw-nand-capture-mismatch",
        "sha256": ["rpass-0.raw", "rpass-1.raw"],
    }
    quality = {
        "archive_quality_accepted": True,
        "whole_chip_restoration_verified": False,
        "geometry": {"pages": 131072, "page_bytes": 2048, "oob_bytes": 64, "passes": 2},
        "corrected_views_equal": True,
        "oob_equal": True,
        "unclassified_chunks_equal": True,
        "raw_sha256": capture["sha256"],
        "data_sha256": ["d" * 64] * 2,
        "passes": [{"uncorrectable": 0}] * 2,
        "all_chunks_ecc_verified": False,
    }
    save(root / "raw", "capture.json", encode(capture))
    save(root / "analysis", "quality.json", encode(quality))
    save(
        root,
        "analysis-binding.json",
        encode(
            {
                "capture_sha256": nand_backup.digest(root / "raw/capture.json"),
                "quality_sha256": nand_backup.digest(root / "analysis/quality.json"),
            }
        ),
    )
    return session


def test_full_raw_and_oob_are_preserved_with_ecc_limit_explicit(archive):
    result = nand_backup.check(archive)
    assert result["passes"] == 2 and result["raw_oob_bytes_per_pass"] == 276824064
    assert (
        result["whole_chip_restoration_verified"] is False
        and result["all_chunks_ecc_verified"] is False
    )


@pytest.mark.parametrize(
    "fault",
    (
        "receipt",
        "identity",
        "source",
        "truncated",
        "permissions",
        "symlink",
        "missing-footer-record",
        "different-data",
    ),
)
def test_changed_or_incomplete_full_backup_cannot_pass_install_gate(archive, fault):
    root = archive / "nand"
    path = root / "analysis/quality.json"
    if fault == "receipt":
        path.write_bytes(path.read_bytes() + b" ")
    elif fault == "identity":
        (archive / "identity.json").write_text("{}")
    elif fault == "source":
        (archive / "installer-source.zip").write_bytes(b"changed")
    elif fault == "truncated":
        (root / "raw/pass-0.raw").write_bytes(b"short")
    elif fault == "permissions":
        (root / "raw/pass-0.raw").chmod(0o644)
    elif fault == "symlink":
        (root / "raw/pass-0.raw").unlink()
        (root / "raw/pass-0.raw").symlink_to(root / "raw/pass-1.raw")
    elif fault == "missing-footer-record":
        (root / "finished.json").unlink()
    else:
        report = json.loads(path.read_bytes())
        report["data_sha256"][1] = "different"
        path.write_text(json.dumps(report))
    with pytest.raises((ValueError, OSError, KeyError)):
        nand_backup.check(archive)


def test_install_refuses_unavailable_full_backup_before_any_loader(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "checked", lambda _: (tmp_path, tmp_path, {}))
    monkeypatch.setattr(
        workflow, "identity", lambda: pytest.fail("must refuse before inspecting/arming device")
    )
    with pytest.raises((ValueError, OSError)):
        workflow.install(tmp_path, "/unused", runner=lambda *a, **kw: pytest.fail("must not arm"))


@pytest.mark.parametrize("identity", (("0525", "a4a7"), ("2464", "0002"), ("0451", "d00e")))
def test_full_backup_handoff_accepts_only_its_same_intake_and_exited_ram(
    tmp_path, monkeypatch, identity
):
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    tmp_path.chmod(0o700)
    session = tmp_path / "session"
    session.mkdir(mode=0o700)
    usb = tmp_path / "usb"
    usb.mkdir()
    for name, value in zip(("idVendor", "idProduct"), identity, strict=True):
        (usb / name).write_text(value)
    (tmp_path / "1-1").symlink_to(usb)
    monkeypatch.setattr(nand_backup.usb_port, "SYSFS", tmp_path)
    checked = []
    monkeypatch.setattr(nand_backup, "check", lambda root: checked.append(root))
    if identity == ("0525", "a4a7"):
        nand_backup.require_handoff(session / "nand", session)
        assert checked == [session]
    else:
        with pytest.raises(ValueError):
            nand_backup.require_handoff(session / "nand", session)
    with pytest.raises(ValueError):
        nand_backup.require_handoff(session / "other", session)


@pytest.mark.parametrize("fault", (None, "base", "manifest", "execution", "location"))
def test_restartable_reader_is_bound_to_exact_backup_execution(archive, monkeypatch, fault):
    from firmware.file_writer.run import encode, save
    from firmware.nand_handoff import profile as handoff

    monkeypatch.setattr(handoff, "check", lambda _: None)
    root = archive / "nand"
    execution = json.loads((root / "execution.json").read_bytes())
    reader = archive / ("other-reader" if fault == "location" else "nand-handoff-reader")
    reader.mkdir(mode=0o700)
    save(
        reader,
        "profile.json",
        encode({"base": "another base" if fault == "base" else execution["profile"]}),
    )
    execution |= {
        "handoff_profile": str(reader),
        "handoff_manifest_sha256": nand_backup.digest(reader / "profile.json"),
    }
    (root / "execution.json").write_bytes(encode(execution))
    save(reader, "execution-started.json", encode({} if fault == "execution" else execution))
    if fault == "manifest":
        (reader / "profile.json").write_bytes(
            encode({"base": execution["profile"], "changed": True})
        )
    if fault:
        with pytest.raises(ValueError, match="same executed restartable"):
            nand_backup.check(archive)
    else:
        assert nand_backup.check(archive)["passes"] == 2
