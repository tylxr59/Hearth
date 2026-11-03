"""Hearth guided setup.

Run from the extracted hearth-nest-installer.zip on Linux, as your normal user:

    python3 provision.py            # set up a stock Nest
    python3 provision.py --restore  # undo a previous Hearth install
"""

import argparse
import sys


def main():
    if sys.version_info < (3, 12):  # noqa: UP036 - source-archive bootstrap, before installation
        raise SystemExit("Hearth setup requires Python 3.12 or newer.")
    parser = argparse.ArgumentParser(
        description="Set up Hearth on a Nest Learning Thermostat (Gen 2), or undo it.",
        epilog="Guide: https://github.com/tylxr59/Hearth/blob/main/docs/installation.md",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="put back the original files saved during a previous setup",
    )
    args = parser.parse_args()
    if args.restore:
        from installer.recovery_wizard import run
    else:
        from installer.wizard import run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
