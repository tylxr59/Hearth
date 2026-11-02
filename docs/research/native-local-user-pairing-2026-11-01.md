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
