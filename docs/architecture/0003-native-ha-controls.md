# Native HA control transport

Hearth terminates the thermostat's redirected native HTTPS transport inside the
custom HA integration. Native code retains UI, schedules, equipment protection
and all HVAC control loops. The protocol subscription is an HTTP request waiting
for updated buckets, unrelated to a paid subscription or Nest Pro account.

The original bounded implementation in backend/native_controls.py extends the
telemetry receiver only when native_controls is explicitly enabled. Standalone
telemetry mode keeps rejecting commands. HA0.3.0 adds one climate entity while
preserving the three existing sensors and their unique IDs; MQTT is absent.

Commands are fixed temperature/mode/fan operations, not arbitrary field writes.
The first stage supports single temperature10..30C, off/heat/cool and a fan timer
with ten-minute maximum duration. Heating/cooling/fan capabilities require actual
reported booleans plus configured capability permission; missing values do not
default to equipment support. HVAC action derives from reported native booleans,
not differences between measured and target temperatures. Contradictory heating
and cooling evidence produces unknown action.

Each intent expires after30 seconds and remains volatile. Enqueue advances the
native bucket revision, but never changes HA's reported temperature or mode.
Only the allowlisted desired scalar values enter subscription responses;
telemetry PUT acknowledgements remain metadata-only, including conflicts.
Private/unknown native values remain keyed fingerprints and are never echoed. Metadata revision
and timestamp precede object_key for the measured native parser constraint.

A live subscription wakes to receive the new revision and partial value. This is
delivery evidence, not success. An accepted native upload containing the requested
value confirms the intent and updates reported state. Stale conditional uploads
cannot confirm it. A different accepted device value supersedes the HA intent;
unrelated telemetry rebases it without extending its deadline. Multiple disjoint
operations share a bucket revision. Newer same-operation intent replaces earlier
intent; expired intents, backend restarts and credential rotation do not replay.

HA's authenticated service calls feed this transport directly. The management
HTTPS endpoint remains Bearer-authenticated; canonical device polling stays
separate and disabled in native mode. A pending, confirmed, superseded or expired
command status is visible on the climate entity. The unauthenticated connectivity
204 view cannot enqueue, read or acknowledge commands.

The pinned public MIT NLE transport/command helpers provide protocol reference;
no implementation is copied. Additional reference identities are locked in
research/upstreams.json. Partial control values still require an actual unwired
unit measurement before physical HVAC testing. Host and real HA sandbox success
are not proof of on-device command acceptance or equipment operation.

## NLE functional parity checklist

| Capability on the Gen2 | Current Hearth state | Remaining evidence/work |
| --- | --- | --- |
| Local authenticated transport and telemetry | Working on owner unit | Long-duration reliability |
| Local connectivity checks and chosen time service | Updated; owner traffic and HA reconnect observed | Bounded observation, not all future endpoints |
| Native HA climate entity and single target | Physical63→62→63°F and HA target acknowledgement verified | Long-duration reliability; explicit target echoes remain separate |
| Off/heat/cool and fan timer | Host and real HA sandbox pass | Actual native capability/report mapping and bench acceptance |
| Reported HVAC operating action | Boolean mapping implemented | Compare against real equipment states |
| Heat/cool range and emergency mode | Implemented in0.4; host and real HA sandbox pass | Actual native range/preset acceptance on suitable bench |
| Eco preset and eco bounds | Physical manual on/off and restoration verified; Heat-to Off unchanged |0.6.9 fresh-mode feedback verification; bounds writes untested |
| Weekly schedules and schedule mode | Native week acquired; HA future point and original restore physically verified |0.6.9 consistent readback/revision verification; schedule-mode writes untested |
| Learning/preconditioning and other NLE device settings | Not implemented | Per-field native writability/types/bounds; no generic arbitrary setter |
| Weather/outdoor data and useful diagnostics | HA weather bridge and local native JSON in0.5; payload-free diagnostics | Native weather-fetch acceptance; advanced fault entities |
| Native local operation when HA/network is unavailable | Native logic preserved | Supervised outage/return tests, no stale replay |
| Actual heating/cooling/fan and equipment protections | Unverified | Separate equipment inspection/authorization and supervised test |

This checklist defines the functional-parity target. Passing the first basic
control roundtrip does not mark the whole project complete. Retain the stock
control loops throughout; HA sends settings, not relay commands or replacement
control algorithms.

## First device result and0.3.1 correction

HA0.3.0 loaded on the owner host and registered all four entities. One actual
0.5C target increase was reported by the unwired Nest. Its reverse request was
accepted by HA but did not produce confirmed original-target restoration in the
bounded watch. No additional control intent was automatically retried. Preserve
that partial result; it does not validate a complete command/restore cycle.

Code review found a0.3.0 mistake: pending values could be piggybacked on PUT
acknowledgements. The pinned NLE reference explicitly warns that doing so can
clear native dirty state or overwrite a local/scheduled change.0.3.1 removes those
values from PUT responses; only the subscription channel may carry intent.
This is a concrete protocol correction, not proof that it alone caused the
observed reverse-request failure.

