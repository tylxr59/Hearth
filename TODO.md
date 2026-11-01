# Outstanding work

Release-blocking:

- Identity intake and authorized ROM enumeration complete: enclosure `02A`, reported `Display-2.6`, firmware `5.9.4-5`, normal USB `2464:0002`, brief OMAP `0451:d00e` during restart; see docs/research/device-intake-2026-10-30.md. Obtain base/board identity and reviewed Gen 2 firmware acquisition/MTD/boot/recovery evidence. A later diagnostic RAM heartbeat boot succeeded; no firmware was acquired. Actual nlclient/osm now exist privately after full raw capture and offline ECC/JFFS2 reconstruction; static inspection of their usable interfaces remains next.
- Native static review traced D-Bus methods to power/sniffer/heartbeat and identified a loopback test-access temperature getter/setter candidate. Ghidra supports dormant startup (zero initializer/thread refs); units and TCP framing also remain unverified. No activation patch or production bridge. ADR remains provisional; no bridge is enabled. See docs/research/native-interface-2026-10-30.md.
- Native TLS review found overrides for not-yet-valid certificates and selected CRL failures. The private default-callback candidate is now measured in the 18-case device-loopback harness but remains uninstalled; require full native fetch/effective-trust configuration, fresh owner CA/CRL and trusted operational-time bootstrap tests. Unique stock-client credential/bootstrap installation and rollback remain open. No plaintext production fallback. See docs/research/native-tls-2026-10-30.md.
- Native bootstrap review confirms assigned-setting reads, response-header rotation and assigned-to-default fallback on 401. The update helper logs new credentials; a private logging-removal candidate is statically checked but uninstalled. Storage follow-up finds entry-write failures that log key/value without reaching the outer writer result, plus dirty clearing after directory-sync failure. The earlier client candidate does not fix these library paths. Offline staging now disables the traced uploadlogs sender; storage fault propagation/retry and a complete log/outbound audit remain commissioning blockers. See docs/research/native-storage-2026-10-30.md. Host regressions reject native-looking/default claims and inbound-header rotation. See docs/research/native-bootstrap-2026-10-30.md.
- Second supervised TLS RAM run completed all 18 expected cases with native curl/OpenSSL and original/candidate hooks. Candidate accepts valid and rejects all eight invalid cases; native home icon and normal USB returned after a full timed restart. No persistent install, full native fetch/config, time bootstrap, recovery or HVAC claim. Preserve both private attempts. See docs/research/tls-probe-result-2026-10-30.md.
- The corrected settings RAM diagnostic completed all twelve cases and returned to native startup. It confirms silent entry loss/invalid XML on write failure and skipped retry after directory-sync failure. After four preserved startup failures, the exact GNU-linked correction passed all 29 synthetic RAM comparison cases with native USB return. Full native application integration, derived callback behavior, credential-pair transactions and other log paths remain open; no persistent installation exists. See docs/research/settings-compat-result-2026-10-31.md. These are synthetic RAM results, not flash durability, power loss or real commissioning. See docs/research/settings-probe-result-2026-10-31.md.
- Implement/validate full native entry, pairing and revision/CAS/chunked subscribe transport, with power/schedule regression fixtures, or replace it with a verified local bridge. Experimental decoder is incomplete and default-disabled.
- Build a revision-specific deployable firmware image and complete service hardening profile. Deployment artifacts remain inert review bundles and partial offline replacements; the separate experimental RAM probe is diagnostic boot code only.
- Diagnostic RAM heartbeat boot and native startup return observed once using the paced loader and owner-installed ROM/tty ACL rule. A separate guarded NAND geometry-only kernel now passes offline checks and 27 new tests (124 host tests total); one supervised boot reported 256 MiB NAND, 128 KiB erase blocks, 2 KiB pages and 64-byte OOB with zero capability flags. Normal Nest USB mode returned after the owner reported ready. A bounded first-block raw/OOB sample profile now passes offline checks and 14 new tests (138 host tests total); initial transport failed closed due to gadget newline processing. A fresh binary-tty build passes offline checks and 141 host tests; the corrected boot captured two matching first-block samples including OOB (135168 bytes each), verified privately. Normal Nest USB returned after owner restart. Full-chip acquisition completed; raw passes differ by 79 single data bits, OOB matches. Offline BCH-derived data views agree and root0 binaries were reconstructed privately. The four previously unclassified chunks validate after excluding noncanonical unused parity bits, with no data changes; no verified restoration. See docs/research/nand-padding-review-2026-10-31.md. Next actual native IPC/protocol inspection. Do not grant diagnostic disk writes for automation. Evidence: docs/research/usb-handshake-2026-10-30.md.
- Establish programmed firmware-region recovery before installation. Owner selected one local recovery archive instead of two encrypted offline destinations; all 37 archived files were read back and verified, originals unchanged. See docs/research/local-recovery-archive-2026-10-31.md. This accepts same-PC storage loss; the subsequent scratch test establishes only its bounded restoration primitive. Preserve fresh exact-region backups before any new persistent experiment. No production firmware/provision apply command exists and no device service verification has been performed.
- The fixed-block recovery experiment under firmware/scratch_test/ passed ONCE: block 1312, one synthetic page program, one erase and one cleanmarker restoration, all four programmed BCH4 sectors independently verified, all 135168 original/final data+OOB bytes identical, final WP reported and native USB returned. Preserve the executed v1/private output; do not rerun it or use its repro as a retry. All 61 scratch checks pass; full suite 432 passed/three optional skips. Two builds reproduce six artifacts and 17 host helpers. Next: the NLE-derived authenticated state-exchange milestone and a narrow file-level commissioning/rollback plan. Additional general RAW recovery work is deferred; the scratch pass is not firmware restoration. See docs/research/scratch-result-2026-10-31.md.
- Implement/test device firewall compatible with measured kernel/tools; external VLAN restrictions are mandatory in the interim.
- Complete separately authorized dummy-load HVAC regulation, native scheduling, protective behavior, restart/power, sleep/battery, outage and interrupted-write tests. No live HVAC claims.

