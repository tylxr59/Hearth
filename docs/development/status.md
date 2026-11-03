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
(diagnostic21, verified0, safe_to_restart0). The command exited; the display remains
in sealed/protected RAM. Do not restart until independent read-only evidence
resolves that failure. No loader is armed. Cleanup3 never committed or mounted
writable.

The fresh preflight-only diagnostic exited0, sealed/protected, with no writes.
It measured RAM free50,913,280 bytes and root0 available13,201,408 against the
copy-based update requirement19,534,505. The root cause is flash space, not RAM.
A saved corrected NAND view contains one old restored network4 archive
(5,822,879 file bytes); all four originals match the earlier preserved host backup.
No archive has been deleted or reused on hardware.

The commissioning-only stock return ran once under explicit owner authorization.
Its failed final result remains unchanged. A fresh write-disabled audit is
prepared and reproduces: it captures the nine active files, inventories their
compression codecs and the exact plan-named archive, and fingerprints the saved
originals/journal. Codec reporting does not loosen the NONE/ZERO acceptance gate.
The audit admits only the checked, exited, sealed restore state. Obtain fresh
owner readiness before arming its one ROM boot; no further write is authorized.

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

Normal-wizard archive discovery and a combined capacity check before the first
write are still pending. Do not ask the owner to continue a partial installation
or advertise the complete stock-device flow as verified. After the checked stock
return, finish that integration and test the normal wizard with fresh profiles.

## Published delivery and validation

Experimental0.10.2 fixes source-only recovery ZIP creation. Its HACS integration
and installer assets/checksums were downloaded and matched tested source; CI and
hassfest pass, and installed HACS selection methods choose the ordinary release.
The owner's HA entry/bundle were created successfully during the fresh wizard.
No agent HA Core restart or live HA deployment occurred during this storage work.
Use HACS for delivery and obtain fresh approval for another agent Core restart.

The combined development suite passes1,816 tests with seven optional skips;
the separately enabled pinned BCH checks pass16 tests, covering the two optional
BCH skips. All26 focused encoding-audit/startup checks and static checks pass. The network-isolated real HA2026.10.4 sandbox passes24 native control round
trips and the separate-process admin onboarding/address/bundle exchange.

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
