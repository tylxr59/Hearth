# Current status

_Last updated 2026-11-04. Keep this page short and current. Dated detail goes
in [history](history/), lasting facts go in [findings](findings.md) and
release history goes in the release notes._

## Device state right now

| | |
| --- | --- |
| Unit | Gen 2, Display-2.6, primary firmware 5.9.4-5 (the only measured target) |
| Where it is | Display **reattached to the wired base** by the owner. Normal dial and fresh HA readings confirmed |
| HVAC base | **Wired to real oil/baseboard heat.** Never assume an unwired base when it's reattached |
| Last on-base state | Heat 63 °F, Eco off, empty schedule, heating idle (owner confirmed) |
| Loader | None armed. The last host exited |
| Flash contents | Commissioning9 and cleanup3 installed, both readback- and encoding-verified |
| On flash, keep | One old restored network4 rollback archive (5,822,879 bytes). Deleting it is **not** authorised |
| HA | One loaded Hearth entry, restored from the exact matching saved profile. Live bundle matches this Nest |
| Private evidence | Recovery archives, executed profiles, reports and source snapshots under `private/`. All single-use |

**Authorised now:** local code, docs, packaging, tests, commits and pushes.
**Not authorised:** HA Core restarts, persistent device writes, arming a loader,
intentional HVAC calls or deleting anything on the device. Each needs fresh
owner approval.

## Last hardware events (newest first)

- **HA entry repaired, on-base readings confirmed.** With owner approval, the
  matching saved HA profile was restored and its missing entry registered. The
  owner reattached the display and confirmed the normal dial and readings. No
  HA Core restart and no HVAC call.
  [Repair and final check](history/research/ha-profile-repair-2026-11-03.md).
- **Combined install passed** from a manual boot: zero-write capacity check,
  then both separately approved file groups, each complete, readback- and
  encoding-verified and safe to restart, with zero failed NAND operations.
  [Result](history/research/combined-install-success-2026-11-03.md).
- **Live acquisition passed** after offline extraction refused a
  checksum-invalid `settings.config` fragment on a fresh backup.
  [Refusal](history/research/handoff-extraction-refusal-2026-11-03.md) ·
  [acquisition](history/research/handoff-live-acquisition-2026-11-03.md).
- **Backup-to-install restart** completed the successor transfer without a ring
  press, then the supervisor stopped before readiness (rootfs bind mounts). It
  was corrected and not retried.
  [Result](history/research/backup-install-handoff-result-2026-11-03.md).

Older events are in [history/research](history/research/).

## Released

**v0.12.0** (experimental) is the latest release. It ships the combined install
and the live-reader fallback. There's no unreleased code since then.

## What's next

Each step needs fresh owner approval and a fresh profile:

- Measure the automatic backup-to-install restart through a completed install.
- Measure a guided restore after the combined install, which also checks the
  lowered space margins.
- A supervised heating start/stop, with the equipment identified.

The full list of gates is in the [release checklist](roadmap.md).

## Unmeasured on hardware

The automatic backup-to-install route end to end, combined guided restore,
handling of natively recompressed archive originals, the complete wizard on a
pristine stock unit, whole-firmware recovery and power-loss recovery.

## Validation snapshot

1,975 tests pass, with seven optional skips. Static checks pass. The
network-isolated HA 2026.10.4 sandbox passes 24 native control round trips plus
the onboarding exchange.

What has been measured on hardware is listed in
[compatibility](../compatibility.md).
