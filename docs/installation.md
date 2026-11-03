# Install Hearth

Hearth has two separate installations: the HA integration and the thermostat's
local-service modifications. HACS manages the integration, not the USB operation.
Currently supported development profile: Linux, Gen2 Display-2.6, primary5.9.4-5.
Keep the legacy thermostat on an isolated local network; do not expose its services
or Hearth's listener directly to the internet. Native OS/security review and
whole-firmware recovery remain incomplete.

The native connectivity check needs a reachable plain-HTTP `/api/h/204` on HA's
frontend port (normally8123), even though thermostat telemetry/control use the
separate authenticated HTTPS listener. A directly TLS-only HA frontend needs an
explicit compatible local HTTP route; that topology is not yet covered by the
guided kit. Reverse-proxy HTTPS for normal HA access does not prevent using HA's
internal HTTP frontend when that route is available on the thermostat network.

## Guided setup

The full-NAND archive and `--restore` flow below are in the **0.10.0 source
preview**, awaiting its supervised archive/handoff test and publication. Published
0.9.1 has the earlier selected-file backup wizard. Do not expect the new archive
step in that older download.

Download `hearth-installer-source.zip` from the latest experimental release and
extract it on the Linux computer connected to your Nest. Open a terminal in that
folder and run:

```sh
python3 provision.py
```

The wizard walks through HACS installation, reads the device identity, offers HA's
local addresses, saves the matching private bundle, builds the protected reader,
saves two complete raw NAND/OOB passes and matching ECC-derived data views,
acquires readable original files, and prepares both install and restore images. It then
runs two checked installation phases, each requiring its own confirmation before
writing. Finish by reconnecting normal Wi-Fi and checking fresh readings in HA.
You do not need to assemble the individual commands below. `hearth` or
`python3 -m installer.cli wizard` launches the same flow from an installed checkout.

At **Time server [time.nist.gov]**, press Enter for NIST or enter one NTP hostname
or IPv4 address, such as your local time server. The selection is validated and
applied to both the primary NTP configuration and ConnMan's fallback. No port,
URL, password or additional configuration text is accepted. This is an installation
time setting; changing it later requires another reviewed device update.

The computer needs Python3.12+, rootless Podman, Git, Clang/LLD, a C compiler,
patch, pkg-config, mtools, acl and libusb development headers. The wizard checks
these and reports missing requirements; it does not install system packages.
It runs as your normal user. It may ask permission for a fixed read-only `sudo
mtype` diagnostic read and for a narrowly scoped root-managed USB access rule.
It never grants block-device write access or runs the whole wizard as root.
Allow at least1.2GB for private raw/data backup files, plus space for source/kernel
builds. The full NAND read can take up to20 minutes; offline verification follows.
The archive retains unclassified-but-identical ECC chunks unchanged and records
that limitation. It is not a validated whole-chip restore image.
The current measured loader is restricted to USB port **1-1**; arbitrary ports,
other operating systems and other firmware are not supported by this preview.

Keep the display detached from its base and USB connected through acquisition,
build and installation. Follow the ring instructions only when the wizard says
the loader is waiting. A private `private/setup-…` folder retains originals,
custody, logs, plans and results; its `READ-ME-FIRST.txt` explains recovery limits.
A temporary HA administrator token is entered hidden and never saved; revoke it
after setup. The final live-reading check is confirmed by you, not inferred from
a successful file write. No HVAC control test is sent by the wizard.

This remains an experimental stock-device path, not a validated turnkey installer.
The existing/partial-Hearth guard still refuses modified units. Failed steps are
not automatically retried, and interrupted write sessions require report review
before any restart or recovery attempt. The newly combined wizard, cleanup3 and
custom-NTP writer have host/ARM build coverage; their complete stock-device
hardware installation and restoration still need measurement.

## Home Assistant

