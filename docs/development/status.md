# Current development status

Published experimental0.9.1 provides the single-entry `python3 provision.py`
wizard and the optional NTP choice (default time.nist.gov), applied to both native
time sources. Its release gates passed:1,709 CI tests passed,13 optional/platform
tests skipped, and hassfest reported zero invalid integrations. Downloaded assets
have verified published checksums; all46 integration files and327 installer-source
files match the locally tested contents. Compressed ZIP bytes vary across zlib
versions; both local and CI builds reproduce independently. The full combined
stock-device wizard/custom-NTP install and restore remain unmeasured. No live HA
or thermostat changes were made. The owner's stock-return request is still pending.

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
files independently match the published ZIP. The owner restarted Core and reached
the fresh setup form, then requested automatic endpoint/identity entry. Its entry
has not been submitted. Published0.8.1 adds HA-interface suggestions plus a PC-side
onboard command: read a single native USB identity, choose a thermostat-reachable
HA address, create the entry through HA's admin API and save the matched private
bundle. The full real-HA sandbox passes both the24 control round trips and the
new separate-process REST onboarding/bundle exchange. The owner still needs to
test0.8.1 through HACS and this public command. The first0.8.0 tag's release was
cancelled before publication after hassfest rejected a literal URL in translated
help text. The corrected description uses a placeholder; the pinned validator now
reports zero invalid integrations. Publication now depends on hassfest as well
as checked packaging. The0.8.1 release passed both gates; its46-file HACS ZIP and
installer-source archive match the tested source and published checksums. Normal
HACS release selection chooses v0.8.1 without beta flags. The owner has not yet
installed or tested it. No thermostat reset or write
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
is armed. Latest complete host suite:1,642 passed, five optional skips. Static,
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

The next source preview adds `python3 provision.py` as the single guided entry:
HACS instructions, USB identity, HA entry/bundle, protected acquisition, private
kit assembly, two separately confirmed writes and an owner-verified live-reading
check. Long operations run in a PTY with private logs and bounded engine timeouts;
Ctrl-C does not kill an active writer. A narrowly scoped current-UID USB rule is
optional and explicitly confirmed. System dependencies are checked, not installed.
The time-server prompt defaults to time.nist.gov; a new separately pinned cleanup3
format permits a bounded variable-length fallback hostname/IPv4 alongside the
primary NTP update. Legacy equal-width3/4 plans retain their original format.
The custom-time adapter permits a length change only for target2, preserves full
original/candidate hashes and retains original-file, resource and recovery gates.
Neither the combined wizard nor the custom-time/cleanup3 path has run on hardware.
The owner's requested stock return remains pending; this work performs no live
write, reset, HA profile recreation or Core restart.

Wizard validation: the complete host suite passes1,710 tests (five optional skips),
with additional focused USB-rule and packaged-launch checks passing afterward.
Static/format/security checks pass. The pinned network-isolated real HA2026.10.4
sandbox passes24 native control round trips and the separate-process admin setup,
address-suggestion and private-bundle exchange. Public integration and installer
archives reproduce. Live owner HA is unchanged; this is source/release work only.

The0.9.0 release run was cancelled before publication during final USB-rule review.
The corrected wizard pins udev's root-executed ACL helper to the root-managed
/usr/bin/setfacl, refusing symlinks or writable/non-root-owned executables.
It never embeds a helper selected from a user-controlled PATH in a root rule.

Stock return preparation now builds fresh network4 and original core9 restore
images. A restore-only admission binds the exact later native settings observation
through independent acquisition custody, both old plans and the legacy client-file
overlap. Unknown bytes still fail; original backups/journals and all other file
checks remain required. RAM recovery cases additionally exercise this admission.
Both fresh images reproduce offline. No loader or write has run during preparation.
The owner's additional request is to integrate a guided backup/restore path into
provisioning. Selected-file recovery can be carried into that UI; a full NAND copy
must not be described as a tested boot-critical/full-chip restoration procedure.

Stock-return offline validation:1,738 host tests pass with five optional skips;
static checks and the pinned real HA sandbox pass (24 native round trips plus
admin onboarding). Both fresh core/network restore profiles pass the full check
and reproduce every artifact. They remain unused, with no loader armed.

On-device stock return: network4 restored and verified. Core9 passed72 RAM checks
and exact preflight, then reported restored511 with no transaction/cleanup errors.
Its final readback failed (verified0, safe_to_restart0, diagnostic21); gate is
sealed/protected and command exited. Keep the display in powered RAM mode; do not
start native firmware. A fresh protected read-only diagnostic is prepared, with
20 focused tests and all eight artifacts reproduced. Its explicit RAM entry
requires the exact exited sealed failure and checked prior custody. No diagnostic
loader is armed yet.

The owner requests full NAND backup as the pre-install recovery archive. Planned
provisioning must preserve raw data/OOB, ECC and bad-block metadata plus validated
readable originals. A capture alone does not validate full-chip restoration;
routine recovery should remain scoped until boot-critical restoration is measured.

The protected post-restore capture completed without writes. All nine targets
match original bytes/existence/modes/ownership exactly, including absent Hearth
library/launcher. Final encoding verification is being isolated with a new
write-disabled parent kernel plus only the existing read-only inode ioctl. Its
fixed static supervisor reports selected-file and legacy-archive encoding codes
separately and re-captures originals.29 focused tests pass; all eight artifacts
reproduce. No native boot or further write is authorized automatically.

The protected encoding audit passes the complete host suite:1,755 passed, five
optional skips. Formatting/static/security checks pass. Both encoded profiles
retain the protected parent's write-denying callbacks/configuration and reproduce
all eight artifacts; the single ioctl extension is checked against original
source. Neither encoding profile has run; owner readiness is required next.
