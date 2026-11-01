# Native JFFS2 compression incompatibility and recovery preparation

**Do not execute the old priority-compression writer/restore images.** Their
byte-only readback did not establish readability by the native kernel.

The captured native messages contain seven reports that compression type0x07 is
unavailable, paired with seven JFFS2 decompression errors. The pinned public
header identifies0x07 as LZO. The experimental writer inherited LZO enabled,
priority compression enabled, with LZO priority80 ahead of zlib60/rtime50.
Thus the laboratory kernel could read its own writes while the native kernel
could not. Original-byte restoration using that same policy could repeat it.

Stock UI remained at the home icon with green blinking after the byte restoration
and after a two-minute wait/brief wake press. ROM boot/RAM diagnostics still work;
the bootloader/native kernel ranges were not writable through the bounded writer.
This is not evidence of lost ROM recovery, but native UI recovery remains unproven.

Original preserved log messages were separately reconstructed offline without
executing firmware and contained no such error. Two invalid-data-CRC records in
that old log volume were excluded, so this is not a claim of perfect historical
log acquisition. Private diagnostic messages remain the direct failure evidence.

The omission was the writer's native-format compatibility check. The earlier
installation and restoration results remain valid only as byte/mode readback
measurements under the laboratory kernel, not successful native recovery.

## Checked correction, not yet executed

- Require JFFS2_CMODE_NONE and reject other writer modes. An exact-source patch
  independently forces the compression dispatch to NONE. Keep LZO decompression
  enabled to read already-written nodes. Existing read-only kernels are unchanged.
- Add a root-only, read-only ioctl that checks active inode fragments directly
  through flash reads: header/type/inode/CRC and NONE/ZERO encoding. It exposes
  no addresses/data or write operation. A fresh read-only mount after flush,
  unmount and protection seal must pass this check for selected files, rollback
  originals and journal. `encoding_verified` is now mandatory for post-write
  restart/completion. Old reports cannot pass the new contract.
- Action3 explicitly re-encodes the seven existing original files and seven
  rollback originals even when bytes already match. It rewrites the journal,
  keeps the two added paths absent, and preserves the same exact private plan,
  original bytes/modes and host custody. It does not recommission Hearth.
- Preflight validates original/current files, backup bytes, journal/plan, exact
  archive inventory and only recognized temporary prefixes before writes.
  Unknown changes are refused. Partial original/archive writes have bounded
  retry/refusal tests; no automatic physical retry exists.
- The combined unprivileged RAM workload is now66 cases: prior56 plus ten
  forced-rewrite/refusal/interruption cases. The root gate remains closed until
  host validation, real-file read-only preflight and a separate local commit.

Kernel build/file-writer-kernel-20261031-v6 reproduces all six artifacts. Seven
ARM programs at build/file-writer-actions-20261031-v7 reproduce. Private profiles
file-writer-20261031/reencode-v1 and restore-none-v1 each reproduce seven artifacts;
the repair uImage is1805067 bytes, under the existing load bound. All are
unexecuted at preparation. make check and814 host tests pass/five optional skips.
Fifteen sanitizer cases execute the actual kernel audit header against original
fake kernel APIs; they do not substitute for target flash verification.

The owner has received the concrete persistent rewrite/power-loss scope and
explicitly chosen to run checked recovery. After their restart, run all66 RAM
checks and read-only preflight. Only if both pass, manually issue the already
authorized action3 commit; no further general permission is needed. Keep USB
power/base detached, inspect exact byte/encoding/protection report, and do not
claim recovery until the native stock UI is observed. No HVAC operation is allowed.

## First guarded attempt

Source7d313cb/reencode-v1 ran once: all66 ARM cases passed, then real preflight
refused before commit. No window/RW remount/transaction; all NAND counters zero,
protection sealed and host exited. No original reencoding occurred. Snapshot was
unavailable and the report did not distinguish mount/file/archive checks, so the
refusal cause remains unknown. Preserve private reencode-attempt-1; unit remains
powered in sealed RAM.

Fresh v2 adds bounded numeric stages and private CRC-framed kernel-log evidence
without changing write checks. Its explicit read-only resume accepts only the
matching exited zero-write repair run, same capsule/pin/kernel, all66 cases,
no decision and known RAM identity. It never executes an old checker or retries
automatically.823 host tests pass/five skips/make check; paired v2 reproduces.
Next fresh owner-timed restart should identify refusal before any correction.

## Second guarded attempt and exact missing-settings recovery

Source1f9388c/v2 ran once: all66 cases pass, again zero decisions/writes and sealed
WP. Numeric stage101 identifies base restoration preflight; the fixed snapshot
fails at target7 settings.config. The private captured kernel tail contains no
observed mount/ECC/JFFS2 error. This does not establish absence, file contents or
the reason it became unreadable/unexpected. Preserve reencode-attempt-2 in RAM.

V3 adds an exact absence path for settings only: a complete RESTORED journal,
mask511, fixed original target and verified backup are mandatory. The ordinary
restore API remains strict. Other missing originals and present foreign data or
symlinks are refused. Host INFO must identify original-present or truly absent
settings and the missing-original mask before action3 READY can authorize commit.
All69 current RAM cases are required; old66 is accepted only as frozen zero-write
handoff evidence. Three additional filesystem cases test that narrow distinction.

831 host tests/five skips/make check pass; same kernel and v9 helpers/paired v3
profiles reproduce. No compression correction has written NAND at this point.
