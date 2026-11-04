# One install boot

New wizard kits contain one RAM image for the capacity check, commissioning9,
and cleanup3, in that order. The initial full NAND backup is still a separate
boot. Original-file acquisition can happen offline from that archive, with
strict refusal of ambiguous or damaged inodes. New wizard sessions use the
checked restartable backup endpoint to enter the combined image automatically,
with its successor loader waiting first. A supervised automatic transfer was
observed. A later fresh manual boot, using protected live acquisition inputs,
passed capacity and both installs with separate owner approvals; see the
[result](../../docs/development/history/research/combined-install-success-2026-11-03.md).
The complete reduced-boot wizard remains unmeasured end to end.

The supervisor runs the existing original bootstraps as children in fixed
chroots. Libraries use RAM hardlinks. Opaque network originals move from the outer
RAM directory to capacity and then cleanup using rename, preserving their
required link count of one. The pinned kernel rejects rootfs bind mounts. Each bootstrap still runs its
synthetic checks, each action still
checks its original files on the thermostat, and each writer still needs a
separate owner `INSTALL` decision. A host-validated, durably saved successful
result permits one plan/receipt-bound terminal acknowledgement, then the child
exits. Refusals, cancellations and unknown states never advance.

The combined kernel initializes three distinct write windows once. Its capacity
slot cannot write. A sealed capacity slot with zero operations may select the
commissioning slot; a sealed commissioning slot with successful page programs
may select the cleanup slot. Both transitions require exact next-plan custody,
asserted hardware protection, no failed operations, read-only partition flags,
and no mounted flash views. Cleanup enables only root0 and its physical range.
There is no reopening, backwards transition, or replay of a sealed window.
Ordinary standalone kernels retain their existing single-window policy.

The combined profile rechecks constituent sources, ABI/dependencies, restore
images, capacity reservation, kernel patches, full RAM inventory and the
existing 24 MiB archive / 6 MiB USB-image bounds. Standalone launchers refuse
child profiles. All three child profiles become attempted when the single
loader starts, even if capacity refuses. With an automatic handoff, a read-only
readiness check of the backup reader runs first; a silent reader leaves every
profile unattempted. Recovery remains separate, fresh,
owner-approved standalone restore boots in reverse write order. Only groups
with durable write intent are selected for restore.

Host fault tests, ARM compilation, a complete three-slot kernel build and
private offline image composition have passed. Capacity and both installs now
have a successful measured run on the supported unit. Combined guided restore,
whole-firmware and power-loss recovery remain unmeasured.
