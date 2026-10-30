#!/bin/sh
# Explicit device execution only. This script never runs from a build/test target.
set -eu
work=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 "$work/check.py" "$work"
if [ "$#" -eq 0 ]; then
    echo 'Dry run only. Experimental RAM execution requires --execute-experimental-ram-probe.'
    exit 0
fi
if [ "$#" -ne 1 ] || [ "$1" != '--execute-experimental-ram-probe' ]; then
    echo 'Unsupported arguments.' >&2
    exit 2
fi
echo 'EXPERIMENTAL RAM BOOT: not a flash backup or verified recovery procedure.'
echo 'Keep the display detached from its unwired base. No HVAC connection.'
python3 "$work/observe.py" --port 1-1 --require-native
echo 'Waiting up to 90 seconds for ROM mode; use the reviewed manual restart.'
if timeout 90 "$work/artifacts/omap_loader" \
    -f "$work/artifacts/x-load-gen2.bin" \
    -f "$work/artifacts/u-boot.bin" -a 0x80100000 \
    -f "$work/artifacts/uImage" -a 0x80a00000 -j 0x80100000; then
    :
else
    result=$?
    echo 'Upload stopped. After this command exits, manually restart to native startup.' >&2
    echo 'Report the output before another attempt; this script never retries a boot.' >&2
    exit "$result"
fi
echo 'Upload finished. This does not prove the kernel booted. Observe the USB heartbeat next.'
if python3 "$work/observe.py" --port 1-1 --seconds 30; then
    :
else
    result=$?
    echo 'Heartbeat not confirmed. After this command exits, manually restart to native startup.' >&2
    echo 'Report the output before another attempt.' >&2
    exit "$result"
fi
echo 'Heartbeat received. Use the manual restart to return to the original Nest software.'
