# Native eco, weekly schedules and HA weather

Original implementation uses the pinned MIT NLE command/transport reference for
protocol semantics. NLE's weather service currently proxies a Nest endpoint with
certificate verification disabled; Hearth does not reuse that path or code.
The owner selected an existing HA weather entity instead of a direct Open-Meteo
client. The selected HA weather integration remains the provider boundary.

## Scoped home state

Base telemetry still ignores unbound user/where/link/home data. Native controls
permit only the home key referenced by an accepted authenticated device-bucket
`structure_id`, inside that same device's isolated record namespace. This does
not establish external account ownership or authorize global/shared home access.
Foreign home buckets are not retained/reflected. A changed or null device
reference drops the former home record and eco intent; stale conditional device
uploads cannot change the association. Eco writes only the two reviewed manual
eco fields with a fresh timestamp. Current device-clock agreement is a bench
requirement, not established by a synthetic echo.

## Weekly replacement

The schedule codec accepts a full version-2 week only, with all seven native
local days, bounded ordered times/temperatures and a matching equipment mode.
It rejects unknown point fields and incomplete native baselines. Before a HA
replacement, a private original archive is synced and read back; a second
revision/generation check rejects intervening edits or re-enrollment. A cached
week can be read but is insufficient to authorize replacement without a fresh
native week. Pending intent is volatile and still travels only through native
subscriptions. The stock thermostat retains schedule execution and learning.

## Weather parser review

Read-only Ghidra analysis of the privately reconstructed Gen2 client identified
the weather fetch completion, its current/hourly/daily callbacks, timezone
callback and location consumer. No firmware was executed or installed. Private
decompilation remains under `private/native-weather-review-20261101`; no binary,
binary hash or decompiled implementation is included here.

The parser requires current `temp_c` and `humidity`; supported icon strings map
to fixed native conditions. Hourly rows use a1..48 slot, epoch `time`, `temp_c`
and optional humidity. Daily rows use epoch `date`, `temp_low_c`, `temp_high_c`
and optional humidity, up to six entries. Location recognizes short timezone,
`timezone_long`, `zip` and `country`. Native epoch parsing uses signed32-bit
values, so the codec rejects timestamps beyond that range.

The location consumer can clear country/postal values when returned empty.
The endpoint therefore requires the native postal/country query and reflects
only those strictly bounded fields, alongside HA's configured timezone. It
never derives a URL or provider from that query. It does not invent city/state
labels or missing forecast/humidity data. Actual location/timezone effects and
weather fetch authentication still require supervised native observation.

HA forecast calls are local service calls; source/unit/type-bound caches expire
after15 minutes. Current data older than two hours or unsupported units/values
refuse. The source is selected explicitly when multiple HA weather entities
exist; a sole entity may be selected automatically, and weather can be disabled.

A subsequent read-only review traced the weather fetch creation and native fetch
library: weather does not enable Basic auth, the event defaults that flag off,
and the library applies curl Basic credentials only when that flag is enabled.
The initial0.5.0 authenticated weather endpoint therefore mismatched this native
request contract.0.5.1 corrects the single read-only weather route; transport and
management remain authenticated. No firmware was executed for this review.

These additions are host/real-HA build results. Unit eco changes, schedule
replacement/restore, native weather parsing and physical HVAC remain unverified
until separately measured. Whole-firmware recovery remains unverified.
