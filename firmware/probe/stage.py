"""Stage pinned public sources for an offline experimental RAM-probe build.

No downloads, device access or execution of firmware/build scripts occurs here.
"""

import argparse
import hashlib
import json
import shutil

# Fixed git/patch argv; no shell or target-code execution.
import subprocess  # nosec B404
import tarfile
from pathlib import Path


def verify_loader(root, files):
    root = Path(root)
    for name, expected in files.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            raise ValueError("regular bounded loader source required")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("loader source digest mismatch")


def patch_model(text):
    before = "#define\tDIAMOND_DEFAULT_MODEL_INDEX\t\t\tJ49_BOARD_PROTOTYPE_MODEL_INDEX"
    if text.count(before) != 1 or text.count('"Display-2.0"') != 1:
        raise ValueError("unexpected bootloader model source")
    return text.replace(before, before.replace("PROTOTYPE", "PVT")).replace(
        '"Display-2.0"', '"Display-2.6"'
    )


def stage(nestdfu, xloader, loader, output):
    assets = Path(__file__).resolve().parent
    inputs = json.loads((assets / "inputs.json").read_text())
    verify_loader(loader, inputs["loader"]["files"])
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "src").mkdir()
    (output / "root").mkdir()
    archives = {}
    for name, repository in (("nestdfu", nestdfu), ("xloader", xloader)):
        record = inputs[name]
        archive = output / (name + "-source.tar")
        with archive.open("xb") as stream:
            # Fixed git operation and pinned revision, argv only. No target code
            # runs; git archive ignores untracked files and working-tree edits.
            subprocess.run(  # nosec B607
                [
                    "git",
                    "-C",
                    str(Path(repository).resolve()),
                    "archive",
                    "--format=tar",
                    record["revision"],
                    *record["paths"],
                ],
                stdout=stream,
                check=True,
                shell=False,  # nosec B603
            )
        archives[name] = hashlib.sha256(archive.read_bytes()).hexdigest()
        with tarfile.open(archive) as source:
            source.extractall(output / "src", filter="data")
    board = output / "src/Dev/u-boot/board/nest/diamond/diamond.c"
    board.write_text(patch_model(board.read_text()))
    for src, dst in (
        ("init.c", "probe-init.c"),
        ("build.sh", "build.sh"),
        ("configure.py", "configure.py"),
        ("check.py", "check.py"),
        ("boot.sh", "boot.sh"),
        ("observe.py", "observe.py"),
    ):
        shutil.copyfile(assets / src, output / dst)
    (output / "loader").mkdir()
    for name in inputs["loader"]["files"]:
        shutil.copyfile(Path(loader) / name, output / "loader" / name)
    # Apply our checked-in patch to the digest-verified public loader source.
    # No executable from the source or device is invoked.
    subprocess.run(  # nosec B607
        [
            "patch",
            "-d",
            str(output / "loader"),
            "-p1",
            "--batch",
            "--fuzz=0",
            "-i",
            str(assets / "omap-loader.patch"),
        ],
        check=True,
        capture_output=True,
        shell=False,  # nosec B603
    )
    shutil.copyfile(assets / "test_loader.c", output / "loader/test_loader.c")
    report = {
        "status": "experimental-unexecuted-probe-sources",
        "inputs": inputs,
        "source_archive_sha256": archives,
        "recipe_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(assets.iterdir())
            if p.is_file()
        },
    }
    (output / "sources.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    (output / "DO-NOT-FLASH.txt").write_text(
        "Experimental RAM probe only. No flash access in its Linux kernel.\n"
        "Not deployable thermostat firmware, a backup, or a verified recovery tool.\n"
        "Review the boot chain and notify the owner before any device execution.\n"
    )
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nestdfu", required=True)
    parser.add_argument("--xloader", required=True)
    parser.add_argument("--loader", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(stage(args.nestdfu, args.xloader, args.loader, args.output))


if __name__ == "__main__":
    main()
