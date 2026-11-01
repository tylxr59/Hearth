# Protected network-file snapshot

A fixed four-file read-only RAM reader for the owner's Gen2 development unit.
Only original syscall-only code executes on the unchanged protected snapshot
kernel. It mounts the named root0 JFFS2 view read-only, capturing no user settings
or logs. There is no installer or native application in the image.

The fixed file limits are: native client 6 MiB, ConnMan 1 MiB, its configuration
64 KiB and the installed client configuration 64 KiB. Other capture/installer
bounds remain unchanged. At most 7,471,232 report bytes are cached in RAM, without
a second large scratch array. Each file is reread through a 4 KiB comparison
buffer before transmission. This is bounded cached acquisition, not a writer.

The reader refuses unsafe parents, links, special files, unexpected ownership or
permissions, attributes, empty/oversized files, writable/non-JFFS2 mounts, changed
metadata and reread differences. Statfs free/available counts include reclaimable
dirty space after a kernel reserve and are not allocation guarantees. Root0 naming
does not establish native active-root selection; confirm the filtered native plist
separately before a supervised run.

Frames require a fresh 32-byte session, exact ordered records, bounded length,
CRC and completion footer. The first complete frame is preserved even on corruption;
incomplete evidence stays private without a backup receipt. Host custody reads
back/fsyncs all four complete originals and metadata before issuing a receipt.
This is not whole-firmware backup or proven restoration. Never reuse an executed
profile or an existing output path.

Offline preparation, using fresh private paths:

```sh
.venv/bin/python -m firmware.network_snapshot.profile package \
  --base build/PROVEN_READONLY_SNAPSHOT \
  --build build/FRESH_NETWORK_READER --output private/FRESH_PROFILE
.venv/bin/python -m firmware.network_snapshot.run private/FRESH_PROFILE
```

After owner readiness and advance RAM notification, launch through a PTY:

```sh
.venv/bin/python -m firmware.network_snapshot.run \
  private/FRESH_PROFILE private/FRESH_OUTPUT --execute-read-only-network-snapshot
```

No automatic boot retry. After exit use the reviewed full 10-second
hold/release/single-press sequence and confirm native startup/USB. Keep USB
connected and the unwired base detached. Images/data/hashes/results stay private.
`HEARTH_HOST_LAB` permits synthetic host-filesystem tests only; production packaging
never defines it or `HEARTH_RAM_LAB`.

The first supervised profile on 2026-11-01 captured four matching originals with
verified custody, followed by owner-confirmed home and observed native USB return.
See the dated research record. No persistent update or HVAC operation occurred.
