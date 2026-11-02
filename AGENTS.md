# Hearth: agent handoff and repository instructions

## Purpose and current status

Build a local-first Nest Learning Thermostat modification that preserves native hardware/HVAC control. Gen 2 is the primary target; Gen 1 is secondary. Prefer a verified local on-device interface if feasible; otherwise retain the native transport behind a minimal local backend. Do not rewrite HVAC control loops.

The user's unit has arrived and received USB intake on their PC. Arrival/ownership alone does not authorize flashing or physical control. The owner has explicitly authorized device investigation and requests advance notification for potentially dangerous actions such as flashing; preserve the backup/recovery gates below. The [2026-10-30 intake](docs/research/device-intake-2026-10-30.md) records enclosure `02A`, reported `Display-2.6`, firmware `5.9.4-5`, normal-mode USB `2464:0002` and an authorized manual restart briefly exposing OMAP `0451:d00e`. A later paced diagnostic RAM boot succeeded and returned to native startup. One supervised fixed scratch-block program/ECC/erase/restoration test subsequently passed with native USB return; the later nine-file commissioning is recorded below. HVAC operation and whole-firmware recovery remain untested. Two complete owner raw NAND captures and independently matching BCH-derived data views now exist privately; native nlclient/osm were reconstructed for static inspection. Programmed firmware-block and whole-chip restoration remain unverified.

On 2026-10-31 the owner confirmed this is their only unit and explicitly accepted
potentially dangerous same-unit work after asking why a spare was required. A
spare is therefore not mandatory for the recovery investigation. Prepare a concrete
same-unit recovery/installation plan, verify original inputs and partition/write
semantics, and notify the owner before any persistent write with its recovery
limits. This does not establish recovery or authorize physical HVAC switching.
The scratch-block experiment and the later owner-confirmed nine-file commissioning
have written NAND. The latter passed exact readback/native USB return; see the
CURRENT installation entry below. Actual restoration/HVAC remain unverified.

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

Settings privacy measurement update: source 68edfb9/profile-v2 executed ONCE and
all 36 cases passed, loader/collector zero. Candidate new/existing temporary
settings files became 0600 under umask zero; unrelated opens stayed 0666. Injected
fchmod failure preserved old settings and dirty retry then succeeded. Existing
I/O/allocation/binding/canary/log checks passed. Owner reported restart done;
normal USB 2464:0002 on 1-1 independently returned. No loader armed, installation
or actual settings changed. Preserve profile-v2/result and separate immutable
attempt-1-{prepared,observed,native-return}.json. See the dated permissions result.
The exact instrumented GNU candidate is measured; standalone no-trace/full
native application and filesystem install/rollback remain unverified. Next is
that narrow filesystem commissioning path, not more generic NAND research.

## File commissioning engine preparation (2026-10-31)

Read docs/research/file-commissioning-preparation-2026-10-31.md and
firmware/file_install/README.md. Original C transaction/adapter code now handles
the nine fixed files, preflight/staging/readback/journal/rollback, symlink/hardlink
and unsafe-mode refusal. It has host real-filesystem/sanitizer coverage and ARM
cross-compilation. No apply CLI, mount/USB/kernel writer, live snapshot/export,
backup receipt integration or after-reboot journal replay exists. Do not call it
with device roots or claim installation ready. Partial/incomplete rollback is
explicit; originals/journal stay in a private recovery directory.

Native startup is prepared through provisioning/native_startup.py: only start-as
changes to an original exec wrapper. It exports LD_PRELOAD inside the wrapper,
then execs native nlclient; stop executable and PID identity stay unchanged.
Do not put preload on start-stop-daemon itself. Captured native script mode is
0750, web library 0644, settings 0644; selected originals have UID/GID 0. The
private native-commissioning-20261031-v2 is now a nine-file review only, retaining
v1. Credentials are not installed/enrolled. Fresh current settings must be merged;
never blindly apply the stale capture-derived settings. Keep UniFi unchanged.

Prepared combined RAM diagnostic: private/file-commissioning-ram-20261031/profile-v6,
separate profile-v6-repro; helpers build/file-commissioning-ram-20261031/helpers-v4
and helpers-v4-repro. Seven artifacts/full RAM inventories match. It combines
36 checks of the exact GNU standalone no-trace settings candidate with 32 file
transaction cases on synthetic RAM roots only. Kernel has no MTD/block/RTC or
physical network; no native application/actual settings/credentials/mounts. The
RAM adapter rejects JFFS2; normal JFFS2 adapter is separate and unexecuted.
All 29 required libc imports were checked privately. No loader is armed and no
profile has executed. Use firmware/file_install_probe/boot.sh offline; future
PTY flag is --execute-experimental-file-ram-lab only after owner restart readiness.
Preserve final profile/results and use a fresh attempt record; no automatic retry.

Final host validation for this preparation: make check passed; full default suite
564 passed/five unchanged optional integration skips; 62 focused new checks pass.
Public report: docs/security/validation-2026-10-31-file-commissioning.json. The
normal adapter refuses unsupported/nonempty extended-attribute queries; the
future JFFS2 kernel must expose those attributes. RAM-only builds may accept
EOPNOTSUPP on their memory filesystem. Profile-v6 remains unexecuted, with no
file-result.jsonl. The review bundle/host tests do not enable device writes.

## Combined file RAM attempt / current transport correction (2026-10-31)

Profile-v6 executed ONCE using 5ba411d. Three files transferred; collector exited
1 with bounded/owner-only capture error and no file-result.jsonl. A single bounded
read-only cached trace (zero device writes) retained repeated report prefixes
without footer. All private attempt-1-{prepared,observed,native-return}.json,
cached trace and diagnostic chunks are preserved. Owner confirmed home icon;
normal USB 2464:0002 independently returned. No loader armed or installation.
No 68-case matrix pass is established. Never reuse v6/repro; retrospective
execution-started marker now records the attempted profile despite no result.

The corrected supervisor retains cached TX offset on EAGAIN/EINTR instead of
restarting at byte zero. The receiver handles restarted prefixes and preserves
bounded partial evidence. Wrapper writes/fsyncs an exclusive execution marker
before loader launch and refuses any old marker even without a result. Workload,
controller/kernel/boot stages/native libraries/candidate are unchanged. New host
regressions cover 20479-byte queue backpressure, interrupted transmission,
restarted/oversized frames and execution-marker files/symlinks. Make check and
569 host tests pass, with five unchanged optional skips.

CURRENT fresh unexecuted profile: private/file-commissioning-ram-20261031/profile-v7;
repro profile-v7-repro; helpers build/file-commissioning-ram-20261031/helpers-v5 and
helpers-v5-repro. Seven artifacts/full inventories reproduce, rootfs 11045344,
image 6034056 bytes. Prepared-v7.json is separate and immutable. Notify and obtain
owner restart readiness before a new PTY-backed --execute-experimental-file-ram-lab
attempt. No automatic retry. See docs/research/file-commissioning-attempt-2026-10-31.md.

## Second combined attempt / dispatch-corrected preparation (2026-10-31)

Profile-v7 executed ONCE using 7c1572c. Report transport now completed: 20816 bytes,
77 rows saved privately. All 36 standalone storage component cases, two zero
statuses, bindings/canaries and log checks independently validate. Separate
attempt-2-storage-component.json discloses its derived component completion
while preserving the original global false report. The exact standalone GNU
shim now has bounded RAM measurement; full native app remains unverified.

The file process exited 109 with zero file-case rows: supervisor argv named
/file-test but raw exec still used literal /settings-test. Corrected via exec.h,
which executes argv[0] with its same argv/env; injected-exec sanitizer regression
checks the actual adapter. Collector now distinguishes file-process failure.
No 68-case combined pass or ARM file-engine measurement is established yet.
Owner confirmed home icon and normal USB independently returned. No loader armed.
Preserve profile-v7/result/marker and immutable attempt-2 records. Never reuse it.

Third-attempt profile: private/file-commissioning-ram-20261031/profile-v8;
separate profile-v8-repro; helpers build/file-commissioning-ram-20261031/helpers-v6
and helpers-v6-repro. Seven artifacts/inventories match, rootfs 11045344 bytes,
image 6034042 bytes. Make check and 570 host tests pass/five optional skips.
Workload/storage candidate/kernel/boot chain/native libraries are unchanged;
only supervisor dispatch and clearer failure classification changed. Obtain owner
restart readiness before a new --execute-experimental-file-ram-lab PTY attempt.
No automatic retry. Actual filesystem/kernel installer integration remains pending.

## CURRENT: combined RAM commissioning matrix passed (2026-10-31)

Profile-v8 executed ONCE from a0bc948: loader/collector zero, complete private
22123-byte/108-row report independently validated, all 36 standalone settings
and 32 file transaction cases passed, three zero child statuses. Synthetic
secret logs absent in candidate; passthrough/bindings/canaries/readback passed.
Owner confirmed home icon after command exit; normal USB independently observed.
Immutable attempt-3-{prepared,observed,native-return}.json retained privately;
creation manifests and earlier failures remain unchanged. No loader armed.
Never reuse v6/v7/v8 or their repro copies. Host baseline remains 570 passed,
five optional skips and make check; no source changes occurred during this run.

This closes the bounded ARM RAM file-engine measurement and standalone settings
shim comparison. It does not close actual JFFS2 durability, journal replay after
reboot, live active-root/current-settings verification, fresh snapshot export
and durable host receipt, native application startup/transport, or HVAC gates.
Next: integrate a narrow filesystem snapshot/backup/commissioning path using the
pinned existing stack, preserving write protection until a reviewed write step.
Do not repeat generic raw recovery work or add router configuration requirements.
See docs/research/file-commissioning-attempt-2026-10-31.md for historical failures
and the successful result. No firmware/configuration installation occurred.

## CURRENT: protected filesystem snapshot prepared (2026-10-31)

The successful 68-case matrix remains the hardware baseline. New original
read-only capture code is firmware/file_install/snapshot.{c,h}; it shares the
fixed nine-target header with the file adapter, follows no symlinks, rejects
unsafe metadata/attributes and double-reads into caller-bounded RAM. Production
requires JFFS2 plus ST_RDONLY; host lab bypasses only filesystem/mount identity.
The separate firmware/file_snapshot/ profile links no native firmware and no
file mutation adapter. It mounts mtd:root0 and mtd:user-config read-only,
noatime/nodev/nosuid/noexec, retaining hardware WP/status/NAND_ROM/write callback
guards and skipped BBT scanning. Block/MTD char/network/RTC remain disabled.
Xattr/ACL/security handlers are enabled rather than hiding unsupported metadata.
The pinned platform partition table is used; command-line overrides bypassed.

provisioning/file_backup.py now durably preserves the exact nine-file snapshot
and returns a host custody receipt only after fsync and byte readback. Receipt
binds session, collection scope, source-root label and manifest; verification
rechecks complete inventory, metadata and all bytes. This is NOT a target-writer
acknowledgment, actual installation plan, active-root proof or recovery proof.
USB execution still cannot install anything. Interrupted-install replay remains
pending. The shared target header is included in the prior RAM lab source hashes.

Local profile: build/file-snapshot-20261031-v4, unexecuted. Earlier v1/v2 failed
offline compiler/kernel linking; v3 passed offline, v4 adds exact known-patch
rebuild support. All prior trees/logs retained, none executed. The build uses
unchanged validated heartbeat bootstrap bytes and original freestanding init.
Finalized checker verifies kernel image/config/CPIO and all staged host recipes.
Run dry: python3 -m firmware.file_snapshot.run BUILD. Supervised explicit flag:
--execute-read-only-file-snapshot with a fresh private output, PTY, normal USB
preflight and owner-timed restart. Exclusive fsynced build execution-started
marker prevents profile reuse; no automatic device retry. No loader armed.

Before installation, obtain fresh native partition selection: our root0 mount
and RAM cmdline cannot establish native active root. Owner was asked for a
sanitized Technical Info.plist read (loads(stdin.buffer.read()), not load(pipe)).
Do not enable diagnostic disk writes. Keep USB connected and base detached.
After any future run exits, confirm home icon and normal USB independently.
See firmware/file_snapshot/README.md and the dated snapshot-preparation note.

Snapshot preparation validation: make check passed; full host suite 623 passed,
five unchanged optional integration skips. Six artifact digests and staged host
recipe checks match after a second isolated offline build (KBUILD_BUILD_VERSION=1).
CPIO 7096 bytes, uncompressed kernel 2881632 bytes. Profile-v4 remains unexecuted.
Owner supplied a fresh sanitized native plist result: primary, firmware 5.9.4-5;
recorded privately with source attributed to the owner terminal. Normal native
USB is still required at the eventual run preflight. No loader is armed.

