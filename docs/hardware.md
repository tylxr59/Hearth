# Gen 2 bench validation and recovery gates

**No hardware is available or verified. No flash/apply command is implemented.** Preparation artifacts are not bootable images and must not be sent to a USB loader. Gen 1 remains a separate, unvalidated profile; never select a generation from USB vendor/product alone.

Physical device flashing, modification or control requires fresh explicit human authorization for that action. Actual HVAC switching tests additionally require explicit authorization, appropriate isolated equipment and a person qualified for the wiring/system. The project request does not authorize those actions. Do not connect a production HVAC system for initial tests. Do not use a thermostat safety limit as the sole safeguard.

## 1. Establish identity and recovery before writes

1. Record enclosure/base model, serial, generation, board revision and installed software using the native UI or separately authorized read-only access. Photograph wiring and label conductors before any qualified disconnection. Use approved, current-limited power and bench equipment appropriate to that model; no invented voltage/pin assumptions.
2. Inventory USB using `python -m provisioning.cli detect`; TI identities are candidates only, never compatibility proof. Verify tooling source/revision, license and authenticated tool digest independently. Do not run the upstream bundled loader merely because a SHA-256 matches the same download.
3. Acquire a lawful complete firmware dump using a reviewed read-only procedure for that exact model. Capture kernel version/config, `/proc/mtd`, mount layout, boot environment, active processes/listeners, init/service configuration, trust stores and version identifiers. Avoid printing user settings/secrets. Static ELF analysis may use trusted host readelf/objdump/strings; never execute ARM firmware on the host or under emulation without a separate reviewed containment plan.
4. Back up raw flash with bad-block/OOB information using a qualified NAND procedure. A mounted-file copy is insufficient for recovery. Hash, independently re-read and compare; encrypt/store two offline copies. Preserve factory calibration, serial-specific credentials, backplate firmware and user settings. The tool and exact offsets cannot be specified safely until the MTD map/device is known.
5. Demonstrate ROM/recovery entry and a tested restoration path on a spare bench unit. Document button sequences, USB timing, partition identity and power requirements from measurement. If recovery cannot be demonstrated, do not write. No automatic rollback or dual-image support is assumed.

## 2. Read-only reverse engineering

Capture authorized local IPC metadata first: socket files, D-Bus service names/policies, configuration hierarchy and nlclient/osm ELF dependencies. Introspect only with a known non-mutating method after reviewing application behavior. SCPM lifecycle methods can stop control/power services; do not invoke them during discovery. Observe backplate communication passively using suitable high-impedance equipment and an electrical expert; do not inject MCU frames.

Confirm Basic auth wire format, assigned_cred_secret source and lifetime, enrollment/default credential flow, accepted HTTPS protocol/ciphers, certificate-chain and hostname verification, private CA deployment, expired/future clock behavior. Test a wrong CA, wrong SAN, expired cert and wrong credential; each must fail closed. Preserve old settings offline for restoration. Do not claim secure transport if a random credential is sent in plaintext. If no verified secure client path is feasible, leave networking disabled and research a compatible tunnel/bridge instead.

Capture full entry/pairing/subscribe/PUT/CAS traffic to an isolated local endpoint. Establish bucket schemas, session rules, timestamp authority, chunking, retries, sleep/WoWLAN timing and schedule interactions. Add sanitized fixtures and tests before enabling those paths in production. Missing fields must remain unknown rather than invented.

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
