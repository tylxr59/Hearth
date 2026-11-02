# Release checklist

## Before stable v1

- Validate actual heating start/stop and native operating-action feedback with
  separately authorized supervision and the actual equipment identified.
- Test local operation during HA/network outages, reconnect, reboot and no replay.
- Verify an actual timed schedule transition and sustained multi-day operation.
- Validate new settings types/bounds and acknowledgements on supported firmware.
- Verify physical outdoor-weather rendering and unavailable-provider behavior.
- Extend the measured consolidated reader to pristine supported units and measure
  the complete source-built, per-device two-phase installation and restore. The
  offline composed replay build and profile reproduction now pass.
- Add portable, scoped USB access and preserve current native configuration during
  uninstall; exact initial-settings recovery must continue refusing unknown edits.
- Exercise the public installer/restore workflow on supported hosts and supported
  stock units; retain exact originals and interrupted-write refusal/recovery.
- Review legacy native endpoints, logging, trust/clock renewal, dependencies and
  resource limits; publish residual risks and actual tested compatibility.
- Test HACS custom-repository install/update and onboarding on a clean HA system.
- Run release artifact, licensing, reproducibility, hassfest and privacy checks.

## Additional hardware coverage

Cooling, fan, emergency heat and ranges need suitable equipment. Gen1 and other
firmware require their own measured installation/recovery profiles. Do not infer
those results from Gen2 heating tests.

The detailed dated investigation is retained in [history](history/), not mixed
into the user installation instructions.
