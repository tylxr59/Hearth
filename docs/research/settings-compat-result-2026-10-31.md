# Storage correction comparison observed on target

The owner supervised one RAM boot of the fresh GNU-linked comparison profile
using source `109c652`. The loader transferred all three files and exited zero;
the collector independently accepted the complete 29-case matrix and exited zero.
The private result contains 19096 bytes/68 rows, including 24 I/O cases, five
allocation/alias cases, both helper-binding records and two zero child statuses.
Every case's object-tail canary passed. Original report, creation manifest and a
separate attempt-5.json record remain private and immutable.

The original native writer again reproduced its measured faults. With the original
correction preloaded in the separate candidate process:

- Both failed/short entry writes returned failure, preserved the complete old
  file and retried successfully, instead of silently replacing it with missing
  values or invalid XML.
- A directory-sync failure retained retry eligibility. The already-renamed file
  contained new values; this is retry behavior, not proof of rollback or flash
  durability.
- All twelve I/O outcomes and retry results matched the reviewed contract.
  Four controlled allocation/hash failures preserved previous state and succeeded
  on retry, with no old-value free on failure. The aliased-value case also passed.
- Both global interposition checks passed. The original emitted two synthetic
  secret patterns; the candidate emitted zero and counted 50 scoped suppressions.
  Each variant emitted exactly one expected multi-argument/float passthrough log.

Streaming matchers inspected every stderr byte. The bounded caches explicitly
discarded 9016 original and 420951 candidate diagnostic bytes; cached windows and
counts remain private. No real settings, credentials, native application or flash
filesystem were used. Children ran as UID/GID 65534 on synthetic RAM files.

The successful candidate used the historical GNU linker, retaining eager binding,
RELRO, exports and dynamic thread-local storage. Four earlier LLD-linked attempts
failed during startup and remain preserved in the
[attempt history](settings-compat-attempt-2026-10-31.md). Multiple ELF layout/dynamic
table details differ; this success does not identify the precise earlier crashing
instruction or establish a general LLD incompatibility. Do not reuse the failed
profiles or assume an ordinary default LLD build is now validated.

After command exit the owner reported completing the manual restart. USB briefly
disappeared, then normal Nest USB was independently observed. No automatic retry,
installation, real settings change or firmware restoration occurred.

This validates the exact original correction against the native base settings
library in this synthetic matrix. It does not validate the full nlclient/osm
startup, derived settings classes/callbacks, two-key credential transactions,
other logs, permissions/serialized-value limits, power interruption, real storage,
combined TLS/time/commissioning, restoration or HVAC behavior. Next work is native
integration/protocol and an exact same-unit recovery plan, before persistent work.
