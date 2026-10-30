"""Stage a separate, explicit NAND-geometry-only experiment from pinned sources."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from firmware.probe import check as probe_check
from firmware.probe import stage as probe_stage

HOST_FILES = {
    "boot.sh",
    "check.py",
    "configure.py",
    "observe.py",
    "probe_configure.py",
    "serial_observe.py",
    "metadata_report.py",
}


def stage(nestdfu, xloader, loader, base_build, output):
    base_build = Path(base_build)
    probe_check.check(base_build)
    assets = Path(__file__).resolve().parent
    original = assets.parent / "probe"
    output = probe_stage.stage(nestdfu, xloader, loader, output)
    shutil.copyfile(original / "configure.py", output / "probe_configure.py")
    shutil.copyfile(original / "observe.py", output / "serial_observe.py")
    for src, target in (
        ("init.c", "probe-init.c"),
        ("readonly.h", "metadata-readonly.h"),
        ("configure.py", "configure.py"),
        ("observe.py", "observe.py"),
        ("report.py", "metadata_report.py"),
        ("build.sh", "build.sh"),
    ):
        shutil.copyfile(assets / src, output / target)
    # Reuse bounded image/ELF/CPIO checking with a distinct status, helper inventory
    # and our independent configuration verifier. No baseline probe gate is relaxed.
    template = (original / "check.py").read_text()
    template = template.replace(
        '"experimental-unexecuted-ram-probe"', '"experimental-nand-geometry-only"'
    )
    old = 'HOST_FILES = {"boot.sh", "check.py", "configure.py", "observe.py"}'
    if template.count(old) != 1:
        raise ValueError("unexpected shared integrity-check template")
    template = template.replace(
        old, "HOST_FILES = {" + ", ".join(repr(n) for n in sorted(HOST_FILES)) + "}"
    )
    (output / "check.py").write_text(template)
    template = (original / "boot.sh").read_text()
    template = template.replace(
        "--execute-experimental-ram-probe", "--execute-read-only-nand-metadata"
    )
    template = template.replace(
        "EXPERIMENTAL RAM BOOT: not a flash backup or verified recovery procedure.",
        "EXPERIMENTAL NAND METADATA BOOT: asserts write protection; no backup or recovery.",
    )
    template = template.replace(
        'python3 "$work/observe.py" --port 1-1 --require-native',
        'python3 "$work/serial_observe.py" --port 1-1 --require-native',
    )
    template = template.replace("Heartbeat", "Geometry report").replace(
        "heartbeat", "geometry report"
    )
    (output / "boot.sh").write_text(template)
    (output / "artifacts").mkdir()
    old = json.loads((base_build / "probe-manifest.json").read_text())
    for name in ("x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        data = (base_build / "artifacts" / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != old["files"][name]:
            raise ValueError("validated bootstrap artifact changed")
        shutil.copyfile(base_build / "artifacts" / name, output / "artifacts" / name)
    (output / "geometry-sources.json").write_text(
        json.dumps(
            {
                "status": "unexecuted-geometry-only-profile",
                "base_manifest_sha256": hashlib.sha256(
                    (base_build / "probe-manifest.json").read_bytes()
                ).hexdigest(),
                "recipe_sha256": {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(assets.iterdir())
                    if p.is_file()
                },
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    (output / "DO-NOT-FLASH.txt").write_text(
        "Experimental NAND geometry-only RAM kernel. No firmware acquisition or restoration.\n"
        "Hardware WP required; no block/MTD character interface or filesystem mounts.\n"
        "Review and notify the owner before device execution. Never flash this image.\n"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("nestdfu", "xloader", "loader", "base-build", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(stage(args.nestdfu, args.xloader, args.loader, args.base_build, args.output))
