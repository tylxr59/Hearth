"""Offline public-source full raw reader build/check; never a flash writer."""

import json
import subprocess  # nosec B404
import sys

from firmware.nand_capture import finalize, stage
from installer.build import IMAGE, command, container, require_engine
from installer.sources import build_path, verify


def check(root):
    root = build_path(root)
    record = json.loads((root / "capture-profile.json").read_bytes())
    if (
        set(record) != {"format", "base"}
        or record["format"] != "hearth-protected-full-raw-reader-v1"
    ):
        raise ValueError("fixed full raw reader provenance required")
    finalize.finalize(root, build_path(record["base"]), verify_only=True)
    # Only the finalized public generated checker runs; firmware remains opaque.
    subprocess.run(  # nosec B603
        [sys.executable, str(root / "check.py"), str(root)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return {
        "status": "protected-full-nand-reader-checked",
        "flash_writes": False,
        "whole_chip_restoration_verified": False,
    }


def build(cache, reader, output):
    cache, reader, output = map(build_path, (cache, reader, output))
    require_engine()
    verify(cache)
    stage.stage(cache / "nestdfu", cache / "xloader", cache / "loader", reader / "probe", output)
    command(container("podman", IMAGE, output), output / "build.log")
    finalize.finalize(output, reader / "probe")
    (output / "capture-profile.json").write_text(
        json.dumps(
            {"format": "hearth-protected-full-raw-reader-v1", "base": str(reader / "probe")},
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    return check(output)
