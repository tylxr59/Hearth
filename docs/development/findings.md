# Findings

Established facts about the Gen 2 Nest (Display-2.6, 5.9.4-5), its firmware and
its protocol that still shape the code. Each section links the dated notes in
[history/research](history/research/) that hold the full evidence.
Unless stated otherwise, every fact here was measured on **one unit**.

## USB and boot

- Normal mode enumerates as USB `2464:0002` and exposes a small read-only
  diagnostic disk containing `Technical Info.plist` (model, firmware, serial).
- Holding the ring for 10 s, releasing, then pressing once restarts the unit.
  While it restarts, the OMAP ROM appears briefly as `0451:d00e`. A loader that
  is already waiting can upload x-load, U-Boot and a kernel into RAM.
- Hearth's RAM kernels report back over a USB gadget serial interface
  (`0525:a4a7`).
- The ROM stalls at the length word unless the host loader is **paced**. The
  measured loader and udev rule are scoped to physical port **1-1**.
- Never pick a generation from USB IDs alone. Gen 1 needs its own profile.

[usb-handshake](history/research/usb-handshake-2026-10-30.md) ·
[device-intake](history/research/device-intake-2026-10-30.md) ·
[acquisition-review](history/research/acquisition-review-2026-10-30.md)

- A normal Linux warm reset from a protected RAM image exposes OMAP USB ROM
  again without a ring press: ROM appears after about 0.6 s, disconnects at
  about 4.2 s, and native USB returns at about 11.5 s. A waiting successor
  loader can transfer a new image in that window.
- The pinned kernel marks rootfs `MS_NOUSER`, so RAM images cannot bind-mount
  rootfs paths into child chroots. Use RAM hardlinks and renames instead.

[warm-restart result](history/research/rom-warm-restart-success-2026-11-03.md) ·
[backup-install-handoff-result](history/research/backup-install-handoff-result-2026-11-03.md)

## NAND

- 256 MiB NAND with 2048 × 128 KiB erase blocks, 2 KiB pages and 64-byte OOB
  (262,144 page records).
- Read-only kernels keep hardware write-protect asserted, BBT scanning off and
  write callbacks denied.
- Two raw passes over the whole chip can differ byte-for-byte, but their
  BCH-corrected data views match. Four chunks per pass stay "unclassified"
  (identical in both passes, zero uncorrectable). The archive keeps them
  unchanged and records the limitation.
- OOB bytes 0 and 1 read `FF` on every block in both passes. That says nothing
  about other OOB bytes, which hold valid metadata.
- Nothing can write a whole-chip image back yet. The archive is a record, not a
  tested restore.

[nand-geometry](history/research/nand-geometry-2026-10-30.md) ·
[nand-capture](history/research/nand-capture-2026-10-30.md) ·
[nand-ecc-result](history/research/nand-ecc-result-2026-10-31.md) ·
[recovery-layout](history/research/recovery-layout-2026-10-31.md)

## Filesystem (JFFS2)

- System and configuration files live on JFFS2. The writers target fixed files
  on the root0 filesystem.
- **The native kernel cannot read LZO-compressed nodes** (type `0x07`). Files
  written with LZO-priority compression pass byte readback but break native
  startup (steady home icon, blinking green LED). All Hearth writes therefore
  use NONE/ZERO encoding, and the encoding audit refuses anything else.
- The native kernel can **re-compress archived originals** (mixed NONE/ZLIB).
  The strict final-encoding audit then refuses even when every active file is
  correct. Handling natively recompressed archive originals is still open
  work.
- Byte-equal readback isn't enough: a successful write has to be readable by
  the **native** kernel.
- **Flash space is tight.** Stock root0 has about 22 MB free. Factory files
  are **ZLIB-compressed** (stock `nlclient`: 2.92 MB on flash for 5.12 MB of
  data). Hearth writes NONE only, so each restored original and rollback
  archive takes its full uncompressed size. On the measured unit, past
  installs and stock returns have reduced root0 to about 13.2 MB free.
- **`f_bavail` is already net of the kernel's write reserve**
  (`resv_blocks_write`: 2 + 2% of the partition, 10 × 128 KiB on root0).
  Measured NONE-node overhead is 1.71% (about 70 bytes per 4 KiB). The writer's
  margins above the file bytes are sized from that: shared install 1.25 MiB,
  restore 1 MiB, with install ≥ restore + 256 KiB so an install always leaves
  room for its own undo. The old 4 MiB restore margin would have blocked undo on
  this unit after any successful install.
- Shared-original rollback reuses an exact restored archive's inodes instead of
  copying. The combined no-commit capacity preflight checks both phases before
  either writes, and on the measured unit both phases fit in one RAM boot
  (13,201,408 bytes free against 12,461,733 required).
