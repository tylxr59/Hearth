# Read-only NAND controller contract diagnostic

This separate experimental RAM profile reports the detected bus width, bad-block
marker position/scan flags and BCH4/OOB layout from the controller initialized in
the custom kernel. **Prepared source; not yet observed on target.** It acquires no
NAND contents and supplies no write/erase, restore or apply operation. It is not a
stock runtime partition map or proof that programming/restoration will work.

All geometry-profile restrictions remain: hardware WP asserted, protected-status
registration guard, skipped BBT scan, denied MTD mutation callbacks, zero capability
flags, no MTD character/block consumers, partitions, UBI, storage mounts, networking
or shell. A root-read-only sysfs attribute is created after guarded master-device
registration. It has no store/mmap callback and returns only fixed numeric/layout
metadata. Every read checks protected status again. No serial, MAC, credential,
flash data or MMIO register dump is emitted.

The static userspace reads that one attribute and reports a bounded text frame on
the same scoped USB gadget. The host parser retains the existing geometry checks,
requires the measured unit geometry and reviewed BCH4 layout, and rejects missing,
duplicate, unknown or inconsistent fields. Its result explicitly leaves write-path
and restoration verification false. A changed layout fails collection rather than
silently authorizing a different writer. No writer is included.

Use the original pinned source checkouts and validated heartbeat bootstrap:

```sh
.venv/bin/python -m firmware.nand_contract.stage \
  --nestdfu PINNED_NESTDFU --xloader PINNED_XLOADER \
  --loader ORIGINAL_PINNED_LOADER_FILES --base-build VALIDATED_HEARTBEAT_BUILD \
  --output FRESH_CONTRACT_BUILD
podman run --rm --network none --cap-drop all \
  --security-opt no-new-privileges --pids-limit 256 --memory 4g --cpus 4 \
  -v ABSOLUTE_CONTRACT_BUILD:/work:Z localhost/hearth-probe-builder:20261030
.venv/bin/python -m firmware.nand_contract.finalize FRESH_CONTRACT_BUILD \
  --base-build VALIDATED_HEARTBEAT_BUILD
sh FRESH_CONTRACT_BUILD/boot.sh
```

Finalization checks exact generated driver/headers, helper copies, unchanged
configuration restrictions, bounded images and unchanged bootstrap. The last
command checks offline and opens no device. Explicit execution requires
`--execute-read-only-nand-contract`, owner readiness/advance notification, native
USB preflight, a PTY and the reviewed manual sequence. No automatic boot retry.
After command exit, use the full ten-second hold/release/single-press sequence and
confirm native startup. Keep the display detached from the unwired base and on
USB. Boot-stage hardware/power behavior remains unverified. No persistent
modification or HVAC operation is part of this diagnostic.
