# Fixed scratch write/erase/restoration observed

The owner supervised one execution of the sealed v1 scratch profile, source
`2f28a52`, after advance notification of the first intentional flash write and its
power-loss/recovery limits. Normal Nest USB preflight and the local archive/mask
checks passed. The paced loader transferred all three files; loader and collector
exited zero. There was no automatic retry. The display remained detached from
the unwired base and connected only by USB.

The fixed physical region was block 1312, data offset 164 MiB, 128 KiB data plus
4096 OOB bytes. The target reached its guarded READY state after matching raw
reads and the exact empty-data/first-page-cleanmarker predicate. The host saved
and read back all 135168 original bytes and synced the private backup/manifest
and directories before sending the digest-bound acknowledgement. The target
rechecked the live region before mutation. No arbitrary host address/content was
accepted.

The terminal snapshot reports one synthetic data-page program at relative page
1, one block erase and one eight-byte OOB cleanmarker restoration, each with a
zero callback result. Both raw and normal-ECC programmed-page data match the
generated pattern. The independent host BCH4 encoder validates all four sectors,
including the stored parity/padding convention and unchanged marker/free OOB.
It does not rely on the published driver's unreliable zero correction status.

All 135168 final bytes match the preserved original exactly, with matching target
and host SHA-256 checks. The final protected-status field is one. After collection,
the private result was independently re-read: fixed scope/state/counts, four
programmed sectors, exact original/final equality, digests, lengths and owner-only
storage permissions all passed. No private bytes, identifiers, mask or digests
are published.

Private evidence is under `private/scratch-restore-20261031-attempt-1`:
`original.raw-oob`, `original.json`, `result.bin` and `attempt.json`. A separate
pre-execution record and later observation record are preserved under
`private/scratch-attempt-records-20261031`. The sealed creation manifest and all
original input/result files remain unchanged. Do not rerun this profile/output;
the matching repro build is preparation evidence, not a second hardware result.

With the command exited, the owner reported completing the full manual restart.
Normal Nest USB `2464:0002` was then independently observed on the known port.
This records native USB return; it does not substitute for full native UI/HVAC,
power/sleep or production-network validation.

This closes the bounded scratch programming/ECC/erase/cleanmarker restoration
measurement on this unit. It does not demonstrate restoration of a programmed
firmware/boot/configuration block, bad-block migration, interrupted-power recovery,
whole-chip restoration, firmware installation or commissioning. Only the selected
block was acquired/read back; no whole-chip before/after equivalence is claimed.
The owner-selected unencrypted local recovery archive remains on the same PC and
does not protect against loss/compromise of that storage.

Next work must retain these exact results while addressing programmed-block
recovery and the native integration/secure commissioning blockers. A successful
scratch test does not authorize installing the partial replacements or connecting
HVAC. [Machine-readable observation](../security/validation-2026-10-31-scratch-observed.json).
