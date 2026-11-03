# SPDX-License-Identifier: GPL-2.0-only
"""Separate offline verifier process. No USB or firmware execution."""

import argparse
import json

from tools.nand_archive.bch import BCH, analyze
from tools.nand_archive.build import checked_library


def main():
    parser = argparse.ArgumentParser()
    for name in ("library", "raw0", "raw1", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    bch = BCH(checked_library(args.library))
    try:
        report = analyze(args.raw0, args.raw1, args.output, bch)
    finally:
        bch.close()
    print(
        json.dumps(
            {
                "status": "whole-nand-archive-analyzed",
                "archive_quality_accepted": report["archive_quality_accepted"],
                "all_chunks_ecc_verified": report["all_chunks_ecc_verified"],
                "whole_chip_restoration_verified": False,
            }
        )
    )
    return 0 if report["archive_quality_accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
