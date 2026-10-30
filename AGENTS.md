# Hearth: agent handoff and repository instructions

## Purpose and current status

Build a local-first Nest Learning Thermostat modification that preserves native hardware/HVAC control. Gen 2 is the primary target; Gen 1 is secondary. Prefer a verified local on-device interface if feasible; otherwise retain the native transport behind a minimal local backend. Do not rewrite HVAC control loops.

The user's unit has arrived and received USB intake on their PC. Arrival/ownership alone does not authorize flashing or physical control. The owner has explicitly authorized device investigation and requests advance notification for potentially dangerous actions such as flashing; preserve the backup/recovery gates below. The [2026-10-30 intake](docs/research/device-intake-2026-10-30.md) records enclosure `02A`, reported `Display-2.6`, firmware `5.9.4-5`, normal-mode USB `2464:0002` and an authorized manual restart briefly exposing OMAP `0451:d00e`. No payload execution, flashing, HVAC operation or recovery test has been performed. No firmware dump or proprietary nlclient/osm executable is available.

Implementation baseline: commit `30c82f5`. It contains an authenticated host-side laboratory, not deployable thermostat firmware:

- HTTPS API with separate device/manager credentials, enrollment, rotation/revocation, validated commands, expiry and availability.
- MQTT climate discovery/control, dedicated broker ACLs, TLS, retained-command rejection and offline availability handling.
- Linux credential preparation and read-only sysfs USB inventory.
- Deterministic inert firmware review archives and partial offline replacement files. No apply/flash command or bootable image.
- Container, experimental HAOS package, simulated devices, tests, scans and provenance inventory.

The canonical `/v1/device/*` contract is new; stock Nest does not implement it. `backend/nest.py` is a strict partial PUT decoder, disabled in the normal runtime. Pairing, revision/CAS reconciliation, chunked subscriptions and physical command delivery remain incomplete. A passing simulator is not Nest compatibility.

## Read before implementation

1. `README.md` and `TODO.md` for scope and outstanding work.
2. `docs/architecture/0001-local-transport.md` for the provisional architecture decision.
3. `docs/research/findings.md`, `docs/research/upstreams.json` and `docs/protocol/nest.md` for evidence and protocol limits.
4. `docs/security/audit.md`, `docs/security/threat-model.md` and `docs/security/network.md` for boundaries and remaining risks.
5. `docs/hardware.md` before planning any physical-device work.
6. `THIRD_PARTY.md` before reusing source, firmware or tools.

Do not redo completed research indiscriminately. Distinguish confirmed source findings, upstream reports, hypotheses and new hardware measurements. Pin any new upstream revisions and record what changed.

## Resume on another PC

Use the Git repository, including this file and all committed docs. Nothing has been pushed or published as part of this handoff. Do not push/upload without user authorization.

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
