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
Only the allowlisted desired scalar values enter responses; private/unknown
native values remain keyed fingerprints and are never echoed. Metadata revision
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
| Heat/cool range and emergency mode | Not implemented | Capability/bounds mapping, atomic range intents, native tests |
| Eco/away and eco temperatures | Not implemented | Structure ownership binding and native manual-eco timestamp semantics |
| Weekly schedules and schedule mode | Not implemented | Strict weekly schema, conflict handling and complete replacement tests |
| Learning/preconditioning and other NLE device settings | Not implemented | Per-field native writability/types/bounds; no generic arbitrary setter |
| Weather/outdoor data and useful diagnostics | Partial/basic readings | Local HA weather mapping, diagnostic entities and fault reporting |
| Native local operation when HA/network is unavailable | Native logic preserved | Supervised outage/return tests, no stale replay |
| Actual heating/cooling/fan and equipment protections | Unverified | Separate equipment inspection/authorization and supervised test |

This checklist defines the functional-parity target. Passing the first basic
control roundtrip does not mark the whole project complete. Retain the stock
control loops throughout; HA sends settings, not relay commands or replacement
control algorithms.
