# Recovery

The0.10.1 experimental preview adds `python3 provision.py --restore` and a full-NAND
archive before installation. It retains both raw/OOB passes, ECC-derived views,
quality receipts and the matching public installer source. The guided restore
uses the checked saved-file images, not a blind whole-chip reflash. Native settings
changes and incomplete prior writes can still require explicit recovery review.

Keep the private originals, custody receipts, exact plan and matching restore
profile for each installation. Preserve earlier recovery archives. A commissioning
bundle is not a firmware backup, and a raw capture is not proof of restoration.

The guided setup retains its evidence in `private/setup-…`, including a
`READ-ME-FIRST.txt`, private worker logs and the `kit/` directory. An error does
not authorize rerunning `provision.py` against the same modified device: it is a
fresh-install wizard, not an automatic resume or repair tool. Preserve its source
version and all session files.

For a complete private stock kit and unused matching restore images:

```sh
.venv/bin/python -m installer.cli check-kit --kit private/my-kit --for-restore
.venv/bin/python -m installer.cli restore-kit --kit private/my-kit --disk /dev/sdX
```

Restoration runs network cleanup first, then commissioning, with a separate
preflight and RESTORE decision for each. Keep USB connected between phases and
follow the next loader prompt. This is exact selected-file restoration, not a
general uninstall: later native settings changes can invalidate comparison with
the original snapshot. A refusal must not be bypassed or replaced by blindly
restoring old HVAC configuration. Retain the pinned installer source version.

The low-level development command for one intact normal-mode scope is:

```sh
.venv/bin/python -m installer.cli restore \
  --profile private/my-kit/restore --output private/my-restore-attempt
```

The same protected RAM preflight runs before a separate RESTORE confirmation.
Profiles are single-attempt evidence; an executed one must not be reused.

If a write failed, power was interrupted or safe_to_restart is false, retain USB
power and the entire session. Do not blindly run the normal-mode restore command
or reboot partial native files. The underlying writer has separately bound
interrupted-session recovery entry. The kit workflow supports explicit single-phase
recovery and checked RAM handoffs, but never guesses the correct scope from an
incomplete write. Seek review of the actual plan and attempt records before using
`--phase`; no automatic retry is performed.

Selected-file restoration has returned the development unit to its native UI.
Whole-chip/boot-block recovery and hardware power-loss restoration are unverified.
