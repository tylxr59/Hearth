# Protected encoding audit

This data-only diagnostic derives the measured write-denying snapshot kernel and
adds only the existing read-only JFFS2 inode-encoding ioctl. The NAND write-denial
source, hardware WP guard, configuration and bootstraps remain checked against
the protected parent. It has no writer, writable flash mount, commit token,
native application, shell or control-channel API.

The static original supervisor takes the nine-file snapshot and reports encoding
status for those fixed paths plus the owner's legacy rollback originals/journal.
Canonical commissioning paths are reused. All files are opened read-only with
NOFOLLOW/NONBLOCK; only RAM directories, virtual mount state and USB output change.
The report is not a full-NAND acquisition or an automatic recovery action.

The host requires the same original capsule and an exited protected diagnostic
whose snapshot matches every original byte and metadata field. Two bounded,
session/CRC-bound frames must complete. Selected-file and archive encoding results
remain distinct so an archive fault cannot be described as a native-file fault.
The source/config/image/derivation/inventory and RAM load bounds are checked before
one owner-timed ROM boot. Output remains private; no retries or native boot follow
automatically. A reproduced profile is review-only and must never also be run.