Host/software follow-up:

- Validate actual HA Core MQTT entity schema/UI, local add-on Supervisor installation and aarch64 build/runtime. Broker integration and amd64 container are tested.
- Validate temperature range/capabilities per equipment; add bounded fan behavior only when confirmed. No schedules, presets, away or heat-cool support yet.
- Review complete proprietary outbound endpoints/listeners, historical Lua bot/debug shell/remote-support paths on exact firmware. Current hardening is deliberately partial.
- Add transactional commissioning journal/recovery; offline registry edits currently require backend shutdown/restart.
- Registry enrollment spans output and registry files without an all-or-nothing transaction; interruption produces a prepared but uninstalled credential. Inspect reports/files and explicitly revoke/retry; never assume success.
- Scope manager roles if multi-user use arises; current manager credential is full privilege. Add connection/rate limits if the service expands beyond isolated small-device use.
- OS/container and legacy firmware CVE/SBOM analysis; pip-audit covers Python only. Verify binary/source correspondence and redistribution permissions before any release.
- Sign release manifests using an owner-controlled trust root when a real release exists; current manifests are unsigned integrity records.

Completed 2026-10-30: normal Nest USB detection, bounded transition watch and
allowlisted plist diagnostics; source-built offline RAM probe and patched native
loader with synthetic sanitizer checks; rootless Podman laboratory support and
94 passing host tests. This does not close the release-blocking device work above.

Completed 2026-10-31: retained MQTT discovery/state cleanup now survives offline
revocation and backend restart, with identifier-only durable records, queue retry,
reconnect replay and re-enrollment protection. Two real TLS-broker restart cycles
and fresh-subscriber retained-state checks pass. Older already-forgotten orphans
still need explicit revoke or administrator cleanup; HA history remains outside
broker cleanup scope. Full 284-test host/broker/container suite passes. See
docs/security/validation-2026-10-31-mqtt-cleanup.json.

Native telemetry follow-up (2026-10-31): the opt-in authenticated NLE-style
entry/PUT/metadata/subscription host subset and read-only MQTT sensors are
implemented. Unique enrollment, body-read authentication rechecks, bounded holds,
foreign-bucket rejection and shared command disabling have regression coverage.
HAOS private profile support is ready; actual installation/entity creation and
physical native exchange remain pending. Dedicated owner-broker authentication
passed with an explicit trusted CA and scoped legacy certificate-format handling;
no broker changes. Next: HAOS installation and the narrow device commissioning/
rollback plan. See docs/research/native-telemetry-2026-10-31.md.

HAOS deployment update: local Hearth app built/installed on amd64, started
manually, and authenticated HTTPS passed with its dedicated CA/IP certificate.
Automatic startup is disabled. Default suite: 471 passed/five optional skips;
fresh rebuilt-image broker/container subset: five passed. Actual HA entity
creation and physical native exchange remain unverified.

Commissioning preparation: exact offline originals/replacements for five config/
trust files are private and non-installable; native credentials are not enrolled.
Byte-preserving settings/NTP editors have focused tests. Captured user config and
symlink paths are now reconstructed/corroborated; fresh runtime/root checks,
commit/rollback tooling and native permission/TLS integration remain. Owner chose
public NIST NTP and existing UniFi IoT access, and will handle trusted-network
rules after connection. No router change is requested. See
research/native-commissioning-preparation-2026-10-31.md under docs/.

