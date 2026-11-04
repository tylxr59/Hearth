"""Private, fixed-operation worker for the guided PC wizard. Never a shell recipe."""

import hashlib
import json
import sys
from pathlib import Path

from firmware.file_writer.run import encode, save
from firmware.tls_probe.package import private_read
from installer.ui import stage
from tools.elf_review import private_path


def bind_acquisition(session, receipt, limit):
    """Bind the original files to this setup's identity and bundle, then inspect them."""
    from installer.corpus import inspect

    execution = json.loads(private_read(session / "acquisition" / receipt, limit))
    save(
        session / "acquisition",
        "intake-binding.json",
        encode(
            {
                "format": "hearth-acquisition-session-v1",
                "identity": json.loads(private_read(session / "identity.json", 65536)),
                "bundle_sha256": hashlib.sha256(
                    private_read(session / "commissioning.zip", 65536)
                ).hexdigest(),
                "session": execution["session"],
            }
        ),
    )
    inspect(session / "acquisition")


def work(request):
    row = json.loads(private_read(request, 16384))
    session = private_path(row["session"])
    operation = row["operation"]
    build = Path(row["build"])
    if operation == "prepare":
        from installer import build as reader
        from installer import sources

        stage(1, 5, "Downloading pinned sources")
        sources.fetch(build / "sources")
        stage(2, 5, "Building the read-only boot image (the longest part)")
        result = reader.build(build / "sources", build / "reader", session / "reader")
        from firmware.nand_capture.profile import build as build_nand
        from tools.installer_archive import installer_archive
        from tools.nand_archive.build import fetch as build_bch

        stage(3, 5, "Building the flash backup reader")
        build_nand(build / "sources", build / "reader", build / "nand-reader")
        from firmware.nand_handoff.profile import build as build_handoff

        build_handoff(
            build / "nand-reader", build / "nand-handoff", session / "nand-handoff-reader"
        )
        stage(4, 5, "Building the backup checker")
        build_bch(build / "nand-bch")
        stage(5, 5, "Saving a copy of this installer for restores")
        (build / "recovery-source").mkdir(mode=0o700)
        installer_archive(build / "recovery-source/installer-source.zip")
        save(
            session,
            "installer-source.zip",
            (build / "recovery-source/installer-source.zip").read_bytes(),
        )
    elif operation == "nand":
        from installer.nand_backup import run

        result = run(
            session,
            build / "nand-reader",
            build / "nand-bch/compiled/libbch.so",
            handoff_profile=session / "nand-handoff-reader",
        )
    elif operation == "acquire":
        from installer.nand_inputs import extract

        stage(1, 2, "Extracting original files from the verified full backup")
        try:
            result = extract(session)
        except ValueError as exc:
            # A refusal before any output exists leaves the protected live
            # reader as the owner's choice. Anything later is not a refusal.
            if (session / "acquisition").exists():
                raise
            result = {
                "offline_refused": True,
                "reason": str(exc)[:200],
                "device_executed": False,
                "flash_writes": False,
            }
            save(session, "nand-inputs-refused.json", encode(result))
        else:
            stage(2, 2, "Checking original files and native libraries")
            bind_acquisition(session, "nand-inputs.json", 4096)
    elif operation == "acquire-live":
        from firmware.acquisition.run import run

        # Fallback only: the offline extraction refused without output.
        refused = json.loads(private_read(session / "nand-inputs-refused.json", 4096))
        if refused.get("offline_refused") is not True or (session / "acquisition").exists():
            raise ValueError("live reader is only a fallback after a refused offline extraction")
        result = run(
            session / "reader",
            session / "acquisition",
            execute=True,
            handoff_from_nand=session / "nand",
        )
        bind_acquisition(session, "execution.json", 65536)
    elif operation == "kit":
        from installer.kit import build as make_kit

        result = make_kit(
            session,
            build / "sources",
            build / "reader",
            build / "kit",
            session / "kit",
            probe_port=row["probe_port"],
            ntp_server=row["ntp_server"],
        )
    elif operation in ("capacity", "commissioning", "cleanup", "sequence"):
        from firmware.file_writer import run as core
        from installer.workflow import network_engine

        if operation == "sequence":
            from firmware.install_sequence import run as sequence

            engine = sequence
        else:
            engine = core if operation == "commissioning" else network_engine()
        result = engine.run(
            private_path(row["profile"]),
            private_path(row["recovery"]),
            private_path(row["output"]),
            execute=True,
            **{k: private_path(v) for k, v in row["entry"].items()},
        )
    else:
        raise ValueError("fixed wizard operation required")
    save(session, operation + "-worker-result.json", encode(result))


if __name__ == "__main__":
    work(private_path(sys.argv[1]))
