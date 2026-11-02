# Native subscription delivery and confirmation

HA 0.6.4 accepted the observed signed revision forms and received a seven-day
schedule object. Two explicitly scoped Eco-off attempts expired without native
confirmation. The later attempt was queued immediately after a newly observed
subscription; no second POST was issued within that attempt. A subsequent cache
read did not show a new eco timestamp matching its request window. The earlier
saved None value is not proof of restoration. Physical Eco-off remains unverified.

## Candidate transport correction

The 0.6.5 control runtime holds a quiet chunked subscription when there is no actual
configuration or desired value to send. It no longer closes that connection merely
because the client reports stale metadata for a telemetry bucket. Metadata replies
for incoming inline values, including failed conditional writes, remain intact;
ordinary PUT acknowledgements are unchanged. The signed client comparison still
cannot assign a negative server version or bypass a conditional write.

Pending values remain eligible for delivery even when a client already knows the
bucket's current revision. Knowing metadata does not establish receipt or execution
of a desired value. Expired values still cannot be transmitted. A pushed update
on an already held stream gets a bounded three-second settle interval before EOF,
matching the reviewed pinned NLE timing pattern. Shutdown interrupts this wait.
This is a concrete protocol correction and tested comparison, not yet an observed
fix for this physical unit.

Management diagnostics report the number of active subscription handlers, which
is more useful for readiness than an old request count or last-seen availability.
Terminal delivery receipts retain only outcome, offered status, observed successful
stream write, and matching/required field counts. A successful server stream write
is not peer receipt or execution. An absent write observation is likewise not proof
that a packet was never delivered. No command values, identifiers or payloads are
added to these receipts, and they are not persisted or replayed.

## Fresh field confirmation

Every desired field must have been received with a matching value since the current
intent was queued. A new timestamp alone cannot borrow an old cached Eco-off boolean
and produce confirmation. Partial reports can accumulate matching fields within
the same live intent. Replacing the intent resets this evidence. A conflicting
native value still supersedes the command. Expiry cannot cancel an already offered
network packet, so the earlier expired request remains an application risk. The physical Eco
label alone did not distinguish automatic Eco from manual Eco.

## Schedule schema gap

The actual upload has the four expected root members, a heating mode and seven
days, but fails the current strict week schema. Read-only native serialization
review independently found that points include `entry_type` with setpoint or
continuation classification; the current command schema omits this field. Further
native point metadata needs review and preservation before a complete replacement
can be claimed. Expanded type/count/schema diagnostics expose no actual schedule
name, times, targets or unknown member names. The marker used internally for a
native overwrite is now correctly described as an object in these diagnostics.

No unsupported week is promoted into a validated backup or control baseline.
No schedule replacement, new Eco-on test, wiring-check bypass or physical HVAC
operation was performed during preparation. The active unit remains subject to
owner-supervised restoration and native validation after the staged HA update.

## Validation

The full host suite passes 1,279 tests with five optional integrations skipped;
`make check` passes. The pinned real Home Assistant Core 2026.10.4 sandbox passes 18
synthetic control round trips, now using stale signed revisions, plus explicit
None, partial Eco confirmation, inline-CAS failure, private cache reload and no
intent replay. HTTP tests verify a quiet stream stays open, a control frame is
written without optimistic state changes, and shutdown interrupts settling.
These are host/sandbox results. Actual native control latency and restoration
remain unverified until the owner-unit test.

## Device Eco mode and weather request evidence

The candidate retains only the recognized mode from a native device Eco report;
other nested metadata is discarded. HA prefers that report over a possibly stale
house request flag. Manual Eco selects the Eco preset; automatic Eco is labelled
separately, preserving the thermostat's own automatic behavior. An unsupported
observed mode is unknown rather than a guessed previous mode. A restored mode is
labelled as cache and does not make the device available or replay a command.
The earlier physical Eco label did not by itself prove a delayed manual command.

Weather response handling remains unchanged. Rejected weather requests now retain
only a bounded query-shape summary for administrator diagnostics: type, lengths,
comma/parameter counts, empty/two-letter-country flags and a coordinate-shape
hint. No postal code, coordinate value, parameter name or query string is retained.
This is intended to locate the intermittent rejection before changing location
semantics or the thermostat's stored country/units.

## Owner-unit activation and observation

The owner approved activation of 0.6.5 and one Core restart. All 33 active files
read back exactly. Core health checks found four registered entities and no scoped
errors. This is a deployment result, separate from the synthetic validations above.

One original-Eco-off request was queued with an actual active subscription. Its
server stream write completed, but neither requested field was freshly reported;
the intent expired. Restoration remains unverified. The old cached false value
and a physical Eco label cannot resolve manual versus automatic Eco. No automatic
retry or new Eco-on command was sent. The owner subsequently returned the charged
display to its completely unwired base; physical state confirmation is pending.
Whether base absence affected the previous command is only a hypothesis.

The current runtime served one native weather request without rejection. This is
one successful observation, not proof that historical query failures are resolved.
Further read-only schedule review found optional point provenance in addition to
entry classification. These fields must be preserved or explicitly accounted for
before a native week can become a replacement/restore baseline.
