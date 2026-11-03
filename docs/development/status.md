# Current status

_Last updated 2026-11-03. Keep this page short and current. Dated detail goes
in [history](history/), and lasting facts go in [findings](findings.md)._

## Device state right now

| | |
| --- | --- |
| Unit | Gen 2, Display-2.6, primary firmware 5.9.4-5 (the only measured target) |
| Where it is | Display **detached**, on USB to the dev PC, charging, in **native (stock UI) mode** |
| HVAC base | **Wired to real oil/baseboard heat.** Never assume an unwired base when it's reattached |
| Last on-base state | Heat 63 °F, Eco off, empty schedule, heating idle (owner confirmed) |
| Loader | **None armed** |
| Flash contents | Stock files, independently verified (see below). Native home icon and normal USB confirmed |
| On-base stock UI | Not yet re-checked |

**Authorised now:** local code, docs, packaging, tests, commits and pushes.
**Not authorised:** HA Core restarts, persistent device writes, arming a loader,
or intentional HVAC calls. Each needs fresh owner approval.

## Last hardware events (newest first)

1. **Commissioning-only stock return** (after step 3) ran once. All nine files
   were restored (restored mask 511) with zero transaction, rollback, journal or
   seal errors, but its own final verify failed (diagnostic 21: `verified 0`,
   `safe_to_restart 0`). **Preserve that result unchanged.** A separate
   read-only audit then verified every active original's bytes, metadata and
   NONE encoding. The refusal came from archived rollback original 0, which
   contains mixed NONE/ZLIB fragments (mask 65). No extra write was needed.
   Independent review cleared the native restart.
2. **Cleanup3 resource preflight** refused before commit (diagnostic 40). A
   follow-up no-write diagnostic measured refusal 42: 13,201,408 bytes available
   on root0 against 19,534,505 required. The cause is flash space, not RAM.
   There was zero program/erase activity.
3. **Commissioning9** installed and verified through the public wizard.
4. A fresh **full-NAND archive** passed both raw/OOB passes and offline checks,
   with zero uncorrectable chunks and four matching-but-unclassified chunks per
   pass. One old restored network4 rollback archive (5,822,879 bytes) remains on
   flash. Its four originals match the host backups, and deleting it is **not**
   authorised.
5. An **earlier legacy stock return** (network4 + core9) had the same kind of
   failure: its final readback failed with diagnostic 21, while independent
   audits verified all active files. That failure came from compressed archived
   copies 0, 6 and 8. Its report also stays unchanged.

Do not re-run any attempted phase or executed profile. Original reports, profiles
and source snapshots are kept under `private/`. The ignored local handoff note
has private detail.

## Recent development (released in v0.11.0)

- **Combined capacity preflight.** The wizard runs a no-commit space check
  covering both phases before either write. Only an exited, sealed, zero-write
  success unlocks phase 1.
- **Shared-original rollback.** Hardlinks exact existing original inodes from a
  restored old archive instead of copying them, which cuts the space needed to
  staging + largest temp + 2 MiB. This is nominated from the checked NAND
  view, and all device-side checks still run.
- **Continuation commands removed.** Setup is one normal run from start to
  finish.
- **Friendlier wizard output.** `installer/ui.py` was added for formatted steps,
  prompts and summaries.

A fresh shared/capacity preflight profile and its restore reference are
prepared and reproduce (10 artifacts), but they have **not been executed**. The
next optional hardware step is one owner-ready, no-commit run of that preflight.

**Unmeasured:** shared-original writes, handling of native-recompressed archive
originals, the cleanup3 writer, the custom-NTP writer and the full
stock-to-HA wizard.

## Published

**v0.11.1** fixes a v0.11.0 wizard crash: the step 3 backup crashed as soon as
the loader started waiting, before anything reached the Nest. It also adds a
live staged status line, drains worker output after errors, records unexpected
errors and closes HA dialogs left open by refusals.

**v0.11.0** (experimental, ordinary GitHub release, so the HACS default picks
it) is the first release with:

- the combined capacity preflight and shared-original rollback;
- the formatted wizard;
- the computed `hearth-nest-installer.zip` (renamed from
  `hearth-installer-source.zip`);
- HA-sized brand icons.

The owner plans a start-to-end test of it on their own HA and Nest. Until that
test reports back, everything under "Unmeasured" above stays unmeasured.

v0.10.2 is the previous release. The owner's v0.10.1 onboarding created an HA
entry and a matching private bundle. Don't recreate that entry or the old
profile yourself, and don't deploy over the HACS install by hand. Deliver
through HACS only.

## Validation snapshot

About 1,900 tests pass, with five optional skips. Static checks pass. The
network-isolated HA 2026.10.4 sandbox passes 24 native control round trips plus
the onboarding exchange. Shared/capacity ARM compilation and private profile
reproduction pass.

What has been measured on hardware and what hasn't is listed in
[compatibility](../compatibility.md). Open release gates are in the
[roadmap](roadmap.md).
