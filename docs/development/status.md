# Current development status

The owner installation last ran configured HA0.6.9 with a Gen2 Display-2.6 on primary5.9.4-5.
For the clean onboarding test, the owner removed the Hearth entry through HA;
its retained profile/state was archived with exact readback and the live profile
path is absent. The native listener stopped. One authorized HA0.7.0 activation
and Core restart completed, then its manual source copy was archived so the owner
can test a genuine HACS download. No manual source/profile remains in the live
paths. The first HACS download failed: GitHub prerelease filtering skipped0.7.0,
so HACS requested the ZIP asset at a development commit. The packaging-only0.7.1
fix is published as an ordinary GitHub release, retaining experimental status.
Actual installed HACS filtering/selection methods now select v0.7.1 without beta
flags; both downloaded archives match the tested source and published checksums.
The owner successfully downloaded0.7.1 through HACS, and all44 installed source
files independently match the published ZIP. The entry/profile are still absent;
a separate Core restart and fresh onboarding measurement are next. No thermostat reset or write
occurred during this cleanup. The integration uses native HTTPS directly inside
HA Core. The latest confirmed physical state
is Heat63F, manual Ecooff, empty schedule, heating idle. The equipment is described
as oil/baseboard; exact boiler/furnace arrangement remains unverified.

Measured on the real unit:

- Authenticated local telemetry, corrected timezone, local weather requests.
- Single-target63→62→63F cycles, with matching physical/HA acknowledged display.
- Manual Eco on/off confirmed by fresh native mode, unchanged limits, restored off.
- Native week acquisition, HA future point, exact values/revision readback,
  post-write metadata acknowledgement, private backups and original empty restore.
- Selected-file install/readback/restoration and native UI return. Whole-chip
  recovery, hardware power loss and intentional HVAC switching are not measured.

The0.7 preview adds the remaining device settings, public HA setup, HACS layout,
release packaging and guided install/restore. Its configured owner runtime has
not yet been tested through HACS.
The real HA2026.10.4 sandbox passes24 control round trips, including learning/
Early-On restoration, new profile generation and private-key export exclusion.
Hassfest validates the self-contained integration with zero errors. Optional native
diagnostics include voltage, RSSI, filter, outdoor and native activity fields.
The guided writer consumes separately prepared device-bound install/restore
profiles. Pinned source fetching, isolated reader compilation and consolidated
read-only acquisition now have public CLI commands. The fresh source-to-reader
build passes offline and eight reader artifacts reproduce. The rebuilt boot
chain and corrected top-level reader passed a supervised read-only boot: both
snapshots, all four groups,136 private files and the complete34-library closure
validate, with owner-confirmed UI and independently observed native USB return.
This was the already-commissioned owner unit, not a pristine stock install.
Per-unit replacement construction and two-phase write-kit assembly now build
end-to-end offline. A composed replay of preserved originals and acquired libraries
produced four checked profiles; their34 artifacts reproduce against the same
compiled kernels. The replay is explicitly marked review-only and cannot open USB
through the guided workflow. It is not a pristine-stock hardware installation.

The display is now detached from its HVAC base and charging by USB. No loader
is armed. Latest complete host suite:1,619 passed, five optional skips. Static,
formatting and security checks pass. Release archives reproduce; the extracted
installer includes all recipe inputs and its CLI starts independently.

Further offline kit work adds the disjoint three-file network cleanup format,
keeping client configuration exclusively in the nine-file commissioning phase.
Both legacy4 and cleanup3 pass host fault/restore checks; cleanup3 has not run
on hardware. Packaging resolves its libc/interpreter directly from verified
acquisition. The public GNU shim build exactly matches the installed owner copy.
The guarded original TLS recipe also reproduces the installed reviewed candidate.
Source contains only original parsing/instruction logic and synthetic fixtures.

The guided kit coordinates acquisition-to-install RAM handoff, commissioning9,
cleanup3 and reverse-order restoration, retaining separate owner confirmations.
Unknown or incomplete prior evidence stops the next phase. Expired HA leaf
metadata does not block restoring originals. Existing/partial Hearth units are
refused by the stock builder; unknown later native settings stop exact restoration.
Portable USB permissions, a configuration-preserving uninstall and complete stock
install/restore hardware measurement remain public-release gaps.

Canonical sources: `backend/`, `custom_components/hearth/`, `installer/`,
`provisioning/`, `firmware/`. Generated HA transport is checked for exact equality.
Keep the final hardware and release checklist in [roadmap](roadmap.md).
Historical evidence and old experiments are archived in [history](history/).
