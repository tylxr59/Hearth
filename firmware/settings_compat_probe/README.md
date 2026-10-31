# RAM comparison for the native storage correction

This original diagnostic runs the original settings library and the
[storage candidate](../settings_compat/README.md) in separate unprivileged processes
in one RAM boot. **Prepared, unexecuted.** Neither nlclient/osm nor real settings,
credentials, production networking or flash filesystems are used.

It repeats the twelve measured I/O cases for each variant (24 cases), then tests
five candidate allocation/alias cases. The original allocation-failure hazard is
not deliberately triggered. Every case must match its reviewed result, including
old-file preservation, corrected entry failures, directory-sync retry and memory
readback. Missing cases, failed process status, lost bindings or tail-canary
changes fail collection. No completed observation means installation or HVAC
compatibility.

The instrumentation is a separate original shared library below the correction in
startup preload order. It injects errors where the correction can actually observe
them. The helper verifies global writer/setter/entry bindings. The kernel,
bootstrap and 34 native baseline libraries are unchanged; only original helper,
instrumentation and correction code is added. MTD/block/physical-network/RTC
support remains disabled. PID 1 performs no network setup or clock change.
Boot-stage hardware/power behavior remains unverified; keep the base detached.

PID 1 accepts only `BEGIN_SETTINGS_COMPAT_V1`, runs each variant once with a fixed
environment and caches the result. Each child has an 8 KiB stdout and 2 KiB raw
stderr cache, a 90-second alarm and a 120-second supervisor deadline. Excess
stderr is drained and counted, with a 1 MiB excess-output stop limit. The shared
report is bounded at 32 KiB. Streaming matchers inspect **all** stderr bytes,
including those discarded from the diagnostic cache. The original must reproduce
the synthetic disclosure pattern; the candidate must emit none. A formatted
multi-argument/float log marker must survive outside the writer scope, checking
unrelated variadic-log forwarding. This is a specific synthetic log-path test,
not proof that all firmware logs are private.

Preparation from Hearth (all outputs must be fresh):

```sh
.venv/bin/python -m firmware.settings_compat_probe.compile build/FRESH_COMPARISON
umask 077
.venv/bin/python -m firmware.settings_compat_probe.artifact package \
  --base private/VALIDATED_TLS_PROFILE \
  --helpers build/FRESH_COMPARISON \
  --review private/REVIEWED_STORAGE_ABI.json \
  --output private/FRESH_COMPARISON_PROFILE
sh firmware/settings_compat_probe/boot.sh private/FRESH_COMPARISON_PROFILE
```

The last command checks offline and opens no device. The private ABI record must
identify the exact acquired libraries and separately reviewed allocator/comparator
contracts; it cannot be replaced by guessed offsets. No proprietary bytes or
private hashes belong in source. Prepared images and native inputs remain private.

A future supervised execution uses a PTY and the explicit
`--execute-experimental-settings-compat-probe` flag. Notify the owner first, check
normal Nest USB, launch the loader and request the manual restart only when it is
waiting. ROM wait is 90 seconds, collection 300 seconds; no automatic retry exists.
A fresh mode-0600 `compat-result.jsonl` is saved before validation. Existing results
are never overwritten. With the command exited afterward, hold for a full roughly
ten seconds even if already black, release, press/release once and confirm native
home icon plus normal USB. Keep USB connected and the base detached throughout.

Host checks cover native ownership through host NSPR under sanitizers, thread and
callback lifetime isolation, bounded stream matching across every split and after
cache overflow, strict comparison/diagnostic records, original cross-compilation,
fixed serial start framing/private capture, and exact archive/review boundaries.
They do not execute the ARM libraries or establish firmware restoration.
