# Standalone offline archive verifier

`bch.py` and `verify.py` are GPL-2.0-only components. `build.py` fetches only the
hash-pinned public BCH source named in `bch-input.json` and compiles it locally.
The installer invokes the verifier as a separate process; it is never a Home
Assistant dependency. Upstream COPYING is retained with the local build. No
proprietary firmware is executed or used as a host linker input.

The fixed measured layout is Display-2.6, 256 MiB NAND, 2048+64-byte physical
records, four BCH13/4 chunks, polynomial0x201b and OOB offsets36–63. The constant
parity transform is inferred from at least64 agreeing, diverse programmed chunks
with at least90% agreement, then independently checked by correction/re-encoding.
Raw passes/OOB are never altered. Derived views must match, OOB must match, and
uncorrectable chunks stop acceptance. Unclassified chunks are retained unchanged
and must agree between reads; they are explicitly not labelled ECC-verified.
The raw marker summary is not a remapping/erase plan. Whole-chip restoration is
unverified and this utility contains no USB, flash writer or deployment command.
