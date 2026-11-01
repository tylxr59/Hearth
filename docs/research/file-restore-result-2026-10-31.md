# Selected-file restoration after native UI stall

**Compatibility correction:** this was byte-only restoration under an LZO-capable
kernel. Native UI still stalls. See the [identified compression mismatch and
recovery](compression-recovery-2026-10-31.md); do not treat this as native recovery.

After installation, the unwired battery bench remained at a steady home icon
with blinking green LED and no Wi-Fi settings. This did not establish native app
health or connectivity. A supervised protected diagnostic from source `50fe8ff`
captured current nine files and64 log tails read-only. All selected installed
bytes/modes still matched. The log file-count limit was reached; no loader/crash
error was found in that partial capture, which does not identify or exclude a cause.

The owner chose restoration preflight. The matching unexecuted restore-v3 image
was rechecked against the exact capsule/custody and entered from the known
protected diagnostic RAM mode using the reviewed original persistent attempt.
No native startup was required between acquisition and restoration.

All56 synthetic ARM file/recovery cases passed with zero child status and no
diagnostics. Real-file read-only restoration preflight validated the on-device
journal, saved originals and current files. The host paused before writes. The
owner explicitly confirmed the restore commit after receiving its scope and
power-loss/recovery limits; intent/completed token transfer were recorded durably.

The complete strict restore result independently passes:

| Evidence | Observed |
|---|---|
| Targets attempted / restored | Nine / nine |
| Install committed flag | Zero, restoration action |
| Transaction/journal/rollback/cleanup errors | Zero |
| Handle release/unmount/protection errors | Zero |
| Fresh read-only verification after unmount/seal | Exact original bytes/modes; added wrapper/shim absent |
| Final gate / hardware WP | Sealed / asserted |
| Operations |41 page programs, zero erases/OOB markers/failures |
| Complete / safe to restart | Both true |

The host command exited zero. A stock battery/unwired-base startup check is now
pending; the owner was asked to leave Wi-Fi unconfigured. Backend enrollment
remains preserved but the thermostat's selected configuration is restored to
its pre-installation state. Neither app startup recovery nor native transport
can be claimed until observed.

Preserve private startup-diagnostic-attempt-1 and restore-attempt-1 beneath
file-writer-20261031, all creation/execution/report/custody/review records and the
original NAND evidence. Never rerun either executed profile. The selected-file
rollback directory remains on-device as recovery evidence; restoration is not a
whole-filesystem/raw-flash rollback or proof of hardware power-loss recovery.

This is the first actual **selected-file restoration and readback** measurement.
It closes that narrow previously untested scope only. Native UI health, native
kernel/application compatibility, erase/OOB paths in this writer, damaged JFFS2,
hardware power loss, whole-firmware recovery and physical HVAC remain unverified.
Host baseline786/five optional skips and make check; no source changed during
these measurements. The cause of the UI stall remains open.
