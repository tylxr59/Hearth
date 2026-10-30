# Experimental whole-chip read-only acquisition

This extends the [measured raw sample](../nand_sample/README.md) for the owner's
Display-2.6: exactly two whole-chip passes, in one RAM boot. It is built and
checked offline, not yet measured on hardware. It is not a restore/deployment tool.

The same reviewed driver, hardware WP, per-read protected-status check, zero MTD
capability flags, disabled BBT scanning and denied write callbacks remain. MTD
character/block interfaces, partitions, storage filesystem mounts, networking,
shells and native control are absent. Only the fixed read-only sysfs attribute's
extent changes: `hearth_raw` exposes 131072 aligned 2112-byte records, covering
256 MiB data plus 8 MiB OOB. Geometry must match the measured chip. No bad blocks
are skipped, no ECC correction is applied, and an error/short read aborts without
padding. This does not establish ECC validity or restorability.

The producer uses one page buffer. After the host opens private files and makes
its tty raw, it sends exactly `HRTHGO1\n`, an eight-byte fixed start token. This
permits only the fixed two-pass read; there are no supplied offsets, lengths,
write commands or executable inputs. The producer streams ordered CRC-protected
`HRTHRAW1` frames using the validated sample framing, then a mandatory checked
`HRTHEND1` completion footer. It idles after success or failure; no capture retry
or further NAND read follows. USB backpressure bounds buffering; stalled writes
abort after bounded retries. Gadget tty processing remains disabled.

The host reuses the same physical-port/gadget checks, now opens the selected tty
read/write solely for that start token, and temporarily sets/restores its raw
attributes. This profile alone permits a 1200-second capture window (helper hard
limit 1800 seconds). Progress reports contain only record counts. Two 276824064-byte
raw files and SHA-256 records remain under a fresh ignored private directory,
with the existing exclusive 0700/0600 permissions, CRC/order checks, fsync and
incomplete/mismatch handling. The disk-space preflight requires both files plus
64 MiB spare. Complete data, footer and equal pass hashes are required for success.
Raw bytes, hashes and credentials must not enter Git, public logs or uploads.

The bootloaders still initialize hardware; write guards do not prove absence of
persistent effects throughout that chain. Experimental RAM/NAND code may hang,
reset or affect power. Notify the owner before execution; keep the display off
the unwired base and on USB. After acquisition/wrapper exit, return to native
startup once. No HVAC operation or flash modification is included. Whole-chip
raw bytes alone are not a verified full-device backup: calibration, credentials,
ECC/bad-block interpretation, partition identity and backplate/recovery coverage
must be established before the [pre-write gates](../../docs/hardware.md) can close.

Build with `firmware.nand_capture.stage` and `firmware.nand_capture.finalize`,
using the same flags/isolated builder as the sample profile. Current local build:
`build/nand-capture-20261030`. The finalizer checks the generated reader, framing,
binary gadget source, init/config/kernel and unchanged bootstrap bytes; its
unsigned local manifest pins six artifacts and ten runtime helpers. The staged
image checker enforces the same kernel exclusions, ARM ELF, CRC/decompression and
exact minimal initramfs (3900 bytes). A no-argument boot.sh is offline only.
Execution requires `--execute-read-only-nand-capture PRIVATE_OUTPUT_DIRECTORY`
from normal native USB mode, a PTY and the reviewed scoped ACL. No automatic boot
retry occurs. Old builds/captures are preserved. Private bytes are never executed.

Twelve new tests include scaled socket-based transfer/failure/footer checks and
ASan/UBSan harnesses of the actual producer with mocked syscalls plus actual
whole-chip reader bounds with mocked NAND/sysfs. They verify read-only NAND opens,
fixed-token gating, short/error reads, partial/stalled writes and the wire format.
There is no physical hardware in those tests. The full host suite passes 153
tests, including enabled Podman broker/container tests; Ruff/format/Bandit pass.
Historical upstream kernel warnings remain; no new guard warnings were emitted.

Sources/toolchain/bootstrap pins and licensing remain those of the sample profile.
Generated kernel reader and its combined harness are GPL-2.0-or-later; original
standalone exporter/framing/host tooling are MIT. Preserve source/notices for any
later authorized binary distribution. No new third-party dependency was added.
