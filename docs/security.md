# Security and privacy

## Your network

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

## What's private

| Thing | Where | Why it matters |
| --- | --- | --- |
| `private/setup-…/` | Your computer | Full flash backup, original files, credential, logs |
| `commissioning.zip` | Your computer | Anyone with it can pretend to be your thermostat |
| HA access token | Pasted once, never saved | Delete it after setup |
| Thermostat serial number | Kept out of normal output | Identifies your device |

Don't publish or attach any of these to an issue. Hearth's release files never
contain firmware, keys or anyone's backups.

## What Hearth does

- Each thermostat gets its own random credential and its own local certificate
  authority, created by your Home Assistant.
- The commissioning bundle contains the thermostat's credential and HA's
  *public* CA/CRL, never HA's private keys.
- The setup wizard runs as your normal user. It uses sudo only for a USB rule
  limited to your account and port 1-1, and optionally for one read-only
  `mtype` read. It never grants write access to disks.
- Every flash write needs a typed confirmation and is checked against your
  saved originals first.

## Reporting a vulnerability

Please open a [GitHub security advisory](https://github.com/tylxr59/Hearth/security/advisories/new)
rather than a public issue.
