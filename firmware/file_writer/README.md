# Fixed-plan experimental JFFS2 file writer

This is an experimental installer/recovery path for one privately reviewed Gen 2
primary/5.9.4-5 plan. One [persistent installation](../../docs/research/file-install-result-2026-10-31.md)
passed exact readback and native USB return; actual restoration remains untested.
It preserves native HVAC code; this does not validate physical HVAC operation.
The owner must receive advance notice before persistent work, including the
unverified whole-firmware recovery and power-loss limits.

The build requires the private nine-file capsule, its separate reviewed plan pin,
retained native libc/interpreter and pinned public kernel/toolchain. No proprietary
bytes, credentials, generated images or binary hashes belong in Git. Do not use
upstream installers or make the USB diagnostic disk writable.

## Sequence and boundaries

1. `prepare` builds a separate write-capable kernel. Earlier read-only profile
   verifiers are unchanged. Initially hardware WP is asserted; no raw MTD device
   exists. Only fixed root0 and user-config views register. Master callbacks
   restrict writes to their physical ranges and observed page/ECC geometry.
2. `compile` builds original install/restore helpers against public ABI stubs.
   Native firmware is data, never executed or linked on the development host.
   The capsule-bearing executable is root-only in the archive; the synthetic
   selftest runs as UID/GID 65534 and cannot read it or open kernel control.
3. `profile package` creates distinct private install and restore images. The
   passive checker verifies source, kernel, binding, dependency closure, archive
   inventory, execution permissions and RAM load bounds. Link stubs never ship.
4. `run boot` defaults to offline checks. Execution requires
   `--execute-writer-preflight`, fresh private output, matching checked restore
   image, native-mode preflight and one owner-timed restart. No automatic retry.
5. The supervisor runs 56 synthetic file/recovery RAM cases and awaits the host's
   scoped ACK. The host requires every case, zero child status and no diagnostics
   or discarded diagnostic bytes before acknowledging.
6. The root action mounts the real filesystems read-only and checks selected
   original bytes/metadata, plan and protection state. A mismatch never authorizes
   the old plan. When possible it preserves a fresh nine-file read-only snapshot
   in this same session for offline review and a new capsule.
7. Successful preflight emits READY and waits up to 600 seconds. The host records
   that pause and requires a separate local decision. `run decide` has distinct
   `--execute-persistent-file-install` and `--execute-persistent-file-restore`
   switches, or `--abort 1`/`--abort 2`. It requires a live matching execution and
   repeats image/capsule/backup checks. **Never issue commit before advance
   notification and owner timing readiness.** Expiration is not permission.
   Commit is durably recorded before its first USB byte; incomplete transfer is
   uncertain and never automatically retried.
8. The exact commit allows repeated preflight, one-use kernel gate opening and
   writable remount. Even a failed writable remount may have started filesystem
   metadata/GC writes. Each bounded NAND operation checks protection, temporarily
   lifts WP and restores/checks it before returning. Erase callbacks wait until WP
   is restored and the device mutex released.
9. The transaction preserves originals and its plan-bound journal, replaces files
   in fixed order and rolls back on modeled errors. Handles close and both
   filesystems unmount **before** sealing gate/WP. Read-only remount verifies exact
   expected contents/modes, followed by another unmount. Complete requires all
   transaction, cleanup, protection and readback evidence to agree.

The legacy kernel correction changes JFFS2's RO-compatible-feature remount check
to examine the requested flags. Unknown RO-compatible nodes must block a writable
remount; the correction does not force writable mounting.

## Failure handling

Keep USB power connected and the unwired base detached after an incomplete or
contradictory write result. Review private evidence before restarting. Do not
default to native startup after an uncertain transaction.

Prepare the restore image before installation. An explicitly reviewed
`--recover-from PRIVATE_ATTEMPT` entry accepts only restore action, matching plan
and custody, an exited recorded persistent attempt and known RAM USB identity.
It permits the supervised RAM-to-ROM restart without requiring native startup.
It rejects already-active ROM and does not retry uploads. Restore still inspects
the journal/current files read-only before awaiting its own persistent commit.
Whole-firmware, hardware power-loss and damaged-JFFS2 recovery remain unverified.

Evidence is exclusive, owner-only and retained. Reports are CRC framed and bound
to exact plan, backup receipt and action. CRC checks transport integrity; it does
not defend against a malicious USB peer. Owner control of PC/device and reviewed
images remains a trust assumption.

## Snapshot handoff

Stock startup may serialize unchanged settings values into different bytes. Do
not relax exact originals or keep cycling through native startup. After a completed
zero-write changed-file run, `--handoff-from PRIVATE_ATTEMPT` permits one fresh,
owner-timed RAM-to-ROM install preflight. It requires all 56 prior selftests,
matching saved execution/result, no decision files, sealed WP, zero write/remount
counters, verified snapshot custody, and an exact byte match between the new
capsule's source frame and that prior capture. Only the known RAM USB identity is
accepted; native mode and already-active ROM are refused. This is an explicit
new supervised boot, never an automatic retry or persistent commit.
