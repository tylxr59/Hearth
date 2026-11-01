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
| Native HA climate entity and single target | Host and real HA sandbox pass | Unwired-device command/confirmation test |
| Off/heat/cool and fan timer | Host and real HA sandbox pass | Actual native capability/report mapping and bench acceptance |
| Reported HVAC operating action | Boolean mapping implemented | Compare against real equipment states |
| Heat/cool range and emergency mode | Implemented in0.4; host and real HA sandbox pass | Actual native range/preset acceptance on suitable bench |
| Eco/away and eco temperatures | Not implemented | Structure ownership binding and native manual-eco timestamp semantics |
| Weekly schedules and schedule mode | Not implemented | Strict weekly schema, conflict handling and complete replacement tests |
| Learning/preconditioning and other NLE device settings | Not implemented | Per-field native writability/types/bounds; no generic arbitrary setter |
| Weather/outdoor data and useful diagnostics | Payload-free integration diagnostics in0.4; weather absent | Local HA weather mapping and fault entities |
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
or physical equipment. The0.4 package still needs owner-host activation and a
normal reconnect/cache-reload check. Eco, schedules, weather and the remaining
NLE settings are separate unfinished work.
