# Supplemental NAND parity-padding review

The earlier acquisition retained four chunks per raw pass without classifying
their ECC because the unmasked parity value had nonzero bits above its reviewed
52-bit BCH payload. A new offline review resolves that specific limitation.
No device, flash, filesystem mount or target binary was accessed/executed.

All four were the earlier decoder's `padding` category, not erased-page cases.
Each raw pass had one noncanonical bit in the unused high nibble of each affected
seven-byte parity group. Restricting verification to the established protected
52-bit payload, then using the same pinned public BCH implementation, independently
validated all eight affected chunks across the two passes. No data correction or
protected-parity correction was required; the original 512-byte data in each was
already consistent with its BCH payload. Known synthetic one-through-four data
error and parity-error checks were repeated before examining these chunks.

Both complete raw file digests were freshly checked against their private capture
record. Neither raw input nor either earlier derived view/report was changed.
A separate private padding-review record preserves the details and input digests.
No raw bytes, private hashes or identifying contents are published.

This adds four verified programmed chunks per pass to the earlier 118332, for
118336 programmed chunks with valid/corrected protected BCH payloads, alongside
405952 exact all-FF erased chunks. The previously derived data views remain
byte-identical to each other and require no changes for this finding. The original
79 raw bit differences and their earlier corrections remain historical evidence;
the raw captures have not become byte-identical.

The source GPMC BCH4 formatter and the earlier full-chip alignment evidence
corroborate the 52-bit interpretation. This does not diagnose why the padding
bits differ, authenticate firmware, validate every bad-block/boot-ROM convention
or demonstrate restoration. Preserve the original OOB records; do not erase their
padding/metadata merely to make a backup compare cleanly. A persistent operation
still needs an exact reviewed partition/write plan and a demonstrated restoration
procedure. The owner accepts same-unit recovery risk, so a spare is no longer a
mandatory prerequisite, but no persistent write has been performed.