## CURRENT: first protected JFFS2 snapshot succeeded (2026-10-31)

Source c73904e/build file-snapshot-20261031-v4 executed ONCE. PTY session 76980
has exited zero; no loader/collector remains. Complete private frame 81320 bytes,
nine targets (seven existing, two absent), strict session/CRC/footer and custody
receipt/readback accepted. Independent saved-frame decode/full backup verify
passed; all seven fresh original byte strings match offline v2 review.
Private output: private/file-snapshot-20261031-attempt-1/{capture.bin,backup/,
attempt-observed.json,review-comparison.json}. Preserve all; never reuse v4 or
remove its fsynced execution marker. No persistent configuration was installed.

Owner was prompted to restart after exit; native home icon/USB return is PENDING.
Do not arm another loader. On owner confirmation, independently require native
USB and record a separate immutable native-return observation, then update the
public result doc. Source label is custom root0 view; owner separately reported
fresh primary/5.9.4-5 native plist before execution.

This closes bounded read-only JFFS2 mounting/file capture and host custody
measurement, not writer receipt enforcement, plan binding, after-reboot journal
restore, actual installation, native app/transport, whole-firmware recovery or
HVAC. Next implement those narrow commissioning pieces; no generic raw capture
or repeat scratch experiment needed. See the filesystem-snapshot result doc.

Snapshot native return confirmed: owner reported home icon after manual restart,
and require-native independently observed normal USB on port 1-1. Separate
private/file-snapshot-20261031-attempt-1/native-return.json is immutable. Earlier
pending-return notes are historical and now closed. No loader is armed.

## CURRENT: interrupted-install restoration prepared for RAM (2026-10-31)

Snapshot native return is confirmed as above; unit is left at native startup.
Original hearth_posix_restore_files API now validates the entire fixed journal/
plan/current tree before mutation, reconstructs only exact/prefix-checked staged
files, restores originals in reverse, and keeps staging if restoration fails.
Unknown journal.new is preserved and reported through journal_error while
otherwise possible original restoration proceeds. All result fields matter.
Missing existing names require durable committing/restoring intent plus an exact
backup; unrelated absence or changed bytes fails closed. No installer CLI, mount
launcher, target receipt enforcement or device writer is implemented by this API.
Twenty-four host ASan/UBSan interruption/retry/refusal scenarios pass. Process
exit is not hardware power loss. Actual JFFS2 write/recovery remains unmeasured.

The combined RAM profile now has a strict 91-case v2 contract: 36 settings, 32
transaction and 23 recovery scenarios (host xattr case 14 excluded from RAM).
Historical 68-case results can be parsed only with require_recovery=False and
cannot satisfy the new default. The file helper includes fresh child-process
interruption scenarios; all 32 native libc imports were statically corroborated.
Storage shim, 34 base libraries, bootstrap and no-MTD/no-physical-network kernel
are unchanged. Only explicit RAM mode tolerates RAM xattr EOPNOTSUPP; production
still requires observable empty attributes and JFFS2.

Fresh unexecuted profile: private/file-recovery-ram-20261031/profile-v2, separate
profile-v2-repro. Helpers build/file-recovery-ram-20261031/helpers-v1 and -v1-repro.
All seven artifacts/full inventories match: rootfs 11052100, image 6035848 bytes.
Preserve superseded unexecuted profile-v1; never use a repro as an automatic retry.
Make check and 653 host tests pass, five unchanged optional integrations skipped.
Dry wrapper checks passed. No loader is armed; obtain owner restart readiness
before the explicit --execute-experimental-file-ram-lab PTY run. Keep base
detached and USB connected; after command exit confirm home icon and native USB.
See docs/research/file-recovery-preparation-2026-10-31.md. Next target-writer
receipt/plan binding, bounded JFFS2 integration and actual native state exchange.

## CURRENT: all 91 ARM RAM cases passed (2026-10-31)

Source aaf93b7/profile file-recovery-ram-20261031/profile-v2 executed ONCE.
PTY session 9876 exited zero; no loader/collector remains. Complete private
23240-byte/131-row report independently revalidated: 36 settings, 32 file
transactions, 23 interrupted-install recoveries, three zero child statuses.
Original/candidate bindings/canaries/log and strict evidence checks passed.
Private attempt-1-observed.json and attempt-1-native-return.json remain immutable,
alongside original profile/result/marker/manifests. Owner confirmed home icon
and normal USB independently returned on port 1-1. Never reuse v2/repro.

This closes bounded ARM RAM restoration measurement only. Host xattr fixture14
is intentionally separate; no actual JFFS2 writes, hardware power loss, firmware
installation/restoration, native app/transport or HVAC was measured. Next exact
replacement-plan/host-receipt binding, capsule validation and narrowly bounded
JFFS2 writer integration. Advance notice before persistent work remains required.
See docs/research/file-recovery-result-2026-10-31.md. Host baseline unchanged:
653 passed, five optional skips, make check. Unit left at native startup.

## CURRENT: exact-plan private data capsule prepared (2026-10-31)

provisioning/file_capsule.py now binds verified source snapshot custody to a
canonical actual nine-file replacement plan and separate plan-bound backup
receipt. It enforces fixed targets, modes, missing new paths, expected snapshot
session and observed primary/5.9.4-5 profile. Check requires an external plan pin
and revalidates complete private inventory/bytes/custody/header. This is original
data-only preparation, no executable installer or target acknowledgment.
Nineteen new tests; make check and 672 host tests pass/five optional skips.

Actual private output: private/native-file-capsule-20261031-v1 and -v1-repro.
All 23 files reproduce; generated data header 876529 bytes. Original/replacement
digests and metadata match the preserved nine-file review. Fresh settings/NTP/
startup edits independently regenerate identically. Dedicated CA/CRL validates
current backend certificate at host time. No installation or native TLS exchange
was performed. Machine-local original preparation recipe:
build/prepare-bound-file-capsule-20261031.py; it refuses existing output.
Do not publish capsule bytes, credentials, identifiers or binary digests.

Owner has only display/base/USB. A stock battery-only check with the completely
unwired base reached Wi-Fi setup; owner left Wi-Fi unconfigured, detached base
and reconnected USB. Normal USB independently observed afterward. Private
bench-battery-result-20261031.json preserves source attribution. Battery health
and sustained Wi-Fi runtime remain unmeasured; no transformer is assumed needed
for the first short attempt. Unit is back at home icon; no loader armed.

Next: actual bounded filesystem writer integration and target-side plan/receipt
enforcement, including flush/unmount/protection and exact restoration. Existing
91-case RAM pass and read-only JFFS2 pass are separate evidence; no persistent
JFFS2 file installation, hardware power-loss recovery, actual native transport
or HVAC proof. Notify before persistent action under the owner's authorization.
See docs/research/file-capsule-preparation-2026-10-31.md.

## CURRENT: paired file-action images checked, unexecuted (2026-10-31)

The bounded writer is implemented under firmware/file_writer/. Its separate
kernel starts protected, registers only fixed root0/user-config and checks
plan/host-custody binding before enabling bounded write callbacks. Actual I/O
adapter sanitizer tests cover synchronous erase request lifetime and callbacks
after WP restoration/mutex release. The legacy JFFS2 remount compatibility check
now examines requested flags; unknown RO-compatible nodes must block writes.
The existing read-only profiles/verifiers remain separate.

Root-only capsule action runs after 56 synthetic UID/GID65534 RAM cases, strict
host ACK and real-file read-only preflight. It then waits for a separate bound
commit/abort. The host repeats full image/capsule/backup validation; no automatic
commit/retry. Any writable remount counts as potential persistence. Unmount comes
before sealing WP; complete requires exact post-operation read-only verification.
Restore has its own read-only journal inspection, image and commit. An explicitly
reviewed --recover-from entry permits restore from the matching exited persistent
RAM session without native boot; it rejects stale ROM and other plans.

Prepared: build/file-writer-kernel-20261031-v3 (six artifacts match rebuild),
build/file-writer-actions-20261031-v4 and -v4-repro (five helpers match),
private/file-writer-20261031/{install,restore}-v1 and their reproductions. The
separate private reviewed plan pin is native-file-capsule-20261031-v1-pin.json.
All are unexecuted. Older drafts remain preserved, not usable execution evidence.
make check and 766 host tests pass/five optional skips. No proprietary firmware
executes on host. No JFFS2 install/restore, hardware power-loss, whole-firmware
recovery, live native transport or HVAC claim.

Next: notify owner and obtain restart timing readiness for one supervised
write-capable RAM preflight, PTY-backed, no writes until separate decision.
If stock startup changed selected bytes, preserve the same-session fresh
read-only snapshot, stop and rebuild a reviewed plan. After any uncertain
persistent result, keep USB power/base detached and review evidence before
restart; never reflexively request native startup. No loader currently armed.
See docs/research/file-writer-preparation-2026-10-31.md and the writer README.

## CURRENT: first writer preflight refused changed settings, zero writes

Source a7eff49/install-v1 ran once. All 56 ARM selftests passed with zero child
status and no diagnostics. Real-file preflight refused target7 settings.config;
only that target's bytes differed, selected metadata and other eight targets
matched. No commit, window opening, RW remount or transaction; all four NAND
counters zero. Gate sealed/WP asserted, safe restart reported. Same-session
protected snapshot and host custody independently verified. Owner restart done;
normal USB independently observed. No loader armed. Never rerun install-v1.
Private evidence: file-writer-20261031/preflight-attempt-1, including native-return,
changed-files-backup and refreshed-snapshot. Immutable originals preserved.

New v2 capsule and repro regenerate only credential spans against fresh settings;
the other eight payloads are identical. New pin native-file-capsule-20261031-v2-pin.json;
kernel build/file-writer-kernel-20261031-v4, helpers build/file-writer-actions-20261031-v5
and -v5-repro, paired private/file-writer-20261031/{install,restore}-v2. Unexecuted.
The first RAM pass does not validate persistent callbacks/installation/restoration.

Actual device now enrolled in HAOS's existing registry with the capsule's private
credential. Fresh remote registry preserved, app stopped, bytes rechecked,
replacement staged/read back/atomically moved/read back, app restarted. No broker
restart/change. Host synthetic authenticated native entry passed TLS/HTTP200;
not physical traffic. Private evidence native-deployment-20261031/actual-enrollment-20261031.
Do not restore initial registry over this newer state or rotate capsule credentials
without rebuilding the exact private plan. Native telemetry mode still disables
all commands. Next refreshed owner-timed RAM preflight; persistent commit needs
its own advance notice/timing readiness. See the dated preflight result.

## CURRENT: second zero-write refusal; retain sealed RAM for snapshot handoff

534e0b0/install-v2 ran once: all56 selftests pass, target7 changed again,
zero commit/window/RW remount/transaction/counters, sealed WP, safe restart.
Fresh capture/custody saved at private/file-writer-20261031/preflight-attempt-2.
The owner reported the ROM sequence done. **Do not request native startup now**:
unit remains in sealed RAM with USB connected/base detached. XML inspection
confirms identical keys/values between recent snapshots despite changed bytes.
Native boot can invalidate exact-byte originals by rewriting serialization.

New explicit --handoff-from accepts only a completed verified zero-write snapshot,
all56 selftests, consistent execution/result, no decision files, sealed WP, exact
new-capsule source-frame match and verified custody, with known RAM USB identity.
No native/stale-ROM entry or automatic retry. Owner still times a fresh restart.
Eight host tests cover it. Existing --recover-from remains restore-only for a
recorded potentially persistent failed attempt; these are distinct entry reasons.

Fresh private v3 capsule/repro and v3-pin bind attempt2's capture; kernel v5,
helpers v6/repro and paired images v3 are checked/reproduced and unexecuted. Credential unchanged,
backend enrollment already matches. Prior images/results are historical and
must not be rerun. Next checked owner-timed RAM snapshot handoff, no persistent
commit until separate advance notice/timing readiness. No installation/restore
or live physical transport/HVAC claim. See the preflight-result follow-up.
make check and 774 host tests pass/five optional skips; no further source test
rerun is required for documentation-only updates. Next boot command, only after
owner readiness, PTY: .venv/bin/python -m firmware.file_writer.run boot
private/file-writer-20261031/install-v3 private/file-writer-20261031/restore-v3
private/file-writer-20261031/preflight-attempt-3 --execute-writer-preflight
--handoff-from private/file-writer-20261031/preflight-attempt-2.
No persistent commit is part of that readiness request.

