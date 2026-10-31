# Fresh filesystem snapshot: integration boundary

The combined ARM RAM matrix passed all 68 cases. The next hardware milestone
is a fresh filesystem snapshot for commissioning, not another generic raw NAND
acquisition. This note records static findings in the already pinned NestDFU
Linux source; it is not a prepared executable profile or a hardware result.
The companion source inventory pins the reviewed file bytes.

## Mount path

`drivers/mtd/mtdsuper.c:mount_mtd` accepts `mtd:NAME` and obtains the MTD object
by name. JFFS2 calls this path directly. Therefore a snapshot kernel can retain
`CONFIG_BLOCK=n`, no MTD character interface and no mtdblock interface. It needs
MTD partition registration and JFFS2, which the existing diagnostic profiles
explicitly prohibit; their verifiers must not be weakened in place.

`mtdpart.c` inherits child capability flags from the master after applying the
partition mask. The existing protected master, NAND_ROM setup, skipped BBT scan,
protected-status check and denied mutation callbacks can remain in a separate
read-only profile. These controls must be checked after final configuration and
in source, rather than trusting a read-only mount argument alone.

`fs/jffs2/fs.c` requires JFFS2 NAND writebuffer support even for a read-only NAND
mount. Its garbage-collection thread starts only for a writable mount.
`nodemgmt.c` checks read-only state before physical obsolete-node marking.
A snapshot supervisor must request read-only/noatime/nodev/nosuid/noexec mounts,
verify the resulting mount state, keep hardware WP asserted and never remount.
No firmware program, startup service or executable from the mounted tree runs.

Extended attributes must be visible: enable the relevant JFFS2 xattr support
and report/refuse unsupported metadata instead of hiding it through kernel
configuration. Required compression support must be retained from reviewed
source/configuration. Mounting behavior remains unmeasured.

## Identity and data handling

The static board table corroborates named root0, root1 and user-config regions.
A partition table supplied by our custom kernel describes that kernel's view;
it does not establish which root the native bootloader selected. Likewise,
the custom RAM kernel's command line cannot prove the preceding native root.
A fresh native selection observation must be bound to the commissioning plan;
the old intake's primary observation alone is insufficient.

Export only the reviewed target files and required ancestor metadata into a
fresh owner-only host directory. Record absent new-file targets explicitly,
keep firmware/settings/identifiers and their digests private, and do not follow
symlinks or execute mounted content. Fresh settings must feed the byte-preserving
editor; the capture-derived review remains an offline draft.

Before an eventual writer can run, integrate durable host export/readback and
a receipt tied to that exact snapshot and plan. The current transaction API's
caller boolean is not that protocol. Interrupted-install journal inspection and
restoration also remain to be implemented. The normal JFFS2 adapter, kernel and
supervisor must be reviewed together before any persistent commissioning.

## Implementation follow-up

The original read-only reader, host custody receipt and a distinct RAM profile
are now implemented under `firmware/file_snapshot/` and
`provisioning/file_backup.py`. See the profile README for exact bounds and
execution gates. The earlier static-only statements above describe the initial
review; no snapshot has yet executed on the thermostat.

The first offline build exposed a compiler-generated memset dependency, fixed
with an original freestanding byte loop and an independent ARM-link regression.
The second reached kernel link and exposed the already-known forced OMAP RTC
selection; the profile now reuses the previously reviewed clock-disable patch.
Failed build trees/logs remain separate and unexecuted. JFFS2 ACL selection emits
a legacy Kconfig dependency warning with BLOCK disabled; actual ACL and xattr
objects are built, and required configuration is independently checked. The
unused partition-parser table also emits a warning after parser bypass; no
command-line partition override is invoked. Historical upstream warnings remain.

The new capture scope is the custom kernel's root0 view, not an active-root
measurement. Fresh native USB partition selection still requires an owner
terminal read because this account lacks diagnostic-disk read access and no
noninteractive sudo grant is available. Diagnostic-disk writes were not enabled.

Current unexecuted build is `build/file-snapshot-20261031-v4`. The generated
checker passes after initial compilation and an isolated rebuild with fixed
KBUILD_BUILD_VERSION=1: all six artifacts and staged host recipe digests match.
The exact original-only initramfs is 7096 bytes; kernel decompression is 2881632
bytes. Make check passes and the full host suite reports 623 passed, five
unchanged optional skips. No proprietary code was executed on the host.

The owner subsequently provided a sanitized fresh native plist read reporting
primary and firmware 5.9.4-5. A private source-attributed observation preserves
that result. The custom snapshot still labels its own root0 view explicitly;
no filesystem writer or native application startup has been tested. No loader
is armed and a new owner-timed restart is required for this snapshot.
