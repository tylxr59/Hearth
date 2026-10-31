# Hearth: agent handoff and repository instructions

## Purpose and current status

Build a local-first Nest Learning Thermostat modification that preserves native hardware/HVAC control. Gen 2 is the primary target; Gen 1 is secondary. Prefer a verified local on-device interface if feasible; otherwise retain the native transport behind a minimal local backend. Do not rewrite HVAC control loops.

The user's unit has arrived and received USB intake on their PC. Arrival/ownership alone does not authorize flashing or physical control. The owner has explicitly authorized device investigation and requests advance notification for potentially dangerous actions such as flashing; preserve the backup/recovery gates below. The [2026-10-30 intake](docs/research/device-intake-2026-10-30.md) records enclosure `02A`, reported `Display-2.6`, firmware `5.9.4-5`, normal-mode USB `2464:0002` and an authorized manual restart briefly exposing OMAP `0451:d00e`. A later paced diagnostic RAM boot succeeded and returned to native startup. One supervised fixed scratch-block program/ECC/erase/restoration test subsequently passed with native USB return; no firmware installation, HVAC operation or whole-firmware recovery has been tested. Two complete owner raw NAND captures and independently matching BCH-derived data views now exist privately; native nlclient/osm were reconstructed for static inspection. Programmed firmware-block and whole-chip restoration remain unverified.

On 2026-10-31 the owner confirmed this is their only unit and explicitly accepted
potentially dangerous same-unit work after asking why a spare was required. A
spare is therefore not mandatory for the recovery investigation. Prepare a concrete
same-unit recovery/installation plan, verify original inputs and partition/write
semantics, and notify the owner before any persistent write with its recovery
limits. This does not establish recovery or authorize physical HVAC switching.
Only the later fixed scratch-block experiment has written NAND; no firmware installation has occurred.

Implementation baseline: commit `30c82f5`. It contains an authenticated host-side laboratory, not deployable thermostat firmware:

- HTTPS API with separate device/manager credentials, enrollment, rotation/revocation, validated commands, expiry and availability.
- MQTT climate discovery/control, dedicated broker ACLs, TLS, retained-command rejection and offline availability handling.
- Linux credential preparation and read-only sysfs USB inventory.
- Deterministic inert firmware review archives and partial offline replacement files. No apply/flash command or bootable image.
- Container, experimental HAOS package, simulated devices, tests, scans and provenance inventory.

The canonical `/v1/device/*` contract is new; stock Nest does not implement it. `backend/nest.py` is a strict partial PUT decoder, disabled in the normal runtime. Pairing, revision/CAS reconciliation, chunked subscriptions and physical command delivery remain incomplete. A passing simulator is not Nest compatibility.

The [2026-10-30 acquisition review](docs/research/acquisition-review-2026-10-30.md)
adds the diagnostic RAM probe under `firmware/probe/`. The first unpaced upload
failed at the ROM length field. A paced loader then successfully transferred the
three generated files, and the expected USB heartbeat was observed without sudo.
The owner restarted with the loader exited; the home icon and `2464:0002` returned.
The working build is `build/ram-probe-reliability-20261030`; the original remains
at `build/ram-probe-final-20261030`. Both are ignored and will not travel with a
clone. The probe kernel has no MTD/block/network support, and its only userspace
emits a fixed heartbeat. That heartbeat acquired no NAND data and did not test restoration.

The owner installed/reloaded the scoped ROM/tty udev ACL rule prepared under
ignored `build/usb-access-20261030`; installed bytes/root ownership were verified.
It grants access only to the current owner UID for ROM USB and the expected
probe tty on physical port `1-1`. Do not make the diagnostic disk writable for
automation. The native loader now uses 1 ms pacing, 512-byte output chunks and a
20 ms post-upload interval, adapted from the pinned upstream reliability PR.
Its wrapper requires normal Nest mode before a fresh attempt and never retries
a boot automatically. Use a PTY when launching it so native output is immediate.
A prior piped wait timed out without enough buffered stage evidence.

The separate [geometry-only kernel](firmware/nand_metadata/README.md) is built at
`build/nand-geometry-20261030` and passed offline integrity/configuration checks.
It asserts hardware WP, checks protected status, skips BBT scanning, denies write
callbacks and exposes only master sysfs geometry (no MTD char/block interface).
One supervised PTY-backed boot succeeded: 256 MiB NAND, 128 KiB erase blocks,
2 KiB pages, 64-byte OOB, flags zero. The protected-status registration guard
passed. Loader exited 0; the owner was instructed to restart to native startup.
Normal Nest USB mode (2464:0002) returned after the owner reported ready.
A separate first-erase-block sample profile is built and checked offline at
`build/nand-sample-20261030`; see firmware/nand_sample/README.md. It reads only
64 raw page/OOB records twice into RAM, retaining the geometry write guards
and no MTD character interface. Cached CRC-framed transfer goes only to a fresh
private output directory. The first wait expired before transfer. A later upload reached binary streaming
but collection failed closed: the gadget tty inherited OPOST/ONLCR translation.
A bounded private cached trace supports that finding; no complete validated sample
was saved. Home icon and normal USB returned afterward. The corrected build at
`build/nand-sample-rawtty-20261030` disables gadget tty processing and successfully
captured two matching passes: 64 pages, 135168 bytes per pass including OOB.
Private file permissions, lengths and SHA-256 records were verified without
logging bytes/hashes. Loader exited 0; owner reported done after restart instructions and normal
Nest USB 2464:0002 was observed. The full-chip read-only exporter is now built
at `build/nand-capture-20261030`; see firmware/nand_capture/README.md. It retains
the guards and streams two full raw/OOB passes after a fixed start token, using
one page buffer and mandatory completion footer. The acquisition ran once: all 262144 records and footer passed transport checks,
but raw hashes differed by 79 single data bits; every OOB byte matched. The
collector correctly exited 1 and preserved both 276824064-byte raw files under
`private/nand-capture-20261030` (0600). Offline BCH4 processing independently
produced identical 256 MiB data views under `private/nand-analysis-20261030`.
Four embedded image payload CRCs pass; 2567 root0 regular files reconstructed
with zero scanned inode/data/dirent CRC failures, including
`root0-extracted/nestlabs/sbin/{nlclient,osm}`. No native binary was executed.
Four chunks per pass retain unclassified ECC; no restoration/complete-backup
claim is made. Owner said returning to home icon; normal USB 2464:0002 was then
observed. No further mode switch is needed for static inspection.

