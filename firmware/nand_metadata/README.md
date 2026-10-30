# Experimental NAND geometry-only RAM kernel

This separate profile extends the successfully observed [RAM heartbeat
probe](../probe/README.md) for the owner's Display-2.6 unit. It is not firmware
acquisition, backup, recovery, deployment or HVAC control. It has passed offline
build/integrity checks; physical execution has not yet been attempted.

The experiment initializes NAND to obtain seven master-device sysfs attributes:
name, type, flags, size, erase size, page size and OOB size. It does not read NAND
contents or OOB bytes. The reported master geometry is not the stock partition
map. No shell, command receiver, native userspace, credentials, network, storage
filesystem or flash character/block interface is present. The original no-MTD
heartbeat profile and its verifier remain unchanged.

## Write-path review

All source references below refer to NestDFU revision
`930b834b7f1f082b8761aa5c5af765b4b3e99dc9`, under `Dev/linux/`:

- `drivers/mtd/nand/omap2.c` originally calls `GPMC_CONFIG_WP, 0`.
  `arch/arm/mach-omap2/gpmc.c` establishes that value 1 asserts protection;
  this profile changes that call to 1 before ID probing.
- The driver sets `NAND_SKIP_BBTSCAN` before ID probing. The profile requires
  that flag and rejects `NAND_USE_FLASH_BBT` before `nand_scan_tail`, avoiding
  generic bad-block-table creation and updates during initialization.
- `drivers/mtd/nand/nand_base.c` clears low chip-option bits during ID probing.
  `NAND_ROM` must therefore be set afterward, before `nand_scan_tail` assigns
  the MTD capability flags. It produces `MTD_CAP_ROM` (zero).
- After scan-tail, the guard selects chip 0, reads `NAND_CMD_STATUS`, and requires
  `NAND_STATUS_WP` to be clear, using the same interpretation as `nand_check_wp`.
  It deselects the chip afterward. If protection is not reported, registration
  aborts and the host must not accept a geometry result.
- Before MTD registration, write, panic-write, OOB-write, erase, bad-block mark,
  OTP write/lock, device lock/unlock and vectored-write callbacks are replaced
  with `-EROFS` stubs. Both MTD and chip bad-block-mark callbacks are blocked;
  returned byte counts are zeroed and failed erases are marked failed.
- MTD character/block interfaces, partitions, UBI, oops storage and alternative
  flash consumers are disabled. The master is exposed only through sysfs.
  `drivers/mtd/mtdcore.c` cannot perform its writable power-up unlock with zero
  capability flags; the explicit unlock callback is also denied.

The source guard [configure.py](configure.py) requires the exact reviewed OMAP
driver SHA-256 before patching. [readonly.h](readonly.h) is original GPL-compatible
guard code; see the [GPL notice/text](../probe/COPYING.GPL-2.0) and
[THIRD_PARTY.md](../../THIRD_PARTY.md). Other original standalone files are MIT.

These are layered source/configuration safeguards, not proof that no persistent
change can occur throughout the boot chain. The reused x-loader/U-Boot stages
still initialize NAND and other hardware. No destructive write test was run.
The custom kernel can hang/reset or affect power/battery behavior. Native control
is absent while it runs. Keep the display on USB, detached from the unwired base.
Notify the owner before execution under the existing device-work authorization.
Never flash this kernel; persistent modifications remain behind the
[backup/recovery gates](../../docs/hardware.md).

## Offline build and checks

Use the pinned sources, isolated rootless builder, and already validated base
artifacts described in the heartbeat probe README. Staging refuses existing paths:

```sh
.venv/bin/python -m firmware.nand_metadata.stage \
  --nestdfu PINNED_NESTDFU --xloader PINNED_XLOADER \
  --loader ORIGINAL_PINNED_LOADER_FILES --base-build VALIDATED_HEARTBEAT_BUILD \
  --output FRESH_GEOMETRY_BUILD
podman run --rm --network none --cap-drop all \
  --security-opt no-new-privileges --pids-limit 256 --memory 4g --cpus 4 \
  -v ABSOLUTE_GEOMETRY_BUILD:/work:Z localhost/hearth-probe-builder:20261030
.venv/bin/python -m firmware.nand_metadata.finalize FRESH_GEOMETRY_BUILD \
  --base-build VALIDATED_HEARTBEAT_BUILD
sh FRESH_GEOMETRY_BUILD/boot.sh
```

Finalization checks source guards and exported artifacts against the actual build
tree and proven base bootstrap bytes. The unsigned local manifest pins six
artifacts, seven host helpers and current recipes. The staged checker verifies
strict configuration, static ARM init, image CRCs, bounded decompression and the
exact six-entry minimal initramfs. Its dry run never opens USB. Initial staging
provenance is preserved separately; the final manifest records final recipe
hashes, including fixes made during offline build review.

The bounded host parser accepts only a distinct complete metadata frame with
exact known fields, NAND type, zero capability flags and internally consistent
geometry. Unknown bytes and identifiers are not printed. It reuses the reviewed
same-port serial selection, temporarily sets/restores tty attributes and sends
no application commands. Geometry does not prove successful firmware reads or
correct ECC/OOB interpretation.

## Supervised execution, not yet measured

The prepared local build is `build/nand-geometry-20261030`. The callback review
caught and corrected this kernel's non-const OTP-write signature before execution;
the initial build log is preserved separately. The final build has no warnings
in the Hearth guard. Historical upstream kernel/config warnings remain.

The first host launch stopped before USB access because staging had not preserved
the native loader executable bit. Staging now preserves modes and finalization
rejects a non-executable loader. No device restart or transfer occurred in that
launch. The prior manifest is preserved alongside the corrected one locally.

The explicit execution flag is `--execute-read-only-nand-metadata`. Start only
from normal native USB mode on physical port `1-1`, after advance risk notice,
with the reviewed owner-installed ROM/tty ACL rule. Use a PTY for loader output.
While the loader waits, the owner performs one hold-until-black, release,
single-press restart. No automatic retries occur. After the report or failure,
let the wrapper exit and manually return to the home icon; verify normal Nest
USB mode separately. Record observed evidence without changing these offline
checks into a hardware safety or recovery claim.
