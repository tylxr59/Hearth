# Current development status

Published experimental0.10.2 fixes a source-only packaging failure exposed by the owner's
fresh0.10.1 installer run: reader builds passed, but the recovery-source snapshot
incorrectly tried to package the HA integration, which is absent from the installer
ZIP. It now snapshots installer inputs independently. An explicit, guarded
`--continue-prepared` accepts only complete unused reader builds after a failed
host prepare; device attempts and write recovery remain excluded. Focused fresh-ZIP
snapshot and continuation refusal tests pass. The owner's HA entry and private
bundle were created successfully; no device loader/write occurred in that session.
The extracted download was updated exactly to published0.10.2, with
original public source preserved privately. Existing reader/ECC integrity checks
still pass. No loader is armed. Full host tests pass1,788 plus the subsequently
added focused continuation test; the isolated real-HA sandbox passes24 control
round trips and admin onboarding. No live HA update/restart was executed. CI passes1,779 tests with15 optional
skips, plus hassfest. Downloaded checksums and every public file match tested
packages; the owner's patched source matches the release, and default HACS
selection chooses v0.10.2.

Published experimental0.10.1 provides the single-entry `python3 provision.py`
setup wizard, mandatory full-NAND archive, guided selected-file restore, HACS
onboarding and optional NTP defaulting to time.nist.gov for both native sources.
Its downloaded46-file integration and343-file installer archive match the tested
contents and published checksums. CI/hassfest pass and the actual installed HACS
selection methods choose v0.10.1 without beta flags. Live HA has not been updated.

## Live owner unit and HA

The owner's Gen2 Display-2.6 remains on primary5.9.4-5. Its base is wired to
actual oil/baseboard HVAC. The display is detached and connected to this PC by
USB. The owner confirmed native home-icon return after the Nov3 stock-file
restoration; normal2464:0002 USB was independently observed. The fresh full-NAND
backup and the read-only file-acquisition handoff have exited successfully in
protected RAM mode. The owner then confirmed native home-icon return, and normal
USB was independently observed again. No loader is armed.
On-base stock UI and physical heating after restoration are not yet measured.

The stock return restored legacy network4 successfully. Core9 reported all511
target bits restored without transaction/cleanup errors, but its final check
failed. Independent protected snapshots subsequently matched every original
byte, existence, mode and owner/group, including absent Hearth library/launcher.
A protected inode audit verified every active stock file. The earlier failure
was isolated to compression of archived rollback copies0,6,8 outside the strict
NONE/ZERO audit. The original incomplete writer result is retained unchanged;
the independent verification and owner native-return evidence remain private.
No additional flash write was needed for that diagnosis.

For clean HA onboarding, the owner removed Hearth's entry; retained profile,
state and manual source were privately archived with exact readback. HACS0.7.1
was downloaded/verified and Core restarted by the owner. No submitted fresh entry
or retained live profile was known at that earlier stage. The subsequent owner
wizard run created a new entry/bundle, as recorded above. Use HACS for further
delivery; obtain fresh
approval before another agent-executed Core restart. Do not manually reinstall
or recreate the old profile. There has been no new HA deployment during backup
work. Whole-chip restoration and hardware power-loss recovery remain unverified.

## 0.10.1 published experimental preview

The0.10.0 release was not published: CI caught a compiler test assuming a
preexisting build directory. Published0.10.1 creates that fixture parent
explicitly; no device code or write gate changed.

The owner requests a full NAND backup before provisioning and a guided recovery
path. The wizard now builds a fresh write-disabled full reader and saves
two complete raw/OOB passes plus two independently ECC-derived data views. It
retains original raw bytes, quality receipts, USB identity and matching public
installer source. Public original BCH source is hash-pinned and built locally;
the GPL-2.0-only offline verifier runs as a separate process, never in HA.

Raw mismatch remains a capture failure classification. Only complete footer-
checked passes may proceed to independent analysis. Corrected views/OOB must
match, uncorrectable chunks stop acceptance, and unclassified chunks must remain
identical and are explicitly not labelled ECC-verified. The verifier reproduces
the historical owner's two matching derived views, including the four retained
unclassified chunks. This is archival evidence, not validated whole-chip recovery.

The full archive is checked before installation and again before commits. An
explicit checked RAM handoff leads into readable-file acquisition, then the
existing disjoint commissioning9/cleanup3 phases. The script's `--restore` menu
checks a saved kit and archive and runs the original selected-file restore;
it does not erase boot flash or guess changed native settings. Exact-restore
refusal on later preferences, interrupted-session review, portable cold recovery
and preservation of current native configuration remain release gaps. Keep the
matching build workspace as well as the private folder/source ZIP.

The first full-reader reproduction exposed only build-time/host metadata drift.
The same exact-source-checked metadata normalization already used by protected
readers now applies; all six artifacts reproduce between fresh full builds. No
NAND-read or write-denial policy was changed. The fresh supervised backup now
passed: both full raw/OOB passes were preserved, independently corrected views
and all OOB bytes match, and neither pass has uncorrectable chunks. Four matching
unclassified chunks per pass remain explicitly not ECC-verified. No flash writes
occurred. The explicit RAM handoff then preserved both fixed snapshots and all
four library groups (134 private files), with no native execution or flash writes.
The process exited successfully; native restart and normal USB return are confirmed.
End-to-end stock
wizard installation remains unmeasured.

## Validation and measured capabilities

The complete host suite passed1,774 tests with five optional skips; focused archive, parity-order, mutation,
permission, cancellation and source-package checks pass. Static/format/security
checks pass. The pinned network-isolated HA2026.10.4 sandbox passes24 native
control round trips and the separate-process admin onboarding/address/bundle
exchange. Public integration and installer-source archives reproduce locally.

Previously measured on the owner's configured installation: authenticated local
telemetry, corrected timezone and weather requests; bounded63→62→63F targets;
Eco on/off with original restored; native schedule acquisition, HA future entry,
revision readback and empty-week restoration; selected-file install/restoration
and native UI return. No intentional heating start/stop, cooling, fan, emergency
heat or other model/firmware support is established by simulations.

Canonical sources are `backend/`, `custom_components/hearth/`, `installer/`,
`provisioning/`, `firmware/` and the standalone offline archive verifier under
`tools/nand_archive/`. Generated HA transport must remain exact. See
[release checklist](roadmap.md) for remaining gates; old investigation belongs
under [history](history/) and `docs/research/`.
