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
