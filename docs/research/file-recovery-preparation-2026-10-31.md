# Bounded interrupted-install recovery preparation

The read-only JFFS2 snapshot succeeded and the owner confirmed the home icon;
normal USB was independently observed. The seven current originals match the
reviewed capture-derived files, with both new target paths absent. Nothing has
been installed. This work adds the missing narrow restoration API before an
installer is integrated.

The original C adapter now validates an existing fixed journal and exact plan,
checks all current targets/backups and recognizes only known staging prefixes
before performing any restoration. It restores originals in reverse order,
retains evidence if restoration fails and refuses unknown concurrent state.
Missing existing names require durable committing/restoring intent and a
verified original backup. Unknown journal.new remains private and can cause
explicit journal errors even when original file restoration succeeds.

Twenty-four ASan/UBSan host scenarios exercise abrupt process exit, journal
validation, missing-name intent, metadata and content refusal, partial files,
idempotence and failed-then-retried restoration. The mutation adapter remains
separate from the snapshot reader. There is no installer CLI, writable mount,
device supervisor or host-receipt enforcement in this API. Host process exit is
not physical power-loss or after-reboot firmware recovery evidence.

The fresh RAM profile extends the prior measured component workload to 91 cases:
36 settings, 32 file transaction and 23 recovery cases. Recovery xattr fixture
14 requires an actual attribute-supporting host filesystem and is excluded from
RAM. Only the explicit RAM adapter tolerates EOPNOTSUPP for RAM attributes; the
production adapter still requires observable empty attributes and JFFS2.

The new helper uses only original C and retained native libc; all 32 imported
functions are present in the private native libc export table. No firmware ran
on the development host. The exact standalone settings shim, base libraries,
bootstrap and no-flash/no-physical-network kernel are unchanged. The supervisor
still captures three bounded child results; strict parsing additionally requires
every recovery case. Historical 68-case results require explicit legacy scope
and cannot satisfy the new contract.

Local preparation is private/file-recovery-ram-20261031/profile-v2, with separate
-v2-repro; helpers are build/file-recovery-ram-20261031/helpers-v1 and -v1-repro.
Preserve the superseded unexecuted profile-v1. No loader is armed. A new
owner-timed restart is required; never automatically retry or reuse an executed
profile/repro. Keep USB connected and the base detached. After command exit
confirm the home icon and normal USB independently.

Target-writer receipt/plan binding, actual bounded JFFS2 writer integration,
native application startup and live backend/MQTT/HA exchange remain pending.
Notify the owner before any persistent installation.

Preparation validation: make check and 653 host tests pass, five unchanged
optional integrations skipped. Two independent helper builds and packages
produce identical seven artifacts/full inventories: rootfs 11052100 and image
6035848 bytes. The explicit wrapper's dry run passes without opening a device.
No ARM recovery execution, JFFS2 write, firmware installation or hardware
restoration result is claimed.
