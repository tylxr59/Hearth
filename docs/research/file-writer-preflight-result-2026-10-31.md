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