## CURRENT: first nine-file installation passed; Wi-Fi bench pending

Source c4dc064/install-v3 ran once via the explicit verified snapshot handoff from
attempt2. All56 ARM cases and real-file read-only preflight passed. Host paused;
owner received concrete scope/power-loss/native-startup/recovery limits and
explicitly replied Ready—run the install. Separate persistent commit rechecked
exact capsule/backup/restore/image, durably recorded intent, then sent once.
The full strict result passes: attempted511, committed1, both RW remounts,
no transaction/journal/cleanup/release/unmount/seal errors, exact post-unmount
read-only verification, gate sealed/WP asserted, safe restart. Actual94 page
programs, zero erase/OOB operations/failures. Source original bytes remain private.

Owner restart done; normal USB independently observed and private native-return
saved. Never rerun install-v3; no restore image executed. Preserve all attempt3
creation/execution/selftests/preflight/decisions/result/review/native-return.
**Device now has the local endpoint/CA/CRL/credentials/NTP/settings shim/startup
wrapper installed. Do not treat it as stock or restore initial backend registry.**

First Wi-Fi bench: backend is enrolled and telemetry-only, commands disabled.
Owner was asked to detach USB, fit completely unwired base and use normal Wi-Fi
setup on the dedicated IoT SSID, entering password only on the thermostat.
Read-only host watch runs as session81437, private output
native-deployment-20261031/native-wifi-bench-20261031-attempt-1-corrected-watch.
It polls manager status, prints only availability/state field names, sends no
commands. The earlier watch used an incorrect `online` field; stopped and
replaced with actual Core.view `available`. Its saved raw private status remains
valid evidence; its printed online flag is not availability proof.
User's screen/Wi-Fi result and physical telemetry are pending. No loader armed.

Actual restoration, hardware power loss/whole-firmware recovery, erase/OOB paths
in this writer, native app/TLS/time/transport and HVAC remain unverified. Native
startup can rewrite settings: old exact-byte restore preflight may refuse later
changed app data. Preserve fresh read-only evidence/review recovery; do not bypass
its checks. See docs/research/file-install-result-2026-10-31.md. Host774/five skips,
make check passed before documentation-only result updates.

## CURRENT: native UI stuck; protected startup diagnostic prepared

Owner attempted unwired-base/battery Wi-Fi setup after installation; steady home
icon persists even after their reboot, LED blinking GREEN. No Wi-Fi settings.
Backend watch ended with no availability/state telemetry. Treat possible native
startup regression, not successful app/network commissioning. Blinking green
indicator reference recorded in docs/research/startup-stall-2026-10-31.md.
Owner detached base/reconnected USB on request; native USB independently observed.
No loader armed. Do not keep requesting native restarts or make guessed fixes.

New firmware/startup_diagnostic reader is original static code, no native firmware
execution. Reuses unchanged protected build/file-snapshot-20261031-v4 kernel with
raw uncompressed external newc (BLK_DEV_INITRD=y,RD_GZIP=n). Reads current nine
files and bounded mtd:log tails; no data-partition mount, symlinks, FIFOs/devices,
network, MTD char/block or writable callbacks. WP remains asserted. Limits64files,
64KiB each,512entries,depth4; incomplete/limit status explicit. Captures may hold
identifiers/credentials; retain private, never print raw log lines or publish.

Profile private/file-writer-20261031/startup-diagnostic-v2 and -v2-repro: eight
artifacts match; original build/startup-diagnostic-20261031-v2. Unexecuted.
Twelve new host checks incl ASan/UBSan real trusted-host filesystem reader,
symlink/FIFO/tail/limits and strict private frame parsing. make check and full786
tests pass/five optional skips. No firmware executes on host. Older draftv1 remains.
Next obtain timing readiness, then PTY:
.venv/bin/python -m firmware.startup_diagnostic.run
private/file-writer-20261031/startup-diagnostic-v2
private/file-writer-20261031/startup-diagnostic-attempt-1
--execute-read-only-startup-diagnostic
Notify before boot; prompt reviewed manual restart only after loader waits.
No persistent write/restore or native app launch is part of this diagnostic.
Inspect current file comparisons/log evidence privately before proposing a fix.

## CURRENT: original selected files restored, stock UI check pending

50fe8ff/startup-diagnostic-v2 ran once: fixed9 current bytes/modes all matched
installed payloads.64 log tails captured; count limit reached, partial logs show
no identified loader/crash error. This does not diagnose/exclude a cause. Native
code/flash writes disabled in that diagnostic. Evidence startup-diagnostic-attempt-1.
Unit stayed RAM/USB/base detached; no native restart between capture and restore.

Owner chose restoration preflight, then explicit separate Ready—restore now
after scope/recovery/power-loss notice. restore-v3 ran once from matching recorded
persistent attempt3 via --recover-from. All56 selftests and actual RO journal/
original/current-file preflight passed; separate commit rechecked backup/images.
Full strict restore result: attempted511/restored511/committed0, no errors,
exact original bytes/modes and absence of new wrapper/shim verified after unmount,
sealed WP, safe restart.41 page programs, zero erase/OOB/failures. Host exited0.
Preserve restore-attempt-1 all decision/result/restoration-review evidence.
Never rerun restore-v3 or startup-diagnostic-v2. No loader armed.

**Device's nine selected files are now original again; Hearth wrapper/shim absent.**
Backend enrollment/private credential remains retained; do not roll back its registry.
Selected-file backup/journal directory remains on-device; not an untouched raw
filesystem restoration. Whole-firmware/power-loss/damaged-JFFS2 recovery unverified.

Owner was asked to disconnect USB, fit completely unwired base, full10sec hold,
release/single press and report Wi-Fi setup vs home icon; leave Wi-Fi unconfigured.
Stock UI outcome is PENDING. Do not claim restored app health from RO byte readback.
If stock UI returns, isolate runtime integration in RAM before another installation;
no guessed persistent patch. If not, investigate native compatibility/recovery
evidence before further changes. Host786/five optional skips, make check. See
docs/research/file-restore-result-2026-10-31.md.

## CURRENT URGENT: compression recovery checked and authorized, not yet armed

Stock UI still home/green after restoration and2min/briefpress. Owner worried
about bricking; explained ROM/RAM still functional and originals preserved,
native UI unusable, recovery not yet proven. Owner reconnected USB/base detached;
native USB observed. No loader running yet.

Concrete cause: captured native messages contain7 unsupported compression0x07
and7 paired decompression errors.0x07=LZO. Old writer used priority/LZO80 before
zlib60/rtime50. Byte reads under that kernel did not prove native readability;
old byte restoration could rewrite the same incompatible format. Agent admitted
the missed compatibility check and apologized. **NEVER EXECUTE old priority
writer/restore images.** Current verifier refuses them. Original firmware/kernel/
bootloader partitions outside fixed root0/user ranges remain untouched.

Correction checked: kernel build/file-writer-kernel-20261031-v6 (all6 artifacts
reproduce) requiresNONE and hard-forces compressor dispatchNONE; keeps LZO reads.
Read-only per-inode ioctl audits active flash headers/CRC/type/inode andNONE/ZERO.
New mandatory encoding_verified prevents byte-only completion/restart claims.
New explicit action3 forces7 originals and7 rollback copies/journal into fresh
nodes even if bytes match, preserving modes and absence of shim/wrapper. Strict
preflight checks journal, original-only state, backups, fixed archive inventory
and bounded known temporary prefixes. No guessed offsets/raw writes.

helpers build/file-writer-actions-20261031-v7 and -v7-repro (7programs match);
private/file-writer-20261031/reencode-v1 and restore-none-v1 with separate repros
(7artifacts eachmatch). All unexecuted.66-case RAM workload=prior56+10reencode.
make check814tests/five optional skips;15 actual-audit-header sanitizer cases.

**Owner explicitly replied Ready—run checked recovery** to the concrete conditional
plan: after restart run66 RAM checks+real RO preflight; if they pass, manually
send action3 persistent commit. This covers the commit timing/authorization;
do not ask it again. Keep USB/base detached, no restart/unplug during writes.
Next PTY:
.venv/bin/python -m firmware.file_writer.run boot
private/file-writer-20261031/reencode-v1 private/file-writer-20261031/restore-none-v1
private/file-writer-20261031/reencode-attempt-1 --execute-writer-preflight
Prompt10sec hold/release/press only afterloaderwaits. After66+READY check, explicit
localdecision .venv/bin/python -m firmware.file_writer.run decide
private/file-writer-20261031/reencode-attempt-1 --execute-persistent-original-reencode.
Never auto retry. Review original bytes+encoding+WP/cleanup before native startup;
unknown result means retainUSBpower/no reboot. Native UI recovery is unproven.
See docs/research/compression-recovery-2026-10-31.md.

## CURRENT URGENT: reencode preflight refused with zero writes; retain RAM

7d313cb/reencode-v1 ran once. All66 ARM cases passed, real preflight refused:
initial_error2/target-1/snapshot_available0. No commit/window/RW remount/transaction,
all NAND counters0, sealed gate/WP1/safe_to_restart1. Host exited0. Evidence private
file-writer-20261031/reencode-attempt-1. **No compression repair write happened.
Never rerun reencode-v1. Unit stays sealed RAM/USB/base detached; do NOT request
native startup.** No loader armed.

New numeric diagnostic/snapshot_target fields and private bounded kernel-log
frame identify future refusal stages; checks/write behavior unchanged. Explicit
--resume-from-readonly accepts only matching completed sealed zero-write action3,
all66 selftests, no decisions, same capsule/pin/kernel and known RAM identity.
Prior frozen source is evidence only, never executed. Wrong plan/kernel, possible
writes, native/staleROM and bad evidence refused.823tests/five skips/make check
pass. helpers v8/repro, paired private reencode-v2/restore-none-v2/repros checked,
reproduced and unexecuted. Kernelv6 unchanged. No native firmware executes on host.

Next owner-timed restart (timing readiness pending), PTY:
.venv/bin/python -m firmware.file_writer.run boot
private/file-writer-20261031/reencode-v2 private/file-writer-20261031/restore-none-v2
private/file-writer-20261031/reencode-attempt-2 --execute-writer-preflight
--resume-from-readonly private/file-writer-20261031/reencode-attempt-1
Existing conditional recovery authorization remains: only after66+realROchecks
pass manually send --execute-persistent-original-reencode. If refused, inspect
numeric fields/private kernel-log.bin, never raw log lines in public/model output,
before another fix/write. Do not weaken preflight to force progress.

## CURRENT URGENT: second refusal identifies settings; v3 checked, readiness pending

1f9388c/reencode-v2 ran once: all66 cases pass, no writes/decision, sealed WP,
initial_error2/diagnostic101 (base restore preflight)/snapshot_target7, no snapshot.
8473 private kernel-log bytes preserved, no observed mount/ECC/JFFS2 errors in
that captured kernel tail. This narrows unreadable/unexpected settings.config,
not proof it is absent. Never rerun v2. Current unit stays protected RAM on USB,
base detached. No loader running. Owner again asked recoverable; candidly said
likely software-recoverable with ROM/RAM/backups intact, native UI not yet proven.

New action3-only preflight permits truly absent settings at a complete RESTORED
journal/mask511 only with exact original backup. Ordinary restore stays strict.
All other foreign/missing originals remain refused unless old durable in-progress
intent applies. Source has 3 new cases: missing settings reconstructs, missing
other original refused, settings symlink refused; present foreign data already
refused. New preflight INFO frame records missing-original mask/settings state/
NONE policy before READY. Host action3 cannot commit without validated INFO.
69 RAM cases now (prior66+3); current ACK requires69. Historical sealed zero-write
resume validates old66 only against its frozen manifest, not as current readiness.
Reporter also preserves settings_state on refusal. No raw settings/logs printed.

831 host tests/five skips/make check. Same kernelv6; helpers v9/repro, paired
private/file-writer-20261031/reencode-v3,restore-none-v3/repros checked/reproduced,
unexecuted. Next ask timing readiness for fresh RAM handoff (no native reboot):
.venv/bin/python -m firmware.file_writer.run boot
private/file-writer-20261031/reencode-v3 private/file-writer-20261031/restore-none-v3
private/file-writer-20261031/reencode-attempt-3 --execute-writer-preflight
--resume-from-readonly private/file-writer-20261031/reencode-attempt-2
After69+INFO+RO READY verify missingmask0or128/settingsstate0or1, archive/plan
checks pass, then manually commit prior conditional authorization with action3.
Never bypass foreign-state checks. No compression repair write has happened yet.

