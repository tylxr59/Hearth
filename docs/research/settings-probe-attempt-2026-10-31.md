# Settings RAM first attempt and bounded reporting correction

The owner returned for testing after the offline preparation. Source `d6823ed`
was used for one supervised RAM upload of the original settings diagnostic.
Native USB preflight passed, the reviewed manual restart exposed ROM mode and
all three files uploaded. The collector then exited 1 on invalid JSON. There was
no automatic retry or persistent installation. The owner restarted with the
command exited, confirmed the home icon, and normal Nest USB was independently
observed afterward.

The original private 0600 result is preserved: 15,423 bytes, five complete case
rows, 75 hex diagnostic rows, a partial result/process line and failed completion.
The child wait status recovered from its structured suffix is 9 (SIGKILL).
This is not a complete matrix. The private creation manifest/result remain
unchanged, with a separate attempt record; no raw logs or private hashes are
published.

The supervisor initially appended stdout and encoded stderr to one 16 KiB
report cache. Native settings/XML diagnostics exhausted its reserved margin,
triggering the overflow stop. A partial stdout row followed by process metadata
made the resulting line invalid JSON. This was a reporting design defect; it
does not establish that the later native fault cases failed.

The complete normal row reports both updated values after reload and no redundant
second write. File-open/header-write errors report failure and successful retry.
The complete entry-error row reports success despite only one updated value and
no retry; the entry-short-write row likewise reports success with failed readback
and no retry. These bounded partial observations support the earlier static entry
failure finding. They do not cover the remaining cases, directory-sync behavior,
real settings, flash durability, power loss or recovery.

## Corrected reporting

The supervisor now has independent caches: 8 KiB for child stdout and 2 KiB raw
stderr. It continues draining stderr after its diagnostic budget and reports the
number of discarded bytes explicitly. A separate 1 MiB excess-diagnostic limit
and existing process deadline still stop runaway output. The final report is
assembled after collection, so diagnostic insertion cannot split stdout rows.
Static capacity checks reserve room for hex expansion and all framing/status rows.
No native writer/logging code was changed or silenced.

The collector accepts one strictly bounded diagnostic-truncation record only;
it still requires all twelve ordered cases, successful normal write/readback,
observed one-shot injections, canaries, zero child status and true completion.
A full observation still does not mean the original writer is fixed.

Original shared cache code was exercised on the host under ASan/UBSan with
fragmented results and diagnostics many times larger than the old report budget.
All result bytes survived; overflow, negative lengths and excessive output were
rejected. ARM helpers cross-compiled without proprietary link inputs/execution.
The corrected private image and all seven artifacts reproduced in fresh outputs.
Kernel, bootstrap and original libraries are unchanged. A new owner-supervised
attempt, if performed, must use the fresh profile and be recorded separately.

Concurrent MQTT source work is unrelated and is not part of this RAM profile.
No settings correction, new device interface, installation or recovery claim is
introduced by the reporting fix.
