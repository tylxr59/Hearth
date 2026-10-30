# Experimental bounded raw NAND sample

This profile is a separate diagnostic experiment for the owner's Display-2.6,
after the [geometry test](../../docs/research/nand-geometry-2026-10-30.md) observed
256 MiB NAND, 128 KiB erase blocks, 2 KiB pages and 64-byte OOB. It passed offline
build/integrity checks and host tests. Its first actual upload reached binary
streaming but the host rejected translated tty bytes. The corrected binary-tty
boot subsequently captured two matching first-block raw/OOB samples privately.
It is not a whole-chip acquisition, backup, restore or deployment image.

## Fixed scope and protection

The kernel preserves the geometry profile's hardware write-protection assertion,
protected-status registration gate, skipped BBT scan, zero MTD capability flags
and denied write/erase/mark-bad/lock/OTP callbacks. The configuration is unchanged:
no MTD character/block interfaces, partitions, UBI, storage filesystem mounts,
network or shell. The existing geometry/no-MTD verifiers are not weakened.

The only new content interface is a root-read-only sysfs binary attribute,
`/sys/class/mtd/mtd0/hearth_sample`, with no write or mmap callback. It exposes
exactly 64 records of 2112 bytes. Each read must be one aligned record; offsets
outside the first erase block are rejected. The master must have the exact
measured geometry, zero capability flags and HW/SOFT (not syndrome) ECC mode.
Every record requires protected NAND status again before reading.

The callback requests `MTD_OOB_RAW` with both a 2048-byte data buffer and 64-byte
OOB buffer in one call. In pinned NestDFU revision
`930b834b7f1f082b8761aa5c5af765b4b3e99dc9`,
`Dev/linux/drivers/mtd/nand/nand_base.c` routes this to `read_page_raw`, copies
the complete OOB, and returns both byte counts. This bypasses ECC correction.
The pinned OMAP driver uses standard HW/SOFT paths, whose raw reader directly
reads page data followed by OOB. Nonzero errors or short counts abort sampling.
The legacy character-device raw-read path would omit OOB from `read()` and was
therefore not enabled. `fs/sysfs/bin.c` permits the exact 2112-byte reads here.

Original static userspace reads these 64 pages twice into RAM, once per pass,
then closes the sysfs file. It never opens `/dev/mtd*`, accepts commands or writes
flash. USB retransmissions reuse the cached samples and do not reread NAND.
All pages in that physical range are included; bad blocks are neither skipped
nor classified. Readable raw bytes are not proof of ECC correctness or health.

The reused bootloaders still initialize hardware. These source guards and a
read-only interface do not prove absence of persistent effects throughout the
boot chain. Experimental RAM/NAND execution can hang/reset or affect power.
Keep the display detached from the unwired base and on USB. Notify the owner
before execution under the existing device-work authorization. No flashing,
HVAC operation or restoration is included; preserve [the pre-write gates](../../docs/hardware.md).

## Transport and private storage

Each binary frame has a 32-byte little-endian header: eight-byte `HRTHSMP1` magic,
version, pass number, page number, payload length, payload CRC32 and header CRC32.
The fixed payload is 2112 bytes. The host synchronizes at pass 0/page 0, then
requires all 128 ordered records with valid CRCs. It can discard incomplete
pre-session output while the serial tty becomes raw; corruption after the first
accepted record aborts. Synchronization scan, buffers, output size and duration
are bounded. No unknown received bytes or sample hashes appear on stdout.

The collector accepts only a fresh direct child of the repository's ignored
`private/` directory, rejects symlinks/existing paths, creates the directory 0700
and files 0600, and uses exclusive no-follow opens. It preserves `pass-0.raw`,
`pass-1.raw` and `capture.json` privately, including incomplete or mismatching
captures. Each raw file is exactly 135168 bytes on success: 64 consecutive
data-plus-OOB records. Private SHA-256 values must match between passes. Files,
manifest and output directory are synced; storage failure cannot return success.
Two matching reads establish repeatability only for this sampled range.

The emitter repeatedly streams only its cached RAM frames so the host can catch
an entire sequence without a command handshake. Reset it after collection;
native power/control services are absent while it runs. Do not commit or upload
the capture, display proprietary contents in logs, or execute captured firmware.

## Build, checks and supervised test

Use the same pinned inputs, isolated rootless builder and validated heartbeat
bootstrap artifacts as [the geometry profile](../nand_metadata/README.md):

