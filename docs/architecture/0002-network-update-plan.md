# Bounded network correction: proposed device contract

Status: protected four-file acquisition is implemented and observed; the persistent
writer remains preparation only. No network-update writer is armed.
The working native HA 0.2.1 deployment provides the future local connectivity
response; the thermostat's Google URLs have not changed.

Use a separate four-target adapter rather than increasing every bound in the
existing nine-file installer. Its root-relative targets are fixed:

| Target | Maximum file bytes | Candidate change |
| --- | ---: | --- |
| `nestlabs/sbin/nlclient` | 6291456 | One terminated read-only connectivity URL |
| `usr/sbin/connmand` | 1048576 | One terminated read-only connectivity URL |
| `etc/connman/main.conf` | 65536 | Exact preferred fallback time value |
| `etc/nestlabs/client.config` | 65536 | Exact registration URL, logs remain off |

All are existing root0 files. No user-state partition, settings values, trust
anchors, control code, backplate or raw NAND addresses belong to this operation.
Limits are specific to this adapter and do not alter existing capture/image/writer
limits. The active primary partition must be reconfirmed before acquisition.

## Fresh read-only acquisition

The independently checked root0-only read-only RAM profile caches a bounded report
and rereads each file through a small comparison buffer. It captures exact length,
mode/ownership, filesystem identity and per-file SHA256 under a fresh session.
Refuse links, unexpected file types/owners, duplicate targets, growth, truncation,
unbounded records and absent completion. Compare against preserved lawful inputs;
derive candidates only from the fresh records. Preserve the complete capture and
its durable private receipt separately from any write image. A transport checksum
or an unchanged 40-byte string alone cannot bind the rest of a 5 MiB executable.

The [first supervised acquisition](../research/network-snapshot-result-2026-11-01.md)
passed all four original comparisons and private custody readback; native return
was confirmed. This closes fresh acquisition without implementing any writer.

## Full-file streaming replacement, not an in-place range write

Use bounded complete-file writes to fresh temporaries, with candidates derived
through the checked streaming core. Verify full original/candidate hashes,
metadata and equal lengths. The chosen adapter reuses the measured transaction
with bounded RAM-backed data, avoiding a second journal implementation. Opaque
originals can be mapped read-only from a private root-only initramfs; candidate
arenas are bounded by the four target limits. The old 1 MiB contract stays unchanged.
Reject overlap,
multiple occurrences, changes outside the span or a source identity mismatch.

Keep plan-specific original copies and a durable journal; preserve every existing
recovery archive. Reuse the independently tested transaction phase ordering where
applicable, with new callbacks restricted to these four targets. Before any write,
measure available JFFS2 space and account for uncompressed temporary files,
uncompressed original copies, journal overhead and erase-block reserve. If adequate
space cannot be demonstrated, stop; do not fall back to in-place overwrites.

Writing the **complete** candidate with the already checked forced-NONE kernel
allows the existing active-fragment encoding audit to remain meaningful: every
live fragment of the replaced file must be NONE/ZERO after sync and exact readback.
It avoids adding an unmeasured range ioctl and avoids incorrectly applying that
audit to untouched stock compressed fragments. Recovery similarly streams complete
original files through uncompressed temporaries and verifies full readback and
encoding before sealing protection. File length preservation does not establish
atomic multi-file installation or power-loss recovery.

## Gates before a physical attempt

The new adapter still requires host fault tests, bounded ARM RAM cases, reproducible
private packaging, source/ABI checks, immutable fresh backup receipts, root0-only
write-window enforcement and restore preparation. Tests must cover short/interrupted
I/O, mid-span boundaries, full-file mismatch despite a matching span, ENOSPC,
rename/directory-sync errors, interrupted journal states and failed restoration.
No firmware runs on the development host. No native application or physical
networking is needed inside the RAM harness.

The [combined ARM run](../research/network-ram-result-2026-11-01.md) subsequently
passed all 61 synthetic cases and four real preflights. Source/artifact and complete
host-custody verification also pass. Persistent kernel/lifecycle/restore packaging
is still unfinished; these measurements do not authorize bypassing those checks.

Only after those pass may a fresh owner-timed boot perform read-only real-file
preflight and pause. A separate scoped commit must remain bound to its session,
plan and backup receipt. Notify the owner of the concrete persistent change and
power-loss/recovery limits before arming that operation. Abort/refusal does not
justify bypassing a check or automatically retrying a device boot.

After a successful update: verify native startup, all three HA readings, IoT-only
registration reachability and actual probe/time destination metadata. Remove no
more services merely because one traffic capture appears quiet. Command delivery,
physical HVAC and whole-firmware recovery remain separate unfinished work.