Static review now traces three direct D-Bus tables (ten sniffer/SCPM/heartbeat
methods) and a separate 104-command loopback test-access implementation at
127.0.0.1:1234. Native temperature getter/setter paths are present, but startup
reachability and robust request framing are unverified. No device command was
sent. The bounded `tools.elf_review` reproduces private table inspection without
executing firmware; 20 new tests pass. See docs/research/native-interface-2026-10-30.md.
The ADR retains the provisional host transport; no production bridge is enabled.
Ghidra 12.1.2 headless analysis (installed Java 27) supports dormant test-access
code: no incoming initializer/thread-entry refs, with a positive cleanup-call
control. The recovered CA bundle resolves through a metadata-only symlink to
/etc/ssl/certs and contains one self-issued Nest anchor; the eMudhra compromise
is not an evidenced shortcut for that trust store.
The native OpenSSL 1.0.2h/libcurl 7.49.1 path overrides certificate-not-yet-valid
and selected CRL failures. A private one-instruction offline review copy now
selects the default OpenSSL callback, independently checked by LLVM/Ghidra; it
remains uninstalled; the later bounded target measurement is recorded below. Originals remain unchanged. No binary
patch/library/hash was put in source. See docs/research/native-tls-2026-10-30.md.
The original tools/ghidra/HearthStaticReview.java exports only below private/
and was integration-tested, including refusal of a public output directory.
Native credential/bootstrap static review now traces assigned settings, Basic-auth
request builders, response-header credential updates and 401 fallback to default
credentials. The update helper logs both new ID and secret; a separate private
one-instruction candidate skips that logging block, checked by LLVM and a fresh
Ghidra import. Nothing installed; durable settings/rollback and other logging
paths remain unverified. Three host regression tests preserve enrollment/header
boundaries; make check passed, 174 host tests passed with two optional integration
tests skipped. See docs/research/native-bootstrap-2026-10-30.md.
The native storage/log follow-up traces a temp-file/sync/rename/directory-sync
writer, but entry write failures log key/value and do not reach the outer result;
a failed directory sync can still clear dirty state. The earlier client log
candidate does not fix this library path. A known uploadlogs flag controls the
queued-file sender. Offline hardening now prepares uploadlogs=0 and edits only
two reviewed config value spans, refusing ambiguous XML before output. No writer
patch or device installation. Fifteen new tests; make check and 189 host tests
passed, two optional integrations skipped. See docs/research/native-storage-2026-10-30.md.
Native protocol review corroborates response metadata ordering and flags a
preliminary brace-counting extractor; full entry/CAS/subscription semantics remain
open. The RAM-only TLS probe under firmware/tls_probe/ uses a separate kernel with
MTD/block/physical-network/RTC and hardware-clock synchronization disabled. Only
loopback is enabled. UID/GID 65534 helpers compare original/candidate native hooks
against 18 synthetic cases; nlclient/osm and actual credentials/settings are absent.
The first supervised attempt (source commit 3fa529e) transferred all three files
and reached custom USB serial/PID 1 reporting, but saved only a 39-byte failed
completion marker with no TLS cases. No automatic retry. Owner confirmed return
to home icon and normal USB 2464:0002 was observed. Preserve the original private
profile-supervised directory and tls-result.jsonl; creation manifest remains an
immutable pre-execution record. See docs/research/tls-probe-attempt-2026-10-30.md.
A concrete packaging error was found: PT_INTERP's dynamic loader had mode 0444.
It now has required execute mode 0555; ordinary DSOs stay 0444. The first report
cannot prove this was the sole failure. The corrected supervisor records loopback/
RAM-clock setup, pre-exec syscall errors, child wait statuses and private bounded
stderr. Success requires setup, both zero statuses and all 18 expected TLS rows.
The corrected profile at private/native-tls-probe-20261030/profile-launch-diagnostics
now completed a second supervised RAM run using source cd3f9b1. Loader and collector
exited zero; the private 1873-byte/22-row result confirms loopback and RAM-clock
setup, both zero helper statuses, no stderr and all 18 expected TLS cases. Original
hook accepts valid plus future-cert/missing-issuer/expired/future-CRL cases; the
candidate accepts only valid and rejects all eight invalid cases. This validates
the specific callback candidate on ARM/native curl/OpenSSL in the loopback harness,
not full native fetch/startup/config/time bootstrap or secure commissioning.
After command exit the display initially stayed black/probe USB. A full ~10-second
hold, release, single press returned the native home icon (owner confirmed) and
normal USB 2464:0002 (independently observed). No retry or persistent installation.
See docs/research/tls-probe-result-2026-10-30.md and the dated TLS-observed JSON.
Both attempts, creation manifests, results and separate attempt records remain
private and immutable. Never rerun a profile with an existing result. Public
kernel/helpers remain in build/native-tls-lab-20261030/; the kernel/bootstrap bytes
were unchanged. The preparation baseline is 50 probe tests, 239 host tests passed,
two optional integrations skipped and make check passed. No ARM firmware ran on
the host; the independent permission regression uses trusted host true/ld copies.
A separate original twelve-case settings RAM diagnostic is now prepared under
firmware/settings_probe/. It uses the same kernel/bootstrap and 34 unchanged
base libraries, only the reviewed native settings base class, fixed one-shot I/O
faults and synthetic /state files. No real settings, TLS candidate, keys, clock
change, network setup or nlclient/osm. Six exact ABI exports plus constructor
flags are checked; opaque object size is 48 with a tail canary. Host sanitizer
checks exercise original interposition against an original fake NSPR, not firmware.
Private unexecuted profile: private/native-settings-probe-20261030/profile-prepared;
helpers: build/native-settings-lab-20261030/helpers-reviewed. Offline wrapper:
sh firmware/settings_probe/boot.sh PRIVATE_PROFILE. Explicit future execution flag:
--execute-experimental-settings-probe (PTY, owner-timed restart, no automatic retry).
The owner returned for testing. One supervised d6823ed boot uploaded successfully
but failed collection: 15423-byte private result, five complete cases, 75 diagnostic
rows, child SIGKILL and a partial row. Shared stdout/stderr report budget exhausted.
Owner confirmed native home icon and normal USB returned; no automatic retry.
Preserve profile-prepared/result and private/native-settings-probe-20261030/attempt-1.json.
The corrected supervisor separates stdout (8 KiB) and diagnostic (2 KiB raw) caches,
continues draining excess diagnostics and reports dropped bytes. Its original shared
cache sanitizer stress checks and 29 settings tests pass. Corrected private
profile: private/native-settings-probe-20261031/profile-capped-diagnostics; helpers:
build/native-settings-lab-20261031/helpers-capped-diagnostics. Seven artifacts match
a fresh reproducibility profile. No kernel/bootstrap/library/writer change.
A second supervised run using e5b0917 now completed all twelve cases: loader and
collector zero, 8329 private bytes/31 rows, 16 diagnostic chunks plus 7956 explicitly
discarded bytes, zero child status and all tail canaries intact. Original entry
error returns success with one value lost; short write returns success with invalid
XML; neither retries. Directory-sync error also skips retry. Normal write/readback
and other modeled failures behave as recorded. No writer correction is installed.
Owner confirmed native home icon and read-only preflight confirmed normal USB.
Preserve both attempts and private/native-settings-probe-20261031/attempt-2.json.
No further mode switch is needed now; no loader is armed. See
docs/research/settings-probe-result-2026-10-31.md, the first-attempt record and README.
Next: design/test a narrowly scoped settings error/log correction against the
observed matrix, continue native entry/CAS/subscription mapping and establish
recovery before any persistent modification. An original storage correction and a 29-case comparison profile are now being
prepared under firmware/settings_compat/ and firmware/settings_compat_probe/.
The correction delegates native writer/setter behavior, makes entry errors block
replacement, restores dirty state after failure, and replaces AddEntry allocation
ordering while preserving callback input lifetimes. Native serialization/control
are unchanged. Host NSPR/ASan/UBSan checks cover allocator ownership, failures,
thread/nested scopes and aliased setter callbacks. Source/ABI review is private
under private/settings-compat-review-20261031/native-abi.json. Candidate remains uninstalled. One supervised attempt using source 6f77863 and
private/settings-compat-probe-20261031/profile-candidate-v2 transferred all three
files, completed all twelve original I/O cases with zero child status, then failed
closed because the candidate child terminated with SIGSEGV (raw wait status 11)
before any case. The private report is 9176 bytes/33 rows; its immutable attempt
record is private/settings-compat-probe-20261031/attempt-1.json. Native home icon
and USB return were independently confirmed after command exit. No candidate
correction is target validated. See docs/research/settings-compat-attempt-2026-10-31.md.
Preserve all existing profiles/results; never rerun profile-candidate-v2 or earlier
drafts. Current source changes add fixed, value-free phase markers for locating
the failure; standalone candidate builds omit them. Prepare a fresh fully checked
profile before requesting another supervised PTY-backed restart. All 29 cases,
process statuses, binding checks and streaming log checks remain required.
Host preparation before this attempt passed 312 tests with three unchanged optional
broker/container skips, plus make check. Kernel/bootstrap remain the tested TLS
base. Notify before each experimental boot; never arm a loader without owner
readiness. Streaming diagnostics must inspect discarded bytes as well as cached
bytes. No persistent installation has occurred.
Prepared diagnostic profile: private/settings-compat-probe-20261031/profile-phase-v1;
helpers build/settings-compat-20261031/comparison-phase-v1. Seven artifacts match
its separate repro; rootfs 11020556 bytes, image 6018284 bytes. Offline wrapper,
make check and 312 host tests pass (three unchanged optional integration skips).
This profile was executed once using source af32cd5: original twelve cases and
zero child status again, candidate SIGSEGV before any fixed phase marker. Report
9176 bytes/33 rows and private attempt-2.json preserved; owner reported manual
restart done and native USB was independently observed. Never rerun it. Startup
fails before initializer/main diagnostics, with exact cause still unknown.
Next diagnostic profile private/settings-compat-probe-20261031/profile-loader-v1
adds candidate-only LD_DEBUG=files,reloc and retains its final 2 KiB stderr window;
original first-window capture and all-byte secret scanning remain. This profile was executed once using source 21e2e64. Original twelve cases still
pass; candidate SIGSEGV occurs during relocation processing of the compatibility
DSO, before any initializer marker. Report 14247 bytes/50 rows and attempt-3.json
are private; native USB return observed after owner restart done. Never rerun it.
Next fresh profile private/settings-compat-probe-20261031/profile-bindings-v1
adds loader binding diagnostics; all limits and 29 case gates are unchanged.
profile-bindings-v1 executed once using source 5ecabc3: original twelve cases pass,
candidate SIGSEGV during compatibility relocation before any external binding or
initializer marker. Private report 14248 bytes/50 rows, attempt-4.json and tail
preserved. Owner restart done and native USB observed; never rerun this profile.
Latest EXECUTED profile: private/settings-compat-probe-20261031/profile-gnu-v3.
Helpers: build/settings-compat-20261031/comparison-gnu-v3. It uses optional
--legacy-linker to compare the historical GNU linker in the existing rootless
builder; all source/storage behavior and 29 case gates remain. Only original
objects/public stubs mounted, no firmware executed/linked on host. Kernel/base
libraries unchanged. Seven artifacts reproduce; rootfs 11022900, image 6018803.
make check and 313 tests pass with three unchanged integration skips. GNU draft
v1/v2 directories stale; do not package/run them. GNU v3 offline wrapper passes.
The exact GNU v3 profile was executed ONCE using source 109c652 and PASSED all
29 cases: 24 I/O plus five allocation/alias, both wait statuses zero, all canaries
and binding checks passed. Original/candidate synthetic-secret matches 2/0;
unrelated variadic marker 1/1, candidate scoped suppressions 50. Private report is
19096 bytes/68 rows; attempt-5.json separately preserves identity/metadata. Never
rerun this or its repro profile; preserve all original manifests/results. Owner
reported restart done after command exit; native USB independently returned after
a brief disappearance. No persistent installation or real settings access occurred.
See docs/research/settings-compat-result-2026-10-31.md and dated observed JSON.
This closes the exact base-library synthetic comparison, not full app/derived
callbacks, credential-pair atomicity, other logs, real storage, TLS/time bootstrap,
restoration or HVAC. Default LLD builds remain unvalidated; exact earlier crashing
instruction unknown. No loader is armed. Continue native integration/protocol and
concrete same-unit recovery planning before any persistent write; notify owner
before a new diagnostic and request readiness only when fully prepared.
While waiting for owner readiness, read-only Ghidra review traced the native
entry callback at 0x976c0 and URL/platform-key/tier setters. Platform-key values
have additional log paths; tier changes can call settings Write; URL processing
indexes using original length after a bounded copy (LLVM corroborated). No entry
request or native app was run. Details: docs/research/native-entry-2026-10-31.md.
Private exports: private/native-entry-review-20261031. Do not copy the upstream
entry field set or claim it is observational; no production codec was added.
The existing experimental entry fixture was then corrected to omit empty weather
and update fields. It now advertises only transport_url, from the shared
private-IPv4/explicit-port HTTPS validator moved to backend.validation. Controls,
non-ASCII and empty userinfo are rejected before URL parsing. Twelve regression
cases added; make check and all 328 tests including real TLS broker/container
integration pass, plus an explicit rebuilt-container check. Normal runtime still
disables legacy routes; no entry request was sent to the unit. Field omission
does not disable cached/default native service URLs or prove pairing.
Offline recovery-layout follow-up freshly verified raw capture identities, surveyed
marker bytes and recovered two CRC-valid boot environments (credential values stay
private). Their root device references 7/9 corroborate the source overlay numbering.
Fresh corrected-image header/payload CRC checks pass at four expected locations.
Secondary root reconstruction: private/nand-analysis-20261030/root1-extracted and
root1-extraction.json, 2567 regular files, zero scanned CRC failures; no symlinks or
special nodes created, no executable mode. Its four critical native binaries match
primary, but whole regular-file maps differ. In scratch, 725/736 blocks have erased
data plus first-page OOB cleanmarkers; do not treat them as all-FF/free space.
New private metadata: private/nand-marker-review-20261031. No block selected for
writing, live map/write-ECC contract or restoration verified. See
docs/research/recovery-layout-2026-10-31.md. Scripts remain machine-local research
recipes, not portable recovery tools. Next: native integration/protocol and exact
fresh-region acquisition/write-contract planning before persistent operations.
The next original read-only NAND controller diagnostic is prepared under
firmware/nand_contract/. Current fully checked build: build/nand-contract-20261031-v5;
separate v5-repro has six byte-identical artifacts, including kernel/config/init.
Earlier unexecuted draft builds v1-v4 are superseded; never run those. Controller
fields include actual detected bus width, chip marker flags, explicit descriptor
presence/options and BCH4/OOB/free-region layout. Eight-/sixteen-bit correlations
are enforced. With BBT scan intentionally skipped, an absent descriptor is not
evidence of a native bad-block policy or healthy blocks. No NAND content, chip
serial, credentials or register dump is exposed. Original geometry HW-WP/status,
NAND_ROM and denied mutation callbacks remain, no MTD char/block/partition/UBI or
network consumer, no writer. Configuration choices match observed geometry;
only compile metadata timestamps/user/host/domain are normalized via an exact-
source-checked generator patch and KCONFIG_NOTIMESTAMP for reproducibility.
Host validation: 350 passed/three unchanged optional integration skips, make check,
25 new contract checks including original C producer+Python parser under sanitizers.
Prior unchanged backend/broker/container full 328-test run remains separately scoped.
Offline sh build/nand-contract-20261031-v5/boot.sh passes, opens no device.
Future PTY execution flag --execute-read-only-nand-contract requires owner readiness
and advance experimental-RAM notification. No loader armed or device execution yet.
After it exits request full ten-second hold/release/single-press and verify native
return. No automatic retry; this cannot establish restoration/programming.
See docs/security/validation-2026-10-31-nand-contract-prepared.json.
The exact v5 controller profile was subsequently executed ONCE using source
316f50d and passed. Loader/observer zero; observed bus16, protected1, markerpos0,
second-page flag1, last-page/byte1-and6 flags0, explicit descriptor absent under
skipped BBT scanning. ECC HW2, size2048, bytes/total28, steps1; parity positions
36..63 and free OOB offset2/length34. Geometry/zero capabilities unchanged.
Private validated output record: private/nand-contract-20261031/attempt-1.json;
no raw serial frame separately archived, no NAND contents acquired. Owner restart
done and native USB independently returned after a brief disappearance. Preserve
all manifests and do not rerun v5 or drafts. See
docs/research/nand-contract-result-2026-10-31.md and dated observed JSON.
No writer, programming, ECC-fault correction or restoration was tested; next is
bounded normal-ECC read comparison and fresh proposed-region acquisition before
designing persistent operations. No loader currently armed. Full native protocol,
application/TLS/time integration and physical bench validation still remain.
The next original normal-ECC read comparison is now fully prepared under
firmware/nand_ecc_sample/. Build: build/nand-ecc-sample-20261031; separate -repro
has six byte-identical artifacts. Configuration choices/bootstrap unchanged from
observed controller/validated heartbeat. Fixed block190, pages12160..12223 includes
the prior noncanonical-padding page12209. Uses normal read_oob MTD_OOB_PLACE with
physical OOB; no char/block/partition/UBI/network or writer, WP/readonly guards
unchanged. The published BCH4 callback discards decode failures/counts, so zero
status is insufficient; exact host reference comparison is mandatory. No callback
fix or stock-kernel source/binary equivalence is claimed.
Private reference: private/nand-ecc-reference-20261031/expected.ecc-oob and immutable
reference.json. Prepared from freshly reverified raw/corrected file identities,
matching corrected views and raw OOB. Not in image or sent to device. Fresh future
output: private/nand-ecc-sample-20261031 (must not already exist). Magic HRTHCOR1
with absolute page indices; failure HRTHFAL1 preserves bounded typed diagnostics.
No raw bytes/hashes logged. Collector requires 128 records, matching passes and
reference, syncs private 0600 output and preserves partial failures. Host C fixture
executes original fake NAND/sysfs only, under sanitizers. 21 new checks; make check
and 371 host tests pass/three unchanged optional integration skips. No ARM firmware
executed on host. Offline image and private reference/output preflights pass.
Future PTY command (notify owner and obtain readiness before arming):
sh build/nand-ecc-sample-20261031/boot.sh --execute-read-only-nand-ecc-sample /home/tylxr/workspaces/Hearth/private/nand-ecc-sample-20261031 /home/tylxr/workspaces/Hearth/private/nand-ecc-reference-20261031/expected.ecc-oob
After exit request full ten-second hold/release/single-press and verify native USB.
No automatic retry. No loader currently armed or target run yet. See
docs/research/nand-ecc-read-review-2026-10-31.md and dated preparation JSON.
The normal-ECC profile was then executed ONCE using source cae21fa and PASSED.
Loader/collector zero; 128 ordered records, two 135168-byte data+physical-OOB passes
match each other and the independent preserved reference exactly, including the
padding page12209. Private payload lengths/digests, reference byte equality and
600/700 permissions independently rechecked. Private/nand-ecc-sample-20261031 has
capture.json, pass-{0,1}.ecc-oob and separate immutable attempt-1.json. Preserve
all original manifests/reference/results; never rerun this profile or existing
output. Owner restart done and native USB independently observed after brief
disappearance. No diagnostic programming/erase, native app or physical HVAC ran.
This is a bounded normal-read match, not measured ECC-error count/fault injection,
reliable driver status, arbitrary-data integrity, programming or restoration.
See docs/research/nand-ecc-result-2026-10-31.md and dated observed JSON. Next:
fresh complete data/OOB for a specifically proposed restoration-test region,
exact program/erase/ECC and restore bounds/error plan before persistent work.
Both boot/root/config/calibration/backplate remain protected. No loader armed.
The owner has only this unit and explicitly accepts potentially dangerous same-unit
work; spare-only recovery restriction is waived, advance notification before
persistent writes and separate physical HVAC authorization remain. Continue through
RAM validation and a concrete same-unit recovery/commissioning plan.
Independent host progress now closes retained MQTT cleanup across offline
revocation/backend restart: the optional registry revoked list retains validated
identifiers only, saved with credential removal. Every broker connection repeats
offline availability and discovery/state deletion; queue failures retry, and
explicit re-enrollment cancels cleanup. Active identities are always excluded.
Identifiers remain privately after cleanup so stale broker restores can be removed
on reconnect. Legacy already-forgotten orphans need explicit revoke/manual cleanup.
Thirteen new unit checks and one real TLS-broker test cover two fresh backend
instances and fresh subscriber verification. Updated image built with rootless
Podman; full 284 tests passed with broker/container integrations enabled; make
check and runtime/build lockfile audits passed. No HAOS UI/aarch64/firmware or
HVAC claim. See docs/security/validation-2026-10-31-mqtt-cleanup.json.
Prepare any new bounded RAM test completely before another owner-timed restart;
no automatic device retry. Existing TLS measurement does not close the native
settings error/rollback, backup/restoration, full fetch/transport or HVAC gates.
For a future explicit diagnostic, use a fresh private profile, PTY-backed loader,
normal-mode preflight and the reviewed manual sequence. After command exit, use
a full ~10-second hold when the screen is already black, release, press/release
once and confirm native startup. All prepared images/libraries/keys/results stay
private. No base connection or persistent modification is authorized by a TLS pass.
A supplemental offline review now resolves the four previously unclassified
chunks per raw pass: each has one noncanonical unused parity-padding bit, while
its protected 52-bit BCH payload validates without data/ECC correction. Both raw
hashes freshly match capture records; original raw/derived files are unchanged.
Private record: private/nand-padding-review-20261031/padding-review.json; recipe:
build/review-private-padding-20261031.py. See the dated public padding review.
This closes that ECC classification gap, not bad-block/boot-ROM interpretation
or restoration. Preserve all original OOB bytes and the historical reports.
Keep private identifiers, credentials, bytes and binary hashes out of source/logs.
Machine-local offline scripts are `build/{infer-private-bch4-layout,decode-private-bch4,extract-private-jffs2}-20261030.py`;
the public BCH source is pinned in docs/research/bchlib-2.1.3.json. These scripts
are experimental research recipes, not portable recovery tooling. Preserve both
raw inputs and separate derived views. See docs/research/nand-capture-2026-10-30.md.
Notify the owner before experimental RAM execution under
their existing authorization; do not re-ask general device permission. Continue
to enforce backup/recovery gates before persistent writes and separate HVAC
authorization/equipment requirements. See [handshake evidence](docs/research/usb-handshake-2026-10-30.md)
and the separate dated USB validation report. Heartbeat plus native startup is
not firmware recovery, battery/HVAC validation or product compatibility.

