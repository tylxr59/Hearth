# Security review and validation report

Iteration 0.1.0, inspected 2026-10-24/25. This is a source review and host-side test report, not a firmware certification or physical HVAC safety claim. No prior audit existed in the initial workspace. Findings below were independently examined at the exact revisions in docs/research/upstreams.json. Upstream branches may subsequently differ.

The [native bootstrap review](../research/native-bootstrap-2026-10-30.md) adds
a stock-client credential disclosure finding: its response-header update helper
logs the newly assigned ID and secret. A private candidate skips that logging
block, but other logs/uploads and persistence remain unaudited. Assigned-credential
401 responses can select default credentials. Host regression tests preserve
explicit enrollment and revocation; no default-credential bootstrap or native
credential installation is enabled.

The [storage/log follow-up](../research/native-storage-2026-10-30.md) identifies
a second credential-value log in settings-entry write failures, missing propagation
of those failures, and dirty clearing after directory-sync failure. Offline staging
now prepares uploadlogs=0 for the traced queued-file sender and rejects ambiguous
config XML. This is a partial offline artifact change; it neither fixes the writer
nor demonstrates target privacy, durable rotation or complete outbound isolation.

## Reference findings and response

| Potential issue | Evidence at inspected revision | Hearth treatment and limits |
|---|---|---|
| Settings CGI key disclosure | Thermostat deps/settings returns api_key when `initialize` equals hostname; also has an unconfigured first-boot setup grant. Logs raw request/token. | No CGI or initialize/setup grant in runtime. Regression tests reject old paths; firmware staging removes recognized nleapi rcS line and lists CGI/Monit removals. Not yet verified on hardware. |
| Executable HTTP update | deps/update fetches caller-provided URL, trusts caller-provided MD5, then replaces CGI files from archive. Existing key check doesn't supply independent update authenticity. | No updater/download/upload execution route. Builds verify explicit input hashes and output inert artifacts; no automatic remote update mechanism. |
| Default root SSH | Builder uses public fixed password/hash **only when** enable-root-access selected; does not prove all installs have it. Historical rootme also installs root/SSH support. | No SSH server or password defaults shipped. Offline replacement locks root password and removes recognized rcS Dropbear/sshconnect/rootme entries. Other boot/Monit paths and serial shells remain deployment audit gates. |
| Serial impersonation | Backend device_auth authorizes claimed serial ownership, captures Basic password without validating enrollment; open mode and storage-missing bypass exist. | Exact enrolled serial plus digest-validated unique credential required on every device request, with no storage fallback/open mode. Cross-device bucket writes rejected. Tests cover forged serial/header, wrong/revoked key, rotation and separate manager role. Stock-client credential installation unresolved. |
| Unauthenticated management | create_control_app attaches debug/CORS middleware, not manager authentication; control routes installed separately from optional API-key utilities. HA add-on exposes control internally behind ingress by default. | Every management route requires separate Bearer credential, even internally. No management UI/listener, public control route or ingress-header bypass. One full-privilege local manager role only. |
| Raw MQTT bypass | mqtt_integration._handle_raw_command accepts arbitrary object_type/field and merges it independently of the validated HA command handler, when raw MQTT subscription is enabled. | No raw topic/field API. HTTP/MQTT share an explicit validator. Temperature/mode/fan capability bounds, UTF-8/JSON limits and retained-command rejection tested. Broker ACL is a separate required boundary. |
| External Nest weather | weather_service explicitly fetches weather.nest.com with certificate checking disabled. | No weather client or provider. Known endpoints inventoried; external deny-by-default VLAN required for unknown native traffic. Full proprietary outbound audit remains open. |
| Plaintext credentials | Firmware builder default URL and HA reference default api_origin use HTTP. Basic/password-based application auth over that route is plaintext. User-selected HTTPS may change exposure. | Non-loopback runtime refuses plaintext; MQTT TLS checks CA/hostname. Real HTTPS API and TLS broker tested. No assertion that stock Nest supports this configuration yet. Random keys alone do not fix plaintext. |
| Old userspace/kernel | Historical kernel source and NLE prebuilt label 2.6.37; historical toolchain/download sources retained. | Host runtime uses current pinned Python/packages. Old native kernel/userspace remain an unresolved risk; no claim of fixing their CVEs by isolation. |
| Firmware provenance | Thermostat repository includes prebuilts; download/build paths lack a complete pinned source-to-binary proof. | No executable reused or shipped. Hash/revision inventory and per-input/output manifests provided. Unsigned hashes prove identity only; redistribution/authenticity and reproducible kernel builds remain open. |

## Automated checks

