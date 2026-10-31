# Native settings persistence and log-upload review

Offline static review of privately recovered Display-2.6 / 5.9.4-5 files,
continuing the [credential review](native-bootstrap-2026-10-30.md). No device
operation, target firmware execution, installation or network upload occurred.
Original captures/configuration/binaries are unchanged. Native code, decompilations,
binary hashes and generated configuration remain private.

## Settings storage

`nlSettings` is implemented in the recovered `libnlappcore.so`. The client
allocates the base settings class, whose `DidSetValue` hook is a no-op.
The string setter locks the settings hash table, updates its entry, marks it
dirty, unlocks and invokes that hook. It does not itself write the file.
The credential-header helper's two separate setters therefore are not a durable
rotation acknowledgment. Other client paths invoke `Write`, including UI and
state changes; no bounded credential-specific flush/readback guarantee was
established. Immediate transport use and successful persistence are separate.

The configured user-settings path is `/nestlabs/etc/user/settings.config`.
The writer serializes escaped values into XML `s` elements with `key` and
`value` attributes. No encryption/hash transform appears in that storage writer;
the special handling of secrets in startup settings logs is a different path.
File ownership/permissions, effective process umask and mounted filesystem
behavior still require validation. The writer requests mode 0666 for its
temporary file; this alone does not determine its effective permissions.

The reviewed normal write sequence is substantive: create/truncate a temporary
file, write a header, enumerate entries, write a footer, sync and close the file,
rename it over the destination, then open/sync/close its parent directory.
This is evidence of an intended durable whole-file replacement, rather than
individual in-place setting writes. It is not a tested power-loss guarantee.

Two error paths prevent treating that sequence as verified persistence:

- The entry serializer detects a short/failed `PR_Write`, logs its key and
  escaped value, then returns zero. The outer writer does not accumulate that
  entry's failure into its result. If later footer/sync/close operations succeed,
  the incomplete temporary file can reach the rename path. Header/footer write
  checks do not prove all entry writes succeeded.
- After rename, a failed parent-directory sync sets an error result. If closing
  the directory succeeds, the writer nevertheless clears the dirty flag. A
  caller may receive an error while a subsequent write skips a clean object.

Both are corroborated by ARM disassembly and Ghidra control flow. No error was
induced on the real thermostat. We did not patch this writer or replace it with
an unvalidated storage implementation. A later correction needs synthetic fault
injection for entry short writes, file sync/close, rename, directory open/sync/close,
dirty-state retry, and interrupted two-key rotation, followed by target validation
under the existing recovery gates.

## Credential log paths

The settings-entry error log is a second credential disclosure path. The earlier
private client candidate skips the changed-credential message only; it does not
remove this library message, prevent failed writes, or establish a complete log
audit. Merely silencing the library error would leave its failure propagation
problem unresolved.

`nlLogWithComponent` routes to generic text logging. The log manager filters
against a priority threshold, formats the supplied arguments, then writes via
the configured file manager. It falls back to stderr on relevant manager/file
errors; file flags can also request stderr copies. There is no key-aware redactor
in this reviewed generic text path. A threshold suppressing a message is not a
replacement for removing credential-bearing arguments.

The recovered configuration names a generic log root beneath
`/nestlabs/var/log/nlclient`, with rotation configured. A client uploader obtains
queued log files from the log manager and creates post-file requests using the
upload URL. Its request builder can enable the active Basic credentials and
verbose web debugging. Completion handles successful upload/deletion and some
failure cases. No actual destination, transfer, persisted secret or effective
runtime logging configuration was measured.

The `uploadlogs` configuration flag is enabled in the recovered file. Disassembly
and decompilation trace it through client initialization into the uploader's
enable field; the queue sender checks that field before obtaining/sending files.
Disabling this known sender does not disable local logging, remove existing
logs, or prove that crash/support/metrics/other outbound paths are disabled.
Do not delete logs as a substitute for reviewing and preserving private evidence.

## Offline hardening change

`firmware.harden.stage` now prepares `uploadlogs=0` alongside the local
registration endpoint. Its configuration editor requires exactly one reviewed
`/config/a` upload flag and `/config/cloud/a` registration entry. Missing,
duplicate, misplaced, malformed or unsupported entries fail before creating an
overlay. Comments do not count as settings. DTD/entity declarations are refused;
input size and nesting are bounded.

The editor changes only the two attribute-value byte spans, preserving every
other byte, comment and unknown setting. It accepts the recovered config and
produced a separate owner-only private review copy. The synthetic demo now uses
the same config structure, and the inert review plan also lists upload disabling.
No apply/flash operation was added. The four-file replacements remain partial
and non-bootable; they do not include the private TLS/client candidates or a
storage correction.

Fifteen new tests cover malformed/ambiguous settings, DTDs, parser bounds and
byte preservation. Existing artifact tests also verify deterministic archives,
private-file exclusion and repeatable replacement files. `make check` passed;
189 host tests passed with two optional broker/container tests skipped. Those
integration tests were not repeated for this offline artifact change.

Ghidra completion markers and fresh output counts were checked across bounded
runs. One mistakenly selected interior address yielded a partial function export;
it was excluded from the evidence. The complete containing uploader function and
its actual initializer were reviewed separately. No decompiled firmware was run.

Next: finish native entry/revision/subscription mapping and design the storage
failure/commissioning tests. Credential installation, native transport compatibility,
target TLS, restoration and HVAC behavior remain unverified.

## Offline follow-up and prepared fault experiment

The separate [settings RAM diagnostic](../../firmware/settings_probe/README.md)
is now prepared and integrity-checked, but **unexecuted**. It reuses the successful
TLS kernel/bootstrap and unchanged baseline libraries, adds synthetic `/state`
files, and calls only the reviewed native base settings class. One boot measures
twelve normal/error cases plus fresh-object readback and dirty-state retry.
It does not mount flash, load original settings, start nlclient or fix the writer.
The owner is offline; no loader is armed. Host instrumentation checks do not count
as native writer measurements.

Six exported method addresses/extents, constructor dirty/writable initialization,
48-byte allocation, getter/setter return paths and non-deleting destructor were
checked offline. The setter returns zero on its normal successful path. This ABI
review narrows the harness; it does not make its eventual execution observational
or establish storage durability. The custom kernel's RAM filesystem uses no-op
sync operations; injected failures measure application response, not real flash
or power-loss behavior.

A further ARM/Ghidra review of `nlConfig::AddEntry` finds another value-bearing
allocation-error log, beyond the credential-change and entry-write messages
already traced. On an existing-value update, the old value is freed before a new
copy is allocated. If that allocation fails, the reviewed error path returns
without replacing the hash entry. This suggests a dangling-value hazard and
requires a separate focused allocation-failure review/test; no such failure has
been induced and no native code was patched. The current I/O diagnostic does
not inject allocator failures. Three complete Ghidra exports and independent ARM
disassembly remain private. An initial export invocation lacked the required
existing output directory; it was not counted as a successful review, and the
corrected run's completion marker and outputs were checked.

The earlier logging-removal candidate still addresses only its one client log
block. Do not commission actual credentials on the basis of silencing that log,
disabling the known uploader or receiving a successful loopback TLS matrix.


The [second supervised RAM result](settings-probe-result-2026-10-31.md) now
completes all twelve cases and confirms both entry-failure propagation and
directory-sync/retry defects in the original native library. Native startup
returned afterward. This supersedes the experiment's preparation-only status
above; the historical static findings and allocation-failure limits remain.
Nothing was installed or corrected in the native writer.
