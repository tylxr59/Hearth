# Current status

_Last updated 2026-11-03. Keep this page short and current. Dated detail goes
in [history](history/), and lasting facts go in [findings](findings.md)._

## Device state right now

| | |
| --- | --- |
| Unit | Gen 2, Display-2.6, primary firmware 5.9.4-5 (the only measured target) |
| Where it is | Display **reattached to the wired base** by the owner after the verified install. Normal temperature dial and fresh HA readings confirmed by the owner and read-only HA observation |
| HVAC base | **Wired to real oil/baseboard heat.** Never assume an unwired base when it's reattached |
| Last on-base state | Heat 63 °F, Eco off, empty schedule, heating idle (owner confirmed) |
| Loader | Combined loader completed; host exited; no loader armed |
| Flash contents | Commissioning9 and cleanup3 installed; both readback and encoding verified. Recovery archives retained |
| On-base UI | Normal dial confirmed after installation; no intentional HVAC test performed |

**Authorised now:** local code, docs, packaging, tests, commits and pushes.
**Not authorised:** HA Core restarts, persistent device writes, arming a loader,
or intentional HVAC calls. Each needs fresh owner approval.

## Local provisioning work (unreleased)

The capacity check and both install phases **passed in one RAM boot** with
separate owner write approvals. Both groups passed readback and encoding audits;
the host exited and the final report says safe to restart. Native USB returned after the normal restart, detached on USB. HA checks confirmed a missing entry and active profile. The owner approved
restoring an exact matching saved profile unchanged and registering its entry.
HA now reports loaded; its live bundle matches this Nest and native TLS passes
from the HA network. After owner-approved reattachment, HA received fresh
temperature/humidity with no authentication rejections or pending control
intents. The owner confirmed the normal dial and HA readings. See the [combined result](history/research/combined-install-success-2026-11-03.md).

Automatic backup-to-successor transfer without a ring press was measured in an
earlier attempt; its supervisor failed before readiness and was corrected.
Archive extraction passed on the first fresh archive, but later refused a
checksum-invalid settings fragment despite valid duplicates. This successful
install used a separate protected live acquisition and a manual combined boot.
The complete reduced-boot wizard path is not yet measured end to end. No safety
gate was weakened. The existing commissioning bundle and all archives are
preserved. Bundle matching did not establish that the HA entry still exists.

Follow-up host changes (unmeasured on hardware; no device action):

- If offline extraction refuses before creating output, the wizard records the
  refusal and offers the existing protected live reader (one owner-confirmed
  ring boot). The install then uses the measured manual combined boot. A
  refusal after output exists is not treated as a fallback.
- Before any one-use marker, the combined install checks read-only that the
  backup reader still sends its exact readiness line. A silent reader asks the
  owner whether to check again and otherwise stops as "not started", with the kit
  unused. This adds a second host open of the reader tty; the device side is
  unchanged.
- Wizard results now distinguish an owner cancel with zero writes, a safe
  partial install (commissioning verified, cleanup cancelled) and an unknown
  failure. Restore reports "nothing to restore" when a combined kit never sent a
  write and no standalone attempt evidence exists.

## Last hardware events (newest first)

- **On-base return and HA readings confirmed:** after explicit owner approval,
  the matching saved HA profile was restored and its missing entry registered.
  The owner reattached the display and confirmed the normal dial and readings.
  Read-only HA observation confirmed fresh temperature/humidity and device
  availability, with no authentication rejections or pending control intents.
  No HA Core restart or intentional HVAC call. See the
  [repair and final check](history/research/ha-profile-repair-2026-11-03.md).

- **Combined install passed:** capacity passed with zero writes, then both
  separately approved file groups completed in the same RAM boot. Each reported
  complete/readback/encoding/safe-to-restart success, zero transaction errors
  and zero failed NAND operations. No restore or HVAC action was run. See the
  [result](history/research/combined-install-success-2026-11-03.md).

- **Live acquisition passed:** one fresh owner-approved read-only boot captured
  both fixed snapshots and four library groups (134 private files). Fresh
  combined kit and standalone restores built and checked. Existing HA entry
  preserved. This supplied the subsequent successful combined install. See the
  [result](history/research/handoff-live-acquisition-2026-11-03.md).

