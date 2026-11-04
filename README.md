<p align="center">
  <img src="assets/logo.png" alt="Hearth flame" width="112" height="112">
</p>

<h1 align="center">Hearth</h1>

<p align="center"><b>Your Nest thermostat, controlled from Home Assistant. No Google cloud.</b></p>

<p align="center">
  <a href="https://github.com/tylxr59/Hearth/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/tylxr59/Hearth?display_name=tag&sort=semver"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-97ca00"></a>
  <a href="https://github.com/tylxr59/Hearth/actions"><img alt="Checks" src="https://github.com/tylxr59/Hearth/actions/workflows/check.yml/badge.svg"></a>
</p>

<p align="center">
  <a href="#-features">Features</a> ·
  <a href="#-quick-start">Quick start</a> ·
  <a href="#-usage">Usage</a> ·
  <a href="#-troubleshooting">Troubleshooting</a> ·
  <a href="docs/technical.md#whats-tested">What's tested</a>
</p>

---

Google has stopped cloud support for older Nest Learning Thermostats. Hearth
keeps yours useful. A one-time USB setup points the thermostat at **your own
Home Assistant** instead of Google's servers, and it talks to HA directly over
your local network using the Nest's own protocol.

The Nest keeps doing what it's good at: its display, dial, schedule and the
logic that actually runs your heating all stay exactly as they were. Hearth just
replaces the cloud end.

<p align="center">
  <img src="assets/screenshot.png" alt="Hearth thermostat card in Home Assistant showing temperature, humidity and target" width="720">
</p>

> [!WARNING]
> **Experimental preview.** Hearth works on the developer's own thermostat, but
> the full setup from a stock Nest hasn't been tested end to end yet, and
> restoring the whole flash chip has never been tested. Only try this if you're
> comfortable being an early tester. See [what's tested](docs/technical.md#whats-tested).

## 🎯 Features

| Feature | What it does |
| --- | --- |
| 🌡️ **Climate control** | Mode, target temperature and current temperature/humidity in HA |
| 🌿 **Eco mode** | Turn the Nest's Eco preset on and off |
| 📅 **Weekly schedules** | Read and replace the Nest's own schedule, with automatic backups |
| ⛅ **Weather** | The Nest's outdoor weather comes from any HA weather entity you pick |
| 🕐 **Your time server** | Point the Nest's clock at NIST or your own NTP server |
| ⚙️ **Device settings** | Learning, Early-On, Sunblock, display and more, shown only when your Nest reports them |
| 🏠 **Fully local** | The Nest talks only to your Home Assistant. No account, no cloud |
| ↩️ **Undo** | Setup saves a full flash backup and lets you put the original files back |

## 📋 Requirements

- **A Nest Learning Thermostat, 2nd generation**, with display
  **Display-2.6** and software **5.9.4-5** (on the Nest: **Settings →
  Technical info**). It's the only combination tested on real hardware, so
  Gen 1, Gen 3 and other software versions aren't supported yet.
- **Home Assistant** with [HACS](https://hacs.xyz/). Tested on HA 2026.10.
- **A Linux computer** for the one-time USB setup, with Python 3.12+ and Podman.
  The wizard checks for everything else and tells you exactly what to install.
- **A USB data cable** (charge-only cables won't work).
- About **7 GB of free disk space** and roughly **an hour**, mostly unattended.

Readings, target temperature, Eco and schedules work on a real heating system,
but switching the heating on and off from HA hasn't been tested yet. Cooling,
fan and emergency heat have only been tested in simulation.

## 🚀 Quick start

1. Download **`hearth-nest-installer.zip`** from the
   [latest release](https://github.com/tylxr59/Hearth/releases/latest) and
   extract it. It unpacks into its own `hearth-nest-installer-<version>`
   folder. (Releases up to v0.10.2 called it `hearth-installer-source.zip`.)
   The other file, `hearth.zip`, is the HA integration, and HACS downloads it
   for you.
2. Take the Nest display off its wall base and plug it into your Linux computer
   by USB.
3. Open a terminal in the extracted folder and run:

   ```sh
   python3 provision.py
   ```

The wizard walks you through everything: installing Hearth in Home Assistant,
backing up the thermostat, building an install kit made just for your unit,
and installing it. It asks before every write. The full walkthrough is in the
[install guide](docs/installation.md).

To undo it later, run `python3 provision.py --restore` from the same folder.

### Already set up?

If your Nest already has Hearth installed, you only need the HA side. In HACS,
open the three-dot menu, choose **Custom repositories**, add
`https://github.com/tylxr59/Hearth` as an **Integration**, download Hearth and
restart Home Assistant.

## 🧭 Usage

Your Nest appears in Home Assistant as a **Hearth Thermostat** device with a
climate card, sensors and, where your Nest reports them, settings. Schedules
use Home Assistant actions, and the Nest's weather comes from a weather entity
you pick under Hearth's **Configure** options.

| Guide | What's in it |
| --- | --- |
| [Install guide](docs/installation.md) | Requirements, running the wizard, HACS |
| [Using Hearth](docs/usage.md) | Controls, Eco, schedules, weather, settings |
| [Undo and recovery](docs/recovery.md) | Putting the original files back |
| [Technical info](docs/technical.md) | How it works, what's tested, security and privacy |
| [Advanced CLI](docs/advanced-cli.md) | Running each setup step by hand |

## 🩺 Troubleshooting

| Symptom | Fix |
| --- | --- |
| "No Nest found in normal mode on USB port 1-1" | Use a **data** cable, plug into the port Linux calls `1-1`, and wait for the Nest to finish booting |
| Setup stopped partway | Keep USB connected, don't restart the Nest, keep the private folder and don't run the wizard again. See [recovery](docs/recovery.md#if-setup-or-restore-stopped-partway) |
| No readings in HA | Check the Nest can reach HA on port **8443** and HA's HTTP port (8123) |

More in [troubleshooting](docs/troubleshooting.md). When asking for help, never
post your private setup folder, `commissioning.zip`, logs or serial number.
Hearth's **Download diagnostics** file in HA is safe to share.

## 👋 Development

```sh
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.lock
make test && make check
```

Start with the [developer guide](docs/development/README.md). AI coding agents
should read [AGENTS.md](AGENTS.md) first. Bug reports and questions are welcome
through [GitHub Issues](https://github.com/tylxr59/Hearth/issues). Report
security problems through a
[security advisory](https://github.com/tylxr59/Hearth/security/advisories/new)
instead.

## 📦 Releases

Push a `v0.x.y` tag that matches the version in `manifest.json` and
`pyproject.toml`. The [release workflow](.github/workflows/release.yml) checks
it, builds both assets reproducibly and publishes an experimental
[GitHub Release](https://github.com/tylxr59/Hearth/releases) with generated
notes. See [releases](docs/development/README.md#releases) for the details.

## 🤝 Acknowledgements

[NoLongerEvil](https://github.com/codykociemba/NoLongerEvil-SelfHosted) is the
reference for the Nest's native protocol. Hearth's code is an original
implementation. [NestDFUAttack](https://github.com/exploiteers/NestDFUAttack)
and the OMAP loader projects made the USB boot research possible. Details are in
[THIRD_PARTY.md](THIRD_PARTY.md).

## 📃 License

[MIT](LICENSE), except the standalone offline NAND ECC verifier, which is
GPL-2.0-only. Third-party components keep their own licenses. Releases never
include Nest firmware, per-device keys or anyone's backups.
