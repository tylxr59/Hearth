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
- Next: establish whether the matching base is available and disconnected from
  HVAC, then review a model-specific boot/acquisition procedure and its payload
  before seeking authorization to execute it. Keep persistent deployment blocked.

No reboot, ROM-mode entry, payload execution, filesystem write, flashing,
HVAC operation or recovery test was performed during this intake. No complete
firmware image was acquired. Historical host test results were not rerun.