This PC is CachyOS with Python 3.14.8 and rootless Podman 6.1.4, installed by the
owner. Fresh validation: 173 tests passed including simulated TLS broker/container
tests using `HEARTH_CONTAINER_ENGINE=podman`; make check passed. The earlier
same-day dependency audit passed. Separate dated reports preserve both scopes.
The original Docker/amd64 results remain
historical. No HAOS, aarch64, flashing, firmware recovery or HVAC claims were added.

## Read before implementation

Owner decision 2026-10-31: one local recovery archive on this PC is sufficient
for this unit's bounded recovery development; the owner explicitly authorized
modifying the two-encrypted-offline-copy plan. Do not ask for two storage targets
again. Selected unencrypted owner-only archive:
private/local-recovery-20261031/{recovery.tar,manifest.json}, 37 members fully
read back against source digests, four large inputs freshly matched original
records, files/directory fsynced, permissions 0600/0700. Inputs unchanged;
no identifiers/contents/digests published. Recipe in ignored build/. This is
same-storage archival protection, not independent/offline storage or restoration.
Fresh exact-region acquisition, durable backup acknowledgement, reviewed bounded
write/erase/restore, independent ECC verification and advance danger notification
remain required. No loader is armed or flash writer executed. See
docs/research/local-recovery-archive-2026-10-31.md and docs/hardware.md.
Draft fixed-block recovery code now exists under firmware/scratch_test/: original
GPL transaction/core/kernel adapter, MIT supervisor/framing/backup/BCH/session.
Core operates only block1312/page1 and permits one program/erase/marker restore;
hardware bounds are not yet qualified. Host snapshot ACK follows readback and
file/directory/parent fsync; errors never return a token. Independent degree52
BCH encoder matches seven synthetic pinned-bchlib vectors; private storage mask
must remain host-only. Duplex socket tests check pre-ACK storage failure and
post-ACK uncertainty, fixed scope/content/ECC/restoration rejection. Adapter
compiled in build/scratch-compile-20261031, but its borrowed geometry init cannot
issue scratch commands. The new supervisor source is NOT in that kernel draft;
there is no sealed manifest or execution wrapper (boot.sh always refuses).
No device test requested/armed. Next: integrate/review supervisor, fault-test
adapter I/O, verify private mask/archive preflight, then seal/reproduce and notify
owner of exact first-write risk before a ready-timed attempt. Do not manually
boot the compile draft or rerun an executed earlier profile.
Current validation: 419 host tests passed, three optional integrations skipped;
48 new scratch checks, make check passed. Standalone scratch supervisor compiled
as static ARM with -Wall/-Wextra/-Werror in the same isolated builder at
build/scratch-supervisor-compile-20261031; it was not executed/integrated. Original
C core/framing tests use ASan/UBSan; kernel-adapter hardware/I/O semantics are
still unqualified. Public scope: docs/security/validation-2026-10-31-scratch-draft.json.
Normal Nest USB 2464:0002 was independently observed during this offline work.
Scratch preparation follow-up supersedes the preceding compile-only status:
build/scratch-restore-20261031-v1 and -v1-repro are sealed and unexecuted, six
byte-identical artifacts and 17 byte-identical host helpers, both offline image/
config/initramfs checks pass (4192 initramfs bytes, 2759424 kernel bytes).
Supervisor integrated, binary tty configured; original read-only observer unchanged,
scratch-only checked derivation opens scoped tty RDWR. Actual adapter I/O and
supervisor logic pass synthetic sanitizer models, including partial transfers and
missing ACK/result. Full suite 432 passed/three optional skips; make check passed.
Preflight hashes the local archive, binds the private BCH mask record to its
archived original digest, and independently verifies 256 preserved reference
sectors; private mask never reaches target/logs. New public scope:
docs/security/validation-2026-10-31-scratch-prepared.json. Exact future flag:
--execute-experimental-scratch-restore PRIVATE_OUTPUT PRIVATE_ARCHIVE_DIRECTORY
PRIVATE_MASK_RECORD. Use fresh output, normal-mode preflight, PTY, owner readiness
and advance first-write notification. Scope block1312/page1 only, at most one data
program/erase/marker program. No attempt armed or persistent operation executed.
Earlier compile drafts remain prohibited. After ambiguous write outcome preserve
power/evidence and review before any reset/retry. A scratch pass is not firmware
restoration or authorization for firmware installation/HVAC. Next: ask owner timing
only when the checked source milestone is saved, then arm one supervised attempt.
The exact sealed v1 scratch profile subsequently executed ONCE using source
2f28a52 after owner readiness and advance first-write notification. Loader and
collector exited zero; fresh canonical block1312 backup was durable before ACK.
Target reports counts1/1/1 and zero results for synthetic page1 program, erase
and marker restoration, final WP1. Four independently encoded BCH4 sectors pass;
all 135168 original/final data+OOB bytes and target/host digests match. Private
post-collection re-read, lengths and 0600/0700 checks passed. Output:
private/scratch-restore-20261031-attempt-1/{original.raw-oob,original.json,result.bin,attempt.json}.
Separate immutable records: private/scratch-attempt-records-20261031/{prepared-1,observed-1}.json.
Creation manifests/original inputs unchanged. Owner reported reset done with
loader exited; normal USB2464:0002 independently returned. Do not rerun v1/output
or its repro. No loader armed. Public result:
docs/research/scratch-result-2026-10-31.md and scratch-observed security JSON.
This closes only the fixed empty-scratch primitive. No whole-chip before/after,
programmed firmware-block restore, interrupted-power recovery, install, native
commissioning or HVAC claim. Continue programmed-region recovery planning and
native integration/TLS/time/pairing work offline; notify before a new operation.
Offline follow-up pinned/matched the public NAND core and reviewed RAW data/OOB
dispatch. nand_do_write_ops can report full oobretlen after data writer failure;
future adapters must require zero status plus both exact counts and byte readback.
Current successful marker path is OOB-only and already requires status/exact count.
Next synthetic full-block rehearsal/rescue requirements are design-only in
docs/research/programmed-recovery-next-2026-10-31.md; no additional profile built,
armed or authorized to run by that document. Native startup remains in place.
Owner subsequently challenged duplication of NLE. The uncommitted full-block
rehearsal core/model was parked under ignored build/parked-programmed-block-20261031
(one sanitizer host-model test passed; no image built/loader armed/device executed).
Do not automatically resume the 64-page RAW restoration framework. Prioritize
one authenticated native telemetry exchange using NLE's existing transport and
filesystem-level commissioning approach, with Hearth's unique-auth/TLS boundary.
Both upstream main heads freshly match existing pins; no re-fetch/re-audit of
completed research is needed. Map minimum endpoint/trust/credential/logging changes,
active-root checks, exact original-file backups and suitable rollback before any
install. Existing recovery/physical-operation gates are not silently waived.
See docs/research/nle-integration-focus-2026-10-31.md. Device remains native; no
new test requested. This priority supersedes earlier default-next raw-rehearsal plans.

