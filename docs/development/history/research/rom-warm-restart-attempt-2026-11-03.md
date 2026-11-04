# Warm-restart experiment: first load failed before readiness

The owner approved one supervised test. A fresh, previously unexecuted profile
was armed once in a PTY, and the owner performed the initial ring restart.
The loader reported successful transfer of its three files, and USB changed
from native mode to RAM mode. The host never received the experiment's exact
nonce-bound readiness message and timed out. No restart token was requested
or sent. **The warm-restart hypothesis remains untested.**

## Cause and correction

The experimental profile incorrectly gzip-compressed its external filesystem.
The reused protected snapshot kernel explicitly has `CONFIG_RD_GZIP` disabled;
the existing acquisition profile correctly uses raw newc for this kernel.
The experiment's own validator had repeated its packaging assumption instead
of checking that constraint. It therefore accepted an image that did not reach
its intended PID 1. RAM USB enumeration alone was insufficient evidence.

The packager and checker now use raw newc. A new regression test builds an
actual original ARM init against a synthetic protected-kernel fixture and
checks the RAM-disk payload, including independent profile validation. Twenty
focused tests pass. A fresh corrected private profile builds and passes checks;
it has not been attempted. No compression or protection gate was weakened.

## Evidence and current state

The attempted profile, build, execution/finished records and PTY log remain
unchanged. The exact original experiment source files were copied into its
private result directory before editing. Additional outcome evidence records
that readiness and restart-send markers are absent. No retry occurred.

A read-only USB check after host exit still reports RAM mode. The checked kernel
has write-denial guards; no intentional flash write or HVAC call was made.
Runtime flash-operation counters were not captured. Execution of the built-in
fallback reader is consistent with the packaging error but was not independently
observed as a decoded report.

After the host has exited, a normal owner-controlled restart can return this
read-only attempt to stock startup. The display must remain detached from its
wired heating base, with USB power retained. Stock startup may write its usual
settings/logs. Whole-firmware and power-loss recovery remain unverified.
A fresh loader attempt requires renewed owner readiness; none is armed.