```sh
.venv/bin/python -m firmware.nand_sample.stage \
  --nestdfu PINNED_NESTDFU --xloader PINNED_XLOADER \
  --loader ORIGINAL_PINNED_LOADER_FILES --base-build VALIDATED_HEARTBEAT_BUILD \
  --output FRESH_SAMPLE_BUILD
podman run --rm --network none --cap-drop all \
  --security-opt no-new-privileges --pids-limit 256 --memory 4g --cpus 4 \
  -v ABSOLUTE_SAMPLE_BUILD:/work:Z localhost/hearth-probe-builder:20261030
.venv/bin/python -m firmware.nand_sample.finalize FRESH_SAMPLE_BUILD \
  --base-build VALIDATED_HEARTBEAT_BUILD
sh FRESH_SAMPLE_BUILD/boot.sh
```

Finalization verifies the exact generated driver/guards, source copies, exported
kernel/init/configuration and unchanged bootstrap bytes. Its unsigned local
manifest pins six artifacts and nine host helpers. The offline checker validates
the configuration, static ARM ELF, image CRCs, bounded decompression and exact
minimal CPIO. A no-argument dry run opens no device. Current local build:
`build/nand-sample-rawtty-20261030`; generated initramfs 3460 bytes, kernel 2742464 bytes
uncompressed. No new Hearth guard warnings were emitted; historical upstream
warnings remain. There is no whole-image safety or vulnerability clearance.

After advance risk notice, launch the wrapper with a PTY using the explicit flag
`--execute-read-only-nand-sample` and an absolute fresh private output directory.
It checks the output path and native USB mode before waiting for one manual
restart. The owner-installed port-scoped ACL permits ROM/serial access without
sudo. There is no automatic device-boot retry. After success/failure and wrapper
exit, request the manual restart and verify normal Nest USB mode again.

The 14 new tests cover private outputs, CRC/order/truncation, mismatching passes,
bounded resynchronization, failure/timeout and storage sync errors. A host-only
ASan/UBSan C harness exercises the actual callback's read bounds, WP/flag gates,
raw mode/data/OOB lengths and errors, plus the actual producer's CRC/header code
against the Python wire format. The harness mocks NAND/sysfs and never accesses
hardware. All 141 host tests passed with Podman broker/container tests enabled;
Ruff/format/Bandit passed. Complete first-block sample transport is now observed once; whole-chip acquisition
and restoration remain unverified.

Original `sample.h` and its combined kernel harness are GPL-2.0-or-later, with
the [GPLv2 text](../probe/COPYING.GPL-2.0) and [provenance](../../THIRD_PARTY.md).
Other original standalone code is MIT. Generated public GPL sources and all
compiled outputs remain ignored; preserve corresponding source/notices for any
later authorized binary redistribution.

## First wait expired before transfer

The first supervised wait exited 124 after scanning, with no successful USB open
or transfer reported. A follow-up observed ROM mode and the owner reported the
right mode, but the loader had already exited. No sample output directory was
created. The owner was instructed to restore the home icon before a fresh wait;
do not reuse a stale ROM handshake or claim a failed NAND read from this timeout.

## Binary tty correction

The next upload transferred all three files, but collection stopped at the
synchronization bound with zero accepted records. A 65536-byte private trace
from the cached stream showed 28 valid headers/13 complete payload CRCs; after
accounting for CRLF translation, 30 headers/27 complete payload CRCs validated.
This trace remains unvalidated diagnostic material, not a sample capture.
The owner restored the home icon and normal Nest USB mode was observed.

Pinned `u_serial.c` inherits `tty_std_termios`; pinned `tty_io.c` defines
`OPOST|ONLCR`. The fresh raw-tty build explicitly zeros input, output, canonical
and echo processing after that copy. Normal 8-bit control settings remain intact.
The patch requires the exact gadget source digest, and finalization verifies the
actual patched file. Three further tests include a real pseudo-terminal
regression reproducing corruption with ONLCR and byte-exact transport without it.
Old build/partial private outputs are preserved. The retry needs a fresh private
output directory and the same advance notice/manual restart.

## Corrected sample result

The owner restarted while the fresh loader was waiting. Three files transferred,
then the collector returned `raw-sample-matched`: two passes of 64 records,
135168 bytes per pass. The wrapper exited 0. Both private files are regular 0600
files with the expected lengths and matching private SHA-256 values; their
recorded hashes were independently recomputed. No payload bytes/hashes were
logged or added to Git. This establishes repeatability only for the first block.
The owner was instructed to restore native startup with the loader exited;
confirmation is pending. Full-chip acquisition and restoration remain separate.
