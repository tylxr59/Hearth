# Gen 2 bench validation and recovery gates

**A physical unit has received read-only USB intake; firmware compatibility and recovery remain unverified. No flash/apply command is implemented.** See the [2026-10-30 intake](research/device-intake-2026-10-30.md): enclosure `02A`, reported `Display-2.6`, software `5.9.4-5`, normal USB `2464:0002`. Preparation artifacts are not bootable images and must not be sent to a USB loader. Gen 1 remains a separate, unvalidated profile; never select a generation from USB vendor/product alone.

An authorized manual restart subsequently exposed `0451:d00e` briefly. The
separate [RAM probe](../firmware/probe/README.md) now compiles experimental boot
code for this reported model, with no MTD/block/network support in its Linux
kernel. Its first successful heartbeat boot and native return are recorded below.
Its bootloaders still initialize hardware; this is not an observational sysfs
read, a NAND backup or a recovery test. Notify the owner before execution under
their existing device-work authorization. Keep the display detached from its
unwired base, observe a heartbeat if it boots, and confirm native startup after
the loader exits. Never write probe images to flash or confuse them with the
inert review tar/partial replacements. [Review and source pins](research/acquisition-review-2026-10-30.md).

The first upload attempt subsequently stalled at the ROM length word, before
the first-stage file-data call. Native home icon and normal USB mode returned
after the owner restarted with the loader exited. A paced host-loader retry subsequently booted the diagnostic kernel; its USB
heartbeat and return to native startup were observed. The image bytes were unchanged. [Failure evidence and scoped automation
permissions](research/usb-handshake-2026-10-30.md). No NAND acquisition or firmware restoration has been demonstrated.
The heartbeat establishes only this one diagnostic boot/USB path.

A separate [NAND geometry-only profile](../firmware/nand_metadata/README.md)
has passed offline checks and one supervised boot, reporting 256 MiB NAND,
128 KiB erase blocks, 2 KiB pages and 64-byte OOB with zero capability flags.
Normal Nest USB mode returned after the owner reported ready. It adds NAND ID/geometry initialization with hardware WP asserted,
protected-status verification, BBT scanning disabled and write callbacks denied.
There are no MTD char/block interfaces, partitions, firmware reads or storage
mounts. It is still an experimental RAM boot with unverified whole-chain side
effects, not a backup or recovery procedure.

The separate [bounded raw sample profile](../firmware/nand_sample/README.md)
is built and checked offline. It retains those write guards and adds only a
fixed first-erase-block read-only sysfs content interface, read twice into RAM.
No MTD character interface is enabled. Its initial transport test failed closed due to gadget tty newline translation;
the corrected binary-tty boot then captured two matching first-block raw/OOB
samples, verified privately. Normal Nest USB returned after that boot.
Data and OOB captures remain private and cannot be treated as a full backup.

The [full-chip raw reader](../firmware/nand_capture/README.md) now passes offline
checks. It requests two fixed whole-chip passes in one RAM boot and keeps the
same write guards. Its first physical capture completed with a raw mismatch; both inputs were
preserved. Offline BCH-derived views independently match, embedded image CRCs
pass and root0 files are available privately. Four chunks retain unclassified
ECC; native normal USB returned. Raw acquisition does
not demonstrate restorability or close the backup/recovery gates.

Physical device flashing, modification or control requires explicit human authorization covering that action. Honor existing authorization without repeating permission requests; notify this owner before experimental RAM execution and preserve the backup/recovery gates before persistent writes. Actual HVAC switching tests additionally require explicit authorization, appropriate isolated equipment and a person qualified for the wiring/system. The project request does not authorize those actions. Do not connect a production HVAC system for initial tests. Do not use a thermostat safety limit as the sole safeguard.

The [TLS RAM experiment](../firmware/tls_probe/README.md) is separately built
and checked offline. It loads native curl/OpenSSL plus original/candidate hooks
with synthetic loopback peers, without nlclient/osm, flash support or physical
networking. RTC drivers and forced hardware-clock update selections are disabled;
its 2030 clock is a RAM test fixture. The first attempt reported failure before any TLS cases; the corrected second run
completed all 18 expected cases and returned to native startup. Bootstrap hardware/power behavior remains unverified; keep the
display detached from the unwired base. This diagnostic does not waive any
persistent-write, recovery or HVAC gate below.

