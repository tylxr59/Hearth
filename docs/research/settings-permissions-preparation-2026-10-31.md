# Native settings privacy preparation

The next concrete commissioning issue is future file permissions. The native
writer requests 0666 for its temporary file. Merely installing settings at 0600
would not keep later replacements private, and relying on an unmeasured process
umask is insufficient. The existing 29-case correction did not address this.

The original correction now identifies the same exact temporary file within its
per-thread native writer scope, requests owner-only creation bits and restricts
the actual opened descriptor to 0600 before serialization. This covers both new
and pre-existing temporary files. Permission-setting failure closes the handle,
fails through the original open-error path, preserves the destination and keeps
dirty retry. Unrelated opens and the process umask remain unchanged. It retains
the native serializer, writer, locks, control application and all hardware logic.

The adapter obtains the native descriptor through PR_FileDesc2NativeHandle and
calls fchmod. The public NSPR declaration/type is pinned in the existing source
record; required exports were checked in the acquired native libraries without
executing them on the host. No proprietary binary, instruction patch, hash,
credential or identifier is added to source. This does not assert public-source/
native-binary correspondence or full application compatibility.

A fresh GNU-linked RAM profile is prepared at the owner-only ignored path
`private/settings-permissions-probe-20261031/profile-v2`; its separate reproducible
profile is `profile-v2-repro`. Original helpers are under
`build/settings-permissions-20261031/comparison-v1` and the separate `-repro`.
Seven boot/profile artifacts and complete RAM inventories match between fresh
builds: rootfs 11026276 bytes, image 6020604 bytes. The previously validated
kernel/bootstrap and 34 native baseline libraries are unchanged. No profile was
executed, loader armed or device file changed during this preparation. Earlier
preparation records remain private; do not overwrite them or use older executed
profiles as retries.

The matrix now requires 36 cases: the prior 24 I/O plus five allocation/alias
cases, and seven permission cases. Both variants exercise fresh temporary files
under umask zero, pre-existing 0644 temporary files and unrelated opens. Original
fresh/existing modes must be 0666/0644; candidate must yield 0600. Candidate also
injects one fchmod failure, requires old values intact and then successful retry.
Mode observation uses the pinned Linux ARM EABI stat64 layout/syscall with an
aligned oversized buffer, and checks a known 0600 baseline before any case.
Existing process statuses, bindings, canaries and full-stream log checks remain
mandatory. The parser rejects missing/duplicate cases, wrong mode, bool-as-count,
uninjected failure, failed retry, changed unrelated modes and old case manifests.

The synthetic helper runs only on RAM files as an unprivileged UID. No actual
settings, credentials, nlclient/osm, flash interface, physical network or RTC is
included. Existing 8 KiB stdout/2 KiB diagnostic and 32 KiB report limits remain;
observed old rows plus conservative new-row allowances fit those limits.

Host validation passed Ruff lint/format, Bandit and the full default suite:
502 passed, five optional broker/container skips. The focused original-host
NSPR/sanitizer, cross-compilation, parser and artifact checks passed 38 cases.
One full-suite run found the synthetic artifact fixture missing the new case
count; the fixture was corrected and all checks rerun successfully. Runtime
backend/container code did not change, so broker tests were not repeated.
Offline wrapper checks pass and open no device.

Next: obtain owner restart readiness, notify and arm one PTY-backed execution
under existing authorization, with the base detached and USB connected. Use only
the final fresh profile, never automatic retry. Preserve its private result and
attempt record whether it passes or fails. After command exit confirm native
home icon and normal USB return. A pass would establish this bounded permission
behavior, not file installation, flash recovery, full startup or HVAC operation.
The actual filesystem installer/rollback and full native integration remain
pending; this diagnostic does not authorize applying review replacements.
