# Fixed-block normal-ECC read comparison

This original experiment compares the initialized NAND driver's normal ECC read
path with a preserved private reference. **Observed once:** both passes matched
the reference; see the [result](../../docs/research/nand-ecc-result-2026-10-31.md). It is
separate from the earlier raw exporter and controller-metadata profile. No writer,
erase/restore operation, native application, real settings interface or network is
included. All geometry hardware-WP, protected-status, NAND_ROM, denied mutation
callbacks and no-char/block/partition/UBI restrictions remain.

The fixed physical range is erase block 190: pages 12160 through 12223, 128 KiB
inside the source-corroborated root0 range. It includes the previously reviewed
parity-padding case at page 12209. This is not a stock runtime partition-map
observation or an automatically selected free block. The sysfs attribute permits
only one aligned 2112-byte record at a time within that range. It calls
`read_oob` with `MTD_OOB_PLACE`, requesting normal ECC-corrected data plus all
physical OOB bytes. Full successful and full `-EUCLEAN` reads are accepted; short
reads and errors reported by MTD stop acquisition. The published BCH4 callback
discards its decoder's failure/count result before returning zero, so that status
alone cannot establish corrected-data integrity. The independent host reference
comparison is mandatory; this experiment does not fix that driver behavior. The exact
measured bus/ECC/OOB layout is required at registration. No bad block is skipped.

Static userspace caches two complete passes before transmission. Retransmission
uses RAM only. A distinct CRC-framed format uses `HRTHCOR1` and absolute page
numbers, so the original raw-sample collector cannot mislabel these bytes. A
bounded `HRTHFAL1` failure frame carries only stage/pass/page/result and CRC, never
partial firmware data. Its typed diagnosis is preserved privately if acquisition
fails. Binary gadget tty processing remains disabled.

The host requires a fresh private output directory and an owner-only reference
file plus `reference.json`, whose digest and exact scope are checked before USB
execution. The local reference combines independently matching BCH-derived data
with OOB matching both raw captures; it is **not embedded in the RAM image or sent
to the device**. Success requires both received passes to match each other and
that reference exactly. Original payloads, hashes and provenance remain private.
Storage/transport failure cannot return success. No captured firmware executes
on the development host.

Build using the same pinned sources and validated heartbeat bootstrap:

```sh
.venv/bin/python -m firmware.nand_ecc_sample.stage \
  --nestdfu PINNED_NESTDFU --xloader PINNED_XLOADER \
  --loader ORIGINAL_PINNED_LOADER_FILES --base-build VALIDATED_HEARTBEAT_BUILD \
  --output FRESH_ECC_BUILD
podman run --rm --network none --cap-drop all \
  --security-opt no-new-privileges --pids-limit 256 --memory 4g --cpus 4 \
  -v ABSOLUTE_ECC_BUILD:/work:Z localhost/hearth-probe-builder:20261030
.venv/bin/python -m firmware.nand_ecc_sample.finalize FRESH_ECC_BUILD \
  --base-build VALIDATED_HEARTBEAT_BUILD
sh FRESH_ECC_BUILD/boot.sh
```

The last command is offline only. Future supervised PTY execution requires the
explicit `--execute-read-only-nand-ecc-sample PRIVATE_OUTPUT PRIVATE_REFERENCE`
arguments, owner readiness/advance experimental-RAM notification, native USB
preflight and the reviewed manual restart. No automatic retry. Keep the display
detached from its unwired base and on USB; after command exit use the full
ten-second hold/release/single-press and confirm native return. Boot-stage hardware
and power side effects remain unverified.

A matching result would validate this bounded normal-read/reference comparison,
including the captured padding case. It would not establish how many bit errors
were corrected, deliberate ECC fault injection, native runtime mounting,
programming/ECC encoding, flash durability, restoration, full application
integration or HVAC behavior. Preserve all original raw captures and derived views.