## CURRENT URGENT: compression correction passed; stock UI check pending

e90c8ba/reencode-v3 ran once via zero-write RAM resume from attempt2. All69 ARM
cases passed. Actual RO preflight INFO confirmed missing settings only (mask128,
state1, NONE policy), with exact saved original/journal/backups and other files
verified. Under owner's prior explicit conditional recovery go-ahead, manually
sent action3 commit after independent host recheck. No repeated permission ask.

Strict result complete1/restored511/attempted511/committed0, verified1 AND
encoding_verified1, no errors. Recreated original settings, rewrote seven original
files/seven rollback copies/journal uncompressed, maintained absence of added
wrapper/shim. Post-unmount fresh RO active flash-header audit passed for selected
files/rollback/journal; sealed WP1, safe restart.120 page programs,2erases,2markers,
0failures. Host exited0. Private reencode-attempt-3 includes independent review
and all immutable originals/decisions; never rerun reencode-v3. No loader running.

Owner was asked to unplug USB, fit completely unwired base, full10sec hold,
release/singlepress and allow2min for native UI; leave Wi-Fi unconfigured. Their
response is PENDING. Do not claim native recovery until interactive UI observed.
If UI returns, preserve actual result, then recapture fresh native originals
before recommissioning; old .hearth-rollback remains on-device, must be preserved/
retired safely before a new install. Backend enrollment retained but device is
stock-configured again. No physical native network/HVAC proof. Host831/five skips,
make check unchanged. See compression-recovery observed follow-up.

## CURRENT: working primary native UI recovered; prepare safe recommissioning

Owner explicitly confirmed working UI after reencode-attempt3, left Wi-Fi
unconfigured, detached base and reconnected USB. Native USB independently observed.
Owner's filtered read-only plist confirms primary/5.9.4-5. Thus original UI recovery
is demonstrated on the repaired primary, not fallback. Private native-ui-return.json
and native-selection-after-recovery.json preserve attribution. No loader armed.

Next preserve a fresh read-only snapshot of current native originals before
recommissioning. Keep the old .hearth-rollback and host custody intact. Prefer a
plan-derived archive namespace for the new install rather than deleting/overwriting
the recovery archive. Force NONE writes and active flash-header checks remain
mandatory. Do not rerun old priority images or claim networking/HVAC verified.
Backend registration remains matching the private planned credential, device is
currently stock-configured and Wi-Fi unconfigured. Source831/five skips baseline.


## Current preparation after recovery: preserve the legacy archive

Primary/5.9.4-5 was reconfirmed by the owner's filtered USB plist. Device remains
stock-configured, USB connected/base detached. No loader running or write armed.
New optional capsule archive_layout=1 binds a plan-derived rollback directory;
legacy layout0 remains byte-compatible with old capsules. Never delete/overwrite
.hearth-rollback to recommission. New synthetic cases exercise preservation of
that archive, new-plan install/restore, collision refusal and wrong-plan refusal.
The current protocol/helper/profile gate is72 cases (56+16); historical69 only
serves frozen evidence and cannot authorize a current write.

New --handoff-from-snapshot accepts only a completed, source-checked protected
startup diagnostic, execution/session binding, identical capture bytes, verified
backup custody and known RAM USB mode. It permits the owner-timed direct RAM
restart without an intervening native startup changing settings. It does not
commit or bypass current RAM/real-file checks. Fresh source/profile/kernel/helper
builds are required; all executed recovery profiles remain immutable and must not
be rerun. Next prepare a fresh protected snapshot, then new capsule and matching
NONE/auditor install/restore pair. Physical networking remains unverified.


Validation for this preparation: make check passes; full host suite852 passed,
five optional skips. Seven ARM helper programs reproduce at
build/file-writer-actions-20261031-v10 and its -repro path, bound to the old
capsule only for compilation review (not a new installation image). Fresh pure
read-only startup-diagnostic-v3 and -repro profiles reproduce all eight artifacts,
based on unchanged protected snapshot kernelv4. No target execution yet.
Fresh snapshot profile: private/file-writer-20261031/startup-diagnostic-v3.
Suggested fresh output: private/file-writer-20261031/post-recovery-snapshot-attempt-1.
Owner readiness question is pending. Do not arm before reply; after capture,
leave protected RAM rather than reboot native before constructing the new plan.
The read-only runner's new execution.json binds source/session for that handoff.


## CURRENT: corrected nine-file install passed; native UI check pending

Source78ad40d protected startup-diagnostic-v4 ran once, saved fresh nine-file
snapshot and custody under private/file-writer-20261031/post-recovery-snapshot-attempt-2.
Attempt1 timed out before reported transfer, preserved; never rerun either profile.
Log tail capture limited64 files (partial log view). Recovered originals allmatch
old except settings, whose metadata is unchanged; new shim/wrapper paths absent.
Fresh credentials editor preserved unknown fields; unchanged other8 replacements,
trust/CRL checked, newcapsulev4/repro+separatepin+custody verified archive_layout1.

New kernelv7 and v7-repro2 reproduce6 artifacts with fixed identical snapshot
session; initial v7-repro used another random session, differs, remains preserved.
Helpersv11/repro reproduce7; recommission-{install,restore,reencode}-v1/repros each
reproduce7. Source includes72-case gate. Owner explicitly conditionally authorized
corrected nine-file install after concrete NAND/power-loss notice, then performed
RAM-to-ROM sequence. All72 ARM cases and exact real-file preflight passed. Manually
sent one scoped commit after independent pair/capsule/matrix check, no extra ask.

recommission-install-attempt-1 strict result: complete/committed/verified/
encoding_verified/safe_to_restart/protected all1, attempted511, phase2; all errors0.
131programs,0erase,0marker,0failures. Host exited0. Selected files plus new scoped
archive originals/journal passed active flash-header NONE/ZERO check after fresh
RO remount. Legacy .hearth-rollback not targeted; preserved along with all host
originals/raw acquisitions. Never rerun recommission-install-v1. Matched restore
and reencode profiles remain unexecuted. No loader is running; device stays RAM,
USB powered/base detached. Native startup/UI outcome under new files is PENDING.

Next owner test: disconnectUSB, fit completely unwired base, hold10sec/release/
singlepress, allow2min, report UI/home icon/LED. Leave Wi-Fi unconfigured until UI
passes. Then start read-only backendwatch and firstnativeWiFi test. Actual physical
network/TLS/time/native protocol/MQTTcontrols/HVAC remain unverified. Backend pair
retained. See docs/research/recommissioning-preparation-2026-10-31.md. Host852/five
optional skips/makecheck remain latest source validation; no runtime source edits
since78ad40d. Pending source changes now document these actual observations only.


## CURRENT: modified native UI works; first Wi-Fi bench pending

Owner reported "yeah, UI is working" after the requested USB-disconnected fully
unwired-base restart. Private recommission-install-attempt-1/native-ui-return.json
preserves this. Do not call this stock configuration now: corrected nine-file
modifications are installed, selected bytes/encoding verified, native UI works.
No loader running; USB is disconnected and base completely unwired for Wi-Fi.

Fresh read-only HTTPS watch from new machine-local
build/watch-private-native-bench-recommissioned-20261031.py is active10min, output
private/native-deployment-20261031/native-wifi-bench-20261031-attempt-2.
Uses current capsulev4 CA, actual manager credential; only sanitized availability/
state-field names printed. Initial GET succeeded with unavailable/no state.
Watch exec session18753; bounded process exits itself. Never run old enroll script
or overwrite existing watch output. Owner was prompted through async input to use
normal Wi-Fi UI to join dedicated IoT SSID and report resulting screen/error;
password only on device. Await their result; poll read-only watch sensibly while
working. No commands/HVAC. If watch expires, preserve and use a fresh output for
any new observation. Physical native network/TLS/time/backend exchange still pending.


## CURRENT: live HTTPS discovery succeeds; PUT400 under investigation

Owner completed Wi-Fi association (thermostat+AP-controller confirmation), despite
E22 empty-base wiring report which they managed to dismiss. Do not insist E22
needs bench-power gear merely to perform this Wi-Fi check. No wiring changes,
bypass or new flash. Private owner address/screenshot remain excluded fromsource.
Read-only backendwatchattempt2 completed600sec with no accepted state; ICMP fromPC
failed but inconclusiveVLAN. Backend0.1.0 started/trustedHTTPSmanager worked.

Fresh protected startup-diagnostic-v5/repro reproduced8 artifacts; v5 executed
once into post-wifi-diagnostic-attempt-1 with owner ROM sequence. All9 bytes/modes
match installed capsulev4; rootowner and assignedcredentials intact. Backupcustody
verified;64logfiles limited/partial. Current eventlog index9 has same9field layout:
entryHTTP200, transportmetadataHTTP200, putHTTP400 (statusfield4). Sanitized evidence
native-https-status-review.json plus raw frames remain private. Positive native
HTTPS/assignedauth discovery demonstrated; actualPUT rejected before accepted
telemetry. No TLS/network/control/HVAC completeness claim.

Host added finite rejection codes/counts/latest to native-mode manager status only;
no request bodies/fieldnames/identifiers/addresses/exceptiontext stored, unknown
errors shareother, counts saturate/reset. Auth+validation/native responses+command
disabling unchanged, normalstatusunchanged. Three meaningfultests, host855/fiveskips,
makecheck. HAappversion0.1.1 newsourcepackage staged+readback; oldsource preserved at
/app_configs/local_hearth/hearth-source-before-diagnostics-20261031, registrypreserved
byteexact. Supervisorupdated0.1.1started, trustedHTTPSmanager+actualenrollment+empty
newdiagnostics verified. ImmediateHTTPproberacedstartup andrefused; laterreadyGET
passed. Never rerun one-shot deployscript; private native-diagnostics-deployment-
20261031-v1 contains receipts, sourcearchive and all step results.

No loader running, device remains protected RAM from readonlyv5 USB/base detached.
Owner was prompted async to disconnectUSB, fit unwired base, full10sec hold/release/
singlepress and let Wi-Fi reconnect, dismissE22 asbefore, reportconnected. Await
that actual test; do NOT arm another loader or change thermostat files. Fresh
10min read-only backendwatch execsession48747, machine-local
build/watch-private-native-rejection-20261031.py, private native-wifi-bench-20261031-
attempt-3. It records/prints finite native_diagnostics alongsideavailability/field
names. Initialcounters empty/stateempty. Review actual reason before altering
protocol validation; no hypothetical relaxation. All earlier executedprofiles and
watchoutputs preserved. If watch expires, usefreshoutput; no automaticdevice retry.
See docs/research/native-wifi-result-2026-10-31.md.


## CURRENT OWNER OVERRIDE: native HA target; MQTT retired; first handoff underway

Read-only native→backend→MQTT→HA telemetry succeeded after a fresh native startup:
one bucket_shape refusal then accepted temperature/humidity/target_temperature,
online>4min, independent TLSMQTT subscriber received3 discovery/state+availability,
HAregistry3enabled and ownerallnumeric confirmed. Private native-mqtt-observation-
20261031-v1 preserves proof. No decoder relaxation or command delivery occurred.

Owner then chose nativeHA, supplied HA IoT address (ONLY in private/native-ha-
migration-20261031/targets.json), and explicitly said nukeMQTTnow. This supersedes
keep-it-running advice. Stopped local_hearth0.1.1, cleared7ownedretainedtopics with
PUBACK success, fresh subscriberfoundnone, HA MQTTregistryentriesgone. Otherbroker/
HA MQTTdevices untouched. Old app/source/privatebackups preserved but stopped;
DO NOT start Hearth Laboratory: it would reintroduceMQTT and conflictport8443.

Built original native HA customintegration under homeassistant/custom_components/
hearth, packaged by tools.package_native_ha. Canonicalbackend modules copied with
AST-limited relative-import rewrite; CLI/MQTTmodule/provisioning/credentials excluded.
Generated deployment path build/native-ha-package-20261031-v2/repro, all19files
reproduce. Raw source template lacks generated _backend: install built package.
Three pushsensors, expiry/unload, configflow/importunique ID; TLS/profile checks;
no keys/creds in configentrydata, commands disabled. Profilefixed5privatefiles under
HAconfig/.storage/hearth, parent0700/files0600/non-symlink, registryenrollment,
CAissuer/signature, leafvalidity/IP SAN/keymatching verified.

