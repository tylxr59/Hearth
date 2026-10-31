#!/bin/sh
# No automatic USB or write retry. This profile can intentionally mutate NAND.
set -eu
work=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 "$work/check.py" "$work"
if [ "$#" -eq 0 ]; then
    echo 'Offline only. Requires --execute-experimental-scratch-restore PRIVATE_OUTPUT PRIVATE_ARCHIVE_DIRECTORY PRIVATE_MASK_RECORD.'
    exit 0
fi
if [ "$#" -ne 4 ] || [ "$1" != '--execute-experimental-scratch-restore' ]; then
    echo 'Unsupported arguments.' >&2
    exit 2
fi
test -x "$work/artifacts/omap_loader"
python3 "$work/observe.py" --check-output "$2" --archive "$3" --mask-record "$4"
python3 "$work/serial_observe.py" --port 1-1 --require-native
echo 'EXPERIMENTAL FLASH WRITE/ERASE/RESTORE: physical block 1312 only (164 MiB, 128 KiB).'
echo 'Fresh private backup required before one synthetic page program, one erase and cleanmarker restoration.'
echo 'Power loss or a hardware/tool fault can leave this only unit damaged; firmware recovery remains unverified.'
echo 'Keep USB power connected and the display detached from the unwired base. No HVAC connection.'
echo 'Waiting up to 90 seconds for the owner-timed manual restart into ROM mode.'
if timeout 90 "$work/artifacts/omap_loader" \
    -f "$work/artifacts/x-load-gen2.bin" \
    -f "$work/artifacts/u-boot.bin" -a 0x80100000 \
    -f "$work/artifacts/uImage" -a 0x80a00000 -j 0x80100000; then
    :
else
    result=$?
    echo 'Upload unconfirmed. No retry. Preserve outputs and review device state before restarting.' >&2
    exit "$result"
fi
if python3 "$work/observe.py" --output "$2" --archive "$3" --mask-record "$4"; then
    echo 'Exact fixed-block restoration and programmed ECC checked. Not whole-firmware recovery.'
else
    result=$?
    echo 'Write/restoration unconfirmed. Do not interrupt power or retry; preserve private evidence for review.' >&2
    exit "$result"
fi
echo 'The transaction has exited. Use the reviewed manual restart and confirm native startup.'
