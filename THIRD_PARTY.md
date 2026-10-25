# Licensing and provenance

Hearth's original source is MIT licensed (see LICENSE). This does not grant rights to any Nest firmware. No NLE, Valetudo, NestDFUAttack source implementation, firmware executable, bootloader, kernel image or host loader is copied into runtime/build outputs here. Small protocol identifiers and behavioral observations inform independently written code. Sources retained in `/tmp` during research were not executed or committed.

## References

| Upstream | Pinned revision | License / permission finding | Use |
|---|---|---|---|
| codykociemba/NoLongerEvil-Thermostat | fabbe034f01cefdabe06b93d1c312068f563a177 | No repository LICENSE found in inspected tree; embedded dependencies have distinct rights. Do not infer permission to redistribute. | Architecture/security research only. |
| codykociemba/NoLongerEvil-SelfHosted | bca8781012639c1cefc4a08c103fc892158fb630 | MIT, Cody Kociemba 2025. | Protocol/security research; no implementation copied. |
| codykociemba/NoLongerEvil-HomeAssistant | 39a344087c679a36ebfe6d2b37f26f8eb04cae47 | MIT, Cody Kociemba 2025. | Packaging/security reference; no scripts copied. |
| Hypfer/Valetudo | 69c60625b8d48f5f62f02299cfd326c24bb3df2b | Apache-2.0 in inspected package/source. | Philosophical inspiration and capability separation; no implementation/assets copied. |
| exploiteers/NestDFUAttack | 930b834b7f1f082b8761aa5c5af765b4b3e99dc9 | Mixed components. Linux GPL-2.0, bootloader/toolchain and proprietary root content need per-file review. Nest root scripts explicitly retain Nest copyright. No blanket firmware redistribution grant established. | Static boot/kernel/root-config research only; no code or binary reuse. |

[upstreams.json](docs/research/upstreams.json) includes URLs, revisions and individual hashes for reproducible inspection. [binary-inventory.json](docs/research/binary-inventory.json) identifies NLE prebuilts without redistributing them. No source-to-prebuilt correspondence, signature chain, vendor authenticity or legal permission is asserted by matching a Git blob or SHA-256. Any future firmware input must be lawfully obtained by the owner, independently identified and kept out of source/releases.

## Runtime dependencies

Full versions and package metadata: [python-dependencies.json](docs/security/python-dependencies.json). Hash-locked distributions: requirements.lock. Runtime directly uses aiohttp (Apache-2.0 AND MIT) and paho-mqtt (EPL-2.0 OR BSD-3-Clause per distribution metadata; retain notices when distributing). Transitives include aiohappyeyeballs (PSF-2.0), aiosignal/frozenlist/multidict/propcache/yarl (Apache-2.0), attrs (MIT) idna (BSD-3-Clause) and conditional typing_extensions (PSF-2.0); see each distribution's license files for authoritative terms. Metadata inventory is not a substitute for retaining the installed licenses. No dependencies are vendored.

Python container base is official `python:3.13.16-slim`, pinned by manifest digest in Dockerfile. It includes CPython (PSF license) and Debian/system packages with their own licenses and sources; Docker's upstream digest is an integrity pin, not a vulnerability clearance. MQTT integration tests use official eclipse-mosquitto 2.0.22 pinned by digest in tests/test_broker.py; it is a development-only download, not bundled firmware. Mosquitto has its own EPL/EDL licensing terms. OpenSSL and Docker are development tools supplied by the host.

The wheel build backend setuptools 84.2.1 (MIT) is separately hash-pinned in requirements-build.lock and scanned. Development tools (pytest, pytest-asyncio, Hypothesis, Ruff, Bandit, pip-audit and transitives) are version/hash pinned in requirements-dev.lock. CI uses pinned checkout action source; runner OS/toolchain itself is not a reproducible build image. Release tooling creates a source tar and manifests without uploads or publication.

## Firmware retention policy

Future owner-specific images must retain nlclient, osm where necessary, kernel/drivers, backplate MCU firmware, calibration and essential power services until individually understood. Their proprietary status and outdated dependencies remain risks, even when all host code is open. Preserve required notices and obtain applicable permissions before redistribution. Private development does not erase third-party license obligations. No firmware license conclusions are inferred from open-source kernel availability.
