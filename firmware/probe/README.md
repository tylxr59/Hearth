# Experimental Display-2.6 RAM probe

This is a diagnostic boot experiment for the particular unit in
[the intake record](../../docs/research/device-intake-2026-10-30.md). It is not
Hearth firmware, a flash backup, a recovery tool, or a thermostat controller.
It has been built and checked offline. The first physical upload attempt stalled
at the ROM length field before sending the first-stage file. The owner then
restored the home icon and normal Nest USB mode. A paced transport subsequently booted
the custom diagnostic kernel, its heartbeat was observed without sudo, and the
owner returned it to the native home icon and normal USB mode. See the
[handshake investigation](../../docs/research/usb-handshake-2026-10-30.md).
Do not flash these files or use this profile for another model/revision.

The Linux kernel has MTD, block storage and networking disabled. Its entire
userspace is an original, statically linked ARM EABI program that mounts only
proc/sysfs/devtmpfs and repeatedly writes a fixed heartbeat to USB serial.
There is no shell, command receiver, stock startup, installer, credential store
or HVAC interface. The CPIO contains just `.`, `dev`, `proc`, `sys`,
`dev/console`, and `init`. Native persistent firmware is not incorporated.

The preceding x-loader/U-Boot stages still initialize hardware, including NAND
and power-related registers. They have not been proven write-free on this unit.
The kernel's missing MTD subsystem does not prove the entire boot chain harmless.
Experimental code may hang, reset, misconfigure hardware or affect power/battery
behavior. Native control services are absent during the probe: the display must
remain detached from its unwired base. Notify the owner before execution under
the existing device-work authorization. Persistent modifications still require
the backup/recovery gates in [hardware.md](../../docs/hardware.md).

## Inputs and build isolation

[inputs.json](inputs.json) pins the source repositories/revisions and the
historical compiler archive. NLE is a research reference; its installer,
proprietary root and prebuilt boot images are not used to build this probe.
GPL Linux/U-Boot come from the existing NestDFU pin, and x-loader comes from
Google's published 5.9.4 source. The toolchain hash identifies a download from
the HTTPS mirror named by NLE; no independent compiler signature verification
or complete source-to-compiler build has been established. No binary authenticity,
container OS vulnerability clearance or byte-reproducible kernel build is claimed.

Only rootless Podman is required. The builder uses the pinned Ubuntu 20.04 image
in Dockerfile; its package commands run in that Ubuntu container, not on the
CachyOS/Fedora host. Only the image assembly needs package-network access.
Do not mount USB devices, private material or the whole checkout into it.
Keep all downloaded/compiled inputs under ignored `build/`; keep future
device-owned dumps under ignored `private/`.

After obtaining the pinned public sources and compiler archive, put only
Dockerfile and `toolchain.tar.bz2` in a fresh build context. Build:

```sh
podman build -t localhost/hearth-probe-builder:20261030 BUILD_CONTEXT
.venv/bin/python -m firmware.probe.stage \
  --nestdfu PINNED_NESTDFU_CHECKOUT --xloader PINNED_XLOADER_CHECKOUT \
  --loader ORIGINAL_PINNED_LOADER_FILES --output FRESH_BUILD_DIRECTORY
podman run --rm --network none --cap-drop all \
  --security-opt no-new-privileges --pids-limit 256 --memory 4g --cpus 4 \
  -v ABSOLUTE_BUILD_DIRECTORY:/work:Z localhost/hearth-probe-builder:20261030
```

Staging archives the exact commits, ignoring checkout edits and untracked files;
checks the host-loader inputs against their hashes; applies the checked-in patch;
and refuses an existing output directory. The generated source report preserves
archive and recipe hashes. Public source checkouts must have the pinned commits
available locally; staging makes no downloads.

The bootloader model patch selects the source's J49 PVT branch and `Display-2.6`
using the device-reported model. This is a test configuration, not independent
board identification. The kernel needs three source compatibility changes:
newer Perl array syntax, an Ethernet call guard for NET=n, and the missing delay
header in the serial gadget. These are restricted to the generated source tree.

## Host loader and checks

