# Bounded native file transaction (not an executable installer yet)

Original MIT C code for the nine-file Gen 2 commissioning plan. There is no CLI,
USB command handler, filesystem mount, NAND operation, device launcher or automatic
apply command. The engine is host-checked, cross-compiled and measured in the
32-case ARM RAM transaction matrix. Actual JFFS2 and hardware integration remain
pending. Do not call it with device filesystem descriptors or install the private
review payload yet.

The core requires explicit durable-host-backup confirmation from its future
supervisor. The current API receives that confirmation as a caller-owned boolean;
a real receipt/export protocol is not implemented or verified by this module.
All read-only preflight checks finish before its first journal/staging mutation.
It stages private original copies and checked replacement files, syncs files and
parent directories, records activation intent before each rename, verifies all
results and records completion. Originals/journal stay in an owner-only recovery
directory outside library/startup search paths. The native endpoint goes last.

| Ordered target | Purpose |
|---|---|
| Native web-service library | Previously measured default TLS verification callback |
| Owner CA bundle | Local backend trust |
| Owner CRL bundle | Native revocation validation |
| Native NTP config | Owner-selected NIST time service |
| Original storage shim | Settings failure/log/privacy correction |
| Original exec wrapper | Load shim only when executing nlclient |
| Native startup script | Change only start-as argument; preserve PID/stop identity |
| User settings | Unique assigned credentials, preserving other settings |
| Client config | Local endpoint and reviewed log-uploader disabling |

The adapter accepts only these canonical paths, ordered by fixed target IDs.
It walks directories using openat/O_DIRECTORY/O_NOFOLLOW, checks owners and
writable directory bits, and requires regular single-link files with exact
original bytes/modes/owner/group. Nonempty extended attributes cause refusal. The normal adapter also refuses an
unsupported attribute query; a future JFFS2 kernel must expose that metadata.
The RAM-only diagnostic permits EOPNOTSUPP on its memory filesystem.
It refuses reserved staging/rollback names,
existing recovery directories and unexpected new-file destinations. Fresh files
start at 0600; final modes are explicit. It checks metadata before opening content
so a FIFO or special node does not trigger blocking/device reads. Partial writes
are handled and successful writes are synced and read back. It uses ARM-specific
file flags and stat64 layout reviewed against pinned kernel headers.

Activation errors include the uncertain current file in rollback, since rename
may have succeeded before directory sync failed. Rollback runs in reverse order
and continues even if journaling fails. It refuses to overwrite an unexpected
third-party modification. Incomplete restoration is reported separately and
retains staging evidence. Successful rollback removes only staging files created
by that invocation; private originals remain. Cleanup errors are separate from
commit state. Callers must inspect every result flag.

The normal ARM adapter requires JFFS2 roots. The separate HEARTH_RAM_LAB build
accepts only ramfs/tmpfs; HEARTH_HOST_LAB uses caller-created host fixtures. These
lab modes cannot be combined. A lab binary must never become a device writer.
The [RAM profile](../file_install_probe/README.md) additionally has no flash support.

This is not multi-file or cross-filesystem power-loss atomicity. Exact-plan
journal inspection and restoration are implemented and host-tested, as detailed
below. Actual after-reboot device recovery, native application shutdown/health,
writer-bound backup receipts and kernel integration, and actual JFFS2
write/restore remain unimplemented or unmeasured. Hardware use requires those pieces,
a concrete reviewed capsule and advance owner notification under docs/hardware.md.
No whole-firmware recovery or HVAC claim follows from host filesystem tests.

The separate [snapshot reader](../file_snapshot/README.md) now shares the fixed
target allowlist without linking the mutation adapter. Its production build
requires read-only JFFS2; host sanitizer fixtures and freestanding ARM linking
pass. Host backup custody is implemented separately, but target receipt/plan
enforcement and interrupted-install replay remain pending.

## Interrupted-install restoration

`hearth_posix_restore_files` opens the existing owner-only recovery directory,
validates the exact journal length/header/phase/mask/count/plan ID, and checks
every target before its first mutation. Current files must match the exact
original or replacement bytes and metadata. Missing existing targets are
accepted only for durable committing/restoring intent covering that target,
with an exact private original backup. Unexpected state is preserved unchanged.

A fresh process reconstructs staging provenance only from exact known contents
or bounded prefixes with expected ownership/modes. Verified partial restore
temporaries can be retried; replacement staging stays intact if restoration
fails. All targets are conservatively inspected/restored in reverse order,
including an operation whose newer journal update may have been interrupted.
Already-restored originals are idempotent. The private originals remain.

An unknown `journal.new` is retained. It can prevent new journal writes while
file restoration proceeds; the caller must check **all** result fields, including
journal and cleanup errors, rather than treating `error == 0` as complete success.
This module does not mount filesystems, locate a unit, select a plan, verify a
host receipt, launch recovery after reboot or run as a device command.

Twenty-four host sanitizer scenarios include abrupt child-process exit across
transaction phases, partial temporaries, unknown late target changes, invalid
journals/metadata, absence with/without intent, and failed-then-retried restore.
These simulate process interruption, not actual power loss. A separate fresh
91-case RAM profile is prepared: 36 settings, 32 transaction and 23 recovery
cases (the positive extended-attribute fixture remains host-only). No new ARM
recovery measurement or persistent JFFS2 restoration is claimed yet.
