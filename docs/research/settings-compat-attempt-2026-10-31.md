# First storage correction comparison attempt

The owner supervised one experimental RAM boot using source `6f77863` and the
fresh private `profile-candidate-v2` profile. The loader transferred all three
files and exited zero. The collector saved its bounded private report, then
correctly exited one because the matrix was incomplete. No automatic retry ran.

The 9176-byte, 33-row report contains all twelve original I/O cases and the
original helper's zero process status. It reproduces both entry-write failures
and the directory-sync retry defect. The streaming matcher found two synthetic
secret-log patterns and the expected unrelated variadic-log marker. These are
synthetic settings in RAM, not the unit's settings or credentials.

The candidate process terminated with SIGSEGV (raw wait status 11), before any
candidate case or helper-completion row. It emitted no captured diagnostic rows.
This does not validate any of the candidate's corrections, allocation behavior,
logging or native application integration. Host checks and successful loading of
the original library did not establish that the ARM adapter worked on target.

The original result and creation manifest remain unchanged. A separate private
attempt record retains result identity and process metadata. After the command
exited, the owner performed the full ten-second hold/release/single-press sequence
and confirmed the home icon; normal Nest USB was independently observed. Nothing
was installed, and restoration and HVAC operation remain unverified.

Next, prepare value-free phase diagnostics to locate the crash before requesting
another supervised RAM boot. Phase markers must not include paths, pointers,
settings, credentials or native log contents. Preserve this failed profile rather
than rerunning it or treating its baseline rows as a passing comparison.

## Phase-marker attempt

A second supervised attempt used source `af32cd5` and a fresh private
`profile-phase-v1`. All three files transferred; original baseline again completed
all twelve cases with zero status. Its captured fixed phase markers reached main,
library/binding setup, construction, initialization and save. The candidate again
terminated with SIGSEGV (raw wait status 11), with no phase marker, case or helper
row. The saved report is again 9176 bytes/33 rows and the collector exited one.

This narrows the failure to startup before the candidate initializer/main can
emit their first marker; it does not establish the precise relocation, mapping or
constructor cause. No speculative linker change has been treated as a fix.
A second immutable private attempt record preserves the result identity. The owner
reported completing the manual restart after command exit and normal USB was
independently observed. No automatic retry or persistent installation ran.

The next prepared diagnostic adds `LD_DEBUG=files,reloc` only to the candidate
child. Its fixed 2 KiB diagnostic cache retains the final window, with explicit
previous-byte discard counts; the original still retains its first window. Both
streaming log matchers inspect every byte before either cache policy. An original
host sanitizer harness checks final-window contents across chunk sizes and refusal
at the discard limit. This changes diagnostic visibility, not any case acceptance
condition. Loader diagnostics remain private; no actual settings/native app are
introduced and flash/network/clock restrictions remain unchanged.

## Loader-relocation attempt

A third supervised attempt used source `21e2e64` and fresh private
`profile-loader-v1`. The loader again transferred all three files and exited zero;
the collector saved 14247 bytes/50 rows and exited one. Original baseline still
completed twelve cases with zero status. The candidate's final 2 KiB diagnostics
end at relocation processing of `libhearth-settings-compat.so`, after dependencies
and the fault module. It again exited through SIGSEGV before initialization.
The precise failing relocation/symbol remains unknown; the next fresh profile
adds the loader's binding diagnostics, with identical limits and case gates.

Result, decoded private diagnostic tail and attempt-3.json are preserved. The
owner reported restart done after command exit; normal USB was observed. No
persistent write or automatic retry occurred. Do not rerun any executed profile.
