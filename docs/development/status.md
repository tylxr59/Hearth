# Current status

_Last updated 2026-11-08. Keep this page short and current: replace, never
append. Lasting facts go in [internals](internals.md), and release history goes
in the release notes._

## Device state right now

| | |
| --- | --- |
| Unit | Gen 2, Display-2.6, primary firmware 5.9.4-5 (the only measured target) |
| Where it is | Display **reattached to the wired base** by the owner. Normal dial; HA sensor readings are stale |
| HVAC base | **Wired to real oil/baseboard heat.** Never assume an unwired base when it's reattached |
| Last on-base state | Owner confirms Heat 65 °F target and 69 °F current. HA shows cached 76 °F and idle; no intentional HVAC test |
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

- **Stale sensor reports investigated read-only.** HA history contains earlier
  sensor updates, but current temperature and humidity remain cached after HA
  restarts. Native subscriptions continue with no recorded protocol rejections;
  waking the display did not refresh the readings. The saved device bucket has
  no competing current-temperature field, so simulated cross-bucket masking
  does not explain this snapshot. The cause remains unconfirmed. Evidence is
  private; no thermostat settings changed.
- **HA entry repaired, on-base readings confirmed.** With owner approval, the
  matching saved HA profile was restored and its missing entry registered. The
  owner reattached the display and confirmed the normal dial and readings. No
  HA Core restart and no HVAC call.
  [Repair and final check][ha-profile-repair-2026-11-03].
- **Combined install passed** from a manual boot: zero-write capacity check,
  then both separately approved file groups, each complete, readback- and
  encoding-verified and safe to restart, with zero failed NAND operations.
  [Result][combined-install-success-2026-11-03].
- **Live acquisition passed** after offline extraction refused a
  checksum-invalid `settings.config` fragment on a fresh backup.
  [Refusal][handoff-extraction-refusal-2026-11-03] ·
  [acquisition][handoff-live-acquisition-2026-11-03].

Older events are in the
[history archive](https://github.com/tylxr59/Hearth/tree/history-archive-2026-11/docs/development/history/research).

## Released

**v0.13.1** (experimental) adds value-free sensor-report diagnostics. It does
not fix the reporting fault. Updates use HACS, now the built-in Marketplace
on HA 2026.11.

## What's next

First, deploy the sensor-report diagnostics through HACS and determine why
fresh readings stopped. HA Core restarts need fresh owner approval each time.

The optional hardware steps each need fresh owner approval and a fresh profile:

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

2,021 tests pass, with seven optional skips. Static checks pass. The
network-isolated HA 2026.10.4 sandbox passes 24 native control round trips plus
the onboarding exchange.

What has been measured on hardware is listed in
[what's tested](../technical.md#whats-tested).

[ha-profile-repair-2026-11-03]: https://github.com/tylxr59/Hearth/blob/history-archive-2026-11/docs/development/history/research/ha-profile-repair-2026-11-03.md
[combined-install-success-2026-11-03]: https://github.com/tylxr59/Hearth/blob/history-archive-2026-11/docs/development/history/research/combined-install-success-2026-11-03.md
[handoff-extraction-refusal-2026-11-03]: https://github.com/tylxr59/Hearth/blob/history-archive-2026-11/docs/development/history/research/handoff-extraction-refusal-2026-11-03.md
[handoff-live-acquisition-2026-11-03]: https://github.com/tylxr59/Hearth/blob/history-archive-2026-11/docs/development/history/research/handoff-live-acquisition-2026-11-03.md
[backup-install-handoff-result-2026-11-03]: https://github.com/tylxr59/Hearth/blob/history-archive-2026-11/docs/development/history/research/backup-install-handoff-result-2026-11-03.md