Host857passed/fiveoptional, makecheck passed inclnewcomponentlint/Bandit. Real HA
2026.10.4 official container (digest pinned tools.check_native_ha) with networknone
passes userflow/duplicate, TLSauth,3sensorupdates/zero, expiry/recovery, disabled
commands, unloadlistenerclosure,4badprofilecases. Syntheticfixtures only; no MQTT.
Repro command tools.check_native_ha FRESHBUILD --engine podman. Realownerprofile
also validated read-only innetworknonecontainer without startinglistener.

Private profile-v2 preservesactualregistry/admin/devicepair, installedownerCA and
existingRSAserverkey, freshleafSANcoversIoT+previousentryaddresses, CRL+IPverify.
Unused initialprofile EC candidate preserved/uninstalled; useprofile-v2 only.
NativeoriginnewIoTIP:8443. Old device registrationURL not yetrewritten; listener
bindsallHAinterfaces and accepts oldaddress, entry advertisesnewIoTtransport.
BothIPsverifiedonHAnetworkinfo. PCcanreachtrustedoldendpoint, IoTfromPCtimesout
(VLANpolicy). Do not demandnewfirewallrules basedonthatalone. HAtokenAPIproxyfrom
SSHapp401; usemanager endpoint oruserHAUI, no needrequestnewHAcredential yet.

Integration+5profilefiles staged/readback to /homeassistant/custom_components/hearth
and /homeassistant/.storage/hearth. No globalHAconfig edited. Owner authorized one
HAcore restart, commandexit0, thenaddedHearthviaUI. Entitiesappearproperly butno
readingsinitially. BotholdHTTPSendpoint+managerauth work; counters empty. Core
runtime ownslistener; retired App muststaystopped. Askedownerfreshnativebooton
unwiredbase; they justsaid "It's booting back up now". No ROMloader running.
Read-only watch execsession85848, build/watch-private-native-ha-20261031.py, output
private/native-ha-migration-20261031/first-native-ha-watch; viaoldtrustedHTTPSmanager
monitorbecausePCIoTaddressnotreachable. Initialfalse/no state/emptyrejections.
Next inspect this watch foractualhandoff; ifneeded inspectHA-specificlogs privately.
Do NOT flash merely to troubleshoot backend. OwnerphoneUIconfirms actual sensor
values; no globalHAcredential required. Actualnative0.2.0 telemetry pending.

GOOGLE FOLLOWUP STILL ACTIVE: usercapture shows clients3.google.com HTTP and
GoogleNTP. Recovered nlclient andconnmand each contain exact39-byte HTTP204probeURL.
ConnMan1.29 recovered main.conf General has FallbackTimeservers=time.nest.com and
PreferFallbackTimeservers=true; original ntp.conf edit did notcoverthisdaemon.
No on-device Googlefix yet. nlclient5,122,360bytes exceeds current1MiB filewriter
limit, connmand687,028. Do not blindly extend/publish privateELFs or relax write
bounds. Trace configurable/targeted remedy andlocal204service before anynewpatch;
new persistent operation needs reviewedbackup/advanceconcretenotice. No HVAC.
Uncommitted source/docs currently nativeHAimplementation+validation+handoff; commit/
push checkedmilestone per existing authorization, private material excluded.


## CURRENT OBSERVED: native HA readings work; MQTT app removed; Google fix next

Ownerfreshnativeboot returnednormalthermostatdial, thenconfirmedlive3sensorreadings
inHearthintegrationdevicepage. Watch85848 reportsavailabletrue,3statefields andone
initialbucket_shape followedbyaccepteduploads. Private activation/native-ha-telemetry-
observed.json preservesowner+managerproof. This isdirectHA0.2.0, no MQTT. Device
on completelyunwiredbase/WiFi; no loaderarmed. Watchbounded10min, canexpire.

AfterverifieddirectHA, ownerexplicitnuke scopecompletedretiredappremoval:
private retired-app/configuration-archive.out wasreadback/matchedregistry+serverkey,
then ha addons uninstall local_hearth succeeded, its /local_apps/hearth source
moved /homeassistant/.hearth-retired-laboratory-source-20261031 andstorereloaded.
Privatebackups/sourcepreserved; nativeintegrationprofilesseparateunchanged. Do not
attempttostart/reinstalloldapp orreintroduceMQTT. ProducttargetnativeHAonly.

Newsourceallchecks857/fiveskips+realpinnedHAcheck passed. Packagingmanifest now
also coversLICENSE/THIRD_PARTY; focused2packageregressions passedafterthatmetadata
change. Sourcecomponents stagedbytesunchanged. Finishcheckedcommit/push including
nativeHA source/docs/validation; no actualprivateIP, keys, screenshots or firmware.
GOOGLEremediation remainsprioritybeforecommands. CurrentcallbackHAHTTPSendpoint
healthy, storedregistrationoldIPstillpendingupdate; entryadvertisesIoTtransport.
AvoidspeculativeNANDchanges; literalnlclientURLpatchwouldtouch5MBfile exceeding
current1MiBbound. Needtargeted/configurable remedy andseparatefreshbackup/writeplan.

## CURRENT: local connectivity candidate prepared, working deployment unchanged

On2026-11-01, source candidate HA0.2.1 adds a frontend bodyless204 connectivity
view and the same-auth `/nest/init` alias for a fixed-width IoT registration URL
transition. Host880 tests pass/five optional skips; make check and fresh pinned
HA2026.10.4 sandbox pass, including actual HTTP probe refusal/unload cases. Existing
HA0.2.0 on the owner host remains active. No new loader or device write is armed.

Offline `provisioning.native_network` prepares exact equal-width spans only; it
does not install them or bind full-file identity. Both probe ELFs and ConnMan's
independent preferred fallback time config are reviewed. Public vendor ConnMan
source/revision/hash lock is docs/research/connman-5.9.4.json. Proprietary candidates,
hashes, addresses, decompilations and logs remain private. The URL Ghidra helper
was positively exercised and refused public output; launcher exit0 alone is not
success. Call sites are not function starts: the private caller experiment that
created functions at call instructions is not valid reachability evidence.

Next develop a separate bounded fresh large-file acquisition/update/restore path
with whole-file identity and per-fragment native-compatible encoding verification;
do not widen the old nine-file writer limits or claim all stock fragments NONE.
Keep the working HA sensors online while preparing. Notify owner before concrete
device work and obtain timing only when a fresh fully checked payload is ready.
See docs/research/native-network-preparation-2026-11-01.md.

Subsequent owner authorization: activated staged/readback-verified HA0.2.1 and
restarted Core once, exit0. Full previous0.2.0 code archive verified privately.
Live frontend probe204/zero bytes, query400, POST405; manager HTTPS authenticates.
No thermostat/profile/router changes. Fresh native state still pending on bounded
watch85242 in private/native-ha-local-probe-20261101; do not claim reconnect yet.
The next device design favors streaming full-file temporary replacement and the
existing whole-file NONE/ZERO audit, rather than a new in-place range writer.
See docs/architecture/0002-network-update-plan.md. No device image prepared/armed.

Watch85242 ended after three minutes with authenticated manager/no fresh state and
no decoder rejections. Owner then reported the battery likely ran down overnight.
Instructed detach unwired base/reconnect USB to charge, no ring restart or loader.
Await screen/charge confirmation. This does not establish a HA reconnect defect.
Next preserve fresh network-target originals before any new device update.

Post-charge result: owner observed normal attach-to-base screen, then reseated on
the unwired base and confirmed uploads to HA. Authenticated manager independently
reports available with all three state fields under HA0.2.1. Fresh private receipt:
private/native-ha-local-probe-20261101/post-charge-telemetry.json. Reconnect passes;
no new device writes/restarts were needed. Keep charging/power management separate
from protocol failures. Google dependencies and native commands remain unfinished.


## CURRENT: four network originals acquired; prepare bounded writer

Owner keeps USB connected/base detached for charging/testing. New network_snapshot
uses unchanged protected kernel, root0-only RO mount, original syscall code and no
native libraries/app/logs. Cache7471232 bytes, limits6MiB/1MiB/64KiB/64KiB; old
installer bounds unchanged. Host929/five optional skips/make check/49 focused cases
pass. All8 artifacts reproduce. Owner confirmed primary/5.9.4-5, readiness and
restart. One PTY run passed: all4 originals match preserved inputs, private custody
and600 modes independently verified. No flash writes or firmware execution on host.

Executed ONCE: private/network-snapshot-20261101/profile-v1. Never run it or
profile-v1-repro again. Builds build/network-snapshot-20261101-v1 and -v1-repro.
Capture/backup private/network-snapshot-20261101/attempt-1; separate immutable
attempt-1-record.json binds source recipes/profile/capture. Owner confirmed home
return; native2464:0002 independently observed. No loader running. File bytes
5122360/687028/3063/10380,total5822831. statfs available21782528 includes dirty
reclaimable space and is not an allocation guarantee. Device stays on USB charging.

Next separately bounded full-file streaming temporary replacement/restore with
whole-file hash/span identity, plan-derived originals/journal, fresh space checks,
root0-only gate and NONE/ZERO audit. No Google update installed. See dated snapshot
result and architecture/0002-network-update-plan.md. No physical control authorized.


## CURRENT: network adapter RAM and real-file preflight PASSED

Host1014/five optional skips/make check pass; all9 artifacts reproduce. New core
validates whole original/candidate SHA256 and exact spans with4KiB scratch. Separate
HEARTH_NETWORK_ADAPTER reuses file_install/posix.c transaction under fixed4 root0
targets/6MiB,1MiB,64KiB,64KiB bounds. Legacy1MiB header/default9-target path unchanged
and regressions pass. Original bounded SHA256 is MIT, tested against independent
hashlib and ARM synthetic vectors, not NIST module validation. No implementation
copied. network_plan builds deterministic private DATA from verified full custody
and a separate reviewed plan pin. Current private plan is network-plan-v2, separate
reviewed-network-plan-v2.json under private/network-snapshot-20261101. v1 is older
unexecuted offline data; keep it, do not deploy it.

Executed ONCE: private/network-snapshot-20261101/network-preflight-v2; -v2-repro
is offline only, never run either again. v1 was an unexecuted inventory-count
draft. Build build/network-preflight-20261101-v2 and -v2-repro. One supervised PTY
run passed41 memory/hash/stream cases,20 actual RAM filesystem transaction cases
as UID/GID65534 and4 real original/mode/derived-candidate preflights. Kernel is
unchanged protected RO, no commit capability. Only native libc/interpreter execute
on DEVICE; no firmware runs on HOST and no nlclient/osm executes in the profile.
Result private/network-snapshot-20261101/network-preflight-attempt-1; separate
immutable network-preflight-attempt-1-record.json preserves recipe/profile/result
identities. Owner return sequence done and native2464:0002 independently observed.
Device stays USB/base detached charging. No loader/write armed.

Persistent wrapper still pending: root0-only kernel gate, conservative fresh space/
memory checks, bounded RAM-backed candidates/opaque original files in private
initramfs, exact byte/mode readback and NONE/ZERO audit, separate restore profile.
Reuse measured transaction/journal, do not invent another format or relax old
limits. Gzip initramfs IS enabled in the proven file_writer NONE kernel (unlike
protected snapshot kernel), so original DATA can be privately packaged compressed
without host linking/executing proprietary ELF. Source docs now reflect bounded
RAM backing rather than avoiding all whole-file caches. No Google fix installed.
See docs/research/network-ram-result-2026-11-01.md.

## CURRENT: root0-only network writer preparation (not executed)

New firmware/network_writer has scoped kernel/action/data/profile/session/run.
Root0-only conditional gate/partition registration and four-target lifecycle mask
retain old nine-file defaults. Kernel build/network-writer-kernel-20261101-v2 and
-v2-repro passed offline checks and all6 kernel/bootstrap artifact bytes match.
Original pinned public source archives were used offline; initial v1 source draft
failed for a missing protection header, corrected before v2. Preserve draft/logs.
No new loader or write has been armed. Native USB independently remains normal.

Device has64MiB RAM. Action packages all4 original files as root-only0400 DATA,
read-only original mmap/private COW candidate mmap, complete SHA/span validation,
then mprotect READ. No vendor ELF executes/links on host. Both aliases mount only
root0 (/native,/archive), with plan-specific root0 rollback archive; user-config
not registered/allowed. Forced NONE/GZIP kernel and old encoding audit retained.
24MiB MemFree guard; install space3*sum+2MiB, restore largest+4MiB; dirty statfs
space is not a guarantee. Existing transaction/sync/rename/restore behavior reused.

