"""Launch the Hearth guided setup from an extracted installer source archive."""

import sys


def main():
    if sys.version_info < (3, 12):  # noqa: UP036 - source-archive bootstrap, before installation
        raise SystemExit("Hearth setup requires Python 3.12 or newer.")
    from installer.wizard import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
