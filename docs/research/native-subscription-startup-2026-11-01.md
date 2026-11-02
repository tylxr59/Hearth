# Native subscription startup review

The owner unit reconnects with basic telemetry but has no reported home/eco or
validated weekly schedule baseline. Its unwired base reports no heating/cooling
capability, so the climate selector correctly offers only Off. An initial
`bucket_shape` rejection precedes successful later PUT/subscription traffic.

Read-only Ghidra review traced the private native JSON builder and constructor
through metadata string references. The builder explicitly supports both value
objects and `filters` arrays. Hearth's subscription schema rejected the latter
as an unexpected bucket member. The native production path confirms this is a
possible protocol shape; it does not prove the actual rejected owner frame used
it. Private exports remain below `private/native-startup-shape-review-20261101`
and `private/native-subscription-filter-review-20261101`. No firmware was run.

Version0.5.2 accepts only an empty subscription filters array, whose selection
semantics introduce no additional filtering. It does not permit nonempty filter
expressions, add account access or fabricate home/schedule data. Known bucket
ownership, numeric metadata, native value validation and atomicity remain.

Rejected bucket diagnostics retain only a fixed reason, request kind, JSON type
names, types of fixed known protocol members, unknown-member count and filter
item-type/count summary. Unknown names, object identifiers, session strings and
all values are excluded. The bounded observation is manager-only and copied
before exposure. It can distinguish a different startup mismatch without raw
payload collection. Additional fixed diagnostics distinguish a native schedule
bucket from a validated/fresh week, and an observed home/eco field from a valid
home reference. They expose bucket kinds and booleans, not identifiers or values. Successful parsing records the empty-filter shape separately.

The pinned NLE reference also completes local pairing by sending a user bucket
before a structure bucket, and assigns a home reference for an enrolled device.
Hearth has not enabled that bootstrap. Any later implementation must bind local
identities to the authenticated enrollment, scope ownership and review native
side effects before delivery. This update sends no bootstrap or control values.

Real HA tests additionally withdraw heating/cooling capability flags and restore
them, confirming that the mode selector follows the reported supported modes.
No physical HVAC connection is needed for that protocol/UI test. Actual equipment
capability detection and switching remain separate supervised work.
