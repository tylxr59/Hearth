# Hearth

A local-first laboratory for Nest Learning Thermostat Gen 2, with Gen 1 as a secondary research target. Preserve Nest's hardware control; replace remote services only where behavior is understood.

**Status: functional host-side prototype, not deployable thermostat firmware. No physical device has been flashed or tested.** The complete Nest pairing/subscribe protocol and device credential/TLS installation are unresolved. Do not connect this prototype to live HVAC equipment. This iteration does not meet the physical firmware compatibility portion of the definition of done.

Implemented:

- TLS local API, separate device/management authentication, registration, rotation and revocation.
- Validated state, constrained commands, reported-state separation, availability and command expiry.
- MQTT climate discovery and commands, tested with a real authenticated TLS Mosquitto broker and simulated devices.
- Linux credential preparation, read-only USB inventory, SHA-256 input verification, deterministic inert firmware review bundles and offline hardening replacements.
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

`make container-test` builds and tests the unprivileged HTTPS container. `make integration` starts an ephemeral TLS Mosquitto container on loopback and removes it afterward. It does not access USB or HVAC hardware. `make demo` creates synthetic input, `build/demo/review.tar`, a SHA-256 manifest and private offline replacement files. All firmware artifacts are inert and explicitly marked non-flashable.

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