Separate immutable local backup private/local-recovery-20261101-network/backup
verified equal fresh snapshot, under existing owner one-local-unencrypted-archive
exception; no second target/encryption permission question. Current reviewed
plan/pin still network-plan-v2/reviewed-network-plan-v2.json. Kernel includes exact
plan/receipt binding. Profile recipes inspect critical pinned public kernel sources.
New run never commits automatically:61 synthetic checks ->ACK root RO preflight ->
resource-info ->READY ->separate local commit/abort. Persistent intent durable before
USB token; no automatic retry. Direct RAM recovery only accepts matching exited
persistent attempt and prepared restore action2. Protected old profiles remain
immutable; updated source checkers are not licenses to rerun them.

Host full suite1086 passed/five optional skips before adding final large mapped
install/restore case (that focused11-test suite also passes); make check passed.
Final source checks/profile reproducibility and full tally still need recording.
Unexecuted draft1/draft2 and network-install-v1 images remain private, never run.
Final pair preparation in progress; confirm manifests against current recipes
before selecting exact next payload. Whole-firmware/power-loss and large-file
NAND restoration remain unverified. Advance concrete notification/readiness and
fresh filtered primary/5.9.4-5 are needed before this new persistent operation.

Final preparation verified:1087 host tests passed/five optional skips, make check,
11 large mapped-data custody/install/restore checks, root0 gate/lifecycle fault
checks. Selected private profiles network-install-v1 / network-restore-v1 under
private/network-snapshot-20261101; matching network-install-repro-v1 /
network-restore-repro-v1 are offline-only. All10 artifacts per action reproduce;
install/restore USB images4167686/4167667 bytes. Offline checked_pair passes.
Neither selected profile has executed; execution-started marker must be absent.
Preserve older unexecuted draft1/draft2 packages. Sources/recipes are immutable
once an attempt starts. Await owner filtered primary/version and new persistent
operation readiness before arming. Do not mark Google traffic removed yet.

## CURRENT: network four-file install PASSED; native/network return pending

Owner freshly confirmed primary/5.9.4-5 and readiness after concrete NAND/power-loss
notice. PTY boot ran network-install-v1 ONCE from source a2089a3, output
private/network-snapshot-20261101/network-install-attempt-1; never rerun this image
or its repro. All41+20 RAM cases passed, childstatus/output0; all4 real originals
and resource guards passed. FreeRAM50933760, flashavailable21774336 versus required
19565645 bytes. Matching restore image rechecked, separate scoped commit sent under
owner's checked-update readiness authorization. No automatic device retry.

Loader/collector exited0. Strict final report: action1 complete1/safe_to_restart1/
encoding_verified1, attempted15/restored0/committed1, phase2/protected1, program5808,
erase0/marker0/failed0. Whole selected bytes/modes plus target/backup/journal encoding
passed after unmount/seal/remountRO. Independent immutable attempt record preserved
at private/network-snapshot-20261101/network-install-attempt-1-record.json; original
creation/backup/preparation records unchanged. Restore-v1 is still UNEXECUTED.
No further loader or persistent operation is running. Owner must now perform full
10-second hold/release/single press with USB/base detached and confirm home/attach
screen; independently verify nativeUSB. Then start HA rejection/availability watch
and ask unwired-base WiFi return plus router destination metadata check. Native UI,
actual new connectivity/NIST destinations and fresh HA uploads are NOT YET observed.
No whole-firmware recovery, large-file NAND restoration, physical HVAC/control claim.

Post-install native return: owner confirmed home icon; normal2464:0002 independently
observed. Owner reseated on completely unwired base/WiFi. Authenticated backend watch
post-network-install-watch-1 reports fresh available +temperature/humidity/target.
Owner traffic screenshot shows time.nist.gov; initially apparent Google NTP row was
explicitly confirmed by owner to predate install by over an hour. Owner reports no
new Google row so far. Private reconnect-and-traffic-observed.json preserves fresh
HA receipt and bounded owner observations. Do not mistake historical row for a new
failure or require another flash/snapshot on that basis. No claim of all future
traffic absence. Connectivity replacement/install succeeds; hardware restoration
and actual HVAC remain unverified. Next user's requested sustained native HA climate
and HVAC feature development, keeping base unwired; no physical switching authorized.

## CURRENT: native HA basic climate/control code; not deployed or unit-tested

Owner clarified NLE functional parity target. docs/architecture/0003-native-ha-controls.md
tracks basic +range/emergency/eco/schedules/settings/weather/diagnostics/outage/HVAC
gaps; do not call basic heat/cool a complete project. Nativecontrol loops retained.
User's 'subscription' question answered: local native HTTPS long-poll/bucket service,
not NestPro/paidaccount spoofing. Actual physical switching still separate authorization.

Uncommitted backend/native_controls.py original opt-in NativeControls adds bounded
volatile temp/mode/fan intent,30s expiry, fixed partial-value responses/metadataorder,
accepted-PUT confirmation, local supersession, revision rebase, generation clearing.
No raw native bucket values retained/echoed. Heating/cooling/fan require observed
booleans plus registry permission; fan on is600s native timer. Reported action maps
native bools, never temperature-difference control. Old telemetry-only default and
canonicalpoll refusal remain. New HA runtime explicitly enables NativeControls.
One climate entity added, existing three sensor IDs preserved, package includes new
module/climate.py, manifest0.3.0. No live HA code/restart/commands changed yet.

1111 host tests/five optional skips and make check passed. Real pinned HA2026.10.4
sandbox v2 passed five native command roundtrips with confirmed reported state,
TLS/auth/probe/unload/profile checks. v1 caught HA forwarding entity_id into settemp;
fixed by accepting that routing attribute. v3 sandbox now running to additionally
verify Fahrenheit conversion; session84372. Public packages build/native-ha-climate-
20261101-v1/v2/v3; never deploy failed v1. After code stable prepare fresh final
package and remote staged readback +old0.2.1 source backup BEFORE asking activation/
HA Core restart readiness. No new thermostat flash needed for this basic test.
NLE public command.py/helpers.py downloaded only at existing pinned MIT revision,
source hashes appended to upstreams.json; no upstream code copied/executed.

Final basic-controls preparation: sandbox v4 passed6 real HA synthetic wire/service
roundtrips including77F->25C, immediate command-status confirmation, mode/fan,
existing3sensors/auth/probe/profile/unload/expiry. NativeControls notify now updates
HA after accepted-upload outcome/capability changes, not before confirmation.
1111 host tests/five skips and make check pass;24 native control tests. Version0.3.0
source package build/native-ha-climate-20261101-v4 matches fresh -v4-repro exactly.
The earlier '-final' package predates notifier fix; do not deploy that one.

SSH staging first failed because prior temporary askpass secret file expired;
no remote change. User entered password via T3 secure request_secret file delivery,
not chat. Fresh private/native-ha-climate-20261101/ssh-askpass reads current temporary
secret; don't print contents or add to source. Immutable failed stage-v1 retained.
Successful stage-v2 preserved full active0.2.1 code backup/readback; all21 new files
read back exactly from remote /homeassistant/.hearth-native-climate-stage-20261101-v1.
Receipt/staged/backup tar files private/native-ha-climate-20261101/stage-v2. No profile,
thermostat, active integration or HA restart changed. Next owner activation/restart
readiness; then move source directories with old version preserved, restart Coreonce,
checkhealth/listener/entities/telemetry, prepare single bounded unwired target change.
No physical HVAC attached/authorized. Basiccontrol unit acceptance still unverified.
NLE parity remaining range/emergency/eco/schedule/settings/weather matrix in ADR0003.

Owner explicitly authorized HA0.3.0 activation and one Core restart. Activation-v1
rechecked active0.2.1 backup and staged21 files, moved old source to remote
/homeassistant/.hearth-native-previous-20261101-030, activated/readback-verified new
source, then ha core restart exited0. Private receipts under native-ha-climate-
20261101/activation-v1. Profile/certs/credentials unchanged; no thermostat command.
Health-v4 confirms four registered entities (three sensors/one climate), none
disabled and no Hearth setup error in scoped logs. Earlier registry read while
HA still starting showed3; do not misdiagnose that early read as failed platform.
Supervisor/Core template query returned401 (SSH environment has no API token);
used scoped on-disk Hearth entity-registry filtering instead, no new HA token ask.

New reconnect watch session12756 records fresh HA listener manager auth but no
native uploads yet (empty state, unavailable, zero decoder rejections). Owner
woke ring once: wiring error with WiFi connected. This did not produce upload yet.
Asked via async input for ordinary native restart ON the unwired base, full10sec
hold/release/singlepress; NO loader/flashing running. Await return before bounded
target command. Do not claim physical unit command acceptance or autonomous
post-Core-restart reconnect. First staged-control run may require this handshake.

User asked public packaging/installer architecture. Explained integration vs
Supervisor add-on, GitHub versioned release/ZIP +early custom HACS repository,
default catalog later after HACS Action/Hassfest/releases. Recommended one dev
source repo now, generated distribution later if useful (no new repo created).
Proposed HA setup/pairing wizard plus guided desktop USB installer with model/
firmware checks, backups, reachability, scoped write confirmation. Research tooling
is not public installer. HACS requires self-contained custom_components/<domain>
layout; current nested/generated dev layout needs release packaging work. Native
HVAC development objective continues; those release questions are context/steering.

## CURRENT: unit target increase confirmed; original restore UNCONFIRMED;0.3.1 staged

Owner ordinary native restart on unwired base returned dial; fresh uploads arrived.
.0.3.0 controls validator confirmed active with deliberately invalid empty request
(400,no command). Authorized+announced single0.5C target increase and original restore
via Hearth insideHA (manager API,sameNativeControls path). Test target accepted and
reported within~2s. Restore intent accepted but original value NOT observed within40s
or later read-only check. No automatic command retry. Private target-test-v1 preserves
baseline, precise reviewed original/test values, both intents, observations and late
reads. Precise original/test values remain only in private reviewed-targets.json.
Thermostat remains completely UNWIRED, so no physicalHVAC. Owner couldn't locate
command_status; attached HA image shows all4unavailable with earlierHeat transitions.

I acknowledged a code mistake: NativeControls.apply piggybacked pending values on
PUT responses. Pinned NLE warns this can clear dirty flags/override local/scheduled
updates. New0.3.1 permits values ONLY on subscription, keeps PUT metadata-only even
CAS conflict. Exact cause of failed original restore not proved. Availability also
renewed only on sensor deltas; now explicitCore.touch on valid authenticated native
requests and active subscribe (generation/transport checked), no fake sensor update.
Native hold290/wakeheader300/defer15/initial-commanddisable-defer60 match pinnedNLE
reference environment.py hash now recorded. Manager-only native_controls diagnostics
adds request counts/baselinepresence/pending/outcome/offered; no raw private values.

0.3.1 source/sandbox path build/native-ha-climate-20261101-v031-1 plus -repro,
all21source bytes match.1115tests/five skips/make check pass; actual HA2026.10.4 sandbox
6syntheticroundtrips pass. Source fix not yet activated. Staged/readback21files at
remote /homeassistant/.hearth-native-climate-stage-20261101-v031; source0.3.0 backed
up/readback privately under native-ha-climate-fix-20261101/stage-v1 (code-backup.tar,
staged-code.tar,readback,receipt). Current active still0.3.0. New Core restart needs
owner readiness (prior approval was one restart, consumed); prepare activation after
reply, same checked old/new byte gates and preserve previous source path distinct.
After activation verifyfresh telemetry+diagnostics, then restore PRECISE ORIGINAL
from target-test-v1/reviewed-targets.json in one reviewed bounded operation. Do not
rerun raise test or claim original already restored. No NAND/ROM operation needed.

Supervisor scoped API file exists but Core template endpoint returned401 even with
proper internal file token; don't keep trying or seek extra privileges. Used scoped
entity registry4+managerauth+logs for live health; HAservice path validated in sandbox,
actual unit target through Hearthmanager. Ask userforUIonlyifneeded; don't request
HA access token unnecessarily. Existing SSH passwordfile stillworkedfor staging;
use private/native-ha-climate-20261101/ssh-askpass, no secret content printing.