The owner screenshot also showed availability expiring between reports.0.3.1
renews native presence on successful authenticated requests and valid active
subscriptions, without fabricating sensor reports. The native listener uses a
290s hold/300s wake safety-net,15s normal defer and60s confirmation defer-disable
when an initial pending update is sent. These timings follow the locked public
reference; power/network-loss behavior still needs actual measurement.

Authenticated manager diagnostics now expose fixed request counts, field-baseline
presence, pending/expired/confirmed outcomes and whether an intent was offered.
They omit unknown native values, credentials and command values.0.3.1 passes1115
host tests/five optional skips, make check and six real HA sandbox roundtrips.
Its21-file source package reproduced and was activated after owner approval, with
0.3.0 backed up and one Core restart. A subsequent fresh native report was close
to the saved original target, and the test increase was gone. Guarded restoration
preflights sent no additional intent because there was initially no baseline and
then a different exact value. The physical dial remains obscured by E22 on the
empty base. This is not an exact reverse-command confirmation or HVAC proof.


##0.4 reported state and additional controls

The reported-only cache retains bounded, allowlisted device/shared values and
bucket metadata in an owner-only atomic file. Credential generation binds each
record to the enrolled device. Credentials, unknown fields, runtime fingerprints
and pending intents are excluded. Loading does not mark a device available or
produce a fresh report. Valid native traffic renews presence; individual entity
attributes distinguish cached values from values reported in the current run.
A refused cache does not prevent fresh authenticated uploads. Disk errors remain
visible in payload-free integration diagnostics.

Heat/cool range uses one intent containing both ordered targets, each10..30C.
The active range mode and positive heating/cooling capabilities are required.
A single target is refused while range mode is active; both reported values must
match before confirmation. Emergency heat is a preset, exposed only when the
reported emergency-heat flag and configured heating permission both allow it.
Clearing that preset requires a fresh mode report. Native protection and control
loops remain untouched. No owner-unit range/emergency command has been sent.

The real HA Core2026.10.4 sandbox covers twelve service/native-report roundtrips,
including Fahrenheit conversion, range pairs and emergency preset transitions.
It also checks unload/reload, absence of command replay, cache source labels,
payload-free diagnostics and continued native operation when cache permissions
are refused. These use synthetic data on an isolated host runtime, not firmware
or physical equipment. The owner activated0.4 with one approved Core restart. Fresh native readings
seeded a private cache. A later owner-triggered integration reload retained all
three readings exactly, with an authenticated subscription and no new PUT yet;
no pending intent was restored. Eco, schedules, weather and the remaining NLE
settings are separate unfinished work.

## Acknowledged targets versus native reports (0.6.8)

Two supervised physical cycles under0.6.6/0.6.7 changed the dial from63 to62 F and
restored63 F without furnace activity. Explicit target reports did not confirm the
requests during their windows. Under0.6.7 the transient notification also produced
more PUT/subscription traffic. This is evidence that a working physical command
and a returned target value are separate events, not proof that any arbitrary
notification clear establishes physical execution.

The0.6.8 candidate recognizes only an accepted shared-bucket clear of a notification
actually written with the still-live target intent. It stops resending that
acknowledged target while continuing to accept explicit value reports. A queued
request, metadata-only acknowledgement, unsent/expired notification or rejected CAS
cannot create this state. Only single/range target notification acknowledgements
use this path; Eco, mode, fan and schedule confirmation rules are unchanged.

HA can display that target as **assumed**, with state source acknowledged and
command status acknowledged. It is not a measured target report or proof of HVAC
operation. The separate reported snapshot and management state remain unchanged;
measured temperature, humidity and HVAC action never derive from the request.
A later actual target report takes precedence. A conflicting device value drops
the assumption. Partially reported range targets retain their individual source
labels. These assumptions stay only in memory, clear on enrollment change, and
are excluded from private reported caches and command replay.

The original observation window remains bounded. An acknowledged intent without
a full value report ends as acknowledged rather than confirmed or expired. A full
accepted matching native report can still confirm within that window. The owner
unit must separately demonstrate this acknowledgement path before calling its
feedback behavior verified. No HVAC output is changed by this display behavior.


## Schedule configuration evidence and Eco mode (0.6.9)

Physical tests under0.6.8 verified manual Eco on/off and a future weekly point
followed by original-week restoration. Both ended with Heat63°F, Eco off and the
furnace idle. The old schedule getter returned older native values with the newer
transport revision, and Eco delivery receipts expired despite fresh actual mode.

Eco now accepts a fresh validated device mode as a separate confirmation source.
Schedule state separates requested, known complete configuration and native reports.
Only an exact post-write subscription metadata match completes schedule delivery
as acknowledged. Complete native reports supersede it. The getter and backup use
one corresponding values/revision/source view. A private enrollment-bound file
persists known complete configuration but no pending intent; reload is cache-only
and cannot emit a control. Fresh matching metadata can reaffirm that known proof.
Unproven merged caches cannot be promoted by metadata alone. Partial native deltas
after a replacement invalidate its baseline until a complete week arrives.

These acknowledgements describe protocol evidence. They do not establish actual
HVAC switching or an explicit complete-week echo. No native control loop changes.
