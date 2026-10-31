# Fixed scratch recovery experiment

**Observed once:** programmed ECC and exact fixed-block restoration passed,
followed by native USB return. See the [result](../../docs/research/scratch-result-2026-10-31.md).
This does not establish whole-firmware recovery. This directory
contains an original transaction core, synthetic NAND fault model, durable host
snapshot gate, independent BCH4 encoder, duplex session and experimental
kernel adapter. The separate explicit execution wrapper can intentionally write
NAND after its private backup gate. It requires advance owner notification and
an owner-timed restart. Existing read-only profiles remain unchanged. Never flash
the diagnostic image itself or manually boot the earlier compile drafts.

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

The integrated profile is sealed and has executed ONCE at `build/scratch-restore-20261031-v1`; a fresh
`-repro` build has six byte-identical artifacts and 17 byte-identical host helpers.
Both pass offline image/configuration/minimal-initramfs integrity checks. The
earlier `build/scratch-compile-20261031` and standalone-supervisor compile drafts
remain preserved and must not execute. Their [historical scope](../../docs/security/validation-2026-10-31-scratch-draft.json)
is superseded for preparation only, not physical validation. Compilation and host
simulation cannot establish hardware safety or restoration.
Preserve the executed profile, private output and separate observation record;
do not rerun it or use the repro as an automatic retry.

The core's host fake implements NAND one-to-zero programming, partial/error paths,
failed/false erase, marker corruption, WP failures, changed reads, wrong/replayed
ACK and neighboring canaries. It runs only original code plus trusted host
OpenSSL under ASan/UBSan. The fake ECC is deliberately not a valid hardware ECC
qualification. The host gate separately checks that every storage fsync failure
prevents acknowledgement. No proprietary firmware runs on the host.

The actual adapter I/O functions also run against synthetic MTD/GPMC objects
under sanitizers. The model asserts exact physical addresses/lengths, protected
reads, full I/O completion and flash-BBT/refresh refusal. The actual supervisor
control flow runs with only its ARM syscall instruction replaced by an original
host simulator; fragmented transfers, failed reads, wrong starts, partial/bad ACK
and missing terminal reports are covered.

The original independent encoder constructs a degree-52 binary generator from
GF(2^13), primitive polynomial 0x201b and roots alpha^1 through alpha^8. Its
MSB-first remainder matches seven synthetic sectors from pinned public bchlib
2.1.3. The private inferred storage mask is a host-only input. The checker requires
all four sectors, exact synthetic data, matching raw/normal OOB and untouched
marker/free bytes. Tests reject every parity/padding bit change even if both read
paths return that same damaged value. This is not target encoder qualification.

The duplex session requires a start token, one bounded CRC-checked prepared
snapshot, durable backup acknowledgement, then one terminal snapshot. It performs
no automatic retry. Target cleanup completes before result transmission; it
does not wait for another host command after programming. A host failure after
any ACK byte is attempted records that a write may have executed. Socket-pair
tests exercise storage failure before ACK and terminal state, scope, content and
ECC failures. Original C framing matches the Python wire schema under sanitizers.

Before USB, preflight reads and hashes the complete owner-selected local archive,
binds the private mask record to its archived original digest, and independently
checks all 256 programmed reference sectors in the earlier measured block. No
private mask, data or digest is logged or sent to the target. The scoped duplex
observer is an exact checked derivation; the shared read-only observer is unchanged.

The [prepared validation](../../docs/security/validation-2026-10-31-scratch-prepared.json)
records 432 passing host tests, three unchanged optional integration skips and
passing lint/format/security checks. No loader was armed by preparation. Future
execution requires a fresh private output directory, native USB preflight, a PTY,
advance danger notification and owner readiness. The successful first execution
is recorded separately and does not rewrite that pre-execution scope. A failed/ambiguous write report
requires review before power interruption, retry or native restart.

The wrapper's zero-argument mode performs offline integrity checks only:

```sh
sh build/scratch-restore-20261031-v1/boot.sh
```

Its explicit future execution arguments are
`--execute-experimental-scratch-restore PRIVATE_OUTPUT PRIVATE_ARCHIVE_DIRECTORY PRIVATE_MASK_RECORD`.
Do not reuse a profile after execution or an existing output. Preserve creation
manifests and record execution/result/native-return separately. No firmware
installation, whole-chip restoration or HVAC gate is closed by this preparation.
