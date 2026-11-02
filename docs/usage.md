# Use Hearth

The climate card exposes only modes supported by reported equipment and allowed
by enrollment. Missing capability flags do not default to support. Heating/Idle
is derived from native operating flags, not a comparison between room and target.

Temperature targets are stored in native Celsius. HA converts for display, using
dial-appropriate precision. Acknowledged targets may be labelled assumed until a
native value report arrives. Later native values take precedence.

## Eco

Eco controls native manual Eco. None stops manual Eco; it does not disable the
thermostat's automatic Eco behavior. A fresh native mode can confirm the command.
Existing limits remain unchanged unless the separate paired-bound action is used.

## Schedules

Use Developer tools → Actions → Hearth: Read weekly schedule. The returned
seven-day week uses explicit Celsius;0–6 are Monday–Sunday. An apparently empty
native schedule may still contain continuation records. Preserve those records.

Replace weekly schedule requires the full desired week, explicit temperature
unit and the revision obtained by reading. Hearth syncs a private backup first,
rechecks enrollment/revision, then queues one replacement. A stale revision refuses.
Read again after applying; do not repeatedly submit an old action.

Sources describe the actual evidence:

- `device`: validated native week received in this run.
- `pending`: requested week, not yet acknowledged.
- `acknowledged`: exact written version was returned in client subscription metadata.
- `cache`: known configuration restored from disk without current freshness.
- `unconfirmed`: a request expired without acknowledgement; investigate before editing.

An acknowledgement is distinct from an explicit full native-week echo. Current
Gen2 replacement and original restoration have been physically verified.

## Device configuration

Switches, numbers and selects expose reported learning, Early-On, Sunblock,
filter, display and equipment settings. No value is invented for missing fields.
Equipment-affecting entities start disabled. The Set device settings action can
change an allowlisted group atomically in one native bucket; safety/equipment
changes require an HA administrator and `confirm_equipment_changes: true`. Temperatures use Celsius.
Fresh per-field baselines and appropriate reported fan/heat-pump/hot-water support
are required. A cached value alone cannot authorize a new setting.

PIN hashes are write-only inputs to the explicit advanced action; they are never
included in the reported cache or normal entity attributes. Hearth does not invent
an undocumented native PIN hashing algorithm.

## Weather

Select a weather entity in Hearth's Configure options. For the native IPv4 fetcher,
set the fallback postal/country to the actual configured location. Hearth adapts
HA current weather and forecasts into native responses; no separate weather
subscription is required. Unavailable HA weather remains unavailable rather than
inventing observations.


## Optional diagnostics

Enable diagnostic entities in the device's entity list for battery voltage,
Wi-Fi signal, filter runtime/replacement, outdoor temperature, Sunblock/Early-On
activity and heat-pump readiness. Battery is shown as reported voltage rather than
an invented battery percentage. Time to target is converted from a native epoch
into minutes remaining; absent values stay unknown. Zero outdoor temperature is
preserved. These diagnostics do not change thermostat or equipment settings.
