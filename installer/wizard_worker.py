"""Private, fixed-operation worker for the guided PC wizard. Never a shell recipe."""

import hashlib
import json
import sys
from pathlib import Path

from firmware.file_writer.run import encode, save
from firmware.tls_probe.package import private_read
from tools.elf_review import private_path


def work(request):
    row = json.loads(private_read(request, 16384))
    session = private_path(row["session"])
    operation = row["operation"]
    build = Path(row["build"])
    if operation == "prepare":
        from installer import build as reader
        from installer import sources

        sources.fetch(build / "sources")
        result = reader.build(build / "sources", build / "reader", session / "reader")
        from firmware.nand_capture.profile import build as build_nand
        from tools.nand_archive.build import fetch as build_bch
        from tools.public_release import installer_archive

        build_nand(build / "sources", build / "reader", build / "nand-reader")
        build_bch(build / "nand-bch")
        (build / "recovery-source").mkdir(mode=0o700)
        installer_archive(build / "recovery-source/hearth-installer-source.zip")
        save(
            session,
            "installer-source.zip",
            (build / "recovery-source/hearth-installer-source.zip").read_bytes(),
        )
    elif operation == "nand":
        from installer.nand_backup import run

        result = run(session, build / "nand-reader", build / "nand-bch/compiled/libbch.so")
    elif operation == "acquire":
        from firmware.acquisition.run import run
        from installer.corpus import inspect

        result = run(
            session / "reader",
            session / "acquisition",
            execute=True,
            handoff_from_nand=session / "nand",
        )
        execution = json.loads(private_read(session / "acquisition/execution.json", 65536))
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
    elif operation in ("commissioning", "cleanup"):
        from firmware.file_writer import run as core
        from installer.workflow import network_engine

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
