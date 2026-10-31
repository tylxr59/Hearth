# Exact-plan filesystem writer preparation

Status: prepared and checked offline, **not executed on the thermostat**.

The earlier 91-case ARM RAM pass and protected nine-file JFFS2 snapshot remain
separate completed evidence. This work connects the exact private capsule to a
bounded write-capable kernel and original userspace action. It does not establish
persistent installation, JFFS2 durability, firmware restoration or native transport.

## Implemented

- A separate kernel registers only fixed root0/user-config views. Hardware WP
  starts asserted; the master stays read-only and no MTD char/block device exists.
  Page writes, block erases and the exact JFFS2 OOB cleanmarker are allowed only
  inside those ranges after a one-use plan/backup-receipt gate opens. All reads,
  protection checks and writes share a mutex. Erase completion callbacks run only
  after WP restoration and unlocking, preserving request lifetime and avoiding
  callback lock inversion. A critical-source inventory pins the reviewed NAND,
  JFFS2, GPMC and statfs implementations.
- JFFS2's legacy remount check now consults requested flags, so RO-compatible
  unknown nodes cannot silently become writable. No compatibility override exists.
- Install and restore images embed exact private original/replacement bytes as
  data in a root-only executable. Only native libc/interpreter execute alongside
  original helpers; no host execution of proprietary firmware occurs. Passive
  checking covers dependency closure, permissions, load bounds and complete bytes.
- Before real-file access, a UID/GID 65534 helper runs 56 synthetic RAM cases:
  32 transaction cases and 24 recovery cases, including read-only restore
  inspection. Host-only positive-xattr fixture 14 remains excluded. The existing
  91-case profile's default workload and historical results are unchanged.
- The actual action initially mounts read-only, verifies originals and awaits a
  separate exact commit. A failed initial preflight can capture all selected
  files read-only in the same session for a new reviewed capsule. It cannot apply
  an old plan to changed files.
- The host requires all selftests before ACK, records READY, then waits for an
  explicit local install/restore/abort decision. It rechecks the complete backup,
  capsule and images before sending. Commit intent is fsynced before USB bytes;
  partial transfer is treated as uncertain, with no logical retry.
- After commit, writable remount itself counts as potentially persistent. The
  transaction closes handles and unmounts both filesystems before sealing WP,
  then verifies all selected bytes/modes through fresh read-only mounts. Strict
  result validation distinguishes complete, safely restored and unknown states.
- A matching prebuilt restore image can enter from a reviewed failed RAM session,
  avoiding native boot through potentially partial files. It still requires its
  own fresh preflight, supervised restart and separate commit.

See [the operating sequence](../../firmware/file_writer/README.md). Report CRC and
plan/receipt binding check transport consistency; they are not peer authentication
against a malicious USB device. The owner-controlled PC/device is assumed trusted.

## Offline evidence and limits

`make check` passes. The full suite passes 766 tests with five unchanged optional
integration skips. New meaningful checks cover physical range/WP faults, actual
adapter callback lifetimes and reentrant reads under sanitizers, lifecycle cleanup,
archive secrecy/ABI refusal, frame corruption/truncation, all selftest completion,
real socket ACK/commit sequencing and refusal after custody changes. No physical
USB or NAND write occurs in these tests.

The separate kernel rebuilt with all six recorded artifacts unchanged. Five ARM
helpers reproduce independently. Private install and restore images each have
seven artifacts; install uImage is 1795751 bytes, restore 1795689 bytes, below the
reviewed 6 MiB load bound. Generated proprietary hashes remain private.

Machine-local preparation, all unexecuted:

- `build/file-writer-kernel-20261031-v3`
- `build/file-writer-actions-20261031-v4` and its separate reproduction
- `private/file-writer-20261031/{install,restore}-v1` and separate reproductions
- Independent reviewed pin: `private/native-file-capsule-20261031-v1-pin.json`

Earlier draft artifacts are preserved and must not be presented as execution
evidence. Creation manifests remain immutable; execution evidence belongs in a
fresh private directory. No loader is armed. The unit remains in native USB mode,
on USB with the unwired base detached, after the stock battery UI check.

Next is one supervised RAM preflight. Notify before this write-capable RAM boot;
do not send a persistent commit without separate advance notice and timing
readiness. If a selected file changed, preserve the fresh snapshot and stop for
offline review. If preflight passes, keep the session waiting while preparing the
concrete first-write decision. Whole-firmware recovery, hardware power loss, real
native TLS/time bootstrap, Wi-Fi runtime and physical HVAC remain unverified.