The referenced GPL OMAP loader has an undersized pointer-array allocation and
an unbounded debug-message string read. [omap-loader.patch](omap-loader.patch)
fixes those, drops ASIC/debug payload logging, explicitly claims/releases the
USB interface, rejects zero-progress transfers and oversized protocol inputs,
closes successfully read input files, binds uploads to observed USB port `1-1`,
and pads the jump frame to the twelve bytes required by Google's 5.9.4 x-loader.
That source declares NAND dump opcode names but implements no NAND dump handler;
those constants do not establish a backup capability.
The updated patch additionally backports USB pacing from Doug Brown's
[upstream reliability PR](https://github.com/grant-h/omap_loader/pull/7), pinned
in inputs.json: a 1 ms pause before each bulk transfer, 512-byte output chunks,
and a 20 ms interval after sending the first-stage file. Its hardware effectiveness
on this Nest remains unverified. The host-only harness now tests the complete
ROM header/data exchange, packet bounds, pacing, settling, and a length-field
timeout that must prevent any first-stage data send.
These changes have no physical USB
validation yet. The source retains its upstream GPL notice and LICENSE.md.
The patch and combined sanitizer harness are GPL-2.0-or-later; Hearth's separate
original probe/build/inspection code is MIT licensed. Do not redistribute a
combined executable without its corresponding source and license notices.
The upstream source credits Martin Mueller (2008) and Grant Hernandez (2014).
The [GPLv2 license text](COPYING.GPL-2.0) accompanies the patch/harness here.

On this Linux host, gcc, pkg-config and libusb development files were already
available. Compile the native loader and its host-only ASan/UBSan harness using
the commands recorded in the [research review](../../docs/research/acquisition-review-2026-10-30.md).
The harness mocks libusb and tests the argument parser plus a full-size,
unterminated device debug message without touching USB. Passing it does not
validate ROM uploads or the custom kernel.

The finalized `probe-manifest.json` records SHA-256 for six artifacts and four
host helpers. `check.py` validates that inventory, the disabled kernel subsystems,
the ARM init ELF without a dynamic interpreter, both uImage CRCs, ARM load/entry
parameters, bounded LZMA decompression, and the exact embedded minimal CPIO.
It never executes image contents. The manifest is an unsigned local integrity
record, not a trust root. Copy check.py/configure.py/observe.py/boot.sh from this
directory alongside the generated artifacts before finalizing the helper hashes.

## Device test — observed once; acquisition still pending

The current local retry build is `build/ram-probe-reliability-20261030`. The failed
first attempt's original build remains preserved at `build/ram-probe-final-20261030`.
The retry uses identical kernel/bootloader/init bytes and updated host transport
and helpers. Without arguments,
its boot.sh only checks integrity and exits; it does not open USB.
Execution requires the explicit `--execute-experimental-ram-probe` flag.

The exact sequence for this prepared build is:

1. Review the risks above and keep the display on USB, detached from the unwired
   base. Close other installers/loaders. Keep its current USB port `1-1`.
2. Start from the home icon and normal Nest mass-storage mode. Run the build's
   boot.sh with the explicit execution flag using the host's
   authorized device-access identity (currently sudo is needed). It waits up to
   90 seconds for `0451:d00e`. The wrapper refuses a stale, already-active ROM
   handshake; restore native startup with the loader exited before trying again.
3. While it waits, use the previously observed hold-until-black, release,
   single-press restart sequence once. The loader transfers the generated
   x-loader, U-Boot at RAM `0x80100000`, and kernel at RAM `0x80a00000`, then jumps
   to U-Boot. These are RAM addresses, not flash offsets. The addresses agree with
   the reviewed NLE transport/U-Boot source and the built image's headers.
4. A successful upload is followed by up to 30 seconds of heartbeat observation.
   The reader accepts only the reviewed USB serial gadget IDs on that same
   physical port. It reads a tty without sending application bytes and prints
   only a recognized fixed heartbeat summary. It temporarily sets/restores host
   tty attributes; this may generate normal USB serial control requests.
5. A blank display can occur; only the USB heartbeat is the proposed success
   evidence. After success or failure, stop and report the output. Use one manual
   restart with the loader exited to return to the native home icon. Do not
   install a root filesystem, enable Wi-Fi or attach an HVAC system.

There is no automated recovery claim. Do not retry repeatedly or progress to
flash acquisition merely because a payload uploads. First record the observed
USB/runtime behavior and establish that the native firmware starts again.
Raw flash/OOB acquisition and demonstrated restoration remain separate work.
