"""Launch the Hearth guided setup from an extracted installer source archive."""

import argparse
import sys


def main():
    if sys.version_info < (3, 12):  # noqa: UP036 - source-archive bootstrap, before installation
        raise SystemExit("Hearth setup requires Python 3.12 or newer.")
    parser = argparse.ArgumentParser(description="Hearth guided setup and saved-file recovery")
    options = parser.add_mutually_exclusive_group()
    options.add_argument(
        "--continue-prepared",
        metavar="SESSION",
        help="continue a checked failed host prepare before any device attempt",
    )
    options.add_argument(
        "--restore", action="store_true", help="restore a checked private installation bundle"
    )
    args = parser.parse_args()
    if args.restore:
        from installer.recovery_wizard import run
    else:
        from installer.wizard import run
    return run(prepared=args.continue_prepared) if args.continue_prepared else run()


if __name__ == "__main__":
    raise SystemExit(main())
