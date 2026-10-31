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

This is not multi-file or cross-filesystem power-loss atomicity. Journal replay,
after-reboot rollback, native application shutdown/health, exact current root
selection, fresh snapshot/export, write-bound kernel integration and actual JFFS2
write/restore remain unimplemented/unmeasured. Hardware use requires those pieces,
a concrete reviewed capsule and advance owner notification under docs/hardware.md.
No whole-firmware recovery or HVAC claim follows from host filesystem tests.

The separate [snapshot reader](../file_snapshot/README.md) now shares the fixed
target allowlist without linking the mutation adapter. Its production build
requires read-only JFFS2; host sanitizer fixtures and freestanding ARM linking
pass. Host backup custody is implemented separately, but target receipt/plan
enforcement and interrupted-install replay remain pending.
