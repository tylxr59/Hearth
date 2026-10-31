# Refocus on NLE integration

The owner questioned whether repeated NAND experiments duplicate work already
covered by NLE. They do in part. Backups, source review and the measured TLS,
settings and scratch results address real project requirements; expanding a
separate raw recovery framework is not the next functional milestone.

The uncommitted full-block rehearsal core and its original host model were
preserved under ignored `build/parked-programmed-block-20261031`. The model passed
one sanitizer test, but no new device image was built, loader armed or hardware
operation executed. Do not resume it by default. Existing executed profiles,
private captures, backup archive and observed results remain unchanged.

Fresh read-only upstream checks found the same heads already pinned in
upstreams.json: thermostat `fabbe034f01cefdabe06b93d1c312068f563a177` and backend
`bca8781012639c1cefc4a08c103fc892158fb630`. No source pin changed. Their current
READMEs advertise a USB installer and a self-hosted native-protocol/MQTT server.
These are upstream capabilities, not new compatibility measurements on this unit.

The already reviewed thermostat builder mounts the native JFFS2 root and changes
files; it does not require our proposed synthetic 64-page RAW restoration exercise.
It redirects cloudregisterurl, replaces trust material, installs CGI/startup/Monit
files and optionally enables SSH. Its broad error suppression and optional fixed
password are separate reasons to adapt that approach rather than run it verbatim.
Do not execute upstream rootme/install/update scripts. The published thermostat
tree still has no established blanket redistribution grant; its GPL components
and MIT backend must be treated according to their individual licenses.

| Area | Existing basis | Next useful work |
|---|---|---|
| ROM boot/kernel | Already reused the pinned upstream GPL stack and paced loader; successful target boots | Keep the measured stack; no new boot implementation |
| Persistent installation | NLE performs filesystem-level changes on the native root | Prepare a narrow file-level change/backup/rollback plan for the measured revision, with active-root and filesystem checks |
| Native control | Both approaches preserve the stock application/backplate control | Retain native loops/services; no HVAC rewrite |
| Entry/PUT/subscribe | NLE's MIT backend implements a much broader native protocol than Hearth's partial decoder | Reuse documented semantics or appropriately attributed MIT components; prioritize authenticated device telemetry before commands |
| Local boundary | Hearth already has TLS API, unique enrollment and MQTT/HA laboratory | Integrate the native transport into this boundary rather than build another canonical API |
| Device hardening | Measured callback/storage candidates and actual credential-log findings | Apply only the fixes required by the concrete commissioning flow; preserve owner-only artifacts |

The next functional milestone is one authenticated native state exchange with a
local backend through the NLE-style transport path, without physical HVAC commands.
Its minimum device-change set still needs a concrete review: endpoint and owner
trust configuration, native TLS/time behavior, unique assigned credentials,
necessary logging/storage fixes, exact original files and rollback procedure.
No new production route is enabled by this note. Recovery requirements before
installation remain; review recovery appropriate to the actual file changes
rather than automatically extending the general NAND experiment framework.

Sources: [thermostat installer documentation](https://github.com/codykociemba/NoLongerEvil-Thermostat/tree/fabbe034f01cefdabe06b93d1c312068f563a177),
[reviewed builder](https://github.com/codykociemba/NoLongerEvil-Thermostat/blob/fabbe034f01cefdabe06b93d1c312068f563a177/firmware/builder/build.sh),
[MIT backend](https://github.com/codykociemba/NoLongerEvil-SelfHosted/tree/bca8781012639c1cefc4a08c103fc892158fb630),
and the existing acquisition/security/native-entry reviews in this repository.
