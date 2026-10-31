#!/bin/sh
# Run from Hearth. Default is offline checking only. Never retry a RAM boot.
set -eu
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo 'Usage: sh firmware/tls_probe/boot.sh PRIVATE_PROFILE [--execute-experimental-tls-probe]' >&2
    exit 2
fi
work=$(CDPATH= cd -- "$1" && pwd)
python3 -m firmware.tls_probe.check "$work"
if [ "$#" -eq 1 ]; then
    echo 'Offline checks only; no device opened.'
    exit 0
fi
if [ "$2" != '--execute-experimental-tls-probe' ]; then
    echo 'Unsupported execution argument.' >&2
    exit 2
fi
if [ -e "$work/tls-result.jsonl" ] || [ -L "$work/tls-result.jsonl" ]; then
    echo 'Existing private result must be preserved; prepare a fresh profile before another boot.' >&2
    exit 2
fi
echo 'EXPERIMENTAL RAM TLS BOOT: not firmware installation or verified recovery.'
echo 'Keep display detached from its unwired base, connected only by USB.'
echo 'Runs synthetic loopback TLS cases with a RAM clock; no flash or physical networking.'
python3 -m firmware.probe.observe --port 1-1 --require-native
echo 'Waiting up to 90 seconds for the reviewed manual restart into ROM mode.'
if timeout 90 "$work/artifacts/omap_loader" \
    -f "$work/artifacts/x-load-gen2.bin" \
    -f "$work/artifacts/u-boot.bin" -a 0x80100000 \
    -f "$work/artifacts/uImage" -a 0x80a00000 -j 0x80100000; then
    :
else
    result=$?
    echo 'Upload stopped; preserve output and manually restart after this command exits. No retry.' >&2
    exit "$result"
fi
echo 'Upload completed. Waiting for the bounded TLS report; no claim that it has booted yet.'
if python3 -m firmware.tls_probe.observe --port 1-1 --seconds 240 --output "$work/tls-result.jsonl"; then
    echo 'Matrix received. Manually restart to native startup with the loader exited.'
else
    result=$?
    echo 'TLS matrix not confirmed. Manually restart after this command exits; no retry.' >&2
    exit "$result"
fi
