# Protected installer input acquisition

This original reader combines the existing nine-file and four-file snapshots
with four bounded top-level regular-file exports: `/lib`, `/usr/lib`, `/nestlabs/lib` and
`/nestlabs/sbin` from the protected root0 view. It acquires the user's existing
native libraries as private data for a future local kit builder. Nothing from
these exports belongs in a release archive or source checkout.

The unchanged protected snapshot kernel asserts NAND write protection, denies
mutation callbacks and has no writable flash mount, physical networking or
native application execution. The reader opens regular files/directories only,
does not follow symlinks, requires read-only JFFS2 directories and refuses partial
files or exceeded bounds. Symlink targets are not recreated on the host.

Each of the four groups permits at most256 files and512 scanned entries,
8MiB per file and16MiB per frame. A fresh32-byte session binds the ordered
snapshots and groups. The host preserves bounded raw frames before decoding,
requires matching overlapping files and an exact completion marker, then writes
the corpus and two independently verified snapshot archives below a fresh private
directory. Files are0600 and directories0700; original modes are metadata only.
Subdirectories such as kernel modules and locales are skipped; the native
dependency resolver uses the direct files' names/SONAMEs. No acquired program
is run on the host. This is selected-file custody, not a
whole-firmware backup or verified restoration procedure.

Prepare and check offline from an existing verified protected kernel build:

```sh
python -m firmware.acquisition.profile package \
  --base build/protected-snapshot \
  --build build/acquisition-new \
  --output private/acquisition-profile-new
python -m firmware.acquisition.profile check private/acquisition-profile-new
```

After verifying the diagnostic identity against the HA commissioning bundle,
the guided frontend can run one explicitly confirmed acquisition:

```sh
hearth acquire --session private/my-nest \
  --profile private/acquisition-profile-new --disk /dev/REPLACE
```

Use a terminal/PTY. Keep USB connected and the display detached from the base.
The frontend prompts before arming; only after the loader reports scanning,
hold the ring for10 seconds, release, then press/release once. There is no
automatic boot or collection retry. After the host command exits, use the same
manual sequence to return to native startup and confirm the screen/USB identity.

Host protocol, storage and original C sanitizer fixtures pass. The public-source
kernel/bootstrap and helper build pass, with eight reader artifacts reproducing.
The corrected top-level image completed a supervised owner-unit run:136 private
files and34 native dependencies verified, followed by confirmed native UI/USB
return. Earlier traversal-bound failures remain preserved privately. See the
dated observed validation record. Per-device install/restore kit assembly and
a pristine stock-unit installation still remain.