Settings privacy correction: current source restricts native temporary-file
creation and the actual opened descriptor to owner-only mode before serialization,
including pre-existing temporary files. Failure preserves settings and dirty
retry; unrelated opens/umask are unchanged. The 36-case RAM comparison is prepared
but unexecuted; the prior 29-case pass applies only to its preserved older build.
See docs/research/settings-permissions-preparation-2026-10-31.md. File installer/
rollback and full native startup remain pending after this focused measurement.

Observed: the 36-case settings privacy RAM comparison passed using source 68edfb9,
with successful native USB return. New/existing temporary files became 0600;
permission failure preserved old values and retry, unrelated opens stayed 0666.
No persistent installation occurred. The exact instrumented build is measured;
standalone/full application and filesystem installation/rollback remain open.
See docs/research/settings-permissions-result-2026-10-31.md.

File commissioning follow-up: original nine-file transaction/rollback and startup
wrapper preparation now have host/sanitizer/ARM-build coverage. Exact private
nine-file review retained; no installer command/device writer is enabled. A single
68-case RAM profile batches standalone storage and actual file transaction tests.
It is prepared but unexecuted. See docs/research/file-commissioning-preparation-2026-10-31.md.
Live snapshot/root verification, fresh settings merge, backup receipts, filesystem/
kernel integration, interrupted-write recovery and physical native exchange remain.

Combined file RAM attempt: v6 transferred but collection failed; no complete
68-case observation. Native home icon/USB returned. TX backpressure reset and RX
prefix concatenation are corrected with host regressions and durable attempt
markers. Fresh profile-v7 is checked/reproducible but unexecuted; preserve v6 and
all private failure evidence. See the dated file-commissioning attempt document.

Second combined RAM attempt: transport is fixed and the standalone 36-case storage
component passed, but file helper was not launched (hardcoded settings exec path,
exit 109). Dispatch is corrected with a host execution-callback regression. Fresh
profile-v8 is checked/reproducible and unexecuted; 32 ARM file cases still pending.
Native home icon/USB returned. Keep failed global reports/component evidence apart.

Observed third combined RAM attempt: source a0bc948/profile-v8 passed all 68
cases (36 standalone settings, 32 file transactions), three zero child statuses,
complete independently validated private report. Owner home icon and native USB
return confirmed; no loader armed. Earlier unexecuted/pending notes above record
preparation history and are superseded by this result. Next: live root/current
file snapshot, durable backup receipt, interrupted-install recovery and bounded
JFFS2 integration. No persistent commissioning or physical transport pass yet.

Protected snapshot follow-up: bounded read-only file capture and host backup
custody/receipt are implemented with sanitizer, ARM-link and failure regressions.
The separate JFFS2 RAM profile is built/checked locally at
build/file-snapshot-20261031-v4, unexecuted. Next owner-timed snapshot will collect
only the nine fixed files; root0 is a custom kernel view, not native active-root
proof. Target receipt enforcement, actual installation-plan binding and journal
replay remain pending. No installer/device writer was added.

Observed: the first protected JFFS2 snapshot succeeded from c73904e/v4. Nine
targets, seven existing originals all matching review, two new targets absent;
complete private frame and host backup receipt independently verified. No
installation. Native return pending owner confirmation; no loader remains.
Next exact plan/receipt binding and interrupted-install recovery integration.
See docs/research/filesystem-snapshot-result-2026-10-31.md.

Snapshot native return now confirmed by owner home icon and independent normal
USB observation. Next narrow commissioning work can proceed offline.

Interrupted-install restoration now has a bounded journal/plan validation API
and 24 passing host process-interruption/retry/refusal scenarios. Fresh 91-case
RAM profile-v2 is checked/reproduced but unexecuted; 653 host tests pass/five
optional skips. Native snapshot return confirmed. Next one owner-timed ARM run,
then target receipt/plan binding and actual bounded JFFS2 installer integration.
Do not confuse host/RAM process restoration with hardware power-loss recovery.

Observed: all 91 ARM RAM cases passed from aaf93b7/profile-v2, including all23
recovery paths, with a complete independently validated private report. Home
icon and normal USB returned; no loader armed. Next actual plan/receipt binding
and bounded JFFS2 writer integration. No persistent installation or power-loss
recovery claim. See docs/research/file-recovery-result-2026-10-31.md.