1. `README.md` and `TODO.md` for scope and outstanding work.
2. `docs/architecture/0001-local-transport.md` for the provisional architecture decision.
3. `docs/research/findings.md`, `docs/research/upstreams.json` and `docs/protocol/nest.md` for evidence and protocol limits.
4. `docs/security/audit.md`, `docs/security/threat-model.md` and `docs/security/network.md` for boundaries and remaining risks.
5. `docs/hardware.md` before planning any physical-device work.
6. `THIRD_PARTY.md` before reusing source, firmware or tools.

Do not redo completed research indiscriminately. Distinguish confirmed source findings, upstream reports, hypotheses and new hardware measurements. Pin any new upstream revisions and record what changed.

## Resume on another PC

Use the Git repository, including this file and all committed docs. The owner explicitly authorized local commits and pushes as work progresses on 2026-10-30. Push checked source/documentation milestones using judgment; private captures, credentials, identifiers and proprietary firmware remain excluded. No further permission request is needed for this authorized source-push scope.

`.venv/`, `build/` and `private/` are ignored and will not travel with a clone or Git bundle. Initial reference checkouts under `/tmp/hearth-references` are machine-local. They are not required for tests; reconstruct pinned research inputs with:

```sh
.venv/bin/python -m tools.fetch_research build/references
```

