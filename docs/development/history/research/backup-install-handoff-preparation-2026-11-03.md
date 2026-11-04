# Backup-to-install handoff: implementation and supervised plan

## Implemented locally

`firmware/nand_handoff/` adds a fresh nonce-bound restart endpoint after the
canonical full-NAND exporter succeeds. It uses an unchanged checked full-read
kernel with a raw external newc initramfs. Capture, raw/OOB custody, ECC analysis,
source checks, geometry and write-denial gates are retained. Export failure
cannot reach the restart endpoint, and the same source cannot export or restart
a second time.

The new wizard builds this private profile alongside its public-source kernel.
Its manifest and exact execution marker are bound to the archive receipt.
`installer/ram_handoff.py` requires the checked same-session backup, exact nonce,
and a checked combined kit. It starts the successor loader in a PTY, waits for
that live process's scanning message, records intent durably in both sessions,
and sends one restart token. A partial/failed token is consumed as an uncertain
attempt. There are no replacement loaders or automatic retries.

The combined installer now selects this path for restartable backups. Existing
non-restartable sessions retain their original manual path. The user-facing
status tells the owner to leave the ring untouched during automatic transfer.
Successor transfer still must be followed by image-specific selftests, capacity
and original-file checks, then separate owner approvals for the two writes.

## Local evidence

- Fresh full-reader kernel built from the pinned public sources and passed its
  original checker. No old source/provenance refusal was bypassed.
- A fresh private restartable wrapper compiled for ARM and passed exact image,
  raw archive, kernel/bootstrap and source checks.
- C fault cases verify successful two-pass export before readiness, export
  failure, incorrect nonce and one reboot attempt even if the syscall returns.
- Real PTY tests with synthetic loaders verify scanning before restart, durable
  intent before the token, early loader failure, partial delivery with no retry,
  exact nonce validation and kit-check refusal.
- Custody tests refuse mixed reader location, kernel, manifest and execution.
  Wizard/sequence tests verify automatic routing and no repeated ring prompt.

These are local results. No new loader, device write, HA restart or HVAC call
was made during this implementation. The prior ROM enumeration experiment is
not a successor-image-loading pass.

## Next supervised run

1. Confirm owner readiness, detached display, USB power, normal device identity,
   the existing HA commissioning bundle and fresh session/profile/output paths.
   Read the normal diagnostic file through one read-only `mtype` if privilege
   is needed; do not change disk permissions or recreate the HA entry.
2. Arm one fresh full-backup loader in a PTY. The owner makes the first ring
   restart once. Preserve both raw/OOB passes and run independent ECC analysis.
3. Extract original files from that checked archive, without another device
   boot. Bind them to this intake/bundle and build the fresh combined kit and
   both standalone restore images. Stop if any check or capacity bound refuses.
4. With owner readiness for the planned successor, wait for its loader to scan
   before sending the one software restart. The owner leaves the ring untouched.
   Verify the new RAM image's evidence; transfer completion is not sufficient.
5. Before any persistent write, present the concrete nine-file commissioning
   scope and recovery limits and obtain explicit approval. Ask separately for
   the three-file network scope. No intentional HVAC control is included.
6. Require complete sealed readback/encoding evidence, return normally and
   verify readings. A later restore test needs its own fresh owner approval.

If the successor is not captured, the stock boot path may run and write normal
settings/logs. Keep USB power after uncertainty and preserve the attempt; do not
replay it. Selected-file restore has measured evidence; combined installation,
shared-original writes, whole-firmware and power-loss recovery remain unmeasured.

The subsequent supervised attempt completed the automatic transfer but failed
before successor readiness. See the [result and correction](backup-install-handoff-result-2026-11-03.md).
