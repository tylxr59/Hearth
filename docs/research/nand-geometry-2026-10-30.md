# Display-2.6 NAND geometry measurement, 2026-10-30

The owner restarted the USB-connected display while the reviewed geometry-only
loader was waiting. The display was detached from its unwired base, with no HVAC
connection. Existing device-work authorization and advance experimental NAND/RAM
risk notice applied. No persistent install or flash operation was requested.

## Inputs and observed execution

The prepared build is `build/nand-geometry-20261030` (ignored, machine-local).
Source safeguards, source pins, isolated build and exact image checks are described
in [the profile README](../../firmware/nand_metadata/README.md). The initial host
launch failed before USB access because the staged loader lacked executable
permission. Staging now preserves modes, and finalization rejects that condition.
No restart/transfer occurred during that host failure.

The corrected single PTY-backed attempt ran without sudo using the owner-installed
port-scoped ROM/tty ACL. Loader output reported a 69-byte ASIC reply (contents
omitted), boot command, first-stage length/payload of 27856 bytes, and successful
transfer of three files. The metadata observer returned:

| Field | Observed value |
| --- | --- |
| Master name | `omap2-nand.0` |
| Total NAND size | 268435456 bytes (256 MiB) |
| Erase block | 131072 bytes (128 KiB) |
| Page | 2048 bytes (2 KiB) |
| OOB per page | 64 bytes |
| MTD capability flags | 0 (`MTD_CAP_ROM`) |

The guard requires the selected NAND chip's status to indicate hardware write
protection before registering the master. Successful sysfs geometry therefore
provides evidence that this guarded code path reached registration. It is not an
independent electrical WP measurement or a destructive test of write rejection.

The wrapper exited 0. A separate sysfs observation confirmed serial gadget
`0525:a4a7` on physical USB port `1-1`. No raw serial bytes, device identifiers or
firmware data were logged. The owner was then instructed to manually restart
with the loader exited. The owner then reported ready; a follow-up sysfs observation confirmed normal
Nest USB mode (2464:0002). The owner did not separately describe the display
in that reply. No firmware restoration was performed.

## Limits and next steps

This is master geometry from our custom RAM kernel, not the stock partition map.
No flash contents, OOB data, bad-block map, ECC interpretation, calibration,
credentials, backplate firmware or native executable was acquired. The kernel
has no MTD character/block interface, partitions, storage filesystem mounts,
network, shell or commands. Native control services are absent during the test.

Source/configuration guards do not establish absence of persistent effects
throughout the preceding bootloader chain. Firmware backup/restoration, battery,
native HVAC behavior and product compatibility remain unverified. Confirm native
startup first. Then separately review a bounded private raw acquisition design,
including bad blocks, ECC/OOB preservation, integrity/repeatability and transport
failure behavior. Do not infer restore offsets or a recoverable image from this
geometry, and preserve the [pre-write gates](../hardware.md).

The host suite passed 124 tests, including 27 geometry-specific tests and enabled
Podman broker/container tests; Ruff/format/Bandit passed. The OTP callback signature
and executable-mode fixes received focused rechecks. No new host runtime dependency
was introduced. See the [dated validation record](../security/validation-2026-10-30-nand-geometry.json).
