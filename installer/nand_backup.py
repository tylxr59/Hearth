"""Mandatory pre-write whole-NAND archive and independently checked ECC views."""

import json
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path

from firmware.acquisition.custody import read
from firmware.file_writer.run import encode, save
from firmware.nand_capture import profile, receiver, serial
from firmware.probe.observe import require_native
from tools.elf_review import private_path
from tools.nand_archive.build import checked_library, digest


def analysis_recipes():
    root = Path(__file__).resolve().parents[1]
    names = (
        "tools/nand_archive/bch.py",
        "tools/nand_archive/build.py",
        "tools/nand_archive/verify.py",
        "tools/nand_archive/bch-input.json",
        "installer/nand_backup.py",
    )
    return {name: digest(root / name) for name in names}


def binding(session):
    session = private_path(session)
    return {
        "format": "hearth-whole-nand-session-v1",
        "identity": json.loads(read(session / "identity.json", 65536)),
    }


def check(session):
    session = private_path(session)
    root = session / "nand"
    execution = json.loads(read(root / "execution.json", 65536))
    if execution["analysis_recipes"] != analysis_recipes() or execution["source_sha256"] != digest(
        session / "installer-source.zip"
    ):
        raise ValueError("pinned backup analysis/source changed")
    if execution["binding"] != binding(session) or json.loads(
        read(root / "finished.json", 4096)
    ) != {"host_command_exited": True}:
        raise ValueError("matching completed whole NAND session required")
    profile.check(execution["profile"])
    if "handoff_profile" in execution:
        from firmware.nand_handoff.profile import check as check_handoff

        handoff = private_path(execution["handoff_profile"])
        check_handoff(handoff)
        handoff_record = json.loads(read(handoff / "profile.json", 65536))
        if (
            handoff != session / "nand-handoff-reader"
            or handoff_record["base"] != execution["profile"]
            or digest(handoff / "profile.json") != execution["handoff_manifest_sha256"]
            or json.loads(read(handoff / "execution-started.json", 65536)) != execution
        ):
            raise ValueError("same executed restartable backup reader required")
    if execution["profile_manifest_sha256"] != digest(
        Path(execution["profile"]) / "probe-manifest.json"
    ):
        raise ValueError("executed full-read profile changed")
    seal = json.loads(read(root / "analysis-binding.json", 4096))
    if seal != {
        "capture_sha256": digest(root / "raw/capture.json"),
        "quality_sha256": digest(root / "analysis/quality.json"),
    }:
        raise ValueError("archive quality/capture receipt changed")
    capture = json.loads(read(root / "raw/capture.json", 65536))
    quality = json.loads(read(root / "analysis/quality.json", 1048576))
    if (
        capture.get("records_received") != 2 * receiver.PAGES
        or capture.get("status") not in ("raw-nand-capture-matched", "raw-nand-capture-mismatch")
        or not quality.get("archive_quality_accepted")
        or quality.get("whole_chip_restoration_verified") is not False
    ):
        raise ValueError("complete independently analyzed full archive required")
    if (
        quality["geometry"] != {"pages": 131072, "page_bytes": 2048, "oob_bytes": 64, "passes": 2}
        or not quality["corrected_views_equal"]
        or not quality["oob_equal"]
        or not quality["unclassified_chunks_equal"]
    ):
        raise ValueError("measured complete geometry and matching ECC views required")
    for i in range(2):
        raw = private_path(root / f"raw/pass-{i}.raw")
        data = private_path(root / f"analysis/pass-{i}-data.bin")
        for path, size, expected in (
            (raw, 131072 * 2112, capture["sha256"][i]),
            (data, 268435456, quality["data_sha256"][i]),
        ):
            meta = path.stat()
            if (
                meta.st_size != size
                or meta.st_mode & 0o077
                or meta.st_nlink != 1
                or digest(path) != expected
            ):
                raise ValueError("NAND archive content/permissions changed")
        if quality["raw_sha256"][i] != capture["sha256"][i] or quality["passes"][i].get(
            "uncorrectable", 0
        ):
            raise ValueError("raw custody or ECC verification failed")
    if quality["data_sha256"][0] != quality["data_sha256"][1]:
        raise ValueError("independent full views must match")
    return {
        "status": "whole-nand-archive-checked",
        "raw_oob_bytes_per_pass": receiver.PAGES * receiver.RECORD,
        "data_bytes_per_pass": receiver.PAGES * 2048,
        "passes": 2,
        "all_chunks_ecc_verified": quality["all_chunks_ecc_verified"],
        "whole_chip_restoration_verified": False,
    }


