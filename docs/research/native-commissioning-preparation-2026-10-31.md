# Native commissioning file preparation

The next milestone remains a physical authenticated native state exchange with
the HAOS backend, with command delivery disabled. No device restart, mount,
settings update, installation or backend enrollment occurred during this offline
preparation. Normal USB identity was observed, and its serial matched the identity
in the preserved assigned settings without printing either value.

The preserved, independently matching BCH-derived view was checked against its
private acquisition digest before reconstruction. The source-corroborated
116–124 MiB user-config range yielded eleven regular files, including one native
settings file, with zero scanned common/inode/data/dirent CRC failures. This is
an offline range interpretation, not a newly measured runtime partition map.
Root0 symlink metadata corroborates these paths without creating firmware links
on the host:

- `/nestlabs/etc` resolves to `/etc/nestlabs`.
- `/etc/nestlabs/user` resolves to `/media/user-config`.
- `/nestlabs/share/certs` resolves to `/etc/ssl/certs`.

The settings file has an ISO-8859-1 XML declaration, a plain settings root and
134 self-closing key/value entries, including both assigned credential keys.
The new offline editor changes exactly their value spans and preserves every
other byte. It refuses duplicate keys, unsupported structure/encoding, DTDs,
entities, missing entries and invalid new credentials. It has no file writer,
USB access, credential delivery header or installer. Neither old nor generated
credentials enter source, logs or error messages.

A fresh private review directory retains exact original/replacement bytes and
private digests for five files: client configuration, user settings, NTP config,
owner CA bundle and CRL bundle. The intended edits are local registration URL,
known log-uploader disabling, one unique assigned credential pair, owner trust
material and the native NTP server. The backend certificate, IP and newly issued
seven-day CRL verify against the dedicated owner CA. CRL renewal remains a product
maintenance requirement; this is not an unattended production setup. Backend
enrollment has deliberately not happened yet. No CA private key is in the
replacement directory. Original device binaries and captures remain unchanged.

The owner selected public NTP, such as NIST, instead of requiring a new local
NTP server. Captured firmware already has ntpd and one server line. The prepared
edit selects time.nist.gov with minpoll 6/maxpoll 10 and no burst option, retaining
other config bytes. NIST recommends its generic hostname and forbids polling
more often than every four seconds. This ordinary public NTP is unauthenticated;
it does not establish an authenticated time bootstrap or close clock-failure
validation. DNS/NTP reachability and actual native synchronization remain untested.

The owner confirmed UniFi and existing IoT access to HA/MQTT, and will handle
trusted-network access themselves after connection. Do not change the router or
expand firewall work as a prerequisite to this milestone. The HAOS endpoint is
TCP 8443 on the existing HA host; it differs from the Core UI port. Existing
reachability and containment have not been independently measured. Keep all
owner addresses and the SSID in private deployment records.

The review bundle explicitly remains non-installable. Remaining concrete work:
active-root/current-file checks and fresh originals, filesystem-level commit and
rollback tooling, assembly of the measured TLS correction, native settings
permission/application integration, backend enrollment immediately before use,
and native clock/connection observation. The existing settings correction still
forwards mode 0666; initial chmod alone cannot guarantee future settings-file
privacy. Preserve the exact previously measured candidate and all executed
profiles; do not silently modify them or claim a new build target-validated.
Do not install the earlier four-file hardening overlay or these five review files
as a complete deployment. Additional generic raw-NAND restoration work remains
parked.

Sources: [NIST server guidance](https://tf.nist.gov/tf-cgi/servers.cgi),
[UniFi zone firewall documentation](https://help.ui.com/hc/en-us/articles/115003173168-Zone-Based-Firewalls-in-UniFi),
and the existing native TLS/bootstrap/storage reviews. External sources were
read for current operational guidance; no third-party firmware ran on the host.

Validation: all 25 new settings/NTP editor cases passed; the full default suite
passed 496 tests with five optional integrations skipped. Ruff lint/format and
Bandit passed. No runtime backend/container code changed, so the prior real TLS
broker/container results were not rerun for these offline-only additions.