Keep user-specific firmware dumps, packet captures, credentials and backups private and out of Git. Transfer needed private material separately through an owner-approved secure workflow. Do not copy old generated artifacts as evidence that the new PC has passed validation. Fresh output paths are required by artifact tooling; inspect existing outputs instead of deleting them automatically.

Linux setup, tested initially on Python 3.13.16:

```sh
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.lock
make check
make test
make audit
```

Docker and OpenSSL are needed for the full laboratory suite:

```sh
make image
HEARTH_BROKER_TEST=1 HEARTH_CONTAINER_TEST=1 .venv/bin/pytest -q
```

These tests use simulated devices and loopback container services, not USB or HVAC hardware. The initial full run passed 39 tests; treat that as historical evidence, not the result of the new checkout. `docs/security/validation.json` records its scope. Python runtime/build scans do not cover container OS or proprietary firmware vulnerabilities. HA Core/Supervisor runtime and aarch64 remain unverified. The external router's nftables enforcement also remains unverified; the initial host could not perform its netlink check.

## Ordered next steps when Gen 2 arrives

1. **Identify and document the unit.** Record model/generation, display/base/board identifiers and native firmware version through available non-invasive means. Keep identifying details private where appropriate. A TI USB identity alone does not establish generation or compatibility. Keep the unit isolated from Google/NLE and production HVAC during investigation.
2. **Plan acquisition and recovery before executing device tools.** Review the exact model's boot/USB mechanism, tool source and integrity, power requirements, MTD layout and recovery procedure. Classify side effects honestly: a USB boot exploit or RAM payload is not purely observational just because it avoids NAND writes. Obtain the relevant explicit authorization before execution. Do not use guessed flash offsets or run the bundled upstream installer.
3. **Acquire and preserve evidence through an authorized procedure.** Obtain lawful firmware/backups, hashes, kernel/config, partition/mount map, startup services/listeners and boot environment. Preserve calibration, per-device credentials and backplate firmware. Establish the limits of the backup and a demonstrated recovery path before any persistent modification; follow `docs/hardware.md`.
4. **Resolve the architecture's critical unknown.** Statically inspect actual nlclient/osm and libraries; investigate local IPC/sockets/D-Bus without invoking control/lifecycle methods. Historical scripts name `nlclient` as the application and configure `osm` as the updater. SCPM D-Bus is power management, not proof of a thermostat setter. Choose a local bridge only after a usable interface is evidenced; update the ADR with findings.
5. **Verify authentication, TLS and native transport.** Determine credential installation/bootstrap, private CA and hostname/time checks. Capture authorized, isolated traffic to establish actual pairing, bucket schemas, revisions/CAS, subscriptions, sleep/WoWLAN and schedule behavior. Add sanitized fixtures and regression tests before implementing a production adapter. No serial-trust bypass, disabled TLS verification or plaintext production fallback.
6. **Implement a model/revision-specific commissioning path.** Add verified backup/recovery, transactional provisioning, complete startup/service hardening and post-install verification. Existing offline replacements cover only understood files and are not a complete lockdown. Verify available firewall tools/kernel features and external isolation. Keep deployment disabled until these gates are met.
7. **Validate separately authorized bench operation.** Use the hardware plan's dummy-load, power/sleep, offline regulation, schedule, restart, protection and outage matrix. Physical HVAC switching requires explicit authorization and appropriate equipment. Validate actual HAOS MQTT entities/install/upgrade separately. Promote support only for the configurations actually measured.

