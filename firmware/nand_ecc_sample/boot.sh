#!/bin/sh
# Explicit bounded sampling only; no automatic retries or persistent installation.
set -eu
work=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 "$work/check.py" "$work"
if [ "$#" -eq 0 ]; then
    echo 'Dry run only. Requires --execute-read-only-nand-ecc-sample PRIVATE_OUTPUT_DIRECTORY PRIVATE_REFERENCE_FILE.'
    exit 0
fi
if [ "$#" -ne 3 ] || [ "$1" != '--execute-read-only-nand-ecc-sample' ]; then
    echo 'Unsupported arguments.' >&2
    exit 2
fi
test -x "$work/artifacts/omap_loader"
python3 "$work/observe.py" --check-output "$2" --reference "$3"
python3 "$work/serial_observe.py" --port 1-1 --require-native
echo 'EXPERIMENTAL NORMAL-ECC NAND SAMPLE: two reads of a fixed root0 block; private reference comparison.'
echo 'Hardware WP required. Not a backup or recovery. Keep detached from the unwired base, on USB.'
echo 'Waiting up to 90 seconds for ROM mode; use the reviewed manual restart.'
if timeout 90 "$work/artifacts/omap_loader" \
    -f "$work/artifacts/x-load-gen2.bin" \
    -f "$work/artifacts/u-boot.bin" -a 0x80100000 \
    -f "$work/artifacts/uImage" -a 0x80a00000 -j 0x80100000; then
    :
else
    result=$?
    echo 'Upload stopped. After this command exits, manually restart to native startup. No automatic retry.' >&2
    exit "$result"
fi
if python3 "$work/observe.py" --output "$2" --reference "$3" --seconds 60; then
    :
else
    result=$?
    echo 'Sample not confirmed. Preserve private partial output; manually restart after command exits.' >&2
    exit "$result"
fi
echo 'Private sample received. Manually restart to the original Nest software with the loader exited.'
