# Native Home Assistant integration

The current deployment target is a native custom integration:

**Nest native client → Hearth's HTTPS listener inside HA Core → HA entities.**

The integration receives the existing native Nest protocol and uses unique
assigned credentials. MQTT and the separate HA app are not part of this path.
The integration exposes temperature, humidity and target-temperature sensors plus
a climate entity. Scoped settings commands use native subscriptions; physical HVAC
operation remains unverified. The sections below preserve the earlier migration
history; see the current controls and restart-state section for the latest scope.

## Build and validate

Build a fresh public-source installation directory:

```sh
.venv/bin/python -m tools.package_native_ha build/native-ha
```

Copy the **generated** `custom_components/hearth` directory to HA's configuration
directory. The source template alone is incomplete: the packager includes the
single canonical transport implementation with isolated relative imports. It
excludes the MQTT module, broker credentials, firmware and all private data.

The independent runtime check uses the pinned HA Core2026.10.4 image, a temporary
HA instance and synthetic certificates/credentials, with physical networking
disabled:

```sh
.venv/bin/python -m tools.check_native_ha build/native-ha-check --engine podman
```

Use fresh output paths. No attached thermostat, live HA instance or MQTT broker
is used by that check. Passing it does not establish compatibility with other HA
versions or physical HVAC safety.

## Prepared commissioning profile

The integration loads these owner-only regular files from
`.storage/hearth` under HA's configuration directory:

| File | Purpose |
| --- | --- |
| `profile.json` | Format marker and advertised private-IPv4 HTTPS origin |
| `registry.json` | Existing separate manager/device credential hashes |
| `server.pem` / `server.key` | Native-protocol server certificate and matching key |
| `ca.pem` | The owner CA already installed on the thermostat |

The directory must be0700 and files0600, without symlinks or shared hardlinks.
The listener validates its profile, enrolled-device presence, certificate issuer,
validity, IP SAN and key match. No shared/default credential is generated. The
config entry stores no private keys or device credentials. This experimental
revision requires an independently prepared model-specific commissioning profile;
it is not an automatic installation or credential-extraction feature.

Restart HA after staging a new custom integration, then select **Settings →
Devices & services → Add integration → Hearth** and submit the import form.
Port conflicts or invalid private profiles refuse startup. Entity availability
expires with native state silence; unloading the config entry closes the listener
and cancels its timers. New settings intents are volatile and expire after30 seconds.

## This owner's migration

The owner chose HA's IoT address. A certificate signed by the same installed
owner CA covers that address and the previous entry address during handoff,
retaining the server key already proven by the native client. The new transport
origin advertises the IoT address. The old on-device registration URL still needs
its later targeted update; no thermostat flash was required to stage this HA test.

The Hearth MQTT app was stopped at the owner's request. Its seven retained
discovery/state/availability topics were cleared and a fresh subscriber verified
their absence; the old MQTT entity registry entries disappeared. Existing private
source/configuration backups remain for recovery, without a running broker bridge.

Residual Google HTTP connectivity probes and the separate ConnMan time-server
configuration remain an active firmware follow-up. This HA migration does not
claim they are removed. Preserve native control/backplate behavior while preparing
and validating that separate correction.


## Observed native HA activation

The owner explicitly authorized one Core restart, added Hearth, then performed a
fresh normal thermostat startup on the unwired base. The integration's manager
view reports available with temperature/humidity/target-temperature state, and
the owner confirmed all three readings in the native HA device page. HA converts
the native Celsius readings to the user's display units. One initial bucket-shape
request was refused before subsequent uploads succeeded; the decoder remains strict.

The retired Hearth Laboratory app was subsequently uninstalled after its complete
private configuration archive was read back and matched against the active registry
and server key. Its local app source was moved out of the app catalog. The native
integration continues independently, with no MQTT configuration or library bundled.
Google-dependency remediation and native command delivery remain separate unfinished
work; this observation is the read-only native HA milestone.

## Prepared local connectivity response

Candidate0.2.1 adds `/api/h/204` to HA's existing HTTP frontend and an authenticated
`/nest/init` alias to the separate HTTPS native listener. The former returns an
empty204 only for a body-free/query-free GET while Hearth is active, with no
device data or control operation. The alias preserves the original credential
checks and permits the planned equal-length on-device registration URL change.
Neither route requires another app, MQTT or a new device listener.

The candidate passes the real pinned HA runtime check. The owner then authorized
activation and one Core restart; the live frontend passes204/empty-body and
query/method refusal checks. Fresh native telemetry initially awaited charging.
After USB charging and return to the unwired base, the owner and authenticated
manager independently confirmed all three readings under 0.2.1; reconnect now passes.
Device URL/time replacements remain offline only. See the
[network preparation record](research/native-network-preparation-2026-11-01.md)
for exact evidence, remaining update bounds and recovery gates.


## Current controls and restart state (0.4)

The climate entity supports a bounded single target, off/heat/cool, supported
heat/cool range pairs, a ten-minute fan timer, and an emergency-heat preset when
the thermostat explicitly reports support. Unsupported controls remain hidden
or are refused. Values and command status reflect accepted native uploads; a
queued request does not optimistically change the reported target. Physical
control acceptance is still unverified on the owner's completely unwired base.