The final measured results are recorded in validation.json. Tests include real TLS server and broker sockets, device/manager authorization, enrollment/rotation/revocation, credential role uniqueness, cross-device denial, old CGI paths, command schema/range enforcement, malformed/duplicate/non-finite/oversized JSON, retained MQTT commands, raw MQTT bypass, state/intent separation, command expiry, restart state loss, secret-file permissions, root-input symlink rejection, digest mismatch, offline hardening preservation, package assembly and deterministic source/inert archives. Hypothesis exercises arbitrary byte/text inputs and command values; this is bounded property testing, not exhaustive parser fuzzing.

Ruff and Bandit run on original host code/tools. At the initial review, Bandit source suppressions were B104 for the required TLS container bind (host port disabled by default) and B310 for the pinned HTTPS research fetcher's checked-in URL construction. Neither is a general suppression of authentication/input issues. Tests intentionally start loopback laboratory services and are not included in Bandit's runtime scan.

2026-10-30 addition: the experimental RAM probe's source staging tool uses
narrow B404/B603/B607 suppressions for fixed `git archive` and `patch` argv,
without a shell. Revisions and patch paths come from checked-in assets; only
public source is materialized, and no target/build executable is run by staging.
The native loader's synthetic ASan/UBSan regression checks supplement Bandit;
neither scans nor a compiled minimal kernel establish hardware safety. See the
[dated validation report](validation-2026-10-30.json).

pip-audit inspects the hash-locked Python runtime dependency graph against available advisories; saved report is runtime-dependency-audit.json. It does not cover CPython itself, Debian packages, Mosquitto, bootloaders, kernel or missing proprietary userspace. No claim of comprehensive dependency/firmware vulnerability clearance is made. An additional build-backend scan found advisories in the initial setuptools 80.10.2 pin; it was replaced with hash-pinned 84.2.1, rebuilt and rescanned. The final build scan is build-dependency-audit.json.

The router nft fragment could not be checked by the host nft tool because its netlink cache requires privileges unavailable to this process. No firewall was installed. It must be checked and tested on the actual external router. Generated-rule string tests are not kernel enforcement tests.

## Remaining risks and release gates

Physical Nest compatibility, TLS bootstrap, complete transport/power behavior, native HVAC protections and recovery are unverified. The current partial firmware replacements are not a complete service audit or bootable firmware. No on-device isolation is enforced. Actual HAOS/Supervisor and aarch64 runtime validation are pending. Source/inert bundles reproduce; container image byte identity and binary provenance do not. Credential provisioning is not transactional across registry/export files. Manager roles and client/resource limits are intentionally minimal for the isolated laboratory. Retained MQTT state/HA history need owner-managed retention. These are explicit limitations, not waived security requirements for a release.

## Native TLS static review, 2026-10-30

The [native TLS review](../research/native-tls-2026-10-30.md) found error overrides
for a not-yet-valid certificate and selected CRL failures. A private offline
default-callback candidate is statically checked, not installed or target tested.
The recovered trust bundle contains one Nest anchor; no eMudhra trust path was
established. Recovery, clock/bootstrap, hostname/CA/time and CRL target tests
remain required. The public Ghidra helper exports only into private storage; its
actual integration and public-output-refusal checks passed. No native binary
was executed and no proprietary library/patch output was published.

## Unexecuted native TLS RAM test, 2026-10-30

The [separate diagnostic](../../firmware/tls_probe/README.md) is built and passes
offline integrity gates and 45 host regression checks. It uses synthetic
loopback TLS cases with native libraries, plus the separately reviewed private
callback candidate, under an unprivileged helper. Flash, block, physical-network
and RTC/hardware-clock update support are disabled in its custom kernel. The
boot stages still have unverified hardware/power side effects. No target run
or persistent installation occurred; owner-timed restart is next. See the
[dated scope record](validation-2026-10-30-tls-probe.json).

The subsequent [first-attempt record](../research/tls-probe-attempt-2026-10-30.md)
supersedes the preparation-only runtime status above: RAM reporting was observed,
but no TLS cases. The non-executable dynamic interpreter is corrected; richer
setup/launch evidence and independent host permission regression checks pass.
The corrected profile remains unexecuted. Native startup return was confirmed,
with no automatic retry, installation or recovery/HVAC claim.

The [second supervised result](../research/tls-probe-result-2026-10-30.md) now
confirms all 18 expected callback cases with native libraries on device loopback:
the candidate accepts valid and rejects all eight invalid cases. Native startup
returned after a full timed restart. Full native fetch/configuration, trusted time
bootstrap, credential persistence, recovery and HVAC remain unverified. No library
or CA was installed; raw results/hashes remain private.
