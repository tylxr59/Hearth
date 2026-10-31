"""Supervise a fixed scratch transaction on the scoped USB port only."""

import argparse
import json
from pathlib import Path

import backup_helper
import duplex_observe
import preflight_helper
import session_helper

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output")
    group.add_argument("--check-output")
    parser.add_argument("--archive", required=True)
    parser.add_argument("--mask-record", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1].parent / "private"
    try:
        output = args.output or args.check_output
        backup_helper.validate_output(output, root)
        mask, summary = preflight_helper.verify_inputs(args.archive, args.mask_record, root)
        if args.check_output:
            print(json.dumps(summary))
        else:
            duplex_observe.receive = lambda fd, deadline: session_helper.transact(
                fd, deadline, output, root, mask
            )
            print(json.dumps(duplex_observe.observe("1-1", 60)))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Payloads, credential-bearing JSON and private digests must not enter logs.
        parser.exit(
            1,
            "Scratch transaction unconfirmed ("
            + type(exc).__name__
            + "). Preserve private outputs.\n",
        )
