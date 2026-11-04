# Supervised backup-to-install handoff, 2026-11-03

One fresh owner-approved two-pass full-NAND backup passed the independent
archive checks, including equal corrected views and no uncorrectable chunks.
Original files were reconstructed from that archive, and a fresh combined kit
and standalone restore images were built without a separate acquisition boot.
The existing Home Assistant entry and its current commissioning bundle were
preserved.

With separate owner readiness, the host armed one successor loader in a PTY,
observed it waiting, and sent one nonce-bound software restart to the backup
RAM endpoint. All three loader transfers completed without another ring press.
This measures the backup-to-successor transfer, not successor readiness.

The combined supervisor produced no capacity selftest or result before the
host's 240-second receive timeout. Neither commissioning nor cleanup write
intent exists; neither INSTALL decision was requested or sent. The host exited
and no automatic retry was performed. Runtime NAND counters were not received;
this record does not claim a measured zero-program/erase count. The capacity
kernel slot starts physically unable to write, and no child readiness was seen.

## Diagnosis and correction

The executed supervisor tried to bind-mount shared rootfs libraries and
original-data directories into its child chroots. The exact pinned public
kernel marks rootfs MS_NOUSER in `fs/ramfs/inode.c`; `graft_tree` in
`fs/namespace.c` rejects such mounts. That source explains the stop before the
capacity child. The old supervisor silently idled on setup failure, so no
on-device errno was captured: the diagnosis is an inference from the executed
source and pinned kernel, not a device diagnostic.

The corrected supervisor creates RAM hardlinks for the two libraries and
renames the three original-data files between capacity and cleanup. Originals
retain link count one and mode 0400. No flash range, protection, transition,
verification, or restore gate changed. Setup failures now emit a bounded stage
and error report through the existing bootstrap-failure channel; the host
preserves invalid input before refusing.

The real-filesystem syscall harness checks link counts, metadata, rename
custody, no bind mounts, and parent child/gate ordering. All 1,948 tests pass,
with seven optional skips. The corrected ARM supervisor compiles; passive
initramfs checks and private image composition pass within the existing RAM
and USB limits. These are host results; the correction has not run on hardware.

## Preserved state and next step

The original attempted profiles, source snapshot, console, transfer receipts,
backup, and failure review remain private and unchanged. The owner was told to
restart normally with the display detached and USB connected. Native USB was
subsequently confirmed by the host. No loader is armed. No persistent installer write or HVAC action was
authorized during this attempt.

A separate fresh backup profile and session are prepared. A new attempt needs
fresh owner readiness, one initial ring boot, a new backup and kit, separate
successor readiness, and explicit approval for each persistent file group.
Selected-file recovery is measured historically; whole-firmware and power-loss
recovery remain unverified. Do not replay this attempt or present combined
installation as measured.
