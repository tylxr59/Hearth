# Licensing and provenance

Hearth's original source is MIT licensed (see LICENSE). This does not grant rights to any Nest firmware. The host runtime contains no NLE, Valetudo or proprietary firmware implementation. The separate experimental RAM probe now compiles GPL kernel/bootloader sources and a patched GPL native USB loader into ignored local build outputs; no third-party executable or proprietary root is committed or included in source releases. Small protocol identifiers and behavioral observations inform independently written code. Initial sources retained in `/tmp` were not executed or committed.

## References

| Upstream | Pinned revision | License / permission finding | Use |
|---|---|---|---|
| codykociemba/NoLongerEvil-Thermostat | fabbe034f01cefdabe06b93d1c312068f563a177 | No repository LICENSE found in inspected tree; embedded dependencies have distinct rights. Do not infer permission to redistribute. | Architecture/security research only. |
| codykociemba/NoLongerEvil-SelfHosted | bca8781012639c1cefc4a08c103fc892158fb630 | MIT, Cody Kociemba 2025. | Protocol/security research; no implementation copied. |
| codykociemba/NoLongerEvil-HomeAssistant | 39a344087c679a36ebfe6d2b37f26f8eb04cae47 | MIT, Cody Kociemba 2025. | Packaging/security reference; no scripts copied. |
| Hypfer/Valetudo | 69c60625b8d48f5f62f02299cfd326c24bb3df2b | Apache-2.0 in inspected package/source. | Philosophical inspiration and capability separation; no implementation/assets copied. |
| exploiteers/NestDFUAttack | 930b834b7f1f082b8761aa5c5af765b4b3e99dc9 | Mixed components. Linux GPL-2.0, GPL U-Boot notices; proprietary root scripts retain Nest copyright. No blanket firmware redistribution grant established. | Static research; only GPL Linux/U-Boot source subtrees compiled for the local experimental probe. No proprietary root or prebuilt reused. |
| Google Nest 5.9.4 x-loader | 9b7bb7281b715544e6f5201390d8dac416a4a494 | GPL notices/COPYING in the published source; retain complete corresponding source/notices for any later redistribution. | Compiled locally for the model-specific RAM probe; no binary committed or published. |
| ajb142/omap_loader (also grant-h) | dc0758f91a4698054b0629a05f1b38b9b8b13de3 | GPL-2.0-or-later in source; LICENSE.md contains GPLv2. | Source reviewed, patched and compiled locally. Checked-in patch and combined C sanitizer harness are GPL-2.0-or-later. No upstream full source or executable vendored. |

[upstreams.json](docs/research/upstreams.json) includes URLs, revisions and individual hashes for reproducible inspection. [binary-inventory.json](docs/research/binary-inventory.json) identifies NLE prebuilts without redistributing them. No source-to-prebuilt correspondence, signature chain, vendor authenticity or legal permission is asserted by matching a Git blob or SHA-256. Any future firmware input must be lawfully obtained by the owner, independently identified and kept out of source/releases.

[The probe inputs](firmware/probe/inputs.json) additionally pin Google's source,
the historical CodeSourcery compiler mirror/archive and the reviewed host loader.
The compiler archive is used only inside a rootless build container, not installed
or executed directly on the host. It contains components with their own licenses;
no independent signature verification or source reconstruction is established.
It is not redistributed. The probe builder's pinned Ubuntu image and packages
have separate licenses and unresolved OS vulnerability coverage. Preserve the
generated source archives, patch, build configuration and notices alongside any
later owner-approved binary transfer; a SHA manifest is not GPL compliance by itself.

