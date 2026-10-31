# RAM comparison for the native storage correction

This original diagnostic runs the original settings library and the
[storage candidate](../settings_compat/README.md) in separate unprivileged processes
in one RAM boot. The first attempt completed the original baseline but the
candidate crashed before its first case; see the
[attempt record](../../docs/research/settings-compat-attempt-2026-10-31.md).
A phase-marker attempt reproduced the startup crash before any candidate marker.
The GNU-linked build subsequently passed all 29 cases on target; see the
[observed result](../../docs/research/settings-compat-result-2026-10-31.md). Neither nlclient/osm nor real settings,
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

The next diagnostic build enables fixed, once-per-call-site phase markers in the
single-threaded helper/candidate. They use stderr directly without native logging,
TLS, allocation or formatting and contain no values, paths or pointers. Ordinary
standalone candidate builds omit these markers. Diagnostic capture limits and
full-stream secret matching remain unchanged; markers cannot substitute for any
of the 29 required cases or successful child statuses.

PID 1 accepts only `BEGIN_SETTINGS_COMPAT_V1`, runs each variant once with a fixed
environment and caches the result. Each child has an 8 KiB stdout and 2 KiB raw
stderr cache, a 90-second alarm and a 120-second supervisor deadline. Excess
stderr is drained and counted, with a 1 MiB excess-output stop limit. The original
retains the first 2 KiB; the candidate retains the final 2 KiB and enables
`LD_DEBUG=files,reloc,bindings` to locate the pre-initializer failure. The shared
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

The optional `--legacy-linker` compile flag uses GNU ld in the existing
`localhost/hearth-probe-builder:20261030` Podman image to compare its output layout.
It still compiles original objects with Clang and links only public ABI stubs.
The immutable local builder identity is recorded in the private manifest. No image
is pulled automatically; reconstruct the pinned probe builder if absent. The
container mounts only the fresh helper output, has a read-only root/no network/no
capabilities, and retains eager binding and RELRO. The exact GNU-linked comparison passed on target; this does not establish which
ELF difference caused the earlier startup crash. Executed profiles must never
be reused.

## Prepared permission comparison

Current source extends the old 29-case matrix to **36 cases**. Three permission
cases run per variant: a fresh temporary file under umask zero, a pre-existing
0644 temporary file, and an unrelated PR_Open that must retain 0666. Candidate
also injects a descriptor-permission failure and requires original settings
preservation plus successful retry. Original fresh/existing modes are expected
to be 0666/0644; corrected modes must be 0600. This is specific file permission
behavior on synthetic RAM, not a flash or full application claim.

Mode observation uses ARM EABI stat64 directly, checked against the pinned kernel
header, and verifies a known baseline file's 0600 mode first. It avoids using a
host/glibc stat structure on ARM. The parser requires all seven new rows, exact
mode/call/failure/readback evidence, the existing 29 cases, both child statuses,
log checks and completion. Older reports are historical and do not satisfy this
expanded contract. Existing stdout/stderr/report bounds remain unchanged; measured
old rows plus conservative new-row allowances fit the per-child 8 KiB budget.

The prepared privacy comparison subsequently [passed all 36 cases](../../docs/research/settings-permissions-result-2026-10-31.md)
once using source 68edfb9/profile-v2, with loader/collector zero and native USB
return. That executed profile/result must be preserved and never reused.

The combined file lab exposed a cached-report sender issue once reports exceeded
the gadget queue capacity. Current supervisor source uses the original transmit.h
state helper to preserve the byte offset across EAGAIN/EINTR and reset only after
the full footer is queued. This changes report transport only, never repeats child
execution and does not retroactively invalidate or overwrite old observations.
The larger combined profile still requires its own complete target result.
