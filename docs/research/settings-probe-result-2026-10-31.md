# Native settings fault matrix observed in RAM

The second supervised run used source `e5b0917` and the fresh private
`profile-capped-diagnostics`. ROM handshake and all three uploads succeeded;
the collector exited zero. The private report was independently validated after
collection: 8,329 bytes, 31 JSON rows, all twelve ordered cases, all tail canaries
intact, eleven one-shot injections, child wait status zero and true completion.
Sixteen diagnostic chunks preserve the first 2 KiB of stderr; an explicit record
counts 7,956 additional diagnostic bytes discarded. Result rows were not truncated.
The failed first attempt and both creation manifests remain unchanged.

With the command exited, the owner performed the full timed restart and confirmed
the native home icon. Read-only preflight independently observed normal Nest USB.
No automatic retry, library installation, flash mount/write or HVAC operation was
performed. Only synthetic ID/secret values in separate RAM files were involved.

## Measured writer behavior

Each case changes two synthetic values, invokes original native Write, reloads in
a fresh object, then invokes Write again without another setter and reloads again.
The second invocation measures dirty-state retry. No storage correction is loaded.

| Case | First result | First persisted/readable state | Second write |
| --- | --- | --- | --- |
| Normal | 0 | Both new values | Correctly skipped; both still readable |
| Temporary-file open failure | -100 | Both old values preserved | Rewrites; both new values readable |
| Header-write failure | -103 | Both old values preserved | Rewrites; both new values readable |
| Entry-write error | 0 | One new value; other missing | Skipped; missing value remains |
| Entry short write | 0 | XML reload fails (-8) | Skipped; XML reload still fails |
| Footer-write failure | -103 | Both old values preserved | Rewrites; both new values readable |
| File-sync failure | -103 | Both old values preserved | Rewrites; both new values readable |
| File-close failure | -103 | Both old values preserved | Rewrites; both new values readable |
| Rename failure | -103 | Both old values preserved | Rewrites; both new values readable |
| Directory-open failure | -100 | Both new values readable | Rewrites; both new values readable |
| Directory-sync failure | -103 | Both new values readable | Skipped despite sync error |
| Directory-close failure | -103 | Both new values readable | Rewrites; both new values readable |

This confirms the static entry-failure propagation finding in the original ARM
library under the recorded harness. A failed entry can be silently omitted, or a
partial entry can make the renamed XML invalid, while Write reports success and
clears dirty state. A later Write does not repair either result without another
setter. The directory-sync case separately confirms an error followed by a
skipped retry. Its readable new values in RAM do not establish durability.

The ordinary write and several surrounding error paths behave as expected in
this fixture, but the entire writer must not be called transactional or reliable.
Silencing a credential log would not fix these missing-data/retry defects.

## Scope and next work

The experiment uses the native base settings class and unchanged dependencies,
not nlclient/osm, real settings, actual credentials or production transport. Its
kernel has no MTD/block/physical-network/RTC support. The RAM filesystem's real
sync is a no-op; fixed wrappers inject application-visible outcomes. Close failure
means the handle was actually closed and then failure reported. An entry short
return is an extra robustness case; the separate -1 entry-error case follows the
documented error contract. Neither is a NAND wear/power-loss measurement.

The tail canaries, exact exported ABI checks and normal baseline support this
specific harness; they are not a general native memory-safety proof. Bootstrap
hardware/power side effects and restoration remain unverified. The separately
reviewed allocation-failure hazard and credential logs remain unresolved.

Next: design a narrowly scoped storage/error-log correction and test it against
this same fault matrix before considering commissioning. Preserve all original
library bytes and native control. Persistent modification still requires verified
backup/restoration; full native transport/time bootstrap and separately authorized
HVAC validation remain open. Independent MQTT/host work can continue without
another mode switch.
