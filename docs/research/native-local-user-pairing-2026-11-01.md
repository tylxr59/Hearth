# Local user announcement and Gen2 schedule format

The owner unit reports device/shared telemetry but no home, eco or schedule
baseline. The0.5.2 observer saw no new bucket-shape rejection after the reported
restart; it also did not observe an empty-filter frame. This does not establish
filters as the cause of the missing data.

The pinned MIT NLE reference sends a user-name bucket before its home bucket to
complete local association. Read-only native review located the Gen2 user bucket
initializer, its name setter and the called global-name setter. The supported
field is `name`; its direct setter clears/copies an in-memory native string.
This local review does not prove the entire downstream setup flow has no
persistent side effects. Private exports remain below
`private/native-pairing-review-20261101`; no firmware code was executed.

## First explicit step in0.6

The administrator-only HA `begin_local_pairing` action requires explicit boolean
confirmation and a live authenticated enrolled device. It prepares a random local
user handle, bound to that exact credential generation, and saves/fsyncs/reads back
the private configuration before making it available to the transport. An existing
reported home reference requires migration review rather than a silent replacement.
Repeated explicit actions reuse the same handle. Device credential rotation makes
old configuration ineligible; no other device receives its user handle.

Only the constant user name `Hearth` is supplied. The authenticated native GET or
subscription delivers it with metadata before object key and user configuration
before device data. Incoming user values are ignored; metadata is validated before
any device-state mutation. A metadata acknowledgement is tracked separately from
configuration/offered status and is not proof of complete native pairing.

Configured identity is persisted separately in private `local-pairing.json`, not
in the reported-state cache. A configured name can be reoffered on HA reload or
GET, while pending temperature/mode/fan/schedule intents still cannot replay. A
missing acknowledgement alone does not create a continuous subscription push loop.
Unknown metadata/data is never echoed. Diagnostics expose only the three fixed
configured/offered/metadata-acknowledged booleans.

This step creates no home object, eco setting, schedule or equipment capability.
Activation with no local pairing file sends no announcement. Native user/setup
state can change after the explicit administrator action, so perform the first
measurement on the completely unwired base. Actual user acceptance and whether
additional native baselines become available require supervised observation.

## Schedule compatibility

The Gen2 schedule bucket registers `manual_schedule` and also has a special
whole-schedule handler recognizing `days`. The canonical HA weekly schema is
unchanged. The receiver now accepts either a bare validated week or the reviewed
wrapper and preserves the actually observed format on replacement. Mixed/partial
formats still refuse, and a fresh complete original plus private backup and
revision checks remain mandatory. No owner schedule has been changed.

Host tests and the pinned real-HA sandbox cover enrollment isolation, malformed
metadata atomicity, private custody, administrator/confirmation refusal, existing
home refusal, reannouncement after reload, no control-intent replay, and wrapped
schedule service/readback/backup behavior. These are preparation results, not
a claim of full pairing, physical HVAC or whole-firmware recovery.

## Owner-unit observation

After 0.6 activation, the owner performed the confirmed administrator action.
The immediate action response showed configuration saved but not yet offered.
The subsequent read-only manager observation independently showed configured,
offered and metadata-acknowledged all true, continued availability and no receiver
rejections. Only device/shared observed buckets remained: no home reference, eco
field or schedule baseline. This is metadata acceptance, not complete pairing.
No control command or physical HVAC operation was performed.

The next home association is a separate state change. Native structure identity
assignment reaches the native settings writer; it must not be described as
RAM-only merely because the server supplies it. NLE supplies a structure after
the user, but the Gen2 initializer does not register its name/devices fields.
Review the identity callback and user-link processing before a minimal explicit
home-association action; omit away, eco, safety, equipment and schedule defaults.

## Explicit home association (0.6.1 preparation)

