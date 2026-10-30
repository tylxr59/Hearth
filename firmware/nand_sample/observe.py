"""Same-port serial observer with a bounded private raw-sample receiver."""

import argparse
import json

import sample_receiver
import serial_observe

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output")
    group.add_argument("--check-output")
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args()
    try:
        if args.check_output:
            sample_receiver.validate_output(args.check_output)
            print("Fresh private output path checked; no device opened.")
        else:
            sample_receiver.validate_output(args.output)
            serial_observe.receive = lambda fd, deadline: sample_receiver.collect(
                fd, deadline, args.output
            )
            print(json.dumps(serial_observe.observe("1-1", args.seconds), indent=2))
    except (OSError, ValueError) as exc:
        # Never interpolate unrecognized serial bytes or raw payloads.
        parser.exit(1, "Private sample collection failed: " + str(exc) + "\n")
