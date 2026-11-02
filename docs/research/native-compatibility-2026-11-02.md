# NLE comparison and native feature compatibility

The owner installed the Nest on physical HVAC wiring. The wiring error cleared;
the physical dial showed Heat at a low target, and the owner reported no furnace
activity while the room was warmer than target. Read-only reported output flags
were all false. The native equipment report supported heating, with cooling, fan
and emergency heat false. The broader manager enrollment allowance was not an
observed equipment capability. No remote equipment operation was tested.

The owner then opened the Eco menu and saw Start Eco. This confirms the current
physical preset is off; the earlier efficiency leaf did not establish manual Eco.
Prior commands still expired without native value confirmation, so this result
does not establish successful remote Eco delivery or identify its cause. No more
Eco-off requests were sent after the physical observation.

## Reference comparison

Four pinned NLE backend reference files were downloaded and independently matched
the existing provenance inventory. The command path uses the same manual Eco
boolean and seconds timestamp that Hearth already emits; changing field names or
units is not an evidenced fix. Its subscription formatter also places revision
and timestamp before the object key, as Hearth already does. The compared paths
are [commands](https://github.com/codykociemba/NoLongerEvil-SelfHosted/blob/bca8781012639c1cefc4a08c103fc892158fb630/src/nolongerevil/routes/control/command.py)
and [transport](https://github.com/codykociemba/NoLongerEvil-SelfHosted/blob/bca8781012639c1cefc4a08c103fc892158fb630/src/nolongerevil/routes/nest/transport.py).

NLE's [weather service](https://github.com/codykociemba/NoLongerEvil-SelfHosted/blob/bca8781012639c1cefc4a08c103fc892158fb630/src/nolongerevil/services/weather_service.py)
proxies Nest weather, including automatic-location queries. Hearth retains the
owner-selected HA weather source. Separate read-only native fetcher review confirms
the literal ipv4 fallback token, consistent with the observed four-character query
shape; that shape alone was not proof of its exact content.

## Prepared correction

0.6.6 accepts the native fallback token only with a complete, explicitly configured
local postal/country pair from the HA weather source. Missing configuration returns
unavailable. Public query traffic cannot seed this location, and neither caller-IP
geolocation nor an external Nest request is introduced. Standard postal queries
continue to reflect their own bounded fields. Fallback configuration is excluded
from the outgoing native weather JSON.

Read-only native point serialization review identifies entry classification and
optional provenance integers plus an optional user identity. The schedule codec
preserves these recognized fields with type/bounds/group checks, including negative
timezone offsets. Private cache, HA reads and pre-change archives preserve them;
unknown fields still refuse validation. Diagnostic summaries retain types only.
This is compatibility support, not proof that the owner's complete native week
has passed validation or been replaced/restored successfully.

All 1303 host tests pass with five optional skips; make check passes. The pinned
network-isolated HA2026.10.4 sandbox passes 18 synthetic control round trips,
weather fallback/source checks and provenance-preserving schedule backup/replacement.
The initial sandbox run exposed a test variable error; the corrected final run
passes. Final and independent reproduction packages match exactly. All 33 staged
integration files read back exactly; old code, cache and pairing are backed up.
Activation and Core restart await owner approval. No thermostat flash or remote
HVAC operation was performed for this update.

## 0.6.6 activation and reconnect

The owner explicitly approved activation and one Core restart. All active source
bytes matched the staged package; the previous source remains preserved. Core
restart returned zero, with four registered entities and no scoped errors. The
owner saved the fallback location in HA options. A read-only host request to the
literal fallback path returned valid configured location/timezone, current weather,
48 hourly rows and six daily rows. This checks the server response, not native UI
rendering of every forecast field.

The Nest reconnected without another restart. Fresh native GET, PUT and subscription
requests were observed, with an active subscription, local user/home metadata
acknowledgements and one native weather request served without rejection. Effective
modes were off/heat, with no pending commands. The successful native weather request
is not evidence of which query form it used. No thermostat command, flash or
physical HVAC switching was performed during this activation. Actual schedule
replacement and remote control confirmation remain outstanding.

## Supervised physical setpoint cycle

The initial preflight sent no command. Its short request-age check was unsuitable
for a healthy held subscription, and the target had moved from the earlier
baseline. The owner confirmed the current dial was Heat at 63 F. The revised
preflight checked an active subscription, bounded hold age, native report presence,
heat-only capability/mode, no pending commands, finite temperatures and room at
least 3 C above both targets. Eight independent host acceptance/refusal fixtures
passed before executing it.

One 62 F request was sent, with the native original privately preserved. The owner
confirmed the physical dial reached 62 F. One restoration request then used the
saved native original, with the same preflight. The owner confirmed return to
63 F and no furnace activity throughout. This verifies a bounded setpoint delivery
and restore on the unit, without deliberately calling for heat. It does not test
furnace switching, cooling, fan or emergency heat.

Both backend intents expired with successful server stream writes and no matching
native reported values during their windows. Physical execution is therefore
verified independently, while native feedback remains unresolved. No command was
retried. The NLE reference additionally sends target_change_pending=true for target
updates, a transient notification Hearth had omitted. A candidate follows that
behavior without treating the device's clearing of the flag as temperature
confirmation or persisting it for replay. It also corrects stream receipts for
multiple intents written together in one bucket. These changes need independent
validation and deployment before another device measurement.

## Prepared target notification and receipt update (0.6.7)

Only live target-temperature subscription values receive the transient notification;
mode-only, ordinary PUT acknowledgements and expired commands do not. Clearing the
notification cannot satisfy or supersede an outstanding target value. The hint is
excluded from desired-field counts and reported-state persistence. Native reports
still must supply the desired target; queueing and stream writes remain distinct
from execution. Stream receipts now credit each matching intent in a merged bucket
instead of requiring the entire bucket to equal each individual intent.

1306 host tests pass with five optional skips; make check passes. The pinned real
HA sandbox completes 18 synthetic control round trips with the transient hint
cleared by simulated native reports. Separate checks cover clearing without a
reported target, merged-frame partial matches, expiry and cache exclusion. The
final package reproduces exactly, and all 33 remotely staged source files read
back exactly. Active code, cache and pairing are backed up. The source remains
staged pending owner activation/Core restart approval; no further thermostat
command has been sent. This is not yet evidence that owner-unit feedback is fixed.

## 0.6.7 activation and fresh reports

The owner explicitly approved activation and one Core restart. All 33 active source
files matched the staged package and old code remains preserved. Core restart
returned zero; health checks found four registered entities, no scoped errors and
a private single-link reported cache. The endpoint was briefly unavailable during
startup, then returned normally.

The Nest reconnected with a fresh GET, two PUTs and an active subscription. User
and home metadata were acknowledged; there were no rejected native requests or
pending commands. The owner confirmed the display was awake. The fresh report
remained Heat at 63 F with the room more than 3 C above target, and effective
capabilities remained off/heat only. No thermostat commands were sent during
activation. The feedback change is not yet verified on the unit; a separate
supervised bounded cycle has been proposed to the owner.

## 0.6.7 owner feedback measurement

The owner authorized one repeat bounded cycle. Fresh guards passed before one
62 F request; the owner confirmed the physical dial reached62 F. One original-target
restoration followed, and the owner confirmed63 F with no furnace activity
throughout. Native report confirmation still did not follow within the intent
window. Additional accepted PUT/subscription traffic occurred after the notification
was introduced, but its contents were not retained in the observer. Thus the
observation does not independently prove a successful notification clear.

The pinned NLE transport explicitly handles the device clearing
`target_change_pending` back to false. The0.6.8 candidate separates that accepted
client acknowledgement from an actual target-value report. This is an explicit
protocol inference with an assumed-state UI label, not a claim that server writes,
metadata or clearing a flag prove equipment execution. See the control architecture
note for limits and invalidation rules. No additional thermostat command was sent
while preparing this correction.

## 0.6.8 owner-unit acknowledgement result

The owner approved activation and one Core restart. Active source readback matched
all33 files, old source was preserved, and the restart returned zero. Health checks
found four registered entities, no scoped errors and a private single-link reported
cache. Native GET/PUT/subscription traffic returned without another reboot, with
user/home acknowledgements and no rejected native requests.

After separate owner readiness, one guarded62 F request and one saved-original
restore were sent. The owner confirmed62 F, then explicitly both physical Nest
and HA climate card at63 F, with no furnace activity throughout. Both terminal
receipts were acknowledged with a completed stream write and a client notification
clear, while matching explicit target-report count remained zero. This validates
the acknowledgement path and HA original-target display on the unit, not an
explicit target-value report or a deliberate furnace heat call. The acknowledged
subscription remained open. No command was retried by the host helper.

A subsequent read-only Eco preflight found no saved low Eco limit. The current
report validator starts that field at5 C; [Google's documented Eco range](https://support.google.com/googlehome/answer/9245535?hl=en)
includes40 F (about4.4 C), so this is a possible receiver gap. It is not proof of
why this unit's low limit is missing. The owner was asked to read the configured
Eco Heat to setting without changing it; no Eco-on command was sent.

## Eco and native week observations under0.6.8

The owner read Eco Heat to as Off and separately authorized a cycle without
changing those limits. One on request produced a physical Stop Eco menu; one off
restore returned Start Eco, HA None, Heat63 F and no furnace activity. The fresh
reported device Eco mode was schedule after restoration. Structure scalar/time
confirmation remained absent, so the expiry status still did not describe the
physical outcome. No more Eco command was sent after restoration.

The owner confirmed an empty physical schedule. Opening it alone did not upload
a week. One temporary62 F point was added for tomorrow noon through the native UI;
the subsequent complete week passed the existing strict codec: seven days, one
setpoint and seven continuation records, with provenance preserved. After the
owner removed only that point, the UI was empty again and the fresh native week
contained zero setpoints and seven continuations. The dial was63 F and furnace
idle. Both weeks and a synced/read-back private original archive are preserved.
An empty UI must not be represented as seven empty arrays that discard the
native continuation data.

A prepared HA set_schedule action uses the actual original plus the same single
future point, explicit units and the current revision. The integration's backup,
CAS, generation and fresh-baseline checks remain in place. The owner has been
asked to perform it once in HA; backend replacement/restore verification remains
pending. A separate restore will use the preserved original and a newly read
post-apply revision.

## HA weekly apply/restore and readback defect

The owner executed the prepared HA action. A stale-revision refusal was displayed,
but an actual request was also queued/written, and the owner confirmed the future
62 F point on the physical Nest. The refusal is not evidence that nothing changed;
there is insufficient evidence to attribute it to a particular click sequence.

The owner then ran the read-only schedule action: it returned revision3 with the
OLD original week, despite the installed visible point. The getter was combining
reported values with the newer transport version. A separate restore action used
the preserved original and the newly read revision3. The owner confirmed successful
action processing, empty physical schedule, Heat63 F and furnace idle. SSH review
verified two private0600 HA backup archives matching the original week.

Full native-week echoes did not confirm these writes within their intent windows.
The physical replacement/restore path is measured, but current readback consistency
and command feedback remain bugs. The next correction must associate each week
with its own revision/source, keep requested/acknowledged configuration separate
from reported native values, and retain backup, generation, CAS and no-intent-replay
gates. No further thermostat operation is needed during this offline correction.
