# Accepted backup, refused offline originals, 2026-11-03

One new owner-approved PTY boot loaded a fresh protected reader. Both fixed
raw/OOB passes completed. Independent verification accepted archive quality:
corrected views and spare bytes matched, the unclassified chunks matched, and
neither pass had uncorrectable chunks. Whole-chip restoration is not verified.

The next offline extraction refused `settings.config`. A checksum-valid inode
header identifies a fragment whose data CRC fails. Valid duplicates of that
fragment version also exist, as do valid final fragments. The extractor marks
any such inode damaged and refuses it rather than selecting among copies.
This does not establish that the native filesystem's active file is corrupt.
No extraction gate was changed and no inputs were substituted from an older
archive. The exact fragment metadata review remains private.

The driver exited before building a kit or arming a successor loader. No
software restart token or installer write was requested. The corrected combined
supervisor remains unexecuted. All backup, profile, source and console evidence
is preserved; no attempted phase is being replayed.

A fresh standalone protected live original-file acquisition profile has been
built and checked offline. It uses the existing bounded native filesystem read
path, without a writer or native application execution. It requires a separate
owner-ready boot and a fresh output. This is a fallback for testing the remaining
install work, not evidence that archive-only extraction supports this state.
The device was last observed in backup RAM; no loader is armed. Keep USB and
the display detached pending the next supervised decision. Both persistent file
groups still need separate scope/recovery explanations and explicit approval.
