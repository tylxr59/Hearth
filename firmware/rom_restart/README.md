# Supervised warm-restart experiment

This separate experiment tests whether one normal Linux warm reset from a
USB-loaded RAM image exposes the OMAP USB ROM again without a ring press.
It does not force a boot order or assume that `reboot("bootloader")` works.
The pinned kernel's `arch/arm/mach-omap2/prcm.c` implements the warm reset;
its ordinary boot-mode argument is not evidence of USB ROM selection.

The static original PID 1 runs on the existing protected snapshot kernel,
mounts only devtmpfs, and exposes a fresh nonce-bound readiness message. It
mounts no flash, executes no native application, changes no boot registers,
and accepts one fixed restart token. A returned reboot syscall is never
retried. Normal setup does not import or use this experiment.

## Owner-supervised plan

1. Confirm normal USB mode, display detached from the **wired heating base**,
   USB power retained, no other loader running, and a fresh private profile.
2. Get explicit readiness before arming one loader in a PTY. The owner performs
   the initial ring restart once, when the loader starts scanning.
3. Verify the experiment's exact RAM nonce. Ask separately before sending the
   single restart token. From then on, do not touch the ring.
4. Observe USB for 30 seconds. Record ROM enumeration (`0451:d00e`), native
   enumeration, or an inconclusive timeout. No second loader or retry starts.
5. Preserve the output unchanged. Review the result and normal USB state before
   another operation. USB ROM enumeration alone does not prove a second image
   can be loaded; that needs its own owner-approved follow-up.

There are no intentional flash writes in the experiment. **The warm reset can
return to stock startup, which can write its usual settings and logs.**
Whole-firmware and power-loss recovery remain unverified. No on-base or HVAC
experiment is included.

Offline preparation (fresh paths under `build/` and `private/`): call
`firmware.rom_restart.profile.build(protected_kernel, build_path, profile_path)`.
After owner readiness, run in a PTY:

```sh
python -m firmware.rom_restart.run private/<fresh-profile> private/<fresh-output>
```

On the measured Gen 2, the corrected RAM image successfully exposed USB ROM
after one software restart without another ring press. This experiment never
loads a successor image. The wizard's automatic handoff is implemented
separately in [`nand_handoff/`](../nand_handoff/README.md). See the
[result](../../docs/development/history/research/rom-warm-restart-success-2026-11-03.md).

The first approved load timed out before readiness because its RAM filesystem
was gzip-compressed while the protected kernel disables RD_GZIP. No restart
token was sent. Packaging now uses raw newc, matching the acquisition reader.
The original failed attempt and successful corrected profile are preserved.
Neither may be reused. Host serial cleanup is now fixed and observations are
saved before cleanup; the latest fresh profile with those host fixes is
unexecuted. See the
[attempt record](../../docs/development/history/research/rom-warm-restart-attempt-2026-11-03.md).
