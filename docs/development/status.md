# Current development status

The owner installation runs HA0.6.9 with a Gen2 Display-2.6 on primary5.9.4-5.
It uses native HTTPS directly inside HA Core. The latest confirmed physical state
is Heat63F, manual Ecooff, empty schedule, heating idle. The equipment is described
as oil/baseboard; exact boiler/furnace arrangement remains unverified.

Measured on the real unit:

- Authenticated local telemetry, corrected timezone, local weather requests.
- Single-target63→62→63F cycles, with matching physical/HA acknowledged display.
- Manual Eco on/off confirmed by fresh native mode, unchanged limits, restored off.
- Native week acquisition, HA future point, exact values/revision readback,
  post-write metadata acknowledgement, private backups and original empty restore.
- Selected-file install/readback/restoration and native UI return. Whole-chip
  recovery, hardware power loss and intentional HVAC switching are not measured.

Local0.7 work adds the remaining device settings, public HA setup, HACS layout,
release packaging and guided install/restore. It is not deployed to the owner.
The real HA2026.10.4 sandbox passes24 control round trips, including learning/
Early-On restoration, new profile generation and private-key export exclusion.
Hassfest validates the self-contained integration with zero errors. Optional native
diagnostics include voltage, RSSI, filter, outdoor and native activity fields.
The guided writer consumes separately prepared device-bound install/restore
profiles; automatic acquisition and per-unit build remain an explicit release gap.
Do not confuse an implemented frontend with a turnkey stock-device installer.

Canonical sources: `backend/`, `custom_components/hearth/`, `installer/`,
`provisioning/`, `firmware/`. Generated HA transport is checked for exact equality.
Keep the final hardware and release checklist in [roadmap](roadmap.md).
Historical evidence and old experiments are archived in [history](history/).
