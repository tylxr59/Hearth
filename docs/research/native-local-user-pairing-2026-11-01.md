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
