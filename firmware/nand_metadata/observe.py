"""Use the reviewed serial-port selection with the geometry-only receiver."""

import argparse
import json

import serial_observe
from metadata_report import receive

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="1-1")
    parser.add_argument("--seconds", type=int, default=30)
    args = parser.parse_args()
    # This standalone staged helper is a separate process/profile. Its code and
    # both imported helpers are part of the geometry manifest's checked inventory.
    serial_observe.receive = receive
    try:
        print(json.dumps(serial_observe.observe(args.port, args.seconds), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, "Geometry observation failed: " + str(exc) + "\n")