Add `https://github.com/tylxr59/Hearth` as a HACS custom repository of type
Integration. Install a tagged release with its `hearth.zip` asset and restart
Core. For fresh setup, use [automatic USB onboarding](#automatic-usb-onboarding)
below. It creates the HA entry, local trust and unique device credential without
copying the device ID by hand. It refuses to replace an existing profile.

The current release is the experimental **v0.9.1**. In HACS, open Hearth and select
that tagged version for download. It is an ordinary GitHub release so HACS's
default selection works; the project remains experimental and is not stable v1.
If an older repository cache shows a commit hash, use Hearth's **Update information**
action and reopen its download dialog. A manual copy
of the integration does not establish a successful HACS installation. For a clean
onboarding test, retain private backups and remove the previous integration/profile
before starting; removing an HA entry alone does not erase its retained profile.

A previously prepared profile can be imported through **Add integration → Hearth**
without creating new credentials. Manual fresh setup is also available there:
choose an offered local address or enter an explicit HTTPS IPv4 endpoint/port,
then enter the USB-read device ID. Normal HA upgrades do not reflash the thermostat
or rotate its identity.

For source installation, run `python -m tools.package_native_ha build/ha-package`
and copy `build/ha-package/custom_components/hearth` into HA's
`config/custom_components/`. All required runtime files are included. Restart
Core once, then add the integration. Do not copy the entire research repository.

## Guided recovery

From the original matching installer source, run:

```sh
python3 provision.py --restore
```

Choose the saved `private/setup-…` installation. The wizard checks the full NAND
archive, original-file custody and matching restore images, then uses separate
read-only preflight and RESTORE decisions for the two phases. It restores the
saved original settings and selected system/network files and removes Hearth's
additions. Later native settings changes can make this exact-restore preview
refuse; it does not guess new settings or automatically recover partial writes.
Preserve the source ZIP stored in the private folder **and the matching build
workspace**. The preview still validates restore images against those build trees;
automatic relocation/cold reconstruction on another PC is not implemented yet.
No whole-chip erase/write,
HA deletion or HVAC control request is included.

## Automatic USB onboarding

Download `hearth-installer-source.zip` from the same release and extract it on the
Linux computer connected to your Nest by USB. From that directory, with Python3.12+
and `mtype` available:

```sh
mkdir -m 700 private
python3 -m installer.cli onboard \
  --ha-url http://YOUR_HA_LAN_IP:8123 --session private/my-install
```

Use the actual HA frontend address, including its port; this is the URL you use
to open HA. HTTPS is supported and preferred when available. HTTP requires a
literal private LAN address. Close any open Hearth setup dialog before running
the command. The installer prompts privately for a temporary HA administrator
access token, discovers a single normal-mode Nest disk, and reads only its
diagnostic plist. Multiple disks require an explicit `--disk /dev/sdX` selection.

HA offers its own private IPv4 interfaces as thermostat-facing HTTPS endpoints
on port8443. Select the address on the thermostat's network; across VLANs,
reachability still needs your confirmation. You can enter another explicit
endpoint if needed. Type `SETUP` once to create the HA entry and save the matching
bundle/identity in your private session. The HA administrator token is not saved;
revoke the temporary token after onboarding. No ROM loader, flash write or
thermostat control runs during this step.

If your account cannot read the diagnostic disk, add `--sudo-read` to permit only
the fixed `sudo mtype` diagnostic read; sudo prompts locally for your PC password.
This flag never grants write access or runs the installer as root. Alternatively,
save the plist through your normal read-only workflow and pass
`--info /path/to/Technical-Info.plist`.
The installer extracts the identity from that file without asking you to type it.
Do not grant block-device write access. `--endpoint https://YOUR_IOT_HA_IP:8443`
can supply an endpoint explicitly while still reading the identity automatically.

The command creates `private/my-install/identity.json` and `commissioning.zip`;
continue at [Build and acquire the original inputs](#build-and-acquire-the-original-inputs).
An existing profile or refused setup stops without automatic resubmission. If HA
created the entry but its listener is not ready, preserve the session and resolve
the HA setup error before using the separate bundle-download command.

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
application execution. Nothing acquired is made executable on the host. To continue
directly to installation, keep USB connected in the exited RAM session while
building the kit. If stopping here, follow the command's manual restart guidance;
native startup can change settings and invalidate the saved snapshot. The corrected consolidated reader
and rebuilt boot chain completed a supervised read-only run on the existing
owner unit, including native UI/USB return. This does not establish a pristine
stock installation or whole-firmware recovery.

The final offline check reconstructs the ordered raw frames, checks the saved
completion marker, compares every private corpus file and metadata record, and
revalidates both backup receipts. It then resolves the native library closure
from ELF SONAME metadata without host symlinks or native execution. It refuses
modified, missing, extra or permissively stored inputs before kit preparation.

## Build the private kit

The experimental stock-kit builder constructs nine commissioning replacements,
three disjoint connectivity/time replacements, and matching restore images from
this acquisition. It refuses an existing or partial Hearth installation; this
is not an upgrade command. The complete public workflow still needs a measured
stock-unit installation and restore before stable release. See the
[builder guide](development/firmware-kit.md) for validation limits.

```sh
.venv/bin/python -m installer.cli build-kit \
  --session private/my-install --sources build/installer-sources \
  --reader-build build/installer-reader --build build/my-kit --output private/my-kit
.venv/bin/python -m installer.cli check-kit --kit private/my-kit
```

Keep all output private, including the originals, commissioning bundle and native
libraries. A kit from another unit, an old executed profile, a missing restore
image or a changed source recipe is refused. Do not delete failed attempts to
make their paths reusable.

For the explicitly supervised experimental installation:

```sh
.venv/bin/python -m installer.cli install-kit --kit private/my-kit --disk /dev/sdX
```

The current low-level writer/ACL profile uses physical USB port1-1; the doctor
shows the observed port. Other ports need a separately reviewed scoped profile,
not global USB or block-device write permissions.

The tool checks the intake identity, prepared credential, CA/CRL, endpoint and
both profile pairs. In native USB mode it re-reads the current identity; an
acquisition-to-install RAM handoff requires the completed acquisition evidence.
It prompts READY before each RAM boot. Keep the display detached from the
base and USB connected. When the loader is scanning, hold the ring for10seconds,
release, then press/release once.

After RAM tests and real-file read-only preflight pass, a separate INSTALL prompt
permits one persistent write. Enter aborts. The nine-file phase must finish and
verify before the separate three-file phase can start. Each phase gets its own
READY and INSTALL confirmations. Stay in RAM between phases and follow the
loader's prompt for the next button sequence. No automatic retry occurs. Restart
only when the checked result explicitly reports safe_to_restart. A failed or
uncertain post-write session needs recovery review with USB retained.

## Selected-file restoration

```sh
.venv/bin/python -m installer.cli check-kit --kit private/my-kit --for-restore
.venv/bin/python -m installer.cli restore-kit --kit private/my-kit --disk /dev/sdX
```

This restores the three network files first, then the nine commissioning files,
with separate READY/RESTORE confirmations and exact journal/original-byte checks.
Expired HA certificate metadata does not prevent restoring originals. Changed
source recipes, unknown current bytes or used profiles still stop the operation.
An incomplete installation requires review of its saved results before selecting
the explicit `--phase cleanup` or `--phase commissioning` recovery scope.

These are exact selected-file recovery images, not a general uninstall or
whole-firmware recovery tool. Later native configuration changes can invalidate
the original settings comparison. Do not bypass that refusal or overwrite current
HVAC configuration with an old snapshot. Preserve the entire private kit and its
pinned source version for recovery.

After successful native startup, connect normal Wi-Fi on the appropriate base,
verify fresh HA readings, and perform supervised equipment validation before
claiming a completed installation. Never use an unattended first heat call.