- **Backup accepted, extraction refused:** a new fresh two-pass capture passed
  corrected-data, spare-area and ECC quality gates. The offline original-file
  extractor refused a checksum-invalid `settings.config` fragment despite
  valid duplicate fragments. No handoff or write followed. A separate fresh
  protected live acquisition subsequently passed. See the [result](history/research/handoff-extraction-refusal-2026-11-03.md).

- **Fresh backup refused:** both passes completed, corrected data matched and
  neither pass had uncorrectable chunks, but one bit differed in one ECC spare
  byte. The exact-OOB gate refused. No extraction, successor loader, restart
  token or installer write followed. Evidence is preserved; no automatic retry.
  The corrected supervisor subsequently passed in a fresh combined install. See the
  [refusal](history/research/handoff-backup-refusal-2026-11-03.md).

- **Backup-to-install handoff:** fresh two-pass archive accepted; originals
  extracted offline; software restart and successor transfer completed without
  another ring press. Supervisor timed out before capacity selftest or either
  write decision. The legacy kernel rejects rootfs bind mounts. RAM hardlinks
  and renames replace them; no flash policy was changed. Original evidence is
  preserved, with no retry. See the [result](history/research/backup-install-handoff-result-2026-11-03.md).

- **Warm restart reached ROM:** one fresh owner-approved PTY boot, exact RAM
  readiness, one software restart, ROM then native USB confirmed by the host
  journal. No successor loader, installer write, HVAC call or retry. Host exited;
  originals and the serial-cleanup error remain preserved. See the
  [result](history/research/rom-warm-restart-success-2026-11-03.md).

- **Warm-restart test load:** one approved PTY boot, transfer complete, then
  readiness timeout. No restart token or intentional write. Host exited; USB
  was still in protected RAM mode at that point. See [attempt and correction](history/research/rom-warm-restart-attempt-2026-11-03.md).

0. **v0.11.1 public wizard run.** Steps 1–5 passed: HA onboarding, reader build,
   full-NAND backup, acquisition and kit with a shared-original nomination. The
   combined capacity preflight refused by **30,373 bytes** (13,217,792
   available against 13,248,165 required, diagnostic 42), with zero writes.
   Analysis and the margin change (shared install 2 → 1.25 MiB, restore
   4 → 1 MiB) are in
   [capacity-preflight-result](history/research/capacity-preflight-result-2026-11-03.md).
   That session's HA entry exists and is preserved by reusing its matching
   current commissioning bundle; do not recreate it.
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

All attempted profiles remain single-use evidence. Fresh standalone restore
profiles are checked but unexecuted. Do not start a restore without explicit
scope/recovery approval and fresh loader readiness.

**Unmeasured:** combined guided restore, handling of native-recompressed archive
originals, the complete reduced-boot stock-to-HA wizard, whole-firmware recovery,
and power-loss recovery.

## Published

**v0.12.0** (experimental) ships the combined install: one RAM boot runs the
space check and both file groups, with a separate `INSTALL` for each write.
The wizard saves originals from the verified backup and restarts the Nest
from the backup reader into the install without another ring press. If that
extraction refuses, it offers the protected live reader followed by a manual
combined boot. That fallback route is the one measured on hardware. The
automatic backup-to-install route has **not** run end to end. The release also
adds the read-only readiness check before a kit is consumed, per-group stop
messages and "nothing to restore". The HA integration is unchanged apart from
its version.

**v0.11.2** lowers the JFFS2 space margins from measured overhead (shared
install 1.25 MiB, restore 1 MiB). It explains a zero-write space refusal with
its numbers and a safe-restart message. The margins are not yet measured on
hardware.

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

1,975 tests pass, with seven optional skips. Static checks pass. The
network-isolated HA 2026.10.4 sandbox passes 24 native control round trips plus
the onboarding exchange. Shared/capacity ARM compilation and private profile
reproduction pass.

What has been measured on hardware and what hasn't is listed in
[compatibility](../compatibility.md). Open release gates are in the
[roadmap](roadmap.md).
