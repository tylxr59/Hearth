# Native settings privacy result

One supervised run of source `68edfb9`, using the fresh private
`settings-permissions-probe-20261031/profile-v2`, completed all 36 expected cases.
Loader and collector exited zero. The private report passed independent parsing,
file-permission and process-status checks. Prepared, observed and native-return
records are separate immutable private files. No profile was retried or reused.

The original/candidate variants both passed the prior twelve I/O cases (24 total),
and the candidate passed all five allocation/alias cases. Both process statuses
were zero, binding and tail-canary checks passed, the original reproduced the
synthetic secret-log baseline and the candidate emitted no matching synthetic
secret patterns. Unrelated variadic-log forwarding still passed.

The seven new permission observations were:

| Variant / case | Destination mode | First result | Retry mode |
|---|---|---|---|
| Original, fresh temporary file under umask zero | 0666 | success | 0666 |
| Original, existing 0644 temporary file | 0644 | success | 0644 |
| Original, unrelated open | 0666 | success | 0666 |
| Candidate, fresh temporary file under umask zero | 0600 | success | 0600 |
| Candidate, existing 0644 temporary file | 0600 | success | 0600 |
| Candidate, unrelated open | 0666 | success | 0666 |
| Candidate, injected fchmod failure | 0600 (unchanged original) | -100 | 0600 |

The injected failure reached the adapter exactly once, preserved the old values,
failed through the native open-error path and then retried successfully with both
new values present. Fresh/existing cases each restricted the actual descriptor;
unrelated opens made no scoped fchmod call. The baseline 0600 file check also
passed, corroborating the ARM mode-measurement ABI in this harness.

After the command exited, the owner reported completing the manual restart.
Normal USB 2464:0002 on physical port 1-1 was independently observed. No loader
remains armed. The owner did not separately describe the display in this reply;
normal USB return is the independently measured startup evidence here.

This validates the exact GNU-linked, instrumented candidate on synthetic RAM
files with the native settings/NSPR libraries. No actual credentials/settings,
flash filesystem, native application, physical networking, clock change or HVAC
interface was used. No persistent installation occurred. The ordinary standalone
build omits lab phase markers and has not independently run on target. Full
application integration, filesystem installation/rollback and interrupted-write
recovery remain open. Do not silently substitute a different build or treat the
old partial hardening overlay/five review replacements as installable firmware.

Next is the filesystem-level installation path: verified current root/files,
fresh private backups, exact native TLS/storage/startup assembly and bounded
commit/rollback/readback. Keep general raw-NAND research parked and retain the
existing HAOS telemetry backend and owner network choices. No router change is
requested.
