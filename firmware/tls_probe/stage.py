"""Stage public-only kernel inputs. Private libraries never enter the builder."""

import argparse
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

from firmware.probe import check as heartbeat
from firmware.probe import stage as probe_stage


def stage(base_build, sources, output):
    base_build, sources, output = map(Path, (base_build, sources, output))
    heartbeat.check(base_build)
    record = json.loads((sources / "sources.json").read_text())
    pin = json.loads((Path(probe_stage.__file__).parent / "inputs.json").read_text())["nestdfu"]
    if record["inputs"]["nestdfu"] != pin:
        raise ValueError("unexpected public kernel source pin")
    archive = sources / "nestdfu-source.tar"
    if (
        hashlib.sha256(archive.read_bytes()).hexdigest()
        != record["source_archive_sha256"]["nestdfu"]
    ):
        raise ValueError("public source archive digest mismatch")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / "src").mkdir()
    (output / "root").mkdir()
    (output / "artifacts").mkdir()
    with tarfile.open(archive) as stream:
        members = [m for m in stream if m.name == "Dev/linux" or m.name.startswith("Dev/linux/")]
        stream.extractall(output / "src", members=members, filter="data")
    assets = Path(__file__).parent
    probe = assets.parent / "probe"
    for source, target in (
        (probe / "init.c", "fallback-init.c"),
        (probe / "configure.py", "probe_configure.py"),
        (assets / "configure.py", "tls_configure.py"),
        (assets / "kernel-build.sh", "build.sh"),
    ):
        shutil.copyfile(source, output / target)
    manifest = json.loads((base_build / "probe-manifest.json").read_text())
    for name in ("x-load-gen2.bin", "u-boot.bin", "omap_loader"):
        data = (base_build / "artifacts" / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest["files"][name]:
            raise ValueError("reviewed boot-chain artifact changed")
        shutil.copyfile(base_build / "artifacts" / name, output / "artifacts" / name)
    source_report = {
        "status": "public-only-tls-kernel-inputs",
        "kernel_pin": pin,
        "kernel_source_archive_sha256": record["source_archive_sha256"]["nestdfu"],
        "bootstrap_sha256": {
            name: manifest["files"][name]
            for name in ("x-load-gen2.bin", "u-boot.bin", "omap_loader")
        },
        "recipe_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.iterdir()
            if p.is_file()
        },
        "private_material_present": False,
    }
    (output / "tls-kernel-sources.json").write_text(json.dumps(source_report, indent=2) + "\n")
    return source_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-build", required=True)
    parser.add_argument("--sources", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    stage(args.base_build, args.sources, args.output)