The host-loader patch now also adapts Doug Brown's GPL reliability changes from
`dougg3/omap_loader` revision `a33d75376f56f54285cdf6933e312b856146593b`
([upstream PR #7](https://github.com/grant-h/omap_loader/pull/7)). The original
base pin is unchanged; both revisions and source hashes are retained in the locks.

The separate `firmware/nand_metadata/readonly.h` is original GPL-2.0-or-later
code combined with the same pinned Linux driver. Its configuration recipe
modifies generated sources only; no kernel source or binary is vendored. Original
standalone geometry userspace, host parser and build tooling are MIT licensed.
The GPLv2 text accompanies the probe sources; preserve the combined source and
notices for any later authorized binary redistribution.

The separate `firmware/nand_sample/sample.h` and combined synthetic kernel
harness are original GPL-2.0-or-later code using those same pinned Linux interfaces.
Original standalone sample framing/userspace and host/build tooling are MIT.
No third-party binary, full kernel source or private capture is added to Git.

Offline NAND analysis additionally used public `python-bchlib` 2.1.3 source
(GPL-2.0), with sdist/file SHA-256 pinned in
[the analysis source lock](docs/research/bchlib-2.1.3.json). Only standalone public
BCH C code was compiled on the host; no Python package was installed and no
proprietary firmware was executed. The source/library remains under ignored
build/, is not vendored or redistributed, and is not a product runtime dependency.

The optional static-review workflow uses the owner's installed Ghidra 12.1.2 DEV
and Java 27. Only original `tools/ghidra/HearthStaticReview.java` is included;
Ghidra, its projects and proprietary decompilations are not bundled. Public
OpenSSL 1.0.2h/curl 7.49.1 reference files are pinned in
[the native TLS source record](docs/research/native-tls-source-pins.json), retained
under ignored build/, and neither vendored nor executed as target firmware.

The separate original firmware/tls_probe/ diagnostic reuses the same pinned
GPL kernel and validated boot stages. Its generated kernel recipe removes the
OMAP hardware-clock synchronization selections for this RAM-only experiment;
the unchanged native firmware is not patched by that recipe. Original helper,
packaging and observation source is MIT. Installed Clang/LLD compile only original
code with generated public ABI stubs; those stubs are not included on target.
Version-matched public curl/glibc API/startup references are pinned in
[the TLS probe source record](firmware/tls_probe/sources.json), retained under
ignored build/ and not vendored. Recovered libraries, the private review candidate,
synthetic private keys and the prepared image stay private and are not redistributed.

The separate original firmware/settings_probe/ diagnostic reuses those validated
private kernel/bootstrap and unchanged native-library inputs, without carrying
forward the TLS candidate or keys. It invokes only the reviewed base settings
class on synthetic RAM files. Original interposition, ABI checks and host test
doubles are MIT. Public NSPR declarations/constants are separately pinned in
firmware/settings_probe/sources.json; MPL-2.0 reference headers remain under
ignored build/ and are neither copied into source nor redistributed. This is not
a source/binary-correspondence claim for the recovered native NSPR library.

## Runtime dependencies

Full versions and package metadata: [python-dependencies.json](docs/security/python-dependencies.json). Hash-locked distributions: requirements.lock. Runtime directly uses aiohttp (Apache-2.0 AND MIT) and paho-mqtt (EPL-2.0 OR BSD-3-Clause per distribution metadata; retain notices when distributing). Transitives include aiohappyeyeballs (PSF-2.0), aiosignal/frozenlist/multidict/propcache/yarl (Apache-2.0), attrs (MIT) idna (BSD-3-Clause) and conditional typing_extensions (PSF-2.0); see each distribution's license files for authoritative terms. Metadata inventory is not a substitute for retaining the installed licenses. No dependencies are vendored.

Python container base is official `python:3.13.16-slim`, pinned by manifest digest in Dockerfile. It includes CPython (PSF license) and Debian/system packages with their own licenses and sources; Docker's upstream digest is an integrity pin, not a vulnerability clearance. MQTT integration tests use official eclipse-mosquitto 2.0.22 pinned by digest in tests/test_broker.py; it is a development-only download, not bundled firmware. Mosquitto has its own EPL/EDL licensing terms. OpenSSL and Docker are development tools supplied by the host.

The wheel build backend setuptools 84.2.1 (MIT) is separately hash-pinned in requirements-build.lock and scanned. Development tools (pytest, pytest-asyncio, Hypothesis, Ruff, Bandit, pip-audit and transitives) are version/hash pinned in requirements-dev.lock. CI uses pinned checkout action source; runner OS/toolchain itself is not a reproducible build image. Release tooling creates a source tar and manifests without uploads or publication.

## Firmware retention policy

Future owner-specific images must retain nlclient, osm where necessary, kernel/drivers, backplate MCU firmware, calibration and essential power services until individually understood. Their proprietary status and outdated dependencies remain risks, even when all host code is open. Preserve required notices and obtain applicable permissions before redistribution. Private development does not erase third-party license obligations. No firmware license conclusions are inferred from open-source kernel availability.

The original firmware/settings_compat/ candidate and settings_compat_probe/ use
only reviewed ABI identifiers/behavior, generated public link stubs and the same
private native libraries for a diagnostic comparison. No decompiled implementation
or proprietary binary patch is included. Public NSPR hash references are pinned in
firmware/settings_compat/sources.json and remain under ignored build/. Original
host fixtures use the installed host NSPR (not firmware); its headers/library are
not bundled. The candidate, instrumentation, adapters and tests are MIT licensed.
This adds no redistribution permission for native libraries or a deployable image.
