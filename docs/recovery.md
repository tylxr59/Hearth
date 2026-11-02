# Recovery

Keep the private originals, custody receipts, exact plan and matching restore
profile for each installation. Preserve earlier recovery archives. A commissioning
bundle is not a firmware backup, and a raw capture is not proof of restoration.

For an intact normal-mode device and an unused matching restore image:

```sh
.venv/bin/python -m installer.cli restore \
  --profile private/my-kit/restore --output private/my-restore-attempt
```

The same protected RAM preflight runs before a separate RESTORE confirmation.
Profiles are single-attempt evidence; an executed one must not be reused.

If a write failed, power was interrupted or safe_to_restart is false, retain USB
power and the entire session. Do not blindly run the normal-mode restore command
or reboot partial native files. The underlying writer has separately bound
interrupted-session recovery entry, but the simple frontend intentionally does
not guess that entry reason. Seek review of the actual plan and attempt records.

Selected-file restoration has returned the development unit to its native UI.
Whole-chip/boot-block recovery and hardware power-loss restoration are unverified.
