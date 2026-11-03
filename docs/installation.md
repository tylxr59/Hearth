# Install guide

Setting up Hearth involves two pieces:

1. **The Home Assistant integration.** HACS installs it, like any other custom
   integration.
2. **A one-time USB setup on the thermostat.** This points the Nest at your Home
   Assistant instead of Google. The setup wizard (`provision.py`) handles it,
   and also walks you through part 1.

> [!WARNING]
> This is an **experimental preview**. The wizard has safety checks at every
> step, but the complete stock-to-Home-Assistant install hasn't been tested end
> to end yet, and restoring the whole flash chip has never been tested. See
> [what's tested](compatibility.md).

## 1. Check your thermostat

Hearth currently supports only the combination it has been tested on:

| | Required |
| --- | --- |
| Model | Nest Learning Thermostat, **2nd generation** |
| Display | **Display-2.6** |
| Software | **5.9.4-5** |

On the Nest, open **Settings → Technical info** to check. The wizard checks
these too, and it stops if anything doesn't match. It also refuses a Nest that
already has some or all of Hearth installed.

## 2. Get your computer ready

You need a **Linux** computer (the setup doesn't run on Windows or macOS yet) with:

- Python 3.12 or newer and rootless Podman
- Git, Clang + LLD, a C compiler, patch, pkg-config, mtools, acl and the libusb
  development headers
- About **7 GB free disk space** (roughly 5 GB of build files plus 1.2 GB of
  backups) and **4 GB of RAM** available for the build container
- An internet connection, to download pinned sources during the build

The wizard checks all of this and prints the exact command for your distro if
something is missing. Or install everything up front:

| Distro | Command |
| --- | --- |
| Debian / Ubuntu | `sudo apt install podman git clang lld build-essential patch pkg-config mtools acl libusb-1.0-0-dev` |
| Fedora | `sudo dnf install podman git clang lld gcc patch pkgconf-pkg-config mtools acl libusb1-devel` |
| Arch / CachyOS | `sudo pacman -S --needed podman git clang lld base-devel patch pkgconf mtools acl libusb` |

Run the wizard as your **normal user**, not with `sudo`. It asks for sudo once,
to add a USB permission rule scoped to your account. It may also ask for one
read-only `mtype` command if your account can't read the Nest's info file.

## 3. Check your network

The thermostat has to reach Home Assistant on two ports:

| Port | Protocol | Purpose |
| --- | --- | --- |
| **8443** | HTTPS | Hearth's thermostat listener: telemetry and controls |
| **8123** (your HA port) | Plain HTTP | The Nest's "am I online?" check at `/api/h/204` |

If you normally reach HA through an HTTPS reverse proxy, that's fine, as long as
HA's own plain-HTTP port is reachable from the thermostat's network. A
TLS-only HA frontend isn't supported by the wizard yet.

Keep the thermostat on a trusted or isolated network, and never expose it or
port 8443 to the internet. [Security and privacy](security.md) has more.

## 4. Run the setup wizard

Download **`hearth-nest-installer.zip`** from the
[latest release](https://github.com/tylxr59/Hearth/releases) and extract it.
(Releases up to v0.10.2 called it `hearth-installer-source.zip`.) Ignore
`hearth.zip`: that's the HA integration, and HACS fetches it itself.
Take the Nest **display off its wall base** and plug it into the computer by USB.
Then, in a terminal in that folder:

```sh
python3 provision.py
```

The wizard runs seven steps. You'll be asked to confirm before anything touches
the thermostat:

| Step | What happens | Your part | Time |
| --- | --- | --- | --- |
| Checks | Tools, USB connection, thermostat model and software | Choose a time server (Enter = `time.nist.gov`) | 1 min |
| 1. Home Assistant | Installs Hearth via HACS and creates the HA entry | Follow the HACS steps, restart HA, paste a temporary access token | 5 min |
| 2. Build reader | Builds a small read-only USB boot tool in Podman | Nothing | ~10 min |
| 3. Full backup | Copies the Nest's entire flash twice and verifies it | Type `READY`, press the ring when told | ~25 min |
| 4. Save originals | Reads the files Hearth will change | Type `READY`, press the ring when told | 2 min |
| 5. Build kit | Builds install and undo images for *your* unit only | Confirm HA's HTTP port (Enter = 8123) | ~5 min |
| 6. Install | Space check, then two install phases | Type `READY`, then `INSTALL`, for each part | 5 min |
| 7. Finish | Restart the Nest, refit it to the base, check HA | Confirm readings appear | 5 min |

Times are rough estimates.

### Pressing the ring

When the wizard says **"The loader is waiting now"**, hold the Nest's ring down
for **10 seconds**, let go, then **press it once more**. This restarts the Nest
into its USB boot mode. Only do this when the wizard asks.

### Things not to do

- Don't unplug USB or put the display back on its base until step 7.
- Don't restart the Nest yourself unless the wizard tells you to.
- If something fails, **don't run the wizard again** on the same thermostat.
  Each step runs only once by design. Keep the private folder and see
  [troubleshooting](troubleshooting.md#setup-stopped-partway).

### Your private folder

Everything the wizard saves goes into `private/setup-<date>-<id>/`: the full
flash backup, the original files, your install kit, logs and a
`READ-ME-FIRST.txt`. **Keep it**, along with the matching `build/setup-…`
folder and the extracted Hearth folder itself. Restoring needs all three, on
the same computer.

Never share this folder. It contains your thermostat's credential.

## 5. After setup

- Delete the temporary access token. In HA, click your profile, then
  **Security**, then **Long-lived access tokens**.
- Choose a weather entity: **Settings → Devices & services → Hearth →
  Configure**. See [weather](usage.md#weather).
- Read [using Hearth](usage.md) for controls, Eco and schedules.

The wizard never sends a heating command. The first time you control your
heating from HA, do it while you're home and can watch it.

## Home Assistant only (HACS)

Use this if your thermostat already has Hearth installed, or to install the
integration by hand:

1. In HACS, open the three-dot menu and choose **Custom repositories**.
2. Add `https://github.com/tylxr59/Hearth` with the type **Integration**.
3. Find **Hearth** in HACS, download the latest release and restart Home Assistant.
4. If you have an existing Hearth profile, add it under **Settings → Devices &
   services → Add integration → Hearth**.

Hearth updates arrive through HACS like any other integration. Updating the
integration never reflashes the thermostat or changes its identity.

If HACS shows a commit hash instead of a version, use Hearth's **Update
information** action in HACS and reopen the download dialog.

## Automatic USB onboarding

The wizard does this for you in step 1. Use this command only to create the
Home Assistant entry on its own, for example when you run the
[advanced CLI](advanced-cli.md) steps by hand.

From the extracted installer folder, with the Nest plugged in by USB in normal
mode:

```sh
cd hearth-nest-installer-<version>
mkdir -m 700 private
python3 -m installer.cli onboard --ha-url http://YOUR_HA_IP:8123 --session private/my-install
```

- `--ha-url` is the address you use to open HA in a browser. HTTPS is preferred.
  Plain HTTP is accepted only for a private LAN IP address.
- It asks for a temporary HA admin access token (hidden, never saved).
- It reads the Nest's identity over USB (read-only), lists HA's local addresses
  so you can pick the one on the thermostat's network, and asks you to type
  `SETUP`.
- It saves `identity.json` and `commissioning.zip` in your session folder. Both
  are private.

Useful options: `--sudo-read` allows one read-only `sudo mtype` if your account
can't read the Nest's info file. `--disk /dev/sdX` picks a disk when more than
one is connected. `--endpoint https://IP:8443` sets the thermostat-facing
address yourself.

Close any open Hearth setup dialog in HA first. Onboarding refuses to replace an
existing Hearth profile, and it never writes to the thermostat. Removing the
integration in HA keeps its profile in `config/.storage/hearth`. For a fresh
install, move that folder aside first.

## Undo

See [undo and recovery](recovery.md).