## 1. Establish identity and recovery before writes

1. Record enclosure/base model, serial, generation, board revision and installed software using the native UI or separately authorized read-only access. Photograph wiring and label conductors before any qualified disconnection. Use approved, current-limited power and bench equipment appropriate to that model; no invented voltage/pin assumptions.
2. Inventory USB using `python -m provisioning.cli detect`; TI identities are candidates only, never compatibility proof. Verify tooling source/revision, license and authenticated tool digest independently. Do not run the upstream bundled loader merely because a SHA-256 matches the same download.
3. Acquire a lawful complete firmware dump using a reviewed read-only procedure for that exact model. Capture kernel version/config, `/proc/mtd`, mount layout, boot environment, active processes/listeners, init/service configuration, trust stores and version identifiers. Avoid printing user settings/secrets. Static ELF analysis may use trusted host readelf/objdump/strings; never execute ARM firmware on the host or under emulation without a separate reviewed containment plan.
4. Back up raw flash with bad-block/OOB information using a qualified NAND procedure. A mounted-file copy is insufficient for recovery. Hash, independently re-read and compare; encrypt/store two offline copies. Preserve factory calibration, serial-specific credentials, backplate firmware and user settings. The tool and exact offsets cannot be specified safely until the MTD map/device is known.
5. Demonstrate ROM/recovery entry and a tested restoration path. A spare bench unit is preferred; on 2026-10-31 this owner confirmed they have only this unit and accepted potentially dangerous same-unit work, so a spare is not mandatory here. Before the first same-unit persistent recovery test, prepare the exact reviewed operation, verify original inputs/partition identity/write semantics and notify the owner of the recovery limits. Demonstrate restoration before installing modifications. No automatic rollback or dual-image support is assumed.

## 2. Read-only reverse engineering

Capture authorized local IPC metadata first: socket files, D-Bus service names/policies, configuration hierarchy and nlclient/osm ELF dependencies. Introspect only with a known non-mutating method after reviewing application behavior. SCPM lifecycle methods can stop control/power services; do not invoke them during discovery. Observe backplate communication passively using suitable high-impedance equipment and an electrical expert; do not inject MCU frames.

Confirm Basic auth wire format, assigned_cred_secret source and lifetime, enrollment/default credential flow, accepted HTTPS protocol/ciphers, certificate-chain and hostname verification, private CA deployment, expired/future clock behavior. Test a wrong CA, wrong SAN, expired cert and wrong credential; each must fail closed. Preserve old settings offline for restoration. Do not claim secure transport if a random credential is sent in plaintext. If no verified secure client path is feasible, leave networking disabled and research a compatible tunnel/bridge instead.

Capture full entry/pairing/subscribe/PUT/CAS traffic to an isolated local endpoint. Establish bucket schemas, session rules, timestamp authority, chunking, retries, sleep/WoWLAN timing and schedule interactions. Add sanitized fixtures and tests before enabling those paths in production. Missing fields must remain unknown rather than invented.

The [offline native bootstrap review](research/native-bootstrap-2026-10-30.md)
traces assigned credentials and a response-header update path that logs both
values. Its private logging-removal candidate is uninstalled. Validate settings
serialization, two-key commit/rollback, log/upload disclosure, restart readback
and rejection of default fallback after revocation before native commissioning.
Do not send real credentials through that path merely because the header format
is now understood.

The [storage follow-up](research/native-storage-2026-10-30.md) traces file/directory
sync and rename, but entry write errors can log settings values without blocking
replacement, and directory-sync errors can clear dirty state. Require entry-write
fault propagation, correct dirty-state retry and interrupted credential-rotation
tests before trusting persistence. Offline staging disables the traced log uploader
only; existing logs and other outbound paths remain separate review requirements.

