# Hearth contributor instructions

Read [current status](docs/development/status.md) and the relevant source before work.
The historical investigation is archived under `docs/development/history/` and
`docs/research/`; dated preparation notes are not the current project status.

## Scope and live hardware

- Keep the Nest's native HVAC control loops. HA sends bounded settings through
  native subscriptions; do not implement relay or replacement regulation logic.
- Gen2 Display-2.6, primary firmware5.9.4-5 is the measured target. Do not claim
  Gen1, other firmware, cooling, emergency heat or fan operation from simulations.
- The owner's base is wired to actual oil/baseboard HVAC;
  the display is currently detached and charging by USB after the supervised
  installer-reader test. Last on-base state was Heat63F, Ecooff, empty schedule,
  owner-confirmed heating idle. The Nov3 stock return restored network4 successfully.
  Core9 reported restored511 with no transaction errors, but final readback failed
  (verified0, safe_to_restart0, diagnostic21). It is exited in protected/sealed RAM
  mode. Protected snapshots and an inode encoding audit subsequently verified all
  active stock files and metadata; the old failure came from compressed archived
  rollback copies0,6,8. The incomplete writer result remains unchanged. The owner
  has now confirmed the native home icon and normal USB was independently observed.
  The display is again connected to this PC by USB with its HVAC base detached.
  On-base stock UI has not yet been checked. No extra flash write was needed.
  The fresh full-NAND archive passed both raw/OOB passes and offline quality
  checks; corrected data/OOB match with no uncorrectable chunks, while four
  matching chunks per pass remain unclassified. The capture process exited0,
  and the reviewed read-only handoff also exited0, preserving both snapshots and
  four library groups (134 private files) without writes/native execution. The
  owner confirmed native home-icon return afterward and normal USB was observed.
  The display remains detached and charging by USB.
  No loader is armed. Do not assume an unwired
  base when it is reattached.
- For the owner-authorized clean onboarding test, the owner removed the Hearth
  entry through HA. Retained profile/state and the manual integration copy are
  privately archived with exact readback; the live profile is absent and the
  native listener is stopped. One owner-authorized0.7.0 activation/Core restart
  completed before the manual copy was archived for a genuine HACS install test.
  HACS is configured and Hearth is registered. Its first download failed because
  the v0.7.0 GitHub prerelease was skipped and HACS requested a ZIP at a commit
  hash. Published v0.7.1 is an ordinary GitHub release with experimental metadata;
  actual installed HACS selection methods now choose that tag without beta flags.
  Downloaded assets match checksums/tested source. The owner now successfully
  downloaded0.7.1 through HACS; all44 installed source files independently match
  the published ZIP. The owner restarted Core and reached its fresh setup form,
  then requested automatic address/identity entry. No submitted Hearth entry or
  retained profile is known yet. Published0.8.1 adds HA-interface suggestions and
  the PC-side USB-to-HA onboarding command. Its46-file published ZIP and source
  archive match the tested inputs, and normal HACS selection chooses v0.8.1.
  Published0.9.1 adds the single-entry provisioning wizard and configurable
  primary/fallback NTP (default time.nist.gov). Its downloaded46-file integration
  and327-file installer archive match tested contents and published checksums;
  CI and hassfest pass. The complete stock-device wizard/cleanup3/custom-time
  hardware install and restore remain unmeasured. No new live entry, HA update,
  Core restart or device write occurred during the backup implementation. The
  Published0.10.1 adds mandatory full-NAND archiving and guided selected-file
  restore. Fresh full read, offline verification, read-only acquisition handoff
  and native restart passed. All46 integration and343 installer files match the
  tested source and published checksums; CI/hassfest pass and default HACS
  selection chooses v0.10.1. No live HA update occurred. The
  selected-file stock return is independently verified as described above;
  do not bypass restore refusals or blindly erase NAND.
  The live HA instance has not been updated; use HACS for delivery. Obtain
  fresh approval before executing another Core restart. Do not recreate the old
  profile or manually deploy over the HACS test.
  Subsequent owner-run0.10.1 onboarding has now created a fresh HA entry and
  matching private bundle (local create_entry receipt verified). Its host prepare
  failed only at source archiving after both reader builds; no device attempt
  occurred. The extracted download was updated in place to the checked0.10.2
  release with original source preserved. Existing profiles still validate.
  Published0.10.2 and the patched download match every tested public file; CI
  and hassfest pass, and default HACS selection chooses v0.10.2.
  The owner may use the explicit pre-device continuation; do not rerun failed
  hardware attempts or recreate this HA entry. No agent Core restart occurred.
- The owner's continued public wizard has since installed/verified commissioning9.
  Cleanup3 refused resource preflight (diagnostic40) before commit or writable
  mounts, with zero program/erase/marker activity; it exited sealed/protected
  and safe_to_restart1. The first phase remains installed, USB RAM mode is
  retained and the HVAC base remains detached. Do not rerun attempted phases.
  Fresh preflight-only resource images are prepared/reproduced but not executed;
  obtain owner readiness before arming. Original reports and source are retained.
- The owner authorizes local implementation, docs, packaging, tests and commits/
  pushes. The current public-product work does not authorize another HA Core
  restart, a new persistent device write or an intentional HVAC call.
- Before a persistent device write, explain its concrete scope and recovery
  limits. Obtain owner readiness before arming any ROM loader. Use a PTY,
  one owner-timed boot, no automatic retry, and a fresh private output/profile.
- For physical controls, obtain a concrete supervised test first and restore the
  saved original. Never infer equipment support from missing reported flags.
- Recovery of selected files has been measured. Whole-firmware restoration and
  hardware power-loss recovery remain unverified. No spare is mandatory: the
  owner accepted same-unit investigation and one local recovery archive.

## Source, privacy and release

- `backend/` is the canonical native transport. `_backend/` inside the HA
  integration is generated by `python -m tools.sync_integration`; never hand-edit.
  `python -m tools.sync_integration --check` enforces exact correspondence.
- Keep all runtime HA files inside `custom_components/hearth/`. HACS distributes
  the native integration; do not revive the retired laboratory app.
- NLE is a pinned protocol/behavior reference. Write original implementations;
  record behavioral sources and licensing. Do not copy proprietary firmware or
  present reference-code confidence as hardware validation.
- Keep identifiers, credentials, IP topology, native bytes, binary hashes,
  proprietary libraries and per-device kits under ignored `private/`/`build/`.
  Never publish a user's commissioning bundle, private key or restore capsule.
- Preserve executed profiles, manifests, results and backup evidence. Never rerun
  an executed install/restore image or old HA control action.
- Strip photo metadata before publishing images. Keep user documentation free of
  obsolete deployment paths; retain essential research under development docs.
- Read the detected target OS before package/service commands. No new system
  packages or host services without task authorization.

## Validation

Use `make test`, `make check` and the pinned network-isolated real HA sandbox:
`python -m tools.check_native_ha build/<fresh-name> --engine podman`.
Firmware changes additionally require the existing bounded source/ABI/RAM/backup
checks appropriate to that writer. Never remove gates to make an installer pass.
Run `python build/review-source-push-20261030.py` when available before pushing;
release artifacts must contain public original source only. Do not create a
stable v1 tag or advertise a turnkey stock-device installer while its acquisition/
build path or hardware validation is incomplete.
