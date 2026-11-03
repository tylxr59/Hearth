"""Exercise the packaged integration in the pinned real HA Core runtime."""

import argparse
import os
import subprocess  # nosec B404
from pathlib import Path

from tools.package_native_ha import package
from tools.public_release import release

IMAGE = "ghcr.io/home-assistant/home-assistant@sha256:21935614df6d9f24f680a1ef749f0570d2d6b7936c606c0a44253ae875865c04"
ROOT = Path(__file__).resolve().parents[1]


def check(output, engine, *, onboarding_only=False):
    if engine not in ("docker", "podman"):
        raise ValueError("supported container engine required")
    output = Path(output).absolute()
    package(output)
    release(output / "installer-artifacts")
    subprocess.run(  # nosec B603
        [
            engine,
            "run",
            "--rm",
            "--network",
            "none",
            "--cap-drop",
            "all",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "4g",
            "--cpus",
            "4",
            "--entrypoint",
            "python3",
            "-v",
            f"{output}:/package:ro,Z",
            "-v",
            f"{ROOT / 'tests/native_ha_runtime_check.py'}:/check.py:ro,Z",
            IMAGE,
            "/check.py",
            *(["--onboarding-only"] if onboarding_only else []),
        ],
        check=True,
        timeout=240,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--onboarding-only", action="store_true")
    parser.add_argument(
        "--engine",
        choices=("docker", "podman"),
        default=os.environ.get("HEARTH_CONTAINER_ENGINE", "docker"),
    )
    args = parser.parse_args()
    check(args.output, args.engine, onboarding_only=args.onboarding_only)