Owner approved0.3.1 activation +oneCore restart. Activation script
build/activate-native-ha-climate-fix-20261101.py rechecked prior/staged bytes,
preserved0.3.0 source at remote /homeassistant/.hearth-native-previous-20261101-031,
activated/readback0.3.1 and ha core restart exited0. Source commit a26057b pushed.
Receipt private/native-ha-climate-fix-20261101/activation-v1. No new thermostat
write/ROM/flash. Reconnect-watch-v1 session93220 active/possibly later completed;
full private observations include new per-device native_controls diagnostics.

HA0.3.1 received valid native GET+subscriptions autonomously afterCore restart,
renewing availability, but unchanged readings did NOT reupload: empty state,
get1/subscribe2, all temperature/mode/fan baselines false, no decoder rejection.
0.3.1 correctly refuses target intent without actual baseline. First read-only
restore preflight original-target-restore-v1 exited1 after180s, NO intent sent.
Fresh extended read-only preflight original-target-restore-v2 running session71719
from build/restore-native-target-20261101-v3.py; waits360s for available+0.3.1diag+
actual target baseline+valid subscription. If currenttarget matches prior test,
it will send EXACTLY ONE restore intent for saved original and poll45s; if current
alreadyoriginal sendsnothing; unexpected thirdtarget refuses overwrite. This is
not an automatic retry of an already sent command. Do not duplicate this intent.

Asked owner via async input for ordinary native restart ON unwired base (10sec
hold/release/singlepress) to resend startup readings. Await dial-return reply.
NO loader is armed. Worker71719 may act on fresh baseline after that restart;
inspect its result/evidence before any further command. Original target still
UNCONFIRMED at last fresh check. Precise values only in ignored target-test-v1/
reviewed-targets.json; do not log them into public source. Existing firstraise
succeeded, firstrestore .3.0 didnotconfirm, no additional command has been sent
under0.3.1 yet. All wiring terminals remain empty.

Next release requirement discovered: preserve ONLY reported/observed state across
HA restart while discarding intents. Nativeclient sends metadata, not unchanged
values, on warmserver reconnect. Without reported-state cache, warmCore restart
loses baseline and could need manualunit restart. No cache implementation yet.
Proposed bounded known-field cache: device/shared metadata+allowlisted actually
reported scalar telemetry/control/capability fields, generationbound; no unknown
raw values, credentials, intent values/replay. Rebuild fingerprints under a fresh
HMACkey; assign cachedCore.states without Core.report/seen (don't fabricate fresh
readings), renew presence only after real valid native connection. Save atomically
600 with bounded schema and per-unitgeneration; no outbound values without explicit
new intent. Unit acceptance/restoration first, then build/test cache plus remaining
NLE parity. Never interpret cached state as a newly measured device report.

Extended restore preflight71719 exited1 after360s: no target baseline appeared,
NO original-restore intent sent. Both0.3.1 restore directories are read-only refusal
records. Owner normalrestart prompt still pending (no dial-return message yet).
New watch continued connected/authsubscribe but no unchanged readings after full
hold cycle. Do not repeatedly enqueue/seed fabricated sensor readings. Once owner
returns dial, inspect actualnewmanagerstate; only then send one reviewed original
restore intent if current stilltestvalue. If alreadyoriginal sendnothing; unexpected
independenttarget do not overwrite. Precise original private reviewed-targets.json.

While awaiting owner, prepared WIP reported cache backend (NOT deployed):
backend/reported_cache.py strict bounded known-field-only codec, backend/reported_state.py
snapshot/capture/restore, NativeControls.reported hooks and package inclusion. Tests
reported_cache18 +nativecontrols28 focused46 pass. Snapshot excludes pending intent
values (uses actually reported fields), unknown raw fields/credentials/fingerprints.
Restore generation-bound, beforetrafficonly, recomputesHMACunderfreshkey andassigns
cachedCorestates WITHOUT Core.report/seen/touch; no intent replay/freshnessclaim.
No HA diskstore/runtime cache load/save yet, no version bump/package activation for
this WIP. ActiveHA0.3.1 remains frozena26057b source and the checked21-file package.
Do not mix WIPcache with alreadyverifiedliveartifact or claim restartcache working.
Need atomicprivate600 boundedstore and explicitcached-origin metadata before wiring
HAstartup/shutdown, then host+realHArestarttests and laterdeployment. Unitrestore
remainspriority before expandingparity. Current source WIP may be dirty, preserve.


Owner finally confirmed dial after normalrestart; fresh0.3.1target baseline arrived.
Thirdpreflight original-target-restore-v3 (worker42747/build/v4) refused because
nativecurrentvalue differed from BOTH exact savedoriginal/test. No0.3.1intent sent.
Privatecomparison shows current within0.02Cofsavedoriginal andtest+0.5Ccleared; doNOT
claim exact restorecommand confirmed. Leftnativecurrentvalue untouched. Ownercould
onlyseeE22wiringdiagram and estimatesprior62F, NOTverified. Toldownerleaveallterminals
empty; cannotcertifyphysicaldial/HVACcontrolfromechoedtelemetry alone. No furthertarget
requestcurrentlyrunning. Primaryremainingcontrolproof: subscription-onlycommand
mustchangeactualnativeapplication/dialwhenvalidpoweredbenchpermits. Keepcodebuilding.

WIPcache now extended (stillNOTdeployed) with backend/reported_store.py atomicprivate
600 FD-relative save/fsync/replace/readback, strictinodes/no links/unexpectedfile
refusal. NativeControls per-field cache/device/unknown source markers, HA runtime
loadbeforelistener/periodic+stopflush (generationcounter+asynclock), sensor/climate
sourceattributes and payload-freediagnostics.py. Devmanifest0.4.0; live0.3.1 unchanged.
Package includes3cachebackend modules+diagnostics. Hostcachetests27plusnewsource/
invalidcapabilitycasespass; widerchecks pending. RealHAcache sandbox v040-1 FAILED
before setup: packager didnotrewrite `from backend import reported_state`. Fixed
packager exactly-`backend` import form +ASTregression; v040-2 running session62459.
DoNOTdeployv040-1. CacheHA test unloadswithpending24C intent whileactualreported25C,
loads reported25C+no intents/no seen, reconnectsmetadataonly andchecks cachelabel,
acceptsnewactual22.5C andchecks perfieldsourceflips, payloadfreediagnostics. Need
confirm result, fulltests/repro/custody before anyliveactivationreadinessrequest.


HA0.4.0 batch now validated:1158 host tests pass/five optional skips, make check
passes. Real HA2026.10.4 isolated sandbox final-podman passes12 synthetic service/
native-report roundtrips including Fahrenheit conversion, heat/cool range pairs
and capability-gated emergency preset. Reported-only atomic cache unload/reload
passes without intent replay or fabricated availability; source labels/diagnostics
and refused-cache fresh-upload/save recovery pass. Final25-file source package
build/native-ha-cache-range-emergency-20261101-v040-final-podman matches separate
-v040-repro byte-for-byte. Earlier draft packages superseded. No ARMfirmware or
physical HVAC ran. Range/emergency remain untested on owner's empty base.

Source staged/readback exactly on ownerHA; prior0.3.1code backedup privately in
private/native-ha-v040-20261101/stage-v1. Owner explicitly approved activate0.4.0
+oneCore restart. build/activate-native-ha-v040-20261101.py running/possiblyfinished
session9151; receipt activation-v1, remote previous source preserved at
/homeassistant/.hearth-native-previous-20261101-040. Readonly reconnect watch at
private/native-ha-v040-20261101/reconnect-watch-v1. Check results before claiming
livehealth/cache. No thermostat writes/control intent involved. First0.4startup
has no oldcache; mayneed normal ownerunit restart for freshfullreport, then verify
subsequent cache reload without unitrestart. Do not rerun activation or consume
anotherCore restart without newownerreadiness. NLEparity checklist ADR0003 updated;
eco/schedules/weather/settings and physicalbench still unfinished.


0.4activation9151 exited0; exactactive25-file source verified and one ownerapproved
Core restart returned0. Health-v3 confirmsmanifest0.4.0,4registeredentities/none
disabled, zero scopedHearthERROR lines. Warnings are usualcustomintegrationnotice.
Read-onlymanager endpoint responds afterstartup butstateempty/cacheabsent; owner
confirmed NestisonUSBcharging, NOTonbase/WiFi. Thisexplainsnouploadandisnot
evidenceoftransportfailure. AskedownerwhenchargedenoughtodisconnectUSB,fiton
completelyEMPTYbase, letWiFireconnect/dismissE22andreport. No loader/newNAND/control
commands. Readonlywatch41297mayfinishbeforeowner; freshboundedwatchifneeded.
Commitd20dcec pushed main containschecked0.4source. Needactualupload/cache600
verification,thenownerUIintegrationReload tocheckcachedreadingswithoutunitrestart.
NoextraCore restartrequiredorcurrentlyauthorized. Ifownerneedscharge,keepworking
offline; donotclaimphysicalHVAC/controlorfullNLEparity.

Follow-upwatch sawactualauthenticatedGET1/PUT1/SUB3 andavailabletrue whileowner
reportsUSBcharging; noallowlistedreadingfields/baselinesyet,nopendingintents.
DoNOTassumeUSBnecessarilymeansnophysicalnetworking: observedvalidtrafficexists.
Earlierabsenceofuploadsisnotfullyexplainedsolelybycharging. Fullnativeappreport
stillneededtoseedcache,likelynormalstartupontheemptybase. Awaitownerbase/WiFi
replybeforefurtherrestartinstruction; noRAMloaderandnoautomaticcontrolrequest.

OwnerputunitoncompletelyunwiredbaseandconfirmedWiFi. Watch41297thenobserved
availabletrue+freshhumidity/target/temperature. Health-v4 SSHconfirmscacheexists
formatv1/devicecount1/mode600/nlink1andnoHearthERRORlines. Firstcacheisseeded.
AskedownerHASettingsDevicesServicesHearththree-dotReload (ONLYintegration,no
Coreorunitrestart) totestwarmcache. AwaitReloadreply; cache-reload-watch-v1 uses
freshprivatepath. Checkvaluesretained/nointent/nativefreshconnectionbeforeclaiming
owner-hostreloadverified. No setpoint/mode/fancommandswere sent.

OwnerconfirmedHearthintegrationReloadwithoutunitrestart. cache-reload-watch-v1
showsrequestcounterresetfromGET1/PUT14/SUB11 toSUB1alone,availabletrue andall3
readingsEXACTLYequalbefore/afterwhilePUTcountzero. LaterPUTsresumednormally; use
firstpostreloadobservation,notlastrow,toverifycacheproof. Targetbaselinerestored,
pendingempty. Privatecache-reload-observed.json preservesboundedproof. Thiscloses
ownerhostcachewarmreload/reconnecttest; no commandsreplayed/sent, noCore/unitrestart
required. Currentmode/fanbaselinefalse onemptybase; doNOTinferfullcontrolverification.
Continueeco/schedules/settings/weatherparityafterthismilestone; physicalHVACrequires
separateauthorizationandappropriateequipment.

OwnerreportedNest67FvsHAtarget66.8,61vs60.9,66vs65.9; screenshotconfirmsSEPARATE
Targettemperaturesensor,notclimatecard. PreservedlivereportedCelsiusreproduces
oneexampleafterstandardFconversion; noaffineconversionbugfound. Climatealready
usesHAwholeFprecision; targetSensorhadnosuggesteddisplayprecision.0.4.1source
changesONLYtargetsuggestionto0F/1Cbasedonentityactualunit; rawvalues/history/
commands/measuredtemperatureunchanged. RealHA sandboxv041-2passes12roundtrips
plusall3fractionalexamples/rawpreservation/Celsiusoverridechecks. v041-1failed
onlytestundefinedregistryname,corrected; doNOTdeployoldprofile. Fullmakecheck+1158hosttests
pass/fiveoptionalskips. LiveHAremains0.4.0; noactivation/restartfor0.4.1authorizedorperformed. Told
ownerimmediateHAUI TargettemperaturesensorgearDisplayprecision0 needsnorestart.
Package/releasecorrectioncanbundlewithnextfeatures; noneedinterruptHAforthisalone.


