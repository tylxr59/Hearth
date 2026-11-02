# Device-bound firmware kit

The public USB frontend runs the existing checked writer. It does not replace
its plan binding, image-source checks, original-file custody, RAM selftests,
read-only preflight, explicit commit, encoding audit or matching restore image.

## Inputs that must come from this unit

- Filtered native identity/partition/version and a fresh protected snapshot.
- Original fixed files plus verified custody receipts/session binding.
- The unit's native loader/libraries needed for the RAM action, kept private.
- Its new HA commissioning bundle; never another owner's device credential/CA.

## Source preparation stages

These are real public modules, but not yet a one-command acquisition pipeline:

1. `firmware.probe`/`firmware.file_snapshot` stage the pinned public RAM reader
   and perform a notified, owner-timed read-only boot.
2. `provisioning.file_backup` verifies and preserves snapshot custody.
3. `provisioning.native_settings`, `native_startup`, `native_network` and the
   reviewed native TLS/logging edits prepare bounded replacements from originals.
   No proprietary original or patched binary is distributed by Hearth.
4. `provisioning.file_capsule.prepare` binds exactly nine files and a plan-specific
   rollback archive. Use the separately observed supported native selection.
5. `firmware.file_writer.prepare` binds the kernel to that exact plan/receipt;
   compile from the pinned public sources with the rootless builder.
6. `firmware.file_writer.compile` creates the bound action helpers.
7. `firmware.file_writer.profile.package` creates action1 install and action2
   restore images. `checked_pair` revalidates their source, custody and equality.
8. The guided CLI additionally checks the exact bundle credential/CA/CRL/endpoint
   before arming the writer. Fresh real files must still pass the device preflight.

The separate network-file update has its own source/backup/profile boundaries;
it is not silently included by pretending the nine-file plan covers other paths.
The public stock-device pipeline must eventually orchestrate both scopes and
fresh acquisition without changing their protections.

A changed settings serialization can invalidate a snapshot even when values look
identical. Preserve the failed zero-write attempt and use the reviewed bounded
RAM handoff path when appropriate. Never weaken exact original-byte comparison.

## Remaining public-installer work

Automatic source acquisition, per-device replacement construction and reproducible
kit orchestration remain blockers for a turnkey stock-unit release. A new user's
kit cannot be synthesized from the development owner's ignored directories. This
restriction is explicit in the installer documentation and release metadata.