## 3. Review candidate modifications

Pin the actual input hashes. Generate an inert review archive and private hardening replacements. Compare every edited file, prove that unknown/native services are preserved, and map every listener/startup path. The current four-file staging tool is incomplete for stock firmware: audit the historical serial debug shell, Lua bot port 8000, SSH/remote-support service monitors, crash upload paths and all actual firmware init entry points. Do not deploy the partial overlay as if it were hardened firmware.

For any later authorized install, use a model/revision-specific profile with verified backup/restore, transactional file handling, boot failure recovery, uniquely generated credentials, expected post-install listeners, locked password authentication and a verified local TLS trust path. Disable temporary provisioning and CGI services, including Monit restart paths, and verify they stay disabled across restart. Do not delete osm/backplate updates or native code without establishing its role.

## 4. Measurement matrix

Run the following first against sensor simulation/dummy loads, with independent temperature reference, current/power measurement, relay/logic capture and bounded test duration. Record initial/final native settings, exact firmware hashes, power source, HVAC wiring/capability profile, observed thresholds, response times and pass/fail evidence.

| Test | Evidence required |
|---|---|
| Baseline offline native UI | Ring/local setpoint works with network absent; no unintended call for heat/cool. |
| Regulation | Temperature sweep around native target; hysteresis/control behavior and sensor agreement characterized. Do not define expected thresholds without model evidence. |
| Native protective limits | Equipment-specific high/low limits and sensor fault handling; independent cutoff and expert supervision. |
| Compressor protection | Cooling/heat-pump minimum cycle/delay across mode change and restart, based on equipment requirements. |
| Modes and fan | Only physically wired modes; fan request duration/timeout/cancellation and power effect understood. |
| Native schedule | Transitions across backend disconnect/reconnect/restart; no stale server setpoint overrides. |
| HA/broker/backend outage | Local adjustment/regulation continues; availability goes offline; no stale command replay after restart. |
| Wi-Fi/DNS failure | Control continues, retry storm and battery drain measured, no external fallback. |
| Clock failure | No invalid TLS acceptance, native schedule effects measured, command TTL remains bounded on backend. |
| Power restart | No unexpected relay transitions; settings/schedule recovery, watchdog/SCPM and backplate synchronization characterized. |
| Interrupted commissioning | Verified original state recoverable; credentials and endpoint either restored or consistently committed. |
| Interrupted host upgrade | Native control unaffected, no queued command replay; host rollback works. |
| Future firmware interruption | Only on a sacrificial authorized bench unit after recovery validated; power loss at each write stage with measured restoration. No production tests. |
| Privacy/isolation | VLAN/WAN captures confirm no successful external request across all failure cases; IPv6/L2 isolation tested. |

Native code preservation is not proof of safe operation. Any unexpected output, sensor error, battery collapse, repeated restart, schedule overwrite or inability to recover is a stop condition. Restore the known original state through the demonstrated procedure, keep the unit disconnected from physical HVAC, and investigate.

## 5. Promotion gate

Enable a hardware profile only after the firmware/control interfaces, TLS/authentication, post-provision service checks, network restrictions, sleep/power behavior and relevant failure matrix pass with recorded artifacts and human sign-off. Gen 1 requires its own results. Document what remains unsupported rather than inferring compatibility from shared software.

The [second TLS RAM run](research/tls-probe-result-2026-10-30.md) completed all
18 expected original/candidate callback cases, followed by owner-confirmed native
home icon and independently observed normal USB. This is a loopback/native-library
measurement with synthetic fixtures, not full fetch/configuration, credential
commissioning, restoration, power or HVAC validation. The screen remains black
during the probe; native return required a full timed approximately ten-second
hold, release and single press with the loader exited.


The [native settings RAM matrix](research/settings-probe-result-2026-10-31.md)
also completed twelve synthetic-file fault cases after a reporting-budget
correction. It confirms original writer/retry defects; no writer fix, real
settings access, flash durability or power-loss measurement is claimed. The
owner-confirmed home icon and normal USB returned with the loader exited.
