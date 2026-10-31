#!/bin/sh
# Default checks offline only. One owner-timed run, never an automatic retry.
set -eu
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo 'Usage: sh firmware/file_install_probe/boot.sh PRIVATE_PROFILE [--execute-experimental-file-ram-lab]' >&2
    exit 2
fi
work=$(CDPATH= cd -- "$1" && pwd)
python3 -m firmware.file_install_probe.artifact check "$work"
if [ "$#" -eq 1 ]; then
    echo 'Offline checks only; no device opened.'
    exit 0
fi
if [ "$2" != '--execute-experimental-file-ram-lab' ]; then
    echo 'Unsupported execution argument.' >&2
    exit 2
fi
if [ -e "$work/file-result.jsonl" ] || [ -L "$work/file-result.jsonl" ]; then
    echo 'Preserve existing results; prepare a fresh profile before another run.' >&2
    exit 2
fi
echo 'EXPERIMENTAL RAM FILE TRANSACTION / STANDALONE SETTINGS LAB: no persistent installation.'
echo 'Keep USB connected and display detached from its unwired base.'
echo 'Synthetic RAM files only; kernel has no flash or physical network support.'
python3 -m firmware.probe.observe --port 1-1 --require-native
echo 'Waiting up to 90 seconds for the reviewed manual restart into ROM mode.'
if timeout 90 "$work/artifacts/omap_loader" \
    -f "$work/artifacts/x-load-gen2.bin" \
    -f "$work/artifacts/u-boot.bin" -a 0x80100000 \
    -f "$work/artifacts/uImage" -a 0x80a00000 -j 0x80100000; then
    :
else
    result=$?
    echo 'Upload stopped. Manually restart after command exit; no retry.' >&2
    exit "$result"
fi
echo 'Upload completed; waiting for the bounded RAM report, not proof of boot yet.'
if python3 -m firmware.file_install_probe.observe --output "$work/file-result.jsonl"; then
    echo 'RAM measurements received. Manually restart to native startup with loader exited.'
else
    result=$?
    echo 'RAM measurements incomplete. Manually restart after command exit; no retry.' >&2
    exit "$result"
fi
