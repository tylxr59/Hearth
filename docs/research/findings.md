# Research findings and component inventory

Physical evidence update, 2026-10-30: [read-only device intake](device-intake-2026-10-30.md) records a unit reporting `Display-2.6`, software `5.9.4-5` and normal-mode USB `2464:0002`. This adds identity metadata only; firmware acquisition, recovery and control compatibility remain unverified. The historical source findings below retain their original scope.

Further 2026-10-30 work: an authorized restart confirmed brief OMAP ROM
enumeration. The [acquisition review](acquisition-review-2026-10-30.md) statically
inspects the pinned NLE image's embedded initramfs, records why it writes
persistent files, and documents a separate, source-built diagnostic RAM probe.
That probe subsequently booted with the paced loader and emitted its expected
USB heartbeat; native startup returned after a manual restart. NAND acquisition
and restoration remain pending. The newly reviewed native host loader requires
the checked-in memory-safety/privacy and pacing patch before use. See the
[physical handshake/boot evidence](usb-handshake-2026-10-30.md).

Inspected 2026-10-24/25. No existing workspace audit was available. [upstreams.json](upstreams.json) pins all five repositories and hashes the principal inspected files; `python -m tools.fetch_research build/references` retrieves those files without executing them. The additional NestDFUAttack source is necessary because NLE's builder obtains its historical kernel and initramfs there. Do not run its installers or rootme scripts.

## Evidence classification

**Confirmed in inspected source** is distinct from **reported by upstream**, **inferred** and **unknown on a physical target**. Historical 2014-era root files are not a complete dump of current Nest Gen 2 firmware. NLE firmware may have evolved independently of its builder. A uImage label or matching checksum establishes identity, not authenticity or a reproducible source-to-binary relationship.

| Component | Evidence and finding | Disposition |
|---|---|---|
| OMAP USB, x-loader, U-Boot | NLE uses generation-specific x-load images and a common U-Boot/kernel. Its installer ships host USB loaders. | Hash inventory only; no binaries reused or run. USB ID alone cannot establish generation. |
| Linux | NestDFU `Dev/linux/Makefile`: 2.6.37. NLE shipped uImage header also labels 2.6.37. | Preserve pending modernisation feasibility; do not assume ABI, kernel patch state or memory limits. |
| Init | Historical `inittab` invokes rcS, rcS invokes rootme before start/watchdog/time setup. Rootme mounts mtdblock7 JFFS2 and rewrites persistent files. | Never execute historical exploit scripts. |
| Filesystems | Historical fstab mounts mtdblock10 system-config, 11 user-config, 12 data, 13 log, 14 scratch as JFFS2; tmpfs for /tmp and runtime paths. NLE builder edits mtdblock7. | Runtime partition mapping and Gen 1 differences require `/proc/mtd` and mount captures. No flash offsets assumed. |
| Native app | `etc/init.d/nestlabs` names nlclient; configuration hierarchy combines base/product/revision settings. | Preserve, no replacement control loop. |
| osm | client.config configures softwareupdatecommand `/nestlabs/sbin/osm`. | Updater role confirmed in config; executable behavior and signatures unknown. Preserve binary; do not invoke. |
| Backplate | client.config sets `/dev/ttyO2`, backplate update plist and autobackplateupdate. Kernel board source has backplate support. | Preserve. Electrical framing, baud, MCU protocol, protective behavior and update semantics unresolved. |
| SCPM | Init script identifies nlscpmd and `com.nestlabs.scpm`, path `/com/nestlabs/scpm/manager`; script uses `com.nestlabs.scpm.main.Quit` for stopping. | Essential power-management candidate. Do not call during RE or remove. |
| D-Bus | root-only nlclient policy names `com.nestlabs.nlclient`, with default send denial. | Bus name confirmed. No thermostat setter/introspection ABI confirmed. |
| Other services | dbus, connman, wpasupplicant, tiwlan, watchdog, monit, heartbeat, ntp, mdnsd, em357 and cron in historical tree. | Roles/necessity not fully established; no broad service purge. |
| Unsafe legacy additions | rootme installs Dropbear and autossh; start script includes debug serial shell. NLE optionally enables a published root password and adds HTTP CGI service. Historical Lua bot launcher binds `*`:8000. | Exclude from new runtime; offline hardening covers only understood rcS/CGI/root edits, not a complete firmware lockdown. |

