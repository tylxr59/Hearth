# Technical info

## How it works

Hearth has two parts:

- **The Home Assistant integration.** It runs a small HTTPS listener (port
  8443) that speaks the Nest's own cloud protocol. The Nest sends readings to
  it, and HA sends back settings such as the target temperature, Eco or a new
  schedule, the same way Google's servers used to.
- **A one-time USB setup.** It changes 12 files on the Nest so that it trusts
  your HA instead of Google, sends its "am I online?" check to HA, and gets the
  time from the server you choose. Everything else on the Nest stays as it was.

The Nest still runs its own heating logic, schedule and safety features. Hearth
never switches your heating directly. It only changes settings, like turning
the dial would.

Supported hardware: **Nest Learning Thermostat 2nd generation**, display
**Display-2.6**, software **5.9.4-5**. Nothing else is supported yet.

## What's tested

Hearth keeps three kinds of evidence separate: **tested on a real Nest**,
**tested in simulation or automated tests only**, and **not tested**. A
feature showing up in Home Assistant doesn't mean it has been verified on real
hardware.

All real-hardware results come from one unit: a **Gen 2, Display-2.6, software
5.9.4-5**, wired to an oil-fired baseboard heating system.

| Feature | Real Nest | Still to do |
| --- | --- | --- |
| Temperature/humidity readings in HA | ✅ Working | Multi-day reliability |
| Target temperature changes | ✅ 63 → 62 → 63 °F confirmed on the dial | The Nest reporting the new value back to HA |
| Eco on/off | ✅ Confirmed on the device | Other configurations |
| Weekly heat schedule | ✅ Replace, read back, backup and restore of the original | A real timed schedule change; other modes |
| Weather from HA | ✅ Nest requests served, timezone correct | Every forecast field on the Nest's screen |
| Local time | ✅ Corrected local time on the Nest | — |
| Choosing your own time server | ✅ Installed, and the wizard checked every file it wrote | Confirm time-service behaviour after reboot |
| Device settings | 🧪 Automated and HA-sandbox tests | Each field on a real unit |
| Actually switching the furnace on/off | ❌ Not tested | A supervised heating cycle |
| Cooling, fan, ranges, emergency heat | 🧪 Simulation only | Suitable real equipment |
| Power cut / HA outage behaviour | 🧪 No-replay tests | A real outage and return |
| Full flash backup | ✅ Two passes, cross-checked offline | — |
| Originals extracted from the full backup | ✅ Worked on one real backup; a later backup refused one damaged settings fragment, so the wizard now falls back to reading from the Nest | An install that uses backup-extracted originals |
| Free-space check and both install parts in one USB boot | ✅ Passed, with a separate `INSTALL` for each part | Undo through the wizard after this kind of install; the full wizard start to finish |
| Going from the backup straight into the install without pressing the ring | ✅ The Nest restarted and the install was sent without a ring press | The install starting and finishing after that restart |
| Saved-file restore | ✅ Back to the stock home screen | — |
| Full-chip restore | ❌ Not tested, no tool for it | — |
| Any USB port (the wizard finds the Nest itself) | ✅ The port the test unit uses; 🧪 automated tests for others, including ports behind a hub | A real run on another port and behind a hub |
| Full wizard on a stock Nest | ❌ Not run end to end | One supervised stock install and restore |
| Other models / software / Gen 1 / Gen 3 | ❌ Not supported | Their own measured profiles |

✅ verified on hardware · 🧪 automated/simulated only · ❌ not tested

## Security and privacy

### Your network

The Nest runs old, unmaintained software that will never get security updates.
Treat it as an untrusted device:

- **Keep it on a trusted or isolated network** (an IoT VLAN is ideal). Allow it
  to reach Home Assistant on port **8443** (HTTPS) and HA's plain-HTTP port
  (usually **8123**). Allow DNS/NTP only if you point those at local servers.
- **Never expose the Nest or HA's port 8443 to the internet.**
- Hearth doesn't need the Nest to reach the internet at all. Blocking its
  outbound traffic at your router is a good idea.

Hearth's changes to the Nest send its connectivity check and time to your local
network, and its cloud connection to your HA. The Nest's original firmware is
otherwise unchanged, and Hearth has not carried out a full security review of
it.

### What's private

| Thing | Where | Why it matters |
| --- | --- | --- |
| `private/setup-…/` | Your computer | Full flash backup, original files, credential, logs |
| `commissioning.zip` | Your computer | Anyone with it can pretend to be your thermostat |
| HA access token | Pasted once, never saved | Delete it after setup |
| Thermostat serial number | Kept out of normal output | Identifies your device |

Don't publish or attach any of these to an issue. Hearth's release files never
contain firmware, keys or anyone's backups.

### What Hearth does

- Each thermostat gets its own random credential and its own local certificate
  authority, created by your Home Assistant.
- The commissioning bundle contains the thermostat's credential and HA's
  *public* CA/CRL, never HA's private keys.
- The setup wizard runs as your normal user. It uses sudo only for a USB rule
  limited to your account and the one USB port the Nest is on, and optionally for one read-only
  `mtype` read. It never grants write access to disks.
- Every flash write needs a typed confirmation and is checked against your
  saved originals first.

### Reporting a vulnerability

Please open a [GitHub security advisory](https://github.com/tylxr59/Hearth/security/advisories/new)
rather than a public issue.
