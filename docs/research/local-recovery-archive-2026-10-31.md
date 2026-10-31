# Owner-selected local recovery archive

The owner chose one local backup on this PC and authorized changing the hardware
plan accordingly. No additional drive, remote destination or second copy is a
prerequisite for this unit's bounded scratch recovery experiment. We selected
an unencrypted archive with owner-only permissions. This accepts loss of the
backup if the PC's storage fails and exposure to host root/owner compromise.
It is a local archival copy, not disconnected or independent storage.

`private/local-recovery-20261031/recovery.tar` contains 37 ordinary files:
both original full raw/OOB captures, both independently corrected data views,
acquisition/ECC/layout/padding records, original machine-local analysis recipes,
the local public BCH implementation/library, and relevant source pins/review notes.
The four large input digests were freshly checked against the original capture
and decoding records before archiving. Every archived member was read back in
full and matched its source length and SHA-256; the archive and private manifest
were fsynced, followed by the containing directory. The archive contains no
executable-mode members and was neither extracted nor executed for verification.
The directory is 0700 and files 0600. Contents, identifiers, private ECC mask and
digests remain private and excluded from Git. Original inputs are unchanged.

The recipe is `build/archive-local-recovery-20261031.py`; it refuses an existing
output directory. The manifest records the per-file digests and archive digest.
Preserve this archive and manifest; do not replace them with later generated
working files. This is not proof of flash restoration or a complete portable
recovery tool. The older capture's raw passes differ in correctable data bits;
their independent corrected views agree. Both raw originals remain necessary.

A first persistent experiment still needs fresh, matching reads of the exact
selected block, a durable private region backup before write enable, independent
programmed-ECC validation, exact restoration checks, and advance notification of
the concrete operation and remaining power-loss/recovery limits. No writer has
executed and no firmware installation or HVAC operation is authorized by creating
this archive.
