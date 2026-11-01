# Root0-only network writer preparation —2026-11-01

The four-file network changes remain uninstalled. The preceding protected ARM
measurement passed61 synthetic cases and full read-only preflights of all four
real inputs. This follow-up prepares a distinct write-capable install/restore pair;
it does not reinterpret the protected test as permission to write.

The new kernel registers only root0, with the write-range guard denying the
previously accessible user/config region as well as boot/secondary/calibration
regions. Original pinned public source archives were independently verified and
rebuilt in the existing offline rootless container. Two fresh builds produce
identical kernel, config, fallback and bootstrap artifacts. Its default fallback
is inert and explicitly identifies the write-capable kernel; it opens no window.

The selected existing transaction handles complete-file temporaries and private
plan-specific backups/journal. The old nine-file adapter and1MiB bound stay intact.
The new action uses the separately bounded6MiB/1MiB/64KiB/64KiB contract. Hardware
protection opens only after a separately bound commit, and cleanup retains the
existing release/unmount/seal/read-only-verification sequence.

The unit has64MiB RAM. Root-only originals are read-only opaque files in the
private gzip initramfs. Candidate mappings share unchanged original pages, get
private pages for the reviewed spans, pass full original/candidate SHA256 checks,
and are then sealed read-only. No proprietary ELF executes on the development
host or becomes a linker input. Public helper code has no executable stack or
writable executable segment. Imports are passively checked against the preserved
native libc export set; only that libc/interpreter pair executes with the helpers.

A fresh access-restricted copy of all four originals is preserved independently
from working candidate inputs on this machine, under the owner's existing local
archive exception. Both actions verify that custody and the separate reviewed
plan pin. Whole-firmware/power-loss recovery and large-file NAND restoration are
not established by the earlier selected-file UI recovery or scratch-block test.

The writer repeats61 RAM checks, then starts read-only. It requires all four actual
files, modes and complete identities to match and reports memory/space guards
before READY. The host cannot accept READY without those resource observations.
At least24MiB free RAM is required. Install reserve is three times file bytes plus
2MiB; restore reserve is largest file plus4MiB. Space is checked again at commit,
but JFFS2's dirty/reclaimable accounting is not a guarantee against ENOSPC.

Post-write success requires complete bytes/modes, forced NONE/ZERO active fragments
for targets/backups/journal, unmount and protected sealed status. Unknown data,
unexpected preflight content, rollback failure or unsupported fragment encoding
stops the process. No generic instruction to restart follows an unknown result.
The host preserves one-shot commit intent before USB transmission; expired/dead/
already-sent decisions cannot create a fresh authorization.

No new device boot or write has occurred during preparation. Next obtain a fresh
filtered primary/version confirmation and owner-timed readiness with concrete
persistent-write notice, boot once, inspect preflight, and commit only within that
authorization. Afterwards confirm native UI/Wi-Fi, actual HA readings, the local
connectivity destination and NIST NTP traffic. Unobserved services may still have
other native endpoints; do not claim complete Google independence from a quiet
short watch. HA command delivery and physical HVAC validation remain separate.

Validation:1087 host tests pass with five optional integrations skipped, plus
`make check`. Eleven mapped-data tests include a complete large-file install and
restore under host sanitizers with exact original contents/modes preserved. The
six kernel artifacts reproduce; all ten artifacts of each private install/restore
profile reproduce independently. Their USB images are4167686/4167667 bytes,
respectively, below the6MiB limit. Offline matching-pair verification passes.
No ARM firmware was executed on the host, and this new write-capable profile has
not yet executed on the device.
