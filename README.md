# Hearth

A local-first laboratory for Nest Learning Thermostat Gen 2, with Gen 1 as a secondary research target. Preserve Nest's hardware control; replace remote services only where behavior is understood.

**Current hardware result:** [original-file recovery](docs/research/compression-recovery-2026-10-31.md)
restored the working primary native UI. The [corrected nine-file installation](docs/research/recommissioning-preparation-2026-10-31.md)
now passes exact readback and active native-compatible encoding checks, with
write protection asserted. Its native UI check is pending. Do not use the old
LZO-writing images.

**Status: experimental same-unit investigation, not a supported thermostat release.** The first [nine-file install](docs/research/file-install-result-2026-10-31.md) passed readback but the native UI stalled. The selected original files have now been [restored and verified](docs/research/file-restore-result-2026-10-31.md); the owner confirmed the working stock UI, and the native plist confirms the primary slot remains selected on firmware `5.9.4-5`. Live native networking, complete protocol/control, power-loss/whole-firmware recovery and HVAC remain unverified. The local HAOS backend runs in telemetry-only mode, with commands disabled. Do not connect this prototype to live HVAC equipment. This iteration does not meet the physical firmware compatibility portion of the definition of done.

An authorized restart exposed OMAP ROM mode on the unit reporting `Display-2.6` /
`5.9.4-5`. A separate [experimental RAM heartbeat probe](firmware/probe/README.md)
has now booted on this unit, emitted its expected USB heartbeat and returned to
native startup after a manual restart. It does not acquire flash or provide recovery. [Current evidence and next test](docs/research/acquisition-review-2026-10-30.md).

A separate [NAND geometry-only RAM profile](firmware/nand_metadata/README.md)
has booted once and reported 256 MiB NAND with 2 KiB pages. It reads
master geometry through sysfs with layered write guards, without acquiring
firmware contents or establishing recovery.

Two full raw NAND reads are now preserved privately. Their raw bit differences
were resolved in separate offline BCH-derived data views, which match; four boot
image payload CRCs pass and native `nlclient`/`osm` were reconstructed for static
inspection. This is acquisition evidence, not verified restoration or a usable
native control API. [Measurement and limits](docs/research/nand-capture-2026-10-30.md).

The [native interface review](docs/research/native-interface-2026-10-30.md)
identified a loopback temperature-control candidate. Startup and request framing
remain unverified; the host transport remains provisional and no native bridge
is enabled.

A [private RAM-only TLS experiment](firmware/tls_probe/README.md) now completed
all 18 expected callback cases on the device; the candidate accepted valid and
rejected all eight invalid cases. Native startup returned afterward. See the
[measured scope](docs/research/tls-probe-result-2026-10-30.md): nothing was installed,
and full transport/configuration, credential persistence, recovery and HVAC
remain unverified.

An opt-in [authenticated native telemetry laboratory](docs/research/native-telemetry-2026-10-31.md) now accepts bounded NLE-style entry/PUT/metadata/subscription requests and publishes read-only MQTT sensors. Host validation does not establish physical Nest compatibility.

Implemented:

- TLS local API, separate device/management authentication, registration, rotation and revocation.
- Validated state, constrained commands, reported-state separation, availability and command expiry.
- MQTT climate discovery and commands, tested with a real authenticated TLS Mosquitto broker and simulated devices.
- Linux credential preparation, read-only USB inventory/watch, allowlisted diagnostic metadata, SHA-256 input verification, deterministic inert firmware review bundles and offline hardening replacements.
- Unprivileged container, locally assembled HAOS add-on, hash-locked dependencies, scans, regression and property tests.

Nothing implements HVAC control loops. No proprietary firmware or upstream executables are bundled. No telemetry, weather provider, cloud registration, remote support, public defaults, executable upload or automatic update mechanism is included.

## Start locally

Requires Linux, Python 3.12+ (tested with 3.13.16); Docker and OpenSSL for broker/container tests.

```sh
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.lock
make test
make integration
make container-test
make check
make audit
make demo
```

`make container-test` builds and tests the unprivileged HTTPS container. `make integration` starts an ephemeral TLS Mosquitto container on loopback and removes it afterward. It does not access USB or HVAC hardware. `make demo` creates synthetic input, `build/demo/review.tar`, a SHA-256 manifest and private offline replacement files. All firmware artifacts are inert and explicitly marked non-flashable. Offline replacements also prepare `uploadlogs=0`; the config editor requires the reviewed XML structure and preserves other bytes. Native storage error handling and a complete outbound-service audit remain unresolved; see [storage review](docs/research/native-storage-2026-10-30.md).

Prepare a simulated device (secrets are written to private files, never printed):

```sh
.venv/bin/python -m provisioning.cli init --registry private/registry.json --admin-file private/admin.json
.venv/bin/python -m provisioning.cli prepare --registry private/registry.json \
  --output private/device --serial 02AA01AB501203EQ --generation 2 \
  --endpoint https://127.0.0.1:8443 --modes off heat cool
```

Generation is a user claim, **not** detection or verification. See [local setup](docs/development.md) for certificates, the simulator, commands and MQTT configuration. `detect` reads sysfs only and refuses to infer a generation from TI USB identity.

## Read next

- [Next-agent handoff and instructions](AGENTS.md)

- [Implementation plan and status](docs/implementation-plan.md)
- [Research and evidence](docs/research/findings.md), [pinned upstream sources](docs/research/upstreams.json)
- [Architecture decision](docs/architecture/0001-local-transport.md), [protocol](docs/protocol/nest.md)
- [Threat model](docs/security/threat-model.md), [audit](docs/security/audit.md), [network policy](docs/security/network.md)
- [HAOS installation and upgrades](homeassistant/DOCS.md)
- [Hardware validation and recovery gates](docs/hardware.md)
- [Licensing and provenance](THIRD_PARTY.md), [remaining work](TODO.md)

Research references: [NLE thermostat](https://github.com/codykociemba/NoLongerEvil-Thermostat), [backend](https://github.com/codykociemba/NoLongerEvil-SelfHosted), [HA add-on](https://github.com/codykociemba/NoLongerEvil-HomeAssistant), [Valetudo](https://github.com/Hypfer/Valetudo). Exact revisions and individual source hashes are recorded; moving branches are not build inputs.
