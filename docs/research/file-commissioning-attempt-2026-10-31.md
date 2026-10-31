# First combined file RAM attempt and transport correction

One supervised execution used source `5ba411d` and private
`file-commissioning-ram-20261031/profile-v6`. The owner performed the restart while
the PTY-backed loader waited. All three files transferred, but collection exited
1 with a generic bounded/owner-only capture error. No original file-result.jsonl
was saved, and the matrix was not confirmed. The profile was not retried.

The profile directory was checked as mode 0700. With the loader/collector exited,
one bounded read-only observation retained 180215 bytes of the already cached
serial stream privately. It sent zero device bytes and did not restart the tests.
The trace contains nine begin markers and no end marker, with repeated prefixes
up to 20479 bytes. Partial original/candidate rows and diagnostics were visible;
no complete file-case/process/footer evidence was recovered. These are partial
observations, not a pass of the 68-case contract.

Code review identified a concrete sender defect: the nonblocking tty loop reset
its report offset to zero after a write returned backpressure or interruption.
The larger three-child report could therefore lose its tail on every cycle.
The collector also selected the first start marker, potentially concatenating
restarted prefixes into an oversized payload if a later footer arrived. The
original generic capture error did not identify which bound failed, so the exact
first rejected payload is unavailable. The cached trace and code support the
transport diagnosis without claiming a completed matrix.

The corrected raw-syscall transmitter preserves its offset across EAGAIN/EINTR
and resets only after accepting the whole cached report, including its footer.
Only cached bytes are retried; no diagnostic child is rerun. An original host
ASan/UBSan check reproduces the 20479-byte queue limit on a 30000-byte frame,
including interruptions, and requires two exact complete frames. The receiver
selects the latest start before a footer, discards restarted prefixes, distinguishes
privacy/bound errors and preserves bounded partial evidence before rejection.
Fragmented/restarted/oversized-frame regressions pass.

The wrapper now exclusively creates and fsyncs an execution-started marker before
launching the loader. It refuses marker files or symlinks even when collection
failed without a result. Profile-v6 received a retrospective marker tied to its
separate immutable attempt records; never reuse it or its reproducibility copy.
Prepared/observed/native-return records, the cached trace and decoded private
diagnostic chunks are retained separately. Creation manifests are unchanged.

After command exit the owner confirmed the native home icon, and normal USB
2464:0002 on port 1-1 was independently observed. No persistent provisioning,
actual settings change, backend enrollment or native application test occurred.
The diagnostic kernel has no flash/physical-network support; existing bootstrap
hardware/write-free/recovery limitations remain unchanged.

Fresh corrected profile: `private/file-commissioning-ram-20261031/profile-v7`;
separate `profile-v7-repro`. Helpers: `build/file-commissioning-ram-20261031/helpers-v5`
and `helpers-v5-repro`. Seven artifacts and full RAM inventories reproduce:
rootfs 11045344 bytes, image 6034056 bytes. Workload, kernel, bootstrap and native
libraries are unchanged. Current host validation passes make check and 569 tests,
with five unchanged optional integration skips. No corrected profile is executed
or loader armed. A new owner-timed attempt is required to establish its result.

## Second attempt: complete transport, wrong file-helper dispatch

A fresh owner-timed run used source `7c1572c` and profile-v7. The corrected sender
and receiver retained a complete 20816-byte/77-row report, including the completion
record. The collector correctly rejected the aggregate result. Both original and
standalone candidate processes exited zero, and their complete 36-case behavior,
binding/canary and full-stream log evidence independently matches the storage
contract. The exact standalone GNU candidate is therefore measured on RAM, with
full native application integration still unverified.

The file process exited 109 without any file-case rows. Review found that the
supervisor set argv[0] to /file-test but still passed a literal /settings-test to
execve. It launched the settings helper with the files argument, which that helper
rejected immediately. This is a supervisor dispatch mistake, not a measurement
of file-transaction behavior. No combined 68-case pass is claimed.

The original full result is immutable. A separate private component-evaluation
record identifies its source digest, retains the original aggregate false result
and explicitly records the derived completion envelope used to validate only the
two successful storage processes. It does not rewrite or promote the failed
aggregate report. Prepared/observed/native-return records remain separate.
The owner confirmed home icon and normal USB was independently observed afterward.
No loader remains armed or persistent provisioning installed.

The corrected execution adapter always uses the program declared in argv[0] and
passes that same argv/environment to the raw exec backend. An original host
sanitizer check injects an execution callback and verifies settings/file program
selection plus unchanged arguments/environment and invalid-input rejection.
File-process failures now have a specific collector message. Test bodies,
standalone candidate, kernel, bootstrap and native runtime libraries are unchanged.

Current fresh profile: profile-v8 and separate profile-v8-repro under the same
private parent. Helpers: build/file-commissioning-ram-20261031/helpers-v6 and the
separate -repro. Seven artifacts/full inventories reproduce: rootfs 11045344,
image 6034042 bytes. Make check and 570 host tests pass, five unchanged optional
skips. A new owner-timed run is needed for the unmeasured 32 file cases; no new
attempt is armed automatically. Never reuse v6, v7 or their reproduction copies.
