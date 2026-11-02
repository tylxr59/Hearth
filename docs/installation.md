# Install Hearth

Hearth has two separate installations: the HA integration and the thermostat's
local-service modifications. HACS manages the integration, not the USB operation.
Currently supported development profile: Linux, Gen2 Display-2.6, primary5.9.4-5.
Keep the legacy thermostat on an isolated local network; do not expose its services
or Hearth's listener directly to the internet. Native OS/security review and
whole-firmware recovery remain incomplete.

## Home Assistant

Add `https://github.com/tylxr59/Hearth` as a HACS custom repository of type
Integration. Install a tagged preview with its `hearth.zip` asset, restart Core,
then add Hearth through Settings → Devices & services. On a fresh installation,
enter the HTTPS address the thermostat can reach (with an explicit unprivileged
port, normally8443) and the device ID obtained locally with the USB identify tool.
The wizard generates private keys, local trust and a unique device credential.
It refuses to overwrite an existing profile.

A previously prepared profile is imported without creating new credentials.
Normal HA upgrades do not reflash the thermostat or rotate its identity.

For source installation, run `python -m tools.package_native_ha build/ha-package`
and copy `build/ha-package/custom_components/hearth` into HA's
`config/custom_components/`. All required runtime files are included. Restart
Core once, then add the integration. Do not copy the entire research repository.

## Commissioning bundle

An HA administrator can download the private bundle with an authenticated GET of
`/api/hearth/commissioning` on HA's frontend HTTP endpoint. This requires an HA
Bearer token, not the separate thermostat credential. Use an authenticated client;
navigating directly in a new browser tab does not automatically attach HA's token.
The USB CLI can download it without putting a token in shell history:

```sh
mkdir -m 700 private
.venv/bin/python -m installer.cli download --ha-url https://YOUR_HA_HOST --output private/commissioning.zip
```

Use your actual HA frontend origin. The command prompts for an HA administrator
access token locally with input hidden, refuses redirects and saves a0600 file.
HTTPS is preferred; HTTP is accepted only for a literal private LAN address.
No HA SSH access is needed. The ZIP contains the
thermostat's credential and public CA/CRL, never HA's private keys or manager token.
The bundle is sensitive: anyone with it can authenticate as that thermostat.

## USB identity and preparation

From a source checkout with the development environment installed:

```sh
.venv/bin/python -m installer.cli doctor
.venv/bin/python -m installer.cli identify --disk /dev/sdX
```

Replace `/dev/sdX` with the actual Nest diagnostic device; do not guess. This uses
`mtype` read-only. If permissions require root, obtain the plist with your normal
read-only terminal workflow and supply `--info 'Technical Info.plist'` instead.
The default output omits identifiers. `--show-device-id` explicitly prints the ID
needed for HA setup; do not publish it.

```sh
.venv/bin/python -m installer.cli setup \
  --bundle /path/to/hearth-commissioning.zip \
  --info '/path/to/Technical Info.plist' \
  --session private/my-install
```

This checks exact supported model/version/partition and bundle/device identity,
then preserves a private session. It does not open USB or write the thermostat.

## Build and acquire the original inputs

The experimental reader now builds from pinned public sources, without a
developer's existing build tree. This needs Linux, rootless Podman, Clang/LLD,
a native C compiler, Git, patch, pkg-config and libusb development files. The
doctor reports available commands; install missing dependencies using your
host distribution's package manager. Allow at least5GB of working disk and4GB
of container memory. The pinned legacy compiler is downloaded and hash-checked;
its independent signature and complete compiler reconstruction are not verified.

```sh
.venv/bin/python -m installer.cli sources --output build/installer-sources
.venv/bin/python -m installer.cli build-reader \
  --sources build/installer-sources --output build/installer-reader \
  --profile private/my-reader
.venv/bin/python -m installer.cli acquire \
  --session private/my-install --profile private/my-reader --disk /dev/sdX
.venv/bin/python -m installer.cli check-inputs --session private/my-install
```

Only source fetching and container image assembly need internet access. Kernel
compilation runs without networking, capabilities, USB or private-directory
mounts. The native USB loader is compiled on the host and its simulated USB
regressions run without a physical device. Build output is under the specified
directory; a failed build preserves `build.log` and is not automatically retried.

Acquisition requires a terminal, matching fresh identity and an explicit READY
confirmation before the owner-timed restart. It reads two fixed snapshots plus
four library directories into private custody, without a flash writer or native
application execution. Nothing acquired is made executable on the host. Return
to native startup after the command exits. The corrected consolidated reader
and rebuilt boot chain completed a supervised read-only run on the existing
owner unit, including native UI/USB return. This does not establish a pristine
stock installation or whole-firmware recovery.

The final offline check reconstructs the ordered raw frames, checks the saved
completion marker, compares every private corpus file and metadata record, and
revalidates both backup receipts. It then resolves the native library closure
from ELF SONAME metadata without host symlinks or native execution. It refuses
modified, missing, extra or permissively stored inputs before kit preparation.

## Current firmware-kit requirement

The guided frontend does **not yet assemble a stock unit's entire install kit**.
After acquisition, compatible install/restore profiles must still be prepared
from that owner's fresh originals using the public capsule, source-build and
packaging modules. The
[builder guide](development/firmware-kit.md) explains those boundaries. A kit from
another unit, an old executed profile, a missing restore image or a changed source
recipe is refused. Never distribute proprietary native libraries with a release.

Once matching fresh install/restore profiles exist:

```sh
.venv/bin/python -m installer.cli install \
  --session private/my-install --disk /dev/sdX \
  --profile private/my-kit/install \
  --restore-profile private/my-kit/restore
```

The current low-level writer/ACL profile uses physical USB port1-1; the doctor
shows the observed port. Other ports need a separately reviewed scoped profile,
not global USB or block-device write permissions.

The tool re-reads device identity, checks the prepared credential, CA/CRL and
endpoint against the commissioning bundle, and verifies the complete profile pair.
It prompts READY before arming one RAM boot. Keep the display detached from the
base and USB connected. When the loader is scanning, hold the ring for10seconds,
release, then press/release once.

After RAM tests and real-file read-only preflight pass, a separate INSTALL prompt
permits one persistent write. Enter aborts. No automatic retry occurs. Restart
only when the checked result explicitly reports safe_to_restart. A failed or
uncertain post-write session needs recovery review with USB retained.

After successful native startup, connect normal Wi-Fi on the appropriate base,
verify fresh HA readings, and perform supervised equipment validation before
claiming a completed installation. Never use an unattended first heat call.
