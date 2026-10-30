"""Whole-chip collector using the reviewed same-port gadget selection."""

import argparse
import json

import sample_receiver
import serial_observe

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output")
    group.add_argument("--check-output")
    parser.add_argument("--seconds", type=int, default=1200)
    args = parser.parse_args()
    try:
        sample_receiver.validate_output(args.check_output or args.output)
        if args.check_output:
            print("Fresh private path and capture disk space checked; no device opened.")
        else:
            serial_observe.receive = lambda fd, deadline: sample_receiver.collect(
                fd, deadline, args.output
            )
            print(json.dumps(serial_observe.observe("1-1", args.seconds), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, "Private raw capture failed: " + str(exc) + "\n")