Exact-plan capsule/host custody binding is implemented and privately prepared:
native-file-capsule-20261031-v1 and -v1-repro, 23 matching files; 672 host tests
pass/five skips. Not installable; target writer/receipt enforcement pending.
Stock UI reached Wi-Fi setup on battery with the unwired base, then returned to
USB; Wi-Fi remains unconfigured. No additional power gear assumed for first
short attempt. See the dated file-capsule preparation note.

Bounded file writer integration is now implemented and paired private install/
restore images are checked, unexecuted. A 56-case synthetic RAM selftest precedes
real-file read-only preflight and a separate scoped persistent commit. Target
gate enforces plan/host receipt and physical ranges, with WP restored per I/O;
unmount/seal/read-only exact verification governs restart safety. Host socket,
sanitizer, archive/ABI and evidence tests pass; full suite 766/five optional skips.
Next one notified owner-timed RAM preflight. If originals changed, preserve a
fresh read-only snapshot in that session and rebuild the private plan. No flash
commit, live transport, hardware power-loss or HVAC measurement yet. See
docs/research/file-writer-preparation-2026-10-31.md.

Observed first writer preflight: all56 ARM RAM cases pass; settings.config changed
since snapshot, so real-file check refused correctly. Same-session fresh capture
verified; no commit/RW remount/write operations, WP sealed; native USB returned.
Actual unit backend enrollment now matches the private credential; host synthetic
native entry passed TLS, no physical traffic/commands. Fresh v2 capsule/images
prepared against changed settings; next supervised preflight. No installation
or restoration pass. See docs/research/file-writer-preflight-result-2026-10-31.md.

Second run again refused changed target7 with all56 cases passing and zero writes.
Recent XML settings keys/values are identical despite changed serialized bytes.
Keep sealed RAM mode: a new checked --handoff-from entry binds the next private
plan to that exact captured source and custody, avoiding another invalidating
native boot. It rejects decisions/writes, uncertain results, wrong captures,
broken custody, native or stale ROM. Full host suite774/five skips; new v3 pair
checked/reproduced. Next owner-timed RAM handoff, then separate first-write notice
if real-file preflight passes. No persistent installation or physical transport.

Observed: c4dc064/install-v3 first persistent nine-file install PASSED after
owner-confirmed commit: all56 selftests, real-file preflight, all9 committed,
exact post-unmount RO readback, sealed WP,94 page programs/no failures; native
USB return independently observed. No restore test/erase/OOB/power-loss/HVAC
claim. Backend credential matches installed settings; telemetry-only mode still
rejects commands. First battery/unwired-base Wi-Fi setup/physical telemetry is
pending. Never rerun install-v3. See docs/research/file-install-result-2026-10-31.md.

Wi-Fi bench exposed a native UI startup stall: steady home icon/green blinking
LED, no Wi-Fi settings or backend telemetry. Unit reconnected to USB/base detached.
Protected read-only startup diagnostic prepared/reproduced, unexecuted: fixed9
current files + bounded persistent log tails, unchanged RO kernel/no native code.
Full786 host tests/five skips and make check pass. Next notified owner-timed
diagnostic, then private evidence review. No guessed persistent fix/recovery.

Observed protected diagnostic: all9 installed bytes/modes matched;64 log tails
captured (partial count limit), no diagnosed cause. Owner confirmed restore
preflight and separate commit. restore-v3 PASSED actual journal/original/current
inspection, all56 RAM cases and selected-file restoration: all9 originals exact,
new shim/wrapper absent, sealed WP,41 programs/no failures. Stock unwired-base UI
check PENDING; keep Wi-Fi unconfigured. Do not reinstall/claim app recovery or
whole-firmware restoration. Backend enrollment remains. See dated restore result.


Current recovery outcome: original selected files and rollback originals/journal
were reencoded uncompressed; fresh flash-header audit and exact readback passed.
Owner confirmed working native UI; filtered plist confirms primary/5.9.4-5.
See docs/research/compression-recovery-2026-10-31.md. Before recommissioning,
preserve fresh native originals and use a plan-derived rollback directory without
removing the legacy recovery archive. New 72-case gate includes archive separation;
its on-device measurement and the fresh install/native-network test remain pending.


Observed corrected commissioning: fresh protected snapshot and exact original
custody passed; the new plan keeps the legacy archive and uses its own namespace.
All72 ARM cases and real-file preflight passed. Owner-authorized installation
committed all nine files, verified exact contents/modes plus active flash encoding,
and sealed write protection:131 page programs, zero failures. Host exited0.
Next native UI check under the new installation, then isolated native networking;
neither is passed yet. See docs/research/recommissioning-preparation-2026-10-31.md.
