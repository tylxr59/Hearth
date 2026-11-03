# First physical-device intake — 2026-10-30

## Evidence and scope

The owner reports enclosure model `02A`, USB power from the development PC,
and a home icon on the display with no accessible settings menu. Serial,
MAC and volume identifiers are deliberately excluded from this record.

Host sysfs reads observed USB manufacturer `Nest`, product `Learning Thermostat`,
VID:PID `2464:0002`, and one USB mass-storage interface (class/subclass/protocol
`08/06/50`, driver `usb-storage`). The host exposed an approximately 40 MiB FAT
volume. The owner ran read-only `mdir` and `mtype` against the unmounted volume;
the agent could not read its block device without administrator access.

The root directory listed only `Technical Info.plist` (694 bytes). The owner
provided its contents, from which these non-identifying fields were transcribed:

| Field | Reported value |
|---|---|
| Base.Model | `unknown` |
| Display.Model | `Display-2.6` |
| Display.ActivePartition | `primary` |
| Display.SoftwareVersion | `5.9.4-5` |
| Display.SoftwareUpdateState | `Synchronized - None` |

These are device-reported metadata, not independent firmware verification.
`Base.Model=unknown` does not establish a defective base. The display revision
is not a measured board revision. The filesystem's year-2000 timestamp is not
evidence of firmware age or a correctly set device clock.

## Base photographs

The owner supplied front/back photographs and reports no printed model or serial
label. The photographs show the base loose on a table, with no HVAC wiring
attached. Visible left terminals are `Y1`, `Y2`, `G`, `O/B`, `Rc`; right terminals
are `W1`, `W2/AUX`, `C`, `*`, `Rh`. A bubble level and display connector are
visible. No model identifier is legible on either pictured face. Terminal layout
alone does not establish an exact base revision or functional compatibility.

The original photographs are outside the repository and are not committed.
The owner requires EXIF removal before any future photo inclusion; use sanitized
copies with all embedded metadata and any appended motion-photo content removed
and verified. This is not authorization to upload or publish photos.

## Interpretation and remaining work

- The enclosure and display metadata are consistent with the Gen 2 research
  target; base identity, regional variant and board revision remain unverified.
- The observed interface is mass storage, not an observed OMAP ROM loader,
  shell or complete firmware backup. The visible file supplies no battery data,
  MTD layout, kernel version, proprietary executables or recovery evidence.
- The existing `provisioning.cli detect` filters for TI vendor `0451`, so it
  does not inventory this normal-mode Nest USB identity. Its empty output must
  not be interpreted as device absence.
- The pinned NLE README describes an installer that flashes firmware; the
  pinned NestDFUAttack rootme research already establishes persistent writes.
  Neither is an approved acquisition-only procedure. Firmware version alone
  does not establish loader compatibility or recovery.
- The supplied base is available and visibly unwired. Exact pairing remains
  unverified. The authorized restart and USB observation below confirmed a brief
  OMAP ROM identity. Next: continue model-specific acquisition/payload review.
  Keep persistent deployment blocked.

## Restart and USB observation plan

The procedure below was prepared before execution. The owner subsequently
authorized device investigation, requesting advance notification for potentially
dangerous actions such as flashing. This does not remove the backup/recovery
gates for persistent changes. Execution results follow the original plan.

Purpose: observe USB enumeration across one manual restart of this display. This
does not establish firmware acquisition or a recovery path.

1. Leave the display detached from the unwired base and connected by USB. Close
   any installer/loader software; no payload transfer tool should be running.
2. Observe only sysfs vendor/product identifiers for up to 60 seconds, filtering
   Nest `2464` and TI `0451`. Keep serial/device descriptor contents out of logs.
   Sysfs sampling can miss a short event; absence is inconclusive.
3. The owner performs one manual restart: hold the thermostat down until its
   screen turns off (about ten seconds), release, then press and release the
   ring to complete the restart, as documented by
   [Google](https://support.google.com/googlehome/answer/9247296?hl=en-GB)
   (consulted 2026-10-30). Google cautions that unsaved information can be lost.
4. Record observed IDs and the owner's display observations. Stop after this
   single attempt. Do not claim a ROM-mode result unless it was actually seen;
   do not send a payload even if an OMAP identity appears.

This procedure is within the owner's subsequent authorization under AGENTS.md's
physical-device control boundary. It excludes a factory reset, writes initiated by host tools, custom
payload execution and HVAC operation. A normal reboot may itself update native
persistent state; it is not a guarantee of unchanged flash contents.

Additional static review at the existing NLE pin
`fabbe034f01cefdabe06b93d1c312068f563a177`, fetched as text only:

- `firmware/installer/electron/usb-handler.js` expects `0451:d00e` and calls
  `flashOmap` with first/second-stage bootloader and kernel inputs.
  SHA-256: `34b8c5e085491539668881f8f501d1b0172f1a086da63145f03bf1d1026352f8`.
- `firmware/installer/electron/omapLoaderUsb.ts` sends peripheral-boot commands,
  transfers inputs, then sends a jump command. This is code execution, not USB
  enumeration. A RAM destination does not establish absence of persistent writes
  by subsequently executed code.
  SHA-256: `83716ebe33abfe37aba6ef9e203d55b0e87ba07f80610b7e0100394da051254d`.

Neither file nor any downloaded executable was run. No new upstream revision
was selected.

## Observed restart results

The first 60-second host observation recorded only `2464:0002`. The owner later
confirmed performing the hold-until-black, release, single-press restart sequence;
its timing relative to that first capture is not established.

During the second attempt, a host sysfs observer sampled Nest/TI USB identities
approximately every 50 ms. It recorded these transitions (host local clock):

| Time | Observation |
|---|---|
| 15:11:18 | Normal Nest `2464:0002` on port `1-1` |
| 15:11:24 | Disconnected, then TI `0451:d00e` on port `1-1` |
| 15:11:27 | TI identity disappeared |
| 15:11:35 | Normal Nest `2464:0002` returned on port `1-1` |

The owner reports that the display returned to the home icon. The observed TI
identity matches the ROM-mode identity expected by the pinned NLE loader.
This establishes that ROM entry is possible on this specific unit and sequence;
it does not prove payload compatibility, a working acquisition tool, flash
integrity, restoration or control safety. Timing is approximate and does not
establish an invariant upload window.

No payload was sent or executed by host tools. No host-initiated filesystem
write, flashing, HVAC operation or restoration test was performed. No complete
firmware image was acquired. Historical host test results were not rerun.
