# Full raw capture and offline native software recovery

One supervised acquisition boot used the reviewed
[whole-chip read-only profile](../../firmware/nand_capture/README.md). The owner
triggered ROM entry while the loader waited. Three files uploaded without sudo.
The display remained off its unwired base, on USB, without HVAC or network setup.

## Capture result and integrity limits

All 262144 data/OOB records passed transport CRC/order checks and the required
completion footer was accepted. Two complete 276824064-byte raw files were
saved privately. Their hashes differed, so the wrapper correctly exited 1 with
`raw-nand-capture-mismatch`, not success. Independently recomputing each file's
SHA-256 matched its private capture record; both are regular 0600 files.

Comparison found 79 single-bit data differences across 79 pages/75 erase blocks.
Every OOB byte matched. These were programmed-data patterns, not blank-page
differences. Both original raw files remain unchanged. Transport checks do not
establish the physical cause of read variation; no electrical diagnosis is made.

Offline analysis identified four seven-byte BCH4 parity groups at OOB offsets
36–63, with 52 parity bits right-aligned. The BCH model uses m=13, t=4 and
primitive polynomial 0x201b, also present in the pinned OMAP BCH decoder source.
The encoding alignment/constant mask was inferred from multiple captured chunks,
then checked by decoding/re-encoding across the captures. A plain software-Hamming
interpretation did not match. The public standalone BCH code is pinned in
[bchlib-2.1.3.json](bchlib-2.1.3.json); no proprietary code ran on the host.

Synthetic checks first recovered one through four data-bit errors and one parity
error exactly. Each raw pass then independently produced a 268435456-byte derived
data view. The two derived SHA-256 values match. Per pass:

| Measurement | Pass 0 | Pass 1 |
| --- | ---: | ---: |
| BCH-verified chunks | 118332 | 118332 |
| Data-bit corrections | 2809 | 2828 |
| Parity-bit corrections | 27 | 27 |
| All-FF data/parity chunks retained | 405952 | 405952 |
| Unclassified ECC chunks retained unchanged | 4 | 4 |
| Uncorrectable chunks within the supported interpretation | 0 | 0 |

Four unclassified chunks and blank/bad-block interpretation remain limitations.
Matching derived views are acquisition evidence, not a validated restore image.
Backplate coverage, calibration/credential interpretation, electrical behavior
and a demonstrated restoration path remain open. No flash operation occurred.

## Static filesystem/binary inspection

All four embedded legacy image headers and their payload CRCs validate in the
derived view. Their locations corroborate the pinned board source's layout;
that is not a measured stock runtime MTD table or permission to use write offsets.

The source-corroborated root0 range (12–58 MiB) contains JFFS2. A bounded offline
research recipe checked common, inode, compressed-data, dirent and name CRCs;
handled NONE/ZERO/RTIME/ZLIB nodes and inode versions; and reconstructed 2567
regular files. Scanned inode/data/dirent CRC failures were zero. Symlinks and
special nodes were not created; regular files are private and non-executable.
Native `nestlabs/sbin/nlclient` and `nestlabs/sbin/osm` were recovered as ARM ELF32
files. Static readelf reports and dependency lists remain private. Neither was
executed, installed, patched or invoked against hardware.

Initial static inspection found D-Bus helper libraries and nlclient bus identifiers
for heartbeat/SCPM. No usable thermostat setter is established. The architecture
decision remains open; actual native binaries/libraries/startup policy can now
be examined instead of relying only on historical scripts.

## Private preservation and handoff

- `private/nand-capture-20261030`: original two raw/OOB files, immutable capture
  status, comparison and ECC-layout research reports.
- `private/nand-analysis-20261030`: separate uncorrected/corrected data views,
  decode/CRC reports, root0 reconstruction and static ELF reports.
- Machine-local research recipes are under ignored `build/`, including
  `infer-private-bch4-layout-20261030.py`, `decode-private-bch4-20261030.py` and
  `extract-private-jffs2-20261030.py`. They are experimental analysis recipes;
  portable, independently reviewed analysis/recovery tooling is still pending.

Raw bytes, proprietary binaries, private identifiers and their hashes are absent
from Git/public logs. No upload or push occurred. The owner said they were
returning to the home icon; a follow-up observed normal Nest USB `2464:0002`.
No further mode change is needed for offline static inspection. Current host
validation remains 153 passed tests with Podman integration enabled plus static
checks; the separate manual ECC/filesystem measurements above are not CI tests.
See the [dated validation record](../security/validation-2026-10-30-nand-capture.json).
