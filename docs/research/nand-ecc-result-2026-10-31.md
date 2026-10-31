# Bounded normal-ECC read/reference match observed

The owner supervised one RAM boot of the exact prepared normal-ECC sample profile,
source `cae21fa`. All three files transferred; loader and collector exited zero.
All 128 ordered CRC-framed records arrived: two passes of pages 12160 through
12223, each 135168 bytes including physical OOB. Both passes match each other and
the private independently corrected-data/raw-OOB reference byte for byte. This
includes the previously reviewed parity-padding case at page 12209.

Private record, payload lengths, digests, exact reference equality and 0600 file /
0700 directory permissions were independently checked after collection. The
original capture.json, two received files, immutable reference and preparation
manifest remain unchanged. A separate private attempt-1.json records source and
outcome; public [observation metadata](../security/validation-2026-10-31-nand-ecc-observed.json)
contains no firmware contents, identifiers or private binary hashes. The reference
was not in the target image and was not sent to the thermostat.

This observes output from the normal hardware-ECC read path for one programmed
block, including its physical OOB/padding. It does not deliberately inject faults
or measure how many bits were corrected. The pinned driver's BCH4 callback still
discards decoder failures/counts; zero MTD status and its counters remain
insufficient for general data-integrity claims. Exact reference matching is the
evidence here. No callback behavior was patched or generalized to the stock
running kernel, other contents or arbitrary failing flash.

Hardware WP, protected-status checks, NAND_ROM, denied mutation callbacks and
no-char/block/partition/UBI/network restrictions remained. No programmer, eraser,
native application or physical HVAC interface was included. No diagnostic
programming or erase operation ran, and this is not a whole-chip backup or
restoration test. After command exit the owner reported completing the full
manual restart; USB briefly disappeared and normal Nest USB was observed.
No automatic retry ran. Do not rerun the executed profile/output directory.

Next recovery work must freshly acquire and verify complete data/OOB for a
specifically proposed restoration-test region, preserve its metadata, independently
validate any programmed ECC and prepare exact bounds/error recovery before a
persistent operation. Protect both boot/root banks, configuration/calibration and
backplate firmware; notify the owner of the concrete operation and its limits.
