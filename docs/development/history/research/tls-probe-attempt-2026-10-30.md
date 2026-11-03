# First supervised TLS RAM attempt and launch correction

The owner performed the reviewed restart while the loader was waiting. ROM
handshake and transfer of all three files completed; the loader exited zero.
The expected USB serial identity appeared on the reviewed port. The collector
sent its fixed start token and saved a mode-0600 private report.

That report is 39 bytes: one failed completion record, with **no TLS case rows**.
It proves that the custom diagnostic userspace reported, not that either native
TLS hook was tested. The collector rejected it and exited 1. No automatic retry
occurred. With the command exited, the owner restarted and confirmed the native
home icon; normal USB 2464:0002 was also observed. This is native startup return,
not firmware restoration, HVAC validation or a successful TLS matrix.

The original private image, creation manifest and result remain unchanged under
`private/native-tls-probe-20261030/profile-supervised`. The source used was
commit `3fa529e`. A separate private attempt record preserves the result digest;
no binary, digest, credential or actual device identifier is published here.
The earlier unexecuted-build validation record remains historical evidence of
the preparation scope.

## Concrete packaging error

The RAM archive assigned mode 0444 to all library files, including the executable
interpreter named by the helper's PT_INTERP:
`/lib/ld-linux-armhf.so.3`. Linux opens that interpreter with `open_exec`, which
requires execute permission. If helper launch was reached, this packaging would
deny it before main. The first supervisor reported neither setup results nor
child wait/exec status, so the saved frame cannot distinguish that path from an
earlier setup failure. The permission error is confirmed; it is not established
as the sole cause of the observed failed run.

The packager now reads the actual helper PT_INTERP, requires the expected native
interpreter and includes it as mode 0555. Other shared libraries remain 0444.
The independent archive gate enforces that distinction and rejects a
non-executable interpreter even if a manifest agrees with the incorrect mode.
Missing/static/unexpected interpreter contracts are also rejected before upload.

A regression reproduces the permission requirement using the PC's trusted
`true` executable and dynamic loader, copied only into a temporary test directory.
The host kernel rejects its non-executable interpreter and runs it after the
permission correction. **No device firmware runs on the host** in this check.

## Better evidence before another restart

The supervisor now records loopback stage/result and RAM-clock setup result,
separate helper wait statuses, and pre-exec failures with their syscall results.
Helper stderr is bounded and hex-encoded into private diagnostic rows rather than
discarded or printed. Successful collection requires explicit successful setup,
both zero process statuses and every one of the 18 expected TLS results. Private
diagnostics do not substitute for any of that evidence.

The existing kernel and validated bootstrap files are reused unchanged. A fresh
private profile at `private/native-tls-probe-20261030/profile-launch-diagnostics`
passes offline integrity/default-launch checks; it has not run on the thermostat.
It remains RAM-only with synthetic fixtures, loopback networking and no native
control application. No persistent installation, new physical-network access,
storage correction or HVAC operation was attempted.

`make check` passes. The host suite passes 239 tests, with two optional integration
tests skipped; 50 tests cover the diagnostic profile. Next is a separately
coordinated supervised restart with this corrected profile. Do not reuse/delete
the first result or retry its boot automatically.
