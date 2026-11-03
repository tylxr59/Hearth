# Release checklist

Hearth stays on `0.x` experimental releases until every box below is checked.
`tools/public_release.py` enforces the version rule.

## Before stable v1

### Hardware validation

- [ ] Supervised heating start/stop with the equipment identified, and native
      operating-action feedback in HA (needs separate owner authorisation).
- [ ] Local operation through HA/network outages, reconnects and reboots, with
      no command replay.
- [ ] A real timed schedule transition, and sustained multi-day operation.
- [ ] Each new setting type's bounds and acknowledgement on supported firmware.
- [ ] Outdoor weather rendering on the Nest, and behaviour when the provider is
      unavailable.

### Installer

- [ ] Measure the lowered space margins (shared install 1.25 MiB, restore
      1 MiB) on hardware, including a guided restore after install.
- [ ] Recover flash space: write native-supported ZLIB instead of NONE (never
      LZO), with writer-kernel and encoding-audit changes and a measurement.
- [ ] Fewer ring presses. Today: backup, originals, space check, phase 1,
      phase 2, then a final restart is six presses. Options, best first:
      (1) a supervised test of whether a software reset from the RAM kernel
      re-enters ROM USB boot without the ring; (2) derive originals from the
      NAND backup offline (device preflight still verifies exact bytes);
      (3) fold the space check into phase 1's preflight; (4) one writer boot for
      both phases.
- [ ] Run the complete source-built wizard on a **pristine stock** unit: full
      backup, both install phases, HA readings, then the full restore. (The offline
      composed build and profile reproduction already pass.)
- [ ] Measure a passing combined capacity preflight and shared-original writes
      on hardware (a refusal by 30 KB was measured on 2026-11-03).
- [ ] Handle natively recompressed archive originals without loosening the
      NONE/ZERO gate.
- [ ] Support USB ports other than the measured **1-1**, through scoped rules
      only.
- [ ] An uninstall that preserves the current native configuration. Exact
      initial-settings restore must keep refusing unknown edits.
- [ ] Restore that works without the original build folder (portable
      cold rebuild).
- [ ] Exercise install and restore on more supported Linux hosts.

### Security and release

- [ ] Review legacy native endpoints, logging, trust/clock renewal, dependencies
      and resource limits, then publish residual risks and tested compatibility.
- [ ] HACS custom-repository install, update and onboarding on a clean HA system.
- [ ] Release artifacts, licensing, reproducibility, hassfest and privacy checks.

## Beyond v1

Cooling, fan, emergency heat and temperature ranges need suitable equipment.
Gen 1, Gen 3 and other firmware each need their own measured install and
recovery profiles. Never infer those from Gen 2 heating results.
