# Troubleshooting

## No readings

Check power and Wi-Fi, then the thermostat-facing local address/port. HA restarts
can leave an old client subscription; wake the ring once before considering a
normal reboot. Inspect Hearth's payload-free diagnostics for active subscriptions,
rejection categories and command status. Never publish a commissioning bundle,
raw logs, serial, setup code or credentials in an issue.

## Unknown configuration entity

A field must actually be reported and pass its codec. Missing fields remain
unknown. Equipment controls additionally require capabilities and explicit
confirmation. Rejected/CAS-stale uploads and cached values cannot confirm commands.

## Schedule refused

Read the current week/revision. Keep original continuation records. A pending,
unconfirmed or unproven cached baseline cannot authorize a replacement. Do not
edit a revision number to force acceptance or resubmit an old action repeatedly.

## USB refused

Check a data-capable cable, the actual diagnostic disk and scoped ROM/serial
permissions. Normal disk access remains read-only. Do not make a whole block
device writable to bypass a USB permission problem. Only perform the ring
sequence when the intended checked loader is waiting.

## Interrupted installation

Keep USB connected and preserve the private output directory. Follow
[recovery](recovery.md); do not assume a timeout means no bytes were written.
