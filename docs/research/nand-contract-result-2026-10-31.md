# NAND controller metadata observed

One owner-supervised RAM boot of the exact prepared v5 profile, source `316f50d`,
transferred all three files and returned the validated controller report. Loader
and observer exited zero. This reports the custom kernel's initialized master
controller, not the stock runtime partition map or the original firmware's full
bad-block policy.

Observed: 256 MiB NAND, 128 KiB erase blocks, 2048-byte pages and 64-byte OOB;
16-bit bus; zero MTD capability flags; protected NAND status. Marker position is
zero, the chip's second-page scan flag is set, and last-page/byte-1-and-6 scan flags
are clear. The explicit marker descriptor is absent because this profile skips
BBT scanning. That absence does not establish block health or an empty native BBT.

The initialized hardware-ECC configuration reports one 2048-byte step and 28
parity bytes, at OOB positions 36 through 63. The free region starts at byte two
and spans 34 bytes. This matches the source's BCH4 profile (four 512-byte chunks
per page) and the earlier captured layout/cleanmarkers. It does not execute a
normal corrected-data read, inject ECC errors, encode a programmed page or test
erase/program/restoration behavior.

The profile retains hardware WP, protected-status checks, NAND_ROM and denied MTD
mutation callbacks. No MTD char/block/partition/UBI or network consumer, writer,
native application, settings or credentials were introduced. No flash contents
were transmitted. The validated observer output is preserved in a separate
private attempt record; raw serial framing was not separately archived. Public
[observation metadata](../security/validation-2026-10-31-nand-contract-observed.json)
contains only non-identifying controller information. Preparation records and
manifests remain unchanged.

With the loader exited, the owner reported completing the full manual restart.
USB briefly disappeared, then normal Nest USB was independently observed. No
automatic retry or persistent operation ran. Do not rerun the executed profile.

Next, verify the normal ECC-read path against a bounded preserved data reference,
and obtain fresh data/OOB for any proposed restoration-test region before designing
an exact bounded persistent operation. This observation narrows that design; it
does not authorize installation or close the same-unit restoration gate.
