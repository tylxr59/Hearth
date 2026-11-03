# Current development status

The owner requires a normal setup run from beginning to end, without continuation
commands. The development source removes `--continue-prepared`, `--continue-cleanup`
and the prepared-session module. Published0.10.2 remains immutable. Recovery tools
for a reviewed failed write remain separate from fresh installation.

## Current unit and next hardware step

The Gen2 Display-2.6 remains on primary5.9.4-5. Its HVAC base is wired to actual
oil/baseboard heat; the display is detached on USB. The latest commissioning9
stock-return transaction reported all nine targets restored with no transaction,
rollback, journal, cleanup, unmount or protection errors. Its final readback failed
(diagnostic21, verified0, safe_to_restart0). The command exited. The subsequent audit independently verified the stock
return; the owner confirmed the native home icon and normal Nest USB was
independently observed. The display is charging on USB. No loader is armed.
Cleanup3 never committed or mounted writable.

The fresh preflight-only diagnostic exited0, sealed/protected, with no writes.
It measured RAM free50,913,280 bytes and root0 available13,201,408 against the
copy-based update requirement19,534,505. The root cause is flash space, not RAM.
A saved corrected NAND view contains one old restored network4 archive
(5,822,879 file bytes); all four originals match the earlier preserved host backup.
No archive has been deleted or reused on hardware.

The commissioning-only stock return ran once under explicit owner authorization.
Its failed final result remains unchanged. The subsequent write-disabled audit
exited0: all active original bytes, existence/mode/ownership and NONE encoding
match; exact archive inventory, seven backup fingerprints, two absences and the
restored journal match. Only archived original0 has mixed NONE/ZLIB fragments
(mask65), explaining the strict archive-encoding refusal. No additional flash
write occurred. This independent review clears native restart, while the original
writer remains incomplete. Native on-base stock UI remains unchecked.

The first audit launch refused before any loader/output creation because the
host compared the capsule's named archive layout to an integer. The corrected
mapping is regression-tested; a fresh profile/reproduction/source archive was
used for the single actual audit boot. Both preparations remain private.
Codec reporting does not loosen the production NONE/ZERO acceptance gate;
normal-flow handling of native-recompressed archive originals still needs work.

## Normal-flow storage work

An explicit prototype can share exact existing original inodes into a new
plan-specific rollback archive. It requires a fully restored, plan-named four-file
journal; complete original hashes, ownership/modes/attributes and exact reference
identities/counts. The old archive's bytes, names and journal remain in place.
The candidate staging, intent journal, atomic rename, rollback and NONE/ZERO
audits remain enforced. The ordinary copy-based path is unchanged.

The allocation bound for this mode is replacement staging plus one largest
rollback temporary plus the existing2MiB reserve, because originals already
occupy flash. The ordinary3-times-total reserve and restore largest-plus4MiB
reserve remain unchanged. Twenty additional synthetic shared-original cases cover
identity/tampering refusals, incomplete staging, uncertain renames and restoration;
the same sources compile for ARM. Shared-original hardware writes are unmeasured.

The normal kit now nominates candidates from the checked full-NAND root0 view.
The bounded original parser checks record/data CRCs, versioned directory entries,
restored journal, exact archive names and full original contents. Ambiguous or
unsupported data refuses sharing. A nomination is never permission to reuse:
all native inode/link/ownership/encoding/hash checks still run on the device.

The wizard now runs a no-commit combined-capacity profile before either write.
It reserves all root0 core staging plus128KiB, in addition to the network budget;
core's separate user-config/backup preflight remains enforced. The reservation is
bound into the checked ARM binary. Only exited, sealed, zero-write successful
capacity evidence with matching acquisition custody admits the first writer.
A failure starts neither phase. No user-facing continuation path was reintroduced.

A fresh no-commit shared/capacity profile and matching restore reference are
checked; all ten artifacts reproduce. The extra core reservation is216,202 bytes.
This preparation used existing preserved inputs for a development preflight,
not a completed fresh-user run. No loader was armed and no device attempt occurred.
The next optional hardware step is one owner-ready no-commit preflight of this
path. Shared-original writes, native-recompressed archive handling and the full
stock-to-HA normal wizard remain unverified. Do not advertise them as measured.

The owner is handing repository cleanup to Claude. Leave the Nest in native USB
stock-file state. The extracted download contains development-source updates for
this reviewed preparation, with prior exact source snapshots retained privately;
it is not a pristine published0.10.2 download. Do not rerun old executed profiles.
Private handoff details are in the ignored local handoff note.

## Published delivery and validation

Experimental0.10.2 fixes source-only recovery ZIP creation. Its HACS integration
and installer assets/checksums were downloaded and matched tested source; CI and
hassfest pass, and installed HACS selection methods choose the ordinary release.
The owner's HA entry/bundle were created successfully during the fresh wizard.
No agent HA Core restart or live HA deployment occurred during this storage work.
Use HACS for delivery and obtain fresh approval for another agent Core restart.

The current combined suite passes1,878 tests with five optional skips, including
the enabled pinned BCH checks. Static checks pass. The network-isolated real
HA2026.10.4 sandbox passes24 native control round trips and the separate-process
admin onboarding/address/bundle exchange. Shared/capacity ARM compilation and
fresh private profile reproduction pass; hardware validation is still pending.

Previously measured: local telemetry, targets63→62→63F, Eco on/off, future schedule
entry/readback/empty-week restoration, local weather/time correction, full raw/OOB
archive with matching corrected views and read-only acquisition handoff. Four
matching chunks per NAND pass remain unclassified, with zero uncorrectable chunks.
Selected-file restoration and native UI return have been measured. Whole-chip
restoration, hardware power-loss recovery, intentional heating, cooling/fan and
other models/firmware remain unverified.

The earlier Nov3 legacy stock-return writer's incomplete readback report remains
unchanged: independent snapshots and inode audits verified all active originals,
isolating that old failure to compressed archived copies. Preserve the independent
verification rather than relabelling the original report successful.

Canonical sources remain `backend/`, `custom_components/hearth/`, `installer/`,
`provisioning/`, `firmware/` and `tools/nand_archive/`. See the
[release checklist](roadmap.md); older investigation belongs in [history](history/).
