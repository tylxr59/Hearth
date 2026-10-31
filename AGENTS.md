# Hearth: agent handoff and repository instructions

## Purpose and current status

Build a local-first Nest Learning Thermostat modification that preserves native hardware/HVAC control. Gen 2 is the primary target; Gen 1 is secondary. Prefer a verified local on-device interface if feasible; otherwise retain the native transport behind a minimal local backend. Do not rewrite HVAC control loops.

The user's unit has arrived and received USB intake on their PC. Arrival/ownership alone does not authorize flashing or physical control. The owner has explicitly authorized device investigation and requests advance notification for potentially dangerous actions such as flashing; preserve the backup/recovery gates below. The [2026-10-30 intake](docs/research/device-intake-2026-10-30.md) records enclosure `02A`, reported `Display-2.6`, firmware `5.9.4-5`, normal-mode USB `2464:0002` and an authorized manual restart briefly exposing OMAP `0451:d00e`. A later paced diagnostic RAM boot succeeded and returned to native startup. No flashing, HVAC operation or firmware recovery test has been performed. Two complete owner raw NAND captures and independently matching BCH-derived data views now exist privately; native nlclient/osm were reconstructed for static inspection. Restoration remains unverified.

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
is uninstalled and unvalidated on target. Originals remain unchanged. No binary
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
cache sanitizer stress checks and 29 settings tests pass. New private UNEXECUTED
profile: private/native-settings-probe-20261031/profile-capped-diagnostics; helpers:
build/native-settings-lab-20261031/helpers-capped-diagnostics. Seven artifacts match
a fresh reproducibility profile. No kernel/bootstrap/library/writer change.
Notify the owner before any new manually timed run; no loader is armed.
See docs/research/settings-probe-attempt-2026-10-31.md and the probe README.
Next: finish independent host work and native protocol/storage review while the
prepared settings target measurement waits for the owner.
Prepare any new bounded RAM test completely before another owner-timed restart;
no automatic device retry. Existing TLS measurement does not close the native
settings error/rollback, backup/restoration, full fetch/transport or HVAC gates.
For a future explicit diagnostic, use a fresh private profile, PTY-backed loader,
normal-mode preflight and the reviewed manual sequence. After command exit, use
a full ~10-second hold when the screen is already black, release, press/release
once and confirm native startup. All prepared images/libraries/keys/results stay
private. No base connection or persistent modification is authorized by a TLS pass.
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

Progress on independent host work while hardware investigation is blocked. Useful remaining work includes transactional credential/export recovery, retained MQTT cleanup after offline revocation across backend restarts, real HAOS installation, aarch64 validation and container/firmware supply-chain analysis. Keep the small working prototype intact; avoid adding speculative APIs or capabilities.

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
