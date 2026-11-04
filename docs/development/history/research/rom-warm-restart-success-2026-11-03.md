# Gen 2 warm restart exposes USB ROM without another ring press

## Measured result

On the owner's Gen 2, Display-2.6, primary firmware 5.9.4-5, the corrected
raw-newc RAM experiment reached its exact nonce-bound readiness message. The
owner had approved this fresh second attempt and performed its initial ring
restart. The host then sent one nonce-bound software-restart token. No further
ring press was requested or needed.

The host kernel journal records these events, relative to the durable restart
intent timestamp:

| Seconds | USB event |
| --- | --- |
| 0.075 | RAM USB disconnected |
| 0.604 | OMAP ROM enumerated |
| 4.156 | ROM USB disconnected |
| 11.528 | Native USB enumerated |

This establishes that a normal Linux warm reset from this RAM kernel exposes
OMAP USB ROM on this unit. The observed ROM-enumeration-to-disconnect interval
was about 3.55 seconds. No successor loader was armed, so the device continued
to native startup. These are observations from one run, not guaranteed timing.

**Not established:** loading a second image in that window, an entire wizard
run without further ring presses, another model/firmware, or recovery after a
power interruption. Normal setup still uses manual restarts.

## Host cleanup error and independent evidence

The host observation function returned after the restart, but restoring the
old serial termios settings raised `termios.error(EIO)` because the tty had
disconnected. On this Python runtime that exception is not an `OSError`, so the
existing cleanup suppression missed it. The wrapper consequently exited with
an error before writing its usual final observation file.

The readiness, restart-intent, restart-sent and host-finished records were
already durable. Read-only host journal inspection independently recovered ROM
and native enumeration with timestamps. That recovered result is a separate
outcome-review record; the original failed wrapper outcome was not overwritten.
The attempted profile, build, PTY log, raw journal and exact original experiment
and serial-observer sources are retained privately. No token or image was resent.

Cleanup now handles both exception classes during terminal restoration. The
restart observer also saves its received outcome before serial cleanup. Tests
cover both successful receive and a genuine receive failure followed by the
cleanup error, so the latter cannot replace the original error. Fifty-eight
focused tests and static checks pass. The full suite also passes: 1,931 tests,
with seven optional skips. A fresh profile using the current host
source is prepared but unexecuted; the successful profile remains single-use.

## Device and safety scope

The host exited and read-only inspection reports native USB. No loader remains
armed. The display remained detached from its wired oil/baseboard heating base.
No installer flash write or intentional HVAC call was issued. Native startup
can write its usual settings/logs; runtime NAND operation counters were not
captured. Whole-firmware and power-loss recovery remain unverified.

The next optional hardware step is a separately approved, fresh two-image
handoff experiment. It must have a waiting successor loader before triggering
the single warm reset, preserve both profiles and outcomes, and allow no retry.
It is not authorised by this completed one-restart test.