def require_handoff(root, session):
    root = private_path(root)
    session = private_path(session)
    if root != session / "nand":
        raise ValueError("same intake whole NAND archive required")
    check(session)
    usb = Path("/sys/bus/usb/devices/1-1")
    if tuple((usb / n).read_text().strip() for n in ("idVendor", "idProduct")) not in (
        ("0525", "a4a7"),
        ("0525", "a4a6"),
    ):
        raise ValueError("known exited full-read RAM mode required")


def run(session, reader, library, *, handoff_profile=None):
    session = private_path(session)
    reader = Path(reader).absolute()
    library = checked_library(library)
    profile.check(reader)
    if handoff_profile is not None:
        from firmware.nand_handoff.profile import check as check_handoff

        handoff_profile = private_path(handoff_profile)
        check_handoff(handoff_profile)
        row = json.loads(read(handoff_profile / "profile.json", 65536))
        if handoff_profile != session / "nand-handoff-reader" or row["base"] != str(reader):
            raise ValueError("same-session full-read handoff profile required")
    require_native("1-1")
    root = session / "nand"
    if (
        root.exists()
        or (session / "nand-reader-executed.json").exists()
        or (reader / "execution-started.json").exists()
        or (handoff_profile is not None and (handoff_profile / "execution-started.json").exists())
    ):
        raise ValueError("fresh whole NAND archive required; no retry")
    if shutil.disk_usage(session).free < 2 * 131072 * 2112 + 2 * 268435456 + 64 * 1048576:
        raise ValueError("at least 1.2 GB free space required for the private archive")
    root.mkdir(mode=0o700)
    execution = {
        "profile": str(reader),
        "binding": binding(session),
        "profile_manifest_sha256": digest(reader / "probe-manifest.json"),
        "analysis_recipes": analysis_recipes(),
        "source_sha256": digest(session / "installer-source.zip"),
    }
    if handoff_profile is not None:
        execution |= {
            "handoff_profile": str(handoff_profile),
            "handoff_manifest_sha256": digest(handoff_profile / "profile.json"),
        }
    save(root, "execution.json", encode(execution))
    save(session, "nand-reader-executed.json", encode(execution))
    save(reader, "execution-started.json", encode(execution))
    if handoff_profile is not None:
        save(handoff_profile, "execution-started.json", encode(execution))
    print(
        "PROTECTED FULL NAND BACKUP: two fixed raw/OOB passes, followed by offline ECC verification. No writer or native app. Keep USB connected and base detached.",
        flush=True,
    )
    print("Waiting up to 90 seconds for the reviewed manual ROM restart.", flush=True)
    artifacts = (reader if handoff_profile is None else handoff_profile) / "artifacts"
    subprocess.run(  # nosec B603
        [
            str(artifacts / "omap_loader"),
            "-f",
            str(artifacts / "x-load-gen2.bin"),
            "-f",
            str(artifacts / "u-boot.bin"),
            "-a",
            "0x80100000",
            "-f",
            str(artifacts / "uImage"),
            "-a",
            "0x80a00000",
            "-j",
            "0x80100000",
        ],
        check=True,
        timeout=90,
    )

    def collect(fd, deadline):
        try:
            return receiver.collect(fd, deadline, root / "raw", private_root=root)
        except receiver.CaptureMismatch:
            # Preserve the failure classification; only independent ECC analysis
            # of both complete/footer-checked immutable inputs may accept an archive.
            return {"status": "raw-mismatch-requires-ecc-analysis"}

    serial.observe(collect)
    subprocess.run(  # nosec B603
        [
            sys.executable,
            "-m",
            "tools.nand_archive.verify",
            "--library",
            str(library),
            "--raw0",
            str(root / "raw/pass-0.raw"),
            "--raw1",
            str(root / "raw/pass-1.raw"),
            "--output",
            str(root / "analysis"),
        ],
        check=True,
        timeout=1200,
    )
    save(
        root,
        "analysis-binding.json",
        encode(
            {
                "capture_sha256": digest(root / "raw/capture.json"),
                "quality_sha256": digest(root / "analysis/quality.json"),
            }
        ),
    )
    save(root, "finished.json", encode({"host_command_exited": True}))
    result = check(session)
    save(root, "observed.json", encode(result))
    return result