Progress on independent host work while hardware investigation is blocked. Useful remaining work includes transactional credential/export recovery, real HAOS installation, aarch64 validation and container/firmware supply-chain analysis. Keep the small working prototype intact; avoid adding speculative APIs or capabilities.

## Non-negotiable operating boundaries

- Never flash, modify or control a connected physical device without explicit authorization covering that action. Do not repeat approval requests for the same already-authorized scope; do not infer new authorization from possession or a general request to continue.
- Never execute untrusted firmware on the development host. Inspect upstream scripts before running anything; do not run historical rootme/install/update scripts.
- Preserve native control, backplate firmware, drivers, watchdog, SCPM and unknown services until their roles are understood. Preserved proprietary code is not proof of HVAC safety.
- Do not install the generated review tar or partial replacements onto a device. No current artifact is a verified bootable/recoverable firmware image.
- No shared/default credentials, credential logging, open enrollment, arbitrary raw commands, executable uploads, automatic remote updates or unsolicited third-party requests.
- Keep backend credentials private, use TLS and dedicated MQTT ACLs, and preserve state/intent separation and command expiry. Offline registry edits require stopping/restarting the backend.
- Do not assume modern Linux features exist on the thermostat. Historical config is not runtime evidence. Network isolation supplements application fixes.
- Keep licensing/provenance current and proprietary material out of public/source artifacts. Never publish or upload without authorization.