Version0.4 saves only allowlisted reported state to private
`.storage/hearth/reported-state.json`. A reload restores last-known values,
with per-field `reported_state_source` attributes identifying `cache`, `device`
or `unknown`. It does not restore pending commands or mark the unit available.
Availability requires valid native traffic, and cached values are not new
measurements. The initial upgrade needs actual reports to seed the cache; there
is no previous cache to import from0.3.1.

HA's integration diagnostics omit identifiers, addresses, sensor readings and
command values. They include request counts, capability/baseline presence,
command outcomes and cache error flags. A refused cache leaves the native
listener able to accept fresh uploads.

The targeted four-file network update has also been installed and read back,
with native return and telemetry reconnect observed. The owner observed the
chosen public NIST time service and no new Google entries during the bounded
watch. This does not establish that every future endpoint has been removed.

See [the feature checklist](architecture/0003-native-ha-controls.md) for remaining
eco, scheduling, settings, weather and supervised equipment work.


## Target sensor display precision (0.4.1)

The native client reports Celsius setpoints. Converting a reported fractional
value can produce65.9F while the physical Nest displays66F. The separate target
sensor now suggests zero decimal places for Fahrenheit and one for Celsius,
using the entity's actual display unit, including a per-entity override. This
changes display formatting, not the native value, history or command conversion.
Measured temperature keeps its existing precision. An explicit user-selected
precision continues to take precedence over the integration's suggestion.

On an existing installation, open the Target temperature sensor settings and
set Display precision to0 for whole-degree Fahrenheit immediately; this does
not require restarting HA. The climate entity already uses whole-degree
Fahrenheit display through HA's standard climate conversion.


## Eco, weekly schedules and HA weather (0.5)

The climate entity exposes an `eco` preset only after the native device reports
its home reference and a validated eco baseline. Home buckets stay inside that
authenticated device's record namespace; this is a local association, not proof
of ownership of a Google account or permission to share data across devices.
A changed/unset reference discards the old home state and pending eco intent.
Manual eco uses `manual_eco_all` and a current UTC timestamp, matching the pinned
native reference; device clock synchronization and actual acceptance still need
a unit measurement. Clearing a cached eco preset requires a fresh eco report.

The Hearth actions in HA are:

- `hearth.get_schedule`: return the last validated complete week, source
  (`cache` or `device`), Celsius unit and revision.
- `hearth.set_schedule`: require all seven days, explicit units and the expected
  revision. It checks a fresh native baseline, saves/fsyncs/reads back an original
  private archive, and rechecks the revision before queuing a replacement.
- `hearth.set_schedule_mode`: request supported `HEAT`, `COOL` or `RANGE`.
- `hearth.set_eco_temperatures`: set both ordered eco bounds using explicit units
  and reported heating/cooling support.

Each action targets a Hearth climate entity. The native weekly format is
`ver: 2`, a printable name, `schedule_mode`, and `days` with keys `0` through `6`
(Monday through Sunday). Each day is a list or a contiguous numeric-key object
of at most24 ordered points. A point has integer `time` seconds after local
midnight and a matching `type`. HEAT/COOL points need `temp`; RANGE needs ordered
`temp-min` and `temp-max`. Temperatures are bounded to10..30C after explicit unit
conversion. All days, including intentionally empty days, must be present.
Unknown point fields and unsupported/partial native weeks refuse replacement.
No HA timer executes the schedule: native scheduling continues on the thermostat.
Learning behavior remains native and may subsequently edit the week.

Pre-change archives are owner-only0600 files named `schedule-backup-*.json` in
`.storage/hearth`. They contain private device identity, credential-generation
binding and the validated original week; preserve them privately. They are not
replayed at startup. After64 archives, further schedule writes refuse until the
owner preserves/clears old archives. Restoring a prior week uses the same explicit
set-schedule action with a fresh current revision, producing another backup.
This is not a verified whole-firmware restoration mechanism.

In Hearth's Configure menu, select an existing HA `weather.*` entity, select the
single-entity automatic choice, or disable weather. Multiple sources require an
explicit selection; an unavailable source produces an unavailable response.
Hearth makes no direct Open-Meteo, Google, geocoding or other weather-provider
requests. The selected HA integration retains responsibility for its provider
configuration, attribution and availability.

The authenticated native entry handshake advertises the local weather URL when
a source is selected. The local endpoint maps HA current temperature/humidity,
conditions, up to48 hourly points and six daily points into the fields statically
reviewed in this Gen2 client. It supplies HA's configured timezone and preserves
the bounded postal/country fields from the thermostat's own weather query.
The native location consumer can otherwise clear its country when given an
empty location, which can also affect display units; malformed or absent native
postal/country queries therefore refuse instead of returning empty defaults. Unsupported
forecast rows are omitted, unavailable current data refuses the response, and no
missing humidity/forecast is invented. Forecast caching is15 minutes and keyed
by source, forecast type and units; current reports older than two hours refuse.
Query text never selects a URL, provider or external destination.

A new weather URL may require a fresh native entry handshake. No automatic eco,
schedule, mode or target change accompanies activation. All these features are
measured in a synthetic real-HA sandbox; actual native weather fetch and control
acceptance remain separate supervised bench checks on the completely unwired base.
