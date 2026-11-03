# First persistent nine-file installation

Source `c4dc064`, private install-v3 and paired restore-v3 passed offline
checks/reproduction. The owner timed the reviewed ROM restart directly from the
second protected snapshot's RAM session, with USB power/base detached. All three
files transferred. All 56 synthetic ARM RAM cases passed with zero process status
and no diagnostic/discarded bytes. Real-file read-only preflight passed against
the exact refreshed originals.

The host paused before writes. After receiving the concrete scope and
power-loss/native-startup/recovery limits, the owner explicitly replied ready to
run the persistent install. The separate decision rechecked the capsule, preserved
originals/receipt, kernel, helpers and matching restore image. Commit intent and
completed token transfer were separately recorded durably.

The final report independently passes the strict install contract:

| Evidence | Observed |
|---|---|
| Bound commit, one-use window and both RW remount attempts | Confirmed |
| Selected targets attempted / committed | All nine / committed |
| Transaction, rollback, journal and cleanup errors | Zero |
| Handle release, unmount and protection-seal errors | Zero |
| Fresh read-only verification after unmount/seal | All selected expected bytes/modes |
| Final gate / hardware protection | Sealed / asserted |
| NAND operations | 94 page programs, zero erases, zero OOB marker writes |
| NAND operation failures | Zero |
| Complete / safe-to-restart | Both true |

This installs the local endpoint/trust/assigned credentials, NIST NTP
configuration, standalone settings correction and native startup wrapper. Native
HVAC implementation/backplate firmware are preserved. The selected-file rollback
archive remains in user-config; independent host originals/custody and raw
acquisition evidence remain private.

The command exited zero. The owner reported the requested restart done and
normal Nest USB was independently observed. This confirms native USB startup,
not complete application health, native network authentication or HVAC. The
unit remains unwired; a first battery-powered Wi-Fi bench is pending.

Preserved privately: file-writer-20261031/preflight-attempt-3, including immutable
execution/preflight, original selftest/result payloads, decision intent/completion,
independent installation review and native-return evidence. install-v3's execution
marker is permanent; **never rerun it**. No restore image has been executed.

Measured scope is one persistent file installation and selected-file readback.
The adapter's erase/OOB paths were not exercised by this installation; host
sanitizer/synthetic checks are separate evidence. Actual JFFS2 restoration,
hardware power-loss, damaged-filesystem/whole-firmware recovery, live native
TLS/time/bootstrap/transport and physical HVAC remain unverified. Native software
may rewrite settings after boot; do not assume old exact-byte restore preflight
will accept subsequently changed application data. Preserve fresh read-only
evidence and review a concrete recovery plan rather than overriding it.