- Original-file custody can also be reconstructed offline from the checked full
  NAND archive. These host-encoded snapshots carry separate archive provenance;
  their free-space statistics are unknown. Device-side original-byte and live
  resource checks remain mandatory. A preserved data-view parser exercise
  reconstructed all fixed records and 126 library/executable files.
- Archive-only extraction conservatively refuses an inode containing a
  checksum-invalid fragment, even when valid duplicates exist (seen for
  `settings.config`). Keep the refusal. The protected live reader is the
  fallback source of originals.
- A settings file can re-serialise differently while holding identical
  values, which invalidates an exact-original snapshot. Never loosen the byte
  comparison. Take a fresh snapshot instead.

[capacity-preflight-result](history/research/capacity-preflight-result-2026-11-03.md)
·
[combined-install-success](history/research/combined-install-success-2026-11-03.md)
·
[handoff-extraction-refusal](history/research/handoff-extraction-refusal-2026-11-03.md)
· [compression-recovery](history/research/compression-recovery-2026-10-31.md) ·
[startup-stall](history/research/startup-stall-2026-10-31.md) ·
[file-install-result](history/research/file-install-result-2026-10-31.md) ·
[file-restore-result](history/research/file-restore-result-2026-10-31.md)

## Native software

- `nlclient` is the main application and keeps the native control loop. `osm`
  is the updater. Neither is ever invoked by Hearth tooling.
- `nlSettings` (in `libnlappcore.so`) marks settings dirty in memory. The
  setter doesn't write the file itself.
- Native component logs can contain credentials, and a queued uploader can send
  them out. Hearth's settings set `uploadlogs` to 0, but other log paths are
  still unreviewed.
- The client accepts an `X-nl-set-client-credentials` response header that
  rotates its credential and logs it. Hearth never emits it.
- TLS uses native curl/OpenSSL. The **stock verify callback clears failed
  certificate checks and returns success**, so in effect the stock client
  doesn't verify servers. Hearth's guarded recipe changes one instruction so
  the call becomes `SSL_CTX_set_verify(ctx, SSL_VERIFY_PEER, NULL)`, which means
  OpenSSL's default verification is enforced against HA's local CA/CRL. It
  validates the ELF relocation first. An isolated 18-case RAM test passed.
- Connectivity checks (client probe and ConnMan) are redirected to HA's
  plain-HTTP `/api/h/204`. Time comes from the configured NTP server in both the
  primary config and ConnMan's fallback.

[native-interface](history/research/native-interface-2026-10-30.md) ·
[native-storage](history/research/native-storage-2026-10-30.md) ·
[native-bootstrap](history/research/native-bootstrap-2026-10-30.md) ·
[native-tls](history/research/native-tls-2026-10-30.md) ·
[tls-probe-result](history/research/tls-probe-result-2026-10-30.md)

## Protocol

- The flow runs entry, then transport URLs, then PUT and chunked long-poll
  subscribe over buckets (`object_key`, `value`, revision, timestamp). Replies
  put revision and timestamp **before** the key.
- Hold a quiet subscription open when there's nothing to send. Closing it over
  stale metadata breaks delivery.
- Subscribe requests may carry `filters` arrays as well as value objects.
- Local home association needs a user-name bucket **before** the home bucket.
  Hearth only allows the home referenced by the device's own `structure_id`.
- Target changes also send the transient `target_change_pending=true`.
  The flag clearing does **not** confirm the temperature.
- Manual Eco is a boolean plus a seconds timestamp.
- Gen 2 schedule points carry classification and provenance fields, plus
  continuation records. Preserve them.
- The native weather fetcher can send the literal fallback token `ipv4`. Hearth
  answers it only from an explicitly configured postal code and country.
- **Acknowledged doesn't mean applied.** Setpoint changes reached the dial
  physically while no native value echo arrived in the command window. Keep
  "queued", "written to stream", "acknowledged" and "reported" as separate
  states.

[native-protocol](history/research/native-protocol-2026-10-30.md) ·
[native-delivery](history/research/native-delivery-2026-11-02.md) ·
[native-subscription-startup](history/research/native-subscription-startup-2026-11-01.md)
·
[native-local-user-pairing](history/research/native-local-user-pairing-2026-11-01.md)
·
[native-eco-schedule-weather](history/research/native-eco-schedule-weather-2026-11-01.md)
· [native-compatibility](history/research/native-compatibility-2026-11-02.md)

## Equipment

- The owner's base reports heating only. Cooling, fan and emergency heat are
  false. Never infer support from a missing flag or from a broad enrollment
  allowance.
- No intentional heating call has been made. Setpoint tests kept the room at
  least 3 °C above the target.

[native-compatibility](history/research/native-compatibility-2026-11-02.md)

## Process lessons

- Every RAM/flash profile is **single-use**. Executed profiles are evidence and
  never run again.
- No automatic retries. An interrupted write needs its report reviewed before
  any restart.
- Keep simulation, reference-code agreement and hardware measurement as
  separate claims everywhere: docs, release notes and commit messages.
