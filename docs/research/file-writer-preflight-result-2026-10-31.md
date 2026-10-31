# First protected file-action preflight

One supervised run of source `a7eff49` and private install profile v1 completed.
The owner provided the ROM restart with the unwired base detached and USB power
connected. All three upload files transferred; the cached report independently
validated all 56 synthetic ARM RAM file/recovery cases, zero child status and no
diagnostic bytes or discarded diagnostics. The real root action then ran.

Real-file preflight refused target 7, `settings.config`: stock software had changed
its contents since the earlier snapshot. The other eight targets and all selected
metadata matched. No host commit was issued. The kernel write window never opened;
no writable remount or transaction ran. Program/erase/marker/failure counters were
all zero. Handles closed, filesystems unmounted and the gate sealed with WP
asserted. The strict final report confirmed safe restart without claiming install
completion or post-write verification.

The fallback captured a fresh protected nine-file snapshot in the same RAM run.
Its bound CRC frame, fixed scope and durable host backup/receipt independently
validated. The owner reported the requested restart done, and normal Nest USB
was independently observed. The loader exited zero and no automatic retry ran.

Preserved privately and never to rerun:

- `private/file-writer-20261031/install-v1`, its immutable creation manifest and
  exclusive execution marker.
- `private/file-writer-20261031/preflight-attempt-1/`: original selftests/result,
  changed-files frame, host backup/receipt, observed evidence and native return.
- `refreshed-snapshot/`: separately verified fixed snapshot/custody representation
  for capsule generation; original result and capture remain unchanged.

The refreshed v2 capsule preserves current settings while changing only the two
assigned credential spans. The eight other replacement payloads remain unchanged;
the CA/CRL still verifies the deployed backend. Both capsule copies reproduce.
The private v2 pin, kernel v4, helpers v5 and paired v2 action images are fresh,
unexecuted artifacts. Old v1 artifacts are not relabeled as usable new attempts.

The actual unit was also enrolled into the existing HAOS backend while that app
was stopped. A fresh remote registry was fetched and preserved; after stopping,
its bytes were rechecked before adding the existing capsule's dedicated credential.
The replacement was privately staged, read back, atomically activated and read
back again before app restart. Existing manager/revocation records were retained;
no broker restart or broker configuration change occurred. A **host-generated**
authenticated native entry request then passed trusted TLS and returned HTTP 200
with no-store. It is not a physical thermostat exchange. Native telemetry mode
still rejects commands and does not enable HVAC control.

This run demonstrates actual ARM helper launch, synthetic selftests, real-file
read-only inspection, changed-file refusal/capture and clean protected exit.
It does **not** demonstrate persistent JFFS2 installation/restoration, hardware
power-loss or whole-firmware recovery, physical networking/native fetch, trusted
time bootstrap, sustained battery runtime or HVAC operation. Next is a fresh
notified owner-timed preflight against the refreshed plan. Any persistent commit
requires separate advance notice and timing readiness.

## Second preflight and snapshot handoff correction

Source `534e0b0`/install-v2 completed the same 56 cases and again refused target7
before any commit/window/RW remount/transaction. All NAND counters stayed zero;
cleanup sealed WP and confirmed safe restart. A second fresh nine-file capture
and host custody validated. The command exited; the unit remains in sealed RAM
mode with USB connected/base detached, rather than returning to native startup.
Evidence is private/file-writer-20261031/preflight-attempt-2. Never rerun install-v2.

Bounded XML inspection of the two most recent captures found identical keys and
values despite different file bytes. Therefore another native boot can invalidate
an exact-byte snapshot without a meaningful settings change. This is a reason to
change the boot sequence, not weaken original-file validation.

The new `--handoff-from` entry permits only an explicitly reviewed zero-write
snapshot session and a new plan whose captured source bytes exactly match it.
It validates all prior selftests/result/custody, refuses any prior decision or
write attempt, requires sealed protection and accepts only known RAM USB mode.
The owner still times a fresh ROM restart; no automatic retry or commit exists.
Eight new host tests exercise acceptance and rejection for native/stale ROM,
changed capture, broken custody, prior decision, uncertain result and bad selftests.

Fresh v3 capsule/pin, kernel v5, helpers v6 and paired action images v3 preserve
the second capture's exact bytes. The matching backend credential is unchanged.
The second snapshot/result remains immutable. No native restart should occur
between this snapshot and the next supervised RAM preflight.