0.5.0 eco/schedules/weather BUILD (notlive): ownerrequestedallthree, thenchose
EXISTING HAweather instead ofdirectOpenMeteo. LiveHA remains0.4.0;0.4.1displayfix
isincludedin0.5.0. Sourceadds native_features.py strictcompleteweeklyschema/eco
validators, schedule_backup.py ownerprivate/fsynced/readbackprechangearchives,
native_weather.py originalGen2JSONcodec. HAservices.py+services.yaml provide
get_schedule/set_schedule/set_schedule_mode/set_eco_temperatures; climateecopreset
usesdevice-referencedhome onlywithvalidatedbaseline. Native home records stay
PERAUTHENTICATEDDEVICE, neverglobalaccountobjects. Null/changedreferencesdrop
oldhomerecord+ecointent; staleconditionalreferencescannotbind. Noaccountownership
claim. Device.structure_id string/staticnativefields confirmedpresent.

Schedulesfullweekver2/name/mode/days0..6,24points/daymax,integerseconds,10..30C
bounds,matchingHEAT/COOL/RANGEtype; unknown/incompleteoriginalsrefuse. HAaction
requiresfreshnativeweek+expectedrevision, archivesprivateoriginalandthenrechecks
revision/generationbeforeenqueue. Privatearchive64limit; noreplay. Partialdelta
mustNOTfreshenothercachedweekfields: finalcustodyregressioncoversit. Eco bounds
currentlyrequirebothreportedheat/coolcapsandbothbounds. Baselinesmaybemissingon
owneremptybase; doNOTseed fabricatedvaluesorclaimcontrolsverified.

weather_source.py usesHAweatherentity/current+weather.get_forecasts, nooutside
HTTPclient/geocoding. Configureoptionsselectsource/disable; defaultautoonlyifone
HAweatherentity. Ownerregistryhasexactlyoneenabledweatherentity. Source/time/type/
unitcache15min, currentlast_reportedmax2h. NativeweatherHTTPisDEVICEAUTHENTICATED,
GET/boundedqueryonly; responsecurrent+48hour/6dailymaxandHAtimezone. WeatherURL
onlyadvertisedwhenasourceisconfigured. Nativefetchauth/actualparseracceptance
UNVERIFIED. Weatherquerymustpostal,country; preservesunit'sownzip/country. Static
GhidrareviewfoundlocationconsumerwouldCLEARcountrywithblankdefaults, potentially
changingunits; donotremovequeryguard. City/statelabelsnotinvented. Weatherhandshake
mayupdateunitlocation/timezoneviaoriginalnativecode; noeco/schedulesentbyactivation.
Privateexports/logsunderprivate/native-weather-review-20261101; nofirmwareexecuted.
TemporaryGhidraJava copiedbacktobuildonly/removedfromtrackedtree.

FINALCHECKED31filespackage build/native-ha-features-20261101-v050-custody and
-custody-repro EXACTMATCH. 1205hosttests/fiveoptionalskips+makecheckPASS; real
HA2026.10.4sandbox17syntheticroundtripsPASS incl ecoon/off,boundsF,schedule
backup/CAS/fullreplacement, archivefailurepreventingqueue, localHAweathercurrent/
hourly/daily+options/unload/reload/cache/nointent replay. Draftbuildsv0501..6,
-final,-reviewedandremotestage-v1/v2ARESUPERSEDED. Finalsourcecustody/stage-v3
underprivate/native-ha-v050-20261101;remote/homeassistant/.hearth-native-stage-
20261101-v050-v3. Oldactive0.4.0backupreadsback. NEVERactivateoldstages.

Askedownerviaasyncinput: readyactivate0.5.0+oneCore restart,briefautomationspause,
localweatherendpoint; FIRSTread-onlychecks/noecoorschedulechanges. Awaitreply.
UserhasNOTauthorizedthisnewrestartuntilreadyreply. Needcommit/publicscan/push,
thenfreshactivationbasedstage-v3andprior0.4.0. Unwiredbaseonly. NoROMloader/NAND
write/controlcommandwasrun. DoNOTclaimphysicalHVAC/fullNLEparitycomplete.

OwnerprovidedHearthorangeflamePNGforproject/HAuse. Addedcanonical
homeassistant/custom_components/hearth/brand/icon.png; original1254squarepixels
PRESERVED, image-onlyPNGchunks/nometa/EXIF/text. NoAIredraw/transparentvariant.
READMEusesasset; packagerbundlesfixedbrandfile. RealHA2026.10.4actualbrandAPI
returnsEXACTfileforicon/logo/darkicon/@2xfallbacks, offline/noCDN; all17synthetic
roundtripchecksremainpass;makecheckand2packagertestspass. HA2026.3+ supports
localbrandfolder; docs/artwork.mdlinksprimarydocs. Sharedbrandrepofutureresolution
guidelinesnotclaimedmetbyoriginalcanvas. Noexternalbrand/HACSsubmissionmade.

LATESTFINAL0.5package now build/native-ha-features-brand-20261101-v050-1 +
-v050-repro:32EXACTmatchingfilesincllogo. Remotestage-v4underprivate/native-ha-
v050-20261101 readback/old0.4sourcebackupchecked. REMOTESTAGE-v3ANDOLDERsuperseded.
Activationbuild/activate-native-ha-v050-20261101.py updatedtostage-v4,stillNOTRUN.
Prior0.5Core restartreadinessquestionSTILLPENDING; logomessagewasNOTapproval.
KeepactiveHA0.4.0/Nestunchangeduntilownerreadyreply. Brandingwillloadwith0.5.

OwnerEXPLICITLYapproved0.5activation+oneCore restart. Executedprepared
build/activate-native-ha-v050-20261101.py (LATESTstage-v4/32files),session66502
possiblystillrunning. Stagedandoldactivesourcebothrechecked, newsourceactivated
andreadback32filesbeforeha core restart. Previous0.4sourcepreservedremote
/homeassistant/.hearth-native-previous-20261101-050. Receiptactivation-v1.
Read-onlywatch25630 private/native-ha-v050-20261101/reconnect-watch-v1. New
healthscriptbuild/check-native-ha-v050-20261101.py (freshhealth-v1) andread-only
serverweatherprobe build/check-native-ha-v050-weather-20261101.py preparedbut
NOTRUNyet. Weatherprobeusesownassignedauth+syntheticpostalquery; doesNOTcontact
unit/modifysettings. Privateweatherresponsekept600, printsfields/countsonly.
Noeco/schedule/mode/target/fancommandssent. WaitCoreexitthenhealthandweather
checks; actualnativefetch/eco/scheduleacceptanceUNVERIFIED. Emptybaseonly.

0.5activation66502 exited0: approvedCore restartcompletedONCE. Liveactive32files
exactreadback, 4entities/none disabled,0scopedHearthERRORs; cacheloads/600/1device
verified, warningsonlyusualcustomintegrationnotice. HostREADONLYweatherprobe
weather-host-check-v1returns200/currenttemp+humidity+icon/48hourly/6daily/tz,
privatepayload0600. ThisrequestcameFROMHOST,notproofunitweatherfetch. Noeco/
schedule/controlcommands. Watch25630firstseesrestored3cachedreadingfieldsbut
initialavailablefalse/norequests. Askedownernormal10sechold/release/singlepress
ONEMPTYbase/USBunpluggedtoforceentry; awaitWiFi/dialreply. Noloaderorflash.
Featurecachehealth-v2 pending71727reads ONLYfieldpresence/bucketnames, noowner
values. Needactualrestart/nativeconnectionthenchecknewhome/schedulebaselines.
NativeweatheracceptancecanbecheckedonunitUI; managercurrentlydoesnotexport
weatherproviderdiagnostics, avoidclaimbasedonhostprobealone. ExistingHAadmin
SupervisorAPI401restrictionstillapplies; donotseekextraauth/privilegeunnecessarily.

OwnerrestartconfirmedWiFi. Postrestartwatch29090showsavailabletrue,newmode
field+13PUT/13SUB accepted, onebucket_shape refusalinitially. ActualcapsOFFONLY
(expectedemptybase);home_reference/eco/weekstillabsent(health-v4). Noedits/intents.
OwnercannotfindweatherUIandreportsclock3hbehind(westcoast)despiteEastcoastpostal
configured. PrivatehostweatherresponseACTUALtimezoneAmerica/New_York, expected
Eastcoast;nativezoneinfofileexists. DoNOTblameHAconfigoraskchangeZIP. Oldnative
clientweatheroverrideenable0/poll3900s. Needtraceweatherdelivery/nativeapply.
PinnedNLEdevice_auth.py(originalhashverified)EXPLICITLYleavesweatheroutside
transportauth. Hearth0.5weathercurrentlyrequiresassigneddeviceBasic; plausible
compatibilityissue,NOTyetactualrequestproven. ReadonlyGhidrafetchclassreview
running355? seeprivate/native-weather-fetch-review-20261101/headless.log; derives
RTTI/vtablefromprivateELF, nofirmwareexecution. Mustnotclaimweatherworkingonunit
basedhostGET. Noschedule/eco commands andnopersistentfirmwareworkauthorized.

Concrete0.5weatherAUTHBUG: nativeweatherstartFUN00153fb8 allocatesfetchURL event,
InitdoesNOTenableBasic;libconstructor+0x54defaults0;IsBasicAuthEnabledreadsfield;
AddFetchattachescurlUSERPWD/HTTPAUTHonlyiftrue. ComparedpinnedNLEweatherexcluded
fromtransportauth. Hostauthenticated200wasINSUFFICIENTandmissedthiscompatibility
constraint. Nativeweather0.5.1candidateallowsONLYreadonlyoutdoorGETwithoutdevice
auth. Otherentry/transport/manageauthunchanged, TLSunchanged. ExposesonlyHA
outdoorconditions/forecast/tz+boundedcallerpostalcountry, no unitstate/control.
Nativeweathergetterqueryfallbackipv4/countrylessSTILLREFUSED; ownerhaspostal
configured, no geolocationguessingadded. Nativeclockactualapplicationunverified.

0.5.1addsvalue-freeweatherstatsinmanagerstatusandHAdiagnostics:requests,served,
invalid_query,unavailable,client_requests,host_checks. HostprobesMUSTsetUA
HearthReadOnlyCheck/1; classificationisdagnosticnotauth. Usecountstoverifyreal
clientfetchbeforeclaimingclockfixed. HostoldprobestemusedPythonUA; afternewCore
counterresetusefixedUAalways.

0.5.1FINAL32filesbuild/native-ha-weather-auth-20261101-v051-1 +v051-reproexact;
1205host/fiveoptionalskips+makecheck+realHA17roundtrips/unauthweatherGETallpass.
Stageprivate/native-ha-v051-20261101/stage-v1/remote.hearth-native-stage-20261101-
v051readbackwitholdACTIVE0.5.0sourcebackup. NOTACTIVATED; owner0.5approvalconsumed,
neednewCore restartreadinessafterconcretereadyfix. NoROM/NAND/commands.

OwnerEXPLICITLYapproved0.5.1+oneCore restart. Executedprepared
build/activate-native-ha-v051-20261101.py session48397; exactstage/oldsourcechecks
and32newactivefilesreadbackpassedbeforeCore restart. Preserveprivate/native-ha-
v051-20261101/activation-v1 andremote.previous-20261101-051(old0.5.0).
Watcher91687 build/watch-native-ha-v051-20261101.py runs5min, privatefresh
reconnect-watch-v1 includesweather_diagnostics counts; no commands. CheckCore
exitthenbuild/check-native-ha-v051-20261101.py health-v1 andhostweatherprobe
build/check-native-ha-v051-weather-20261101.py taggedUAHearthReadOnlyCheck/1
(noBasicneeded). Thatprobecreatesweather-host-check-v1onlyONCE. AfterCorehealth
watchclient_requests/servedvsfixedhost_checks; noadditionalringrestartunless
needed. OwnerunitremainsEMPTYbase/WiFi,ZIPunchanged. Nativeclockmustbeverified
ownerafteractualclientserved; noautocontrol/noeco/schedule.

0.5.1activation48397 exited0(approvedCore restartcomplete). Health-v1live0.5.1,
4entities/0disabled/0HearthERROR/cache600/1device. NewUNTAGGED? hostweather
probeactuallyTAGGEDUAHearthReadOnlyCheck/1; weather-host-check-v1returns200
48hourly/6daily/expectedtimezone, countersmustshowhost_checks1. No unitcommands.
Watchinitialclient_requests0. AskedownerONEnormalNest10sec/release/singlepress
ONEMPTYbase/USBdisconnectedthenclockcorrectvs3hbehind. Reasonstockweather
poll3900s, waitfornormalpollcould65min. Awaitreply; noRAMloader. Firstreconnected
0.5sawonlyoffequipmentcapability/homeandscheduleabsent, remainsguarded.
