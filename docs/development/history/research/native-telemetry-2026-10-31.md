# Authenticated native telemetry host milestone

The NLE integration follow-up adds an opt-in bounded native entry/PUT/metadata/
subscription path to the existing authenticated backend. It projects temperature,
humidity, target temperature and firmware to three MQTT sensors. All command
entry points are disabled in this mode. No upstream application code was copied;
the same pinned MIT backend revision supplies behavioral reference material.

The regression cases cover envelope ambiguity and body bounds, foreign buckets,
metadata order, patch merging, zero values, conditional revisions, subscriptions,
credential-generation changes, rotation/revocation during body reads, shared
command rejection, sensor migration and retained cleanup. Default canonical
behavior is preserved. HAOS selects this mode only through a private profile.
The local package includes license/provenance notices and no private config.

The owner's existing HAOS SSH service was reached using securely supplied
password authentication and a pinned SSH host key. Modern `/local_apps` and
`/app_configs` mappings were observed. Dedicated MQTT credentials authenticated
over TLS against an owner-provided CA. The current broker leaf omits Authority
Key Identifier and key-usage extensions; Python's strict verifier rejects the
missing AKI. An explicit, CA-required legacy-format option clears only
VERIFY_X509_STRICT. Standard trusted-chain, signature, validity and IP checks
passed, without changing or restarting the broker. No endpoint, username,
password, private key or identifying certificate metadata is recorded here.

The local HAOS app built and installed on amd64, with automatic startup disabled.
Its dedicated HTTPS certificate passed CA and IP verification and the manager
credential authenticated successfully. The default suite passed 471 tests with
five optional skips; the freshly rebuilt image passed all five real TLS broker/
container cases. Ruff/format and Bandit passed. See the dated security validation.
Real HA entity creation and the first physical native exchange remain pending. The thermostat stays at native
startup; no loader was armed and no thermostat file was changed. The next device
work is the concrete filesystem-level endpoint/trust/credential change and
rollback plan, including active-root verification, exact private originals,
clock/CRL handling and necessary logging/storage corrections. The settings
compatibility shim does not yet enforce restrictive permissions on future file
creation; do not claim that gate closed. Do not resume general raw-NAND research
by default or treat host fixtures as device compatibility.

A synthetic client also completed authenticated entry and native PUT against the
actual HAOS app, with expected telemetry projection and command rejection. Its
temporary enrollment was revoked afterward. This verifies the deployed host path,
not physical thermostat traffic or HA entity rendering. The SSH app does not grant
Core entity API access; no additional permission was enabled to inspect it.