The next separate administrator action, `associate_local_home`, requires explicit
confirmation, a live authenticated connection and the current local-user metadata
acknowledgement. It refuses a conflicting reported home and a changed enrollment
or stored user identity. It preserves the first pre-association configuration in
private `local-pairing-before-home.json`, then atomically saves/reads back an
optional home record in `local-pairing.json`. Both use the same owner-only,
no-symlink, single-link custody checks. The original backup is not overwritten.

The outgoing structure contains only `user_id`, referencing the already configured
local user, plus a random per-device structure identity in its object key. Native
review finds that structure key assignment saves `structure_id`; the registered
`user_id` field constructs the user-bucket reference. Structure end-update calls
the native settings writer. The follow-up read-only exports are private under
`private/native-home-association-review-20261101`. No target binary was executed.
NLE's home name/device list is omitted: those fields were not found in this Gen2
initializer. No away, eco, safety, equipment or schedule default is supplied.

Configuration is sent before device updates, only on authenticated GET/subscription,
never piggybacked on PUT. An unanswered offer does not create an endless push loop.
Later mutable structure revisions remain authoritative; the initial configuration
revision does not replace them on every subscription. A reported foreign home
suppresses the configured home announcement. Home configuration, metadata
acknowledgement, actual device-reference observation and conflict are separate
value-free diagnostics. Configuration never manufactures reported baselines.

Activation alone does not add a home to an existing user-only configuration. The
explicit action can cause persistent native setup writes and is not a firmware
flash or a RAM-only change. A native unpair/restore sequence remains unverified;
the saved HA configuration is not a whole-device recovery image. Initial testing
requires the completely unwired base and owner confirmation before the action.
A code rollback to 0.6.0 cannot read the extended home record; preserve the original
configuration backup with the old code, and review restoration before using it.

Host and real-HA sandbox coverage includes enrollment isolation, malformed metadata
atomicity, distinct configuration/reporting, identity ordering, no default control
values, private backup/reload, administrator/confirmation checks, conflicting-home
refusal and unsafe-backup refusal. Actual home acceptance and subsequent native
eco/schedule reports remain unmeasured until the owner performs the action.

## Direct structure report correction (0.6.2 preparation)

After the owner confirmed the home action, the read-only observer saw the home
announcement offered and a structure bucket received, alongside continuing
telemetry. The 0.6.1 diagnostics still showed no exact initial-metadata
acknowledgement or device-bucket home reference. A scoped log check also found a
cache warning, while the last durable cache still contained only device/shared.
These observations do not establish complete pairing or persistent setup readback.

