# Restartable full-backup reader

This private profile uses the unchanged, checked full-NAND reader kernel. Its
raw external newc filesystem contains one original static ARM init and the
standard virtual filesystem directories. No native firmware executes and no
flash filesystem is mounted. Existing source, NAND write-denial, ABI and RAM
bounds remain mandatory.

The init reuses the canonical fixed two-pass exporter, including its footer and
read-only sysfs interface. Export/start failure stays idle. Only a completely
successful export reaches a nonce-bound readiness/restart endpoint; the nonce
is fresh for this profile. A returned reboot syscall is never repeated. There
is no second export, writable NAND path, arbitrary command or offset interface.

The host independently checks and seals the archive, extracts originals, builds
and validates the combined install/restore kit, then reopens the same reader's
serial endpoint. It must observe the exact post-export nonce before starting
the next loader. That loader gets its own PTY and must report live ROM scanning
before the host records restart intent and sends the one restart token.

Both the new execution and the old backup directory retain restart intent,
including uncertain partial delivery. The source cannot be reused to request
another restart. A failed or interrupted handoff never starts another loader;
a potentially started transfer is allowed its existing bounded lifetime.
Loader success alone is not image readiness: the combined image must still
produce its own checked synthetic/resource/file evidence. Both writes retain
separate explicit owner decisions.

`installer/nand_backup.py` binds this exact profile and its execution marker to
the archive's existing kernel, identity, capture, quality and source receipts.
Existing archives are not re-labelled or admitted by bypassing source checks.
Legacy non-restartable backups retain their manual handoff path.

Host C fault tests and synthetic real-PTY loader tests pass. On the measured Gen
2, the reader's software restart and the successor loader's transfer completed
without a ring press. That run's combined image then stopped before readiness,
and the supervisor was corrected; see the
[handoff result](../../docs/development/history/research/backup-install-handoff-result-2026-11-03.md).
The corrected combined image later passed from a manual boot. **The automatic
restart followed by a completed combined install, and restore, have not been
measured together.**