## Working conventions and handoff maintenance

Use the existing Python modules and pinned dependency workflow; Python currently runs on the host, not on the old ARM userspace. Share validation across HTTP/MQTT; do not introduce bypass paths. Add meaningful tests for new protocol/security behavior and run checks appropriate to the change. For artifact changes, verify deterministic outputs and secret exclusion. The source release must include `AGENTS.md`.

Record new evidence under `docs/research/`, protocol fixtures/tests under `tests/`, and decisions under `docs/architecture/`. Update `TODO.md`, relevant security/hardware docs and this handoff as facts change. Preserve historical validation reports or label replacements accurately; never report unperformed flashing, recovery, HAOS or HVAC tests as passed. Use local commits for reviewable milestones and leave the next agent a precise completed/pending/blocked status.

## Native telemetry handoff (2026-10-31)

An opt-in `--native-telemetry` profile now implements the bounded authenticated
NLE-style telemetry subset, separate from the older partial decoder. See
`docs/research/native-telemetry-2026-10-31.md` and `docs/protocol/nest.md`.
It projects only temperature/humidity/target/firmware; all commands are disabled
across HTTP/MQTT/core and discovery uses three sensors. Default runtime remains
canonical. HAOS selects it through private `native-telemetry.json` containing
only origin. Account buckets are ignored/unacknowledged, unknown values are not
backed up and native pairing/sleep/full subscription behavior remains unverified.
Host tests are not a real device exchange.

