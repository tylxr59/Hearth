# Fixed scratch recovery experiment: offline development

**Not executable on the device yet. No operation has run.** This directory
contains an original transaction core, synthetic NAND fault model, durable host
snapshot gate, independent BCH4 encoder, draft duplex session and experimental
kernel adapter. A compile-only staging recipe
has no sealed manifest or execution wrapper. Its boot.sh always refuses execution;
the borrowed geometry-only init cannot issue scratch commands. Do not manually
boot or flash its draft output. Existing read-only profiles remain unchanged.

The proposed scope is one fixed physical block: 1312, data offset 164 MiB,
128 KiB data / 135168 bytes including OOB. This is the start of the scratch range
corroborated by source and historical captures, not a newly observed native mount
map. No different block can be supplied or selected automatically.

The transaction will:

1. Require the measured geometry, 16-bit bus and BCH4 layout, protected hardware,
   NAND_ROM, disabled BBT scanning/refresh and denied public write callbacks.
2. Read all 64 raw data/OOB records twice while protected; require exact equality
   and erased data with only the eight-byte first-page OOB JFFS2 cleanmarker.
   Unknown content, factory markers or any changed bit stop before writes.
3. Hash the snapshot. The host must receive it, independently check the digest,
   write a fresh owner-private backup/manifest, read the backup back, and fsync
   both files and their directory/parent before returning a digest-bound token.
   No host-supplied flash address, content or executable is accepted.
4. Re-read and match the block immediately before mutation. Generate one fixed
   synthetic page in RAM and program page 1 once using the hardware ECC writer.
   Reassert/verify WP immediately; cache raw and normal-ECC reads for independent
   host validation. Zero driver ECC status is insufficient.
5. Erase this block once, reassert protection and verify every data/OOB byte FF.
   Restore only the original eight-byte cleanmarker at page 0 OOB offset 2 through
   the OOB-only writer; reassert protection. Read the whole block and require
   exact original bytes and digest. There is no program or erase retry.

A partial program error still proceeds to the single planned erase/restoration
when protection and bounds remain sound. An erase failure or lost protection
stops further mutation. A marker error remains a failure even if readback matches.
Power loss/hang can leave this block modified; the backup does not itself provide
a demonstrated recovery path. This is a scratch primitive test, not firmware
restoration, installation, crash durability or HVAC qualification. Boot, root,
environment, configuration/calibration and backplate regions are outside its
fixed address range. A future adapter/hardware fault can still defeat software
bounds, so host simulation cannot establish physical safety.

The adapter compiled successfully in the existing isolated builder against the
pinned kernel. The initial compile draft still uses the geometry init, so it
does not incorporate the new supervisor. Compilation alone does not validate
the adapter's addresses or hardware effects. Preserve that unsealed draft under
`build/scratch-compile-20261031`; do not execute it.
The standalone supervisor also compiles as static ARM with warnings treated as
errors under `build/scratch-supervisor-compile-20261031`; it has not run or been
integrated into a kernel. [Validation scope](../../docs/security/validation-2026-10-31-scratch-draft.json).

The core's host fake implements NAND one-to-zero programming, partial/error paths,
failed/false erase, marker corruption, WP failures, changed reads, wrong/replayed
ACK and neighboring canaries. It runs only original code plus trusted host
OpenSSL under ASan/UBSan. The fake ECC is deliberately not a valid hardware ECC
qualification. The host gate separately checks that every storage fsync failure
prevents acknowledgement. No proprietary firmware runs on the host.

The original independent encoder constructs a degree-52 binary generator from
GF(2^13), primitive polynomial 0x201b and roots alpha^1 through alpha^8. Its
MSB-first remainder matches seven synthetic sectors from pinned public bchlib
2.1.3. The private inferred storage mask is a host-only input. The checker requires
all four sectors, exact synthetic data, matching raw/normal OOB and untouched
marker/free bytes. Tests reject every parity/padding bit change even if both read
paths return that same damaged value. This is not target encoder qualification.

The draft duplex session requires a start token, one bounded CRC-checked prepared
snapshot, durable backup acknowledgement, then one terminal snapshot. It performs
no automatic retry. Target cleanup completes before result transmission; it
does not wait for another host command after programming. A host failure after
any ACK byte is attempted records that a write may have executed. Socket-pair
tests exercise storage failure before ACK and terminal state, scope, content and
ECC failures. Original C framing matches the Python wire schema under sanitizers.

Remaining before any owner-timed attempt: integrate/review the draft supervisor,
verify the private mask and archive before USB, complete kernel-adapter fault
testing, source/artifact integrity checks and reproducible sealed builds.
Verify the local recovery archive, notify the owner of the exact first-write risk
and limits, then arm only after readiness. No loader is armed by these tests.