The pinned NLE `utils/structure_assignment.py`, now included in the provenance
inventory, explicitly injects a missing device `structure_id` on the server. It
is not evidence that stock Gen2 uploads that field. Requiring it as the only
reported home identity was a Hearth receiver/cache assumption. See the
[pinned upstream helper](https://github.com/codykociemba/NoLongerEvil-SelfHosted/blob/bca8781012639c1cefc4a08c103fc892158fb630/src/nolongerevil/utils/structure_assignment.py).

The correction records the canonical structure key actually uploaded within the
already authorized device scope. That identity can establish the reported home
without inventing a device field. Unknown structure values and user identifiers
remain excluded from the cache; an identity-only record with empty allowed values
is valid. A device reference, when present, must agree with the cached structure
key. Original caches with only the device reference remain readable. Restoring
this report does not restore connection freshness or pending commands. Old code
may refuse the extended cache; retain its pre-update copy with rollback code.

A home metadata acknowledgement can match the current accepted structure revision
instead of only the initial configuration revision. An intervening native PUT
advances the ordinary bucket revision/timestamp. Matching that response is tracked
only after an offer and when an actual nonempty structure report exists. The
separate `device_reference_observed` flag still means a real device field;
`structure_identity_observed` reports the direct structure path. Both remain
separate from home configuration, eco/schedule values and physical HVAC proof.

Host and real-HA tests reproduce two structure PUTs, acknowledgement of their
current revision, cache save/reload without `device.structure_id`, identity conflict
refusal and absence of invented fields/control replay. Native acceptance under
0.6.2 still requires observing the actual unit after the HA-only update. The
already confirmed home identity is reused; no new association action is required.

## 0.6.2 owner-unit result

The owner approved activation and one HA Core restart. Exact active source
readback passed; Core restart returned zero. After the owner woke the unwired
Nest, both local-user and home metadata acknowledgements became true. A direct
structure identity and native eco field were observed. A subsequent private cache
readback validated the structure key and both `manual_eco_all` and
`manual_eco_timestamp` fields. No device home-reference field was invented.
The week remains absent. Current weather queries are rejected; this is still an
open issue rather than a successful current weather measurement.

The owner attempted Eco through HA; the backend queued and offered that request
to a held subscription, but it expired without confirmation. The latest saved
preset remained None, with no fresh post-command physical state verified yet.
Do not call this a confirmed Eco/restore cycle or retry it automatically. The
original baseline is private; the owner was asked to wake the display once and
report its physical state so a delayed application can be detected.

Further static review identifies a local changed-schedule flag around the native
weekly getter, not an unconditional initial-week upload. The corresponding
cancellation path explicitly names the changed-temperature-schedule-to-cloud state.
The native manual-eco setter marks both eco fields for reporting. These findings
help plan a physical-UI/schedule measurement; they do not authorize supplying a
fabricated week, equipment flags or default eco values. Private exports are under
`private/native-feature-direction-review-20261101` and
`private/native-eco-field-review-20261101/v2`.

Pinned NLE keeps a held subscription open for a short batch interval after a push;
Hearth currently closes it immediately after the first held update. This is a
concrete timing difference to investigate, not a proven cause of the failed Eco
attempt. A quiet battery-powered unit and an offered command without fresh native
feedback are insufficient to establish whether it rejected or delayed the change.

## Late Eco application and 0.6.3 correction

The owner subsequently restarted the native display and saw Eco on the physical
unit. The earlier expired request therefore applied late; expiry was not device
cancellation or proof that the old preset remained in effect. Restoration is
still pending. A requested HA `none` action sent no command because the handler
looked only at its stale None report. The physical Stop Eco path was inaccessible
behind the wiring screen. The base remains completely unwired; no popup or native
wiring/HVAC checks were disabled.

Fresh diagnostics also observed a rejected schedule PUT with an additional
outer member and repeated revision/timestamp errors. Static builder review shows
that native schedule replacements can carry `op: OVERWRITE`. 0.6.3 accepts that
operation only on owned schedule PUTs. It replaces fingerprints and the reported
snapshot rather than merging with the previous week's shape. Unknown/partial
native schedule content may be observed, but cannot enter the validated schedule
cache or authorize schedule controls. Unsupported operations and subscription
operations remain refused before mutation. No received schedule is sent back as
a command merely because it was received.

The pinned reference treats `base_object_revision` as informational, rather than
as CAS. Only the integer -1 unknown-base sentinel is additionally accepted on PUT;
negative conditional revisions, object revisions, timestamps and subscription
metadata remain refused. A finite diagnostic now names the failing metadata field,
its type/sign class and bucket kind, without retaining identifiers or numeric
values. This does not prove which field caused every owner-unit revision error;
remaining failures must be measured rather than bypassed. Schedule schema/type
summaries similarly omit names, point times and temperatures.

The HA handler now sends an explicit Eco-off request for `none` even when its
reported preset is already None. Clearing emergency heat retains its fresh-mode
requirement. A confirmed original-value restore remains required on the unit;
host tests are not that measurement. The staged update has not been activated.

A separately prepared private manager script can queue exactly the saved original
Eco-off value once, after an accepted fresh native subscription, live connection,
known home/eco baseline and no pending commands. It uses the existing authenticated
manager API, not Supervisor/Core privilege workarounds. Offline checking opens no
network. No restore command has yet been sent through it; the request remains
subject to normal native confirmation and will not retry automatically.