Owner deployment targets and securely entered SSH/MQTT credentials are private
under ignored `private/native-deployment-20261031`; never print or commit them.
HAOS SSH password authentication and modern `/local_apps`, `/app_configs` paths
were observed. MQTT auth/TLS passed using the owner-provided CA and explicit
legacy certificate-format compatibility (strict format flag only; all ordinary
peer checks retained). No broker restart/change. Dedicated backend CA/server
certificate and an empty registry are prepared privately. No thermostat loader
is armed, and no thermostat config has changed in this host milestone. Keep
pursuing actual HAOS/native integration rather than expanding the parked raw
rehearsal. Installation/entity creation and concrete device file rollback remain
pending until separately recorded.

HAOS deployment update: local Hearth app built/installed on amd64, started
manually, and authenticated HTTPS passed with its dedicated CA/IP certificate.
Automatic startup is disabled. Default suite: 471 passed/five optional skips;
fresh rebuilt-image broker/container subset: five passed. Actual HA entity
creation and physical native exchange remain unverified.

## Commissioning preparation follow-up (2026-10-31)

Read docs/research/native-commissioning-preparation-2026-10-31.md before the next
device work. Offline user-config reconstruction and root symlink metadata now
exist privately under private/commissioning-inventory-20261031; zero scanned CRC
failures. Live normal USB serial corroborated the captured assigned identity.
The byte-preserving credential/NTP editors are provisioning/native_settings.py.
The fresh private/native-commissioning-20261031-v1 contains five original and
replacement config/trust files, generated unique credentials (not enrolled), a
seven-day owner CRL and an explicit non-installable plan with unresolved gates.
No device writes/restart, backend enrollment or native connection occurred.
Do not publish private identifiers, hashes, credentials or owner network data.

The owner chose public NIST NTP; native ntpd already exists. They use UniFi and
confirmed existing IoT access to HA/MQTT. They will handle trusted-network rules
once connected. Stop expanding router-rule work and do not alter UniFi. Keep
certificate checks enabled. Remaining work is current-root/current-file checking,
filesystem commit/rollback, measured TLS candidate assembly and native settings
permissions/integration. The existing correction still forwards 0666; no new
permission correction or persistent installer exists. Do not claim these five
review files are ready to apply or resume general NAND research by default.


## Settings privacy follow-up (2026-10-31)

The current original correction now requests owner-only creation bits for its
exact native settings temporary file and fchmods the actual NSPR-backed file
handle to 0600 before any serialized write. This also handles existing temporary
files. Permission failure closes the descriptor, fails through the native open
path, preserves the destination and leaves retry dirty. Unrelated opens retain
their requested modes; there is no process-wide umask change. The prior GNU
29-case measurement validates only the preserved older candidate, not this new
build. Public native-handle declarations are pinned; required exports were
checked privately without running firmware on the host.

The synthetic RAM matrix is now 36 cases, adding new/existing temporary files
with umask zero, unrelated opens and injected fchmod failure/retry. ARM stat64
mode layout/syscall were checked against the existing pinned kernel header;
baseline 0600 checks fail if measurement ABI is wrong. Real native application,
flash, networking and actual credentials are absent. Preserve all executed old
profiles. Fresh checked profile and validation scope are recorded in
`docs/research/settings-permissions-preparation-2026-10-31.md`. No loader is
armed; obtain owner restart readiness before execution, under the existing
device-investigation authorization. Never reuse an output with a result.
