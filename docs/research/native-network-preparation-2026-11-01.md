# Local connectivity and time candidates

The native HA integration 0.2.0 now receives real temperature, humidity and target
temperature readings. The owner confirmed all three in HA. This is direct HTTPS
to HA Core, with the old MQTT app removed. It does not establish command delivery,
HVAC operation or removal of every external connection.

## Evidence and intended correction

The owner's network metadata shows HTTP to `clients3.google.com` and NTP labelled
`time.google.com`. Metadata alone does not reveal request contents. Offline owner
firmware review finds the exact terminated Google 204 URL in both `connmand` and
`nlclient`. A private Ghidra review traces the latter string through an initialized
string object to a shell-based curl connectivity helper. Complete indirect caller
reachability and runtime request contents remain unverified; neither binary was
executed on the host. Call-site addresses are not function-entry selectors: do not
infer caller functions from decompilation started at an arbitrary call instruction.

The [published vendor ConnMan source](https://nest-open-source.googlesource.com/nest-learning-thermostat/5.9.4/connman/+/ba669b5831fd37dd868237c13db163256d1b0c52/)
uses the Google URL as a WISPr connectivity fallback. Its source identity and
individual public file hashes are pinned in [connman-5.9.4.json](connman-5.9.4.json).
This is source corroboration, not a reproduced source-to-device binary build.
Disabling online checks could disrupt the native application's connectivity state;
the proposed change instead supplies an equivalent local response.

Recovered `/etc/connman/main.conf` independently prefers `time.nest.com` through
`FallbackTimeservers` and `PreferFallbackTimeservers`. The earlier `ntp.conf`
change did not affect this source. The prepared candidate changes only the exact
fallback value to the owner's chosen public NIST service. A Google DNS alias and
actual post-change NTP traffic have not been measured. Ordinary NTP is unauthenticated.

## Prepared source, not a device update

`provisioning.native_network` constructs fixed-width offline candidates for:

- Each exact Google URL in allocated, read-only, non-code ELF data, redirected to
  the HA frontend's literal private address and `/api/h/204`.
- The uniquely reviewed ConnMan fallback value, preserving other configuration.
- The existing native registration origin, updated to HA's IoT address using the
  equal-width authenticated `/nest/init` alias.

Candidates preserve full file length and every byte outside the selected span.
They are private DATA objects, with no device access or application command.
`FixedSpan.apply` checks the selected original span, not a full-file identity;
a future device operation must independently bind freshly acquired whole-file
contents, metadata and backup receipts before writing. No proprietary binary,
owner address, private hash or generated replacement is included in source.

HA candidate 0.2.1 adds a bodyless HTTP 204 view on its existing HTTP frontend.
It accepts only a query-free, body-free GET while the Hearth listener is active;
it returns 503 when inactive. The view has no authentication because connectivity
probes cannot supply it, and exposes no identity, state, enrollment or command.
The actual native protocol and new entry alias retain their existing HTTPS and
credential checks. This narrow reachability response does not authorize plaintext
telemetry or management. Frontend reachability from the device remains to be tested.

## Validation and remaining gate

On 2026-11-01, `make check` passed and the full host suite passed 880 tests, with
five optional integration skips. The pinned HA 2026.10.4 sandbox also passed real
HTTP 204/empty-body, malformed query/body/method refusal, inactive503, TLS/auth,
three entity updates, expiry, unload and four invalid-profile cases. It used only
synthetic credentials and no physical networking. The subsequent live activation
is recorded below.

The new private Ghidra URL helper successfully exported bounded static results;
a deliberate public output was refused with no exports. Ghidra exit status alone
is insufficient: check its completion marker and expected fresh files. Private
call-site experiments that lacked an established function start are not reachability
evidence. All logs and decompilations remain private.

The native client is about 5 MiB, exceeding the current writer's 1 MiB per-file bound.
Do not enlarge every existing limit or send these candidates to the nine-file
installer. Next prepare a separate bounded update/restore contract, fresh exact
file acquisition, persistent backup verification, RAM fault cases, and active
JFFS2 fragment-encoding verification. Untouched stock compressed fragments cannot
simply be subjected to the prior whole-file NONE/ZERO audit. Notify the owner of
the concrete write scope and recovery limits before any device execution. No new
loader, device-persistent operation or physical control was started for this review.

## Owner-authorized HA activation

The owner authorized activation and one Core restart. Candidate 0.2.1 was staged,
read back exactly and activated after preserving/readback-verifying the complete
previous 0.2.0 code archive. Core restart exited 0. The real HA frontend now returns
204 with zero response bytes; query 400 and POST 405 refusal checks also pass.
The separate HTTPS manager listener authenticates correctly. Fresh thermostat
telemetry after the restart is still pending; do not confuse the earlier 0.2.0
physical readings with a measured 0.2.1 reconnect. No thermostat files, profile
credentials or router rules changed in this activation.

After the bounded three-minute reconnect watch, the owner reported the battery
likely depleted overnight on the unwired base. Charging by USB was requested,
with no loader or ring restart. A reconnect defect is not established; fresh
telemetry remains unmeasured until battery power and Wi-Fi operation resume.

The [proposed bounded device contract](../architecture/0002-network-update-plan.md)
uses full-file streaming replacement through uncompressed temporaries, allowing
the existing whole-file encoding audit to remain applicable. It is a preparation
plan, with fresh acquisition and adapter/RAM validation still required.