## Kernel mechanisms

NLE build-kernel.sh selects `gtvhacker_defconfig`. At the pinned NestDFU source this enables NETFILTER, NF_CONNTRACK, IPv4 iptables/filter/reject/log. It disables xt state/conntrack match, owner match, namespaces, seccomp and SECURITY. IPv6 conntrack is disabled. Therefore modern nftables, containers, seccomp-bpf, LSM policies and even `iptables -m state` cannot be assumed available. The config is source evidence, not runtime proof. Confirm loaded kernel/config/modules and iptables binary before any device firewall change. External isolation is currently required.

## Proprietary binaries

The inspected historical root lacks `/nestlabs/sbin/nlclient` and `/nestlabs/sbin/osm`. No control API can be reverse engineered from nonexistent executables. NLE prebuilt uImage was inspected with the host `file` utility only; it identifies Linux/ARM, uncompressed legacy uImage, 6,995,236 data bytes. [binary-inventory.json](binary-inventory.json) records prebuilt hashes and sizes, with unverified provenance. No proprietary executable was run, copied into Hearth, or claimed reproducible.

## Communication map

| Source | Destination/interface | Status |
|---|---|---|
| nlclient config | `https://frontdoor.nest.com/entry` | Historical source confirmed. NLE rewrites endpoint. |
| nlclient | `/dev/ttyO2` backplate | Config confirmed; protocol unknown. |
| local system | system D-Bus SCPM/nlclient | Policy/scripts confirmed; no reliable control API yet. |
| NLE entry reply | local transport, passphrase, pro_info, weather, upload URLs | Backend source confirmed. Not all needed semantics implemented here. |
| NLE backend weather | `https://weather.nest.com/weather/v1` | Confirmed outbound request with TLS certificate checking disabled in service. No such code in Hearth. |
| NLE firmware default | HTTP `backdoor.nolongerevil.com` | Builder default confirmed; cleartext when selected. |
| Historical remote support | sshconnect/autossh | Installed by rootme; runtime destination/enabled state needs audit of the actual device. |
| Hearth runtime | configured local MQTT broker only | No weather, analytics, remote-support or update client. DNS/TLS libraries may use configured resolver; no external CA/AIA download code. |

This is an inventory of known paths, not an exhaustive outbound audit of missing proprietary binaries. Dynamic capture with a deny-by-default gateway remains mandatory.

## NLE authentication and protocol

NLE parses Basic passwords and references `assigned_cred_secret` in user settings. This suggests a client credential facility, but does not demonstrate safe replacement, entropy preservation or verified TLS/hostname behavior. Its device middleware captures passwords without checking them against an enrolled secret, then authorizes by claimed serial ownership; it also supports open pairing mode and a storage-missing bypass. Entry bootstrap with default credentials must not become a general trust-on-first-use exception in Hearth.

Transport PUT uses object buckets, revisions, timestamps and CAS. Upstream comments report that echoing merged values or replaying stale shared state can override native schedule-derived setpoints. Subscribe chunking and timing affect sleep eligibility and WoWLAN. These observations justify blocking physical use of the partial adapter until independently captured/tested.

## Confirmed unknowns requiring firmware or hardware

Exact Gen 2/Gen 1 firmware revisions, complete MTD map, boot fallback and recovery; nlclient/osm binaries/ABI and local IPC; backplate framing and protective behavior; active listeners and undocumented daemons; TLS trust-store behavior, hostname/time verification, client secret installation; bootstrap registration/pairing; full bucket schema/CAS/time behavior; battery cost of subscription modes; native regulation/schedule/offline/restart behavior; available firewall tools and active kernel configuration.
