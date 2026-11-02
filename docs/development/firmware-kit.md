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

The public reader pipeline is now automated by `hearth sources`, `build-reader`
and `acquire`. A fresh end-to-end source build passed offline, including the host
loader's USB simulation. Eight acquisition artifacts reproduce against its
protected base. The rebuilt bootstrap code/data match the earlier build, with
only version timestamps differing. A supervised corrected reader run acquired
both snapshots and four top-level groups, verified136 private files and the full
34-library closure, and returned to native UI/USB. The existing owner unit was
already commissioned; this is not a stock installation or completed write kit.

`hearth check-inputs` independently reconstructs all saved frames, checks the
completion marker, exact corpus/index equality and both custody archives, then
resolves native ELF dependencies by filename/SONAME. It creates no host aliases
and executes no acquired code. Symlink-only names therefore need not be exported.

The remaining preparation stages are:

1. `installer.sources` fetches pinned public Git commits and hash-checks the
   historical compiler. `installer.build` builds the bootstrap/protected kernel
   in a rootless, isolated container, then `firmware.acquisition` packages the
   original bounded reader. `hearth acquire` requires a separately confirmed,
   owner-timed read-only boot and preserves all captured native files privately.
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
New kit preparation uses the disjoint three-file cleanup format: native client
probe, ConnMan probe and ConnMan NTP settings. The nine-file phase owns client
configuration. This avoids changing the expected original between phases. The
old four-file equal-width address migration remains a separately bound legacy
format, not a user address-length restriction. Both scopes pass host fault and
restore fixtures; the new three-file scope still needs target measurement.

Writer packaging can now obtain the verified libc/interpreter pair directly
from acquisition custody rather than requiring an old TLS research profile.
The public GNU storage-shim build using the new builder image produced exactly
the bytes currently installed on the owner's measured unit. Acquired code was
not executed on the host or linked as a host input.

A changed settings serialization can invalidate a snapshot even when values look
identical. Preserve the failed zero-write attempt and use the reviewed bounded
RAM handoff path when appropriate. Never weaken exact original-byte comparison.

## Remaining public-installer work

Per-device replacement construction, end-to-end disjoint phase coordination,
and reproducible install/restore kit
orchestration remain blockers for a turnkey stock-unit release. A new user's kit
cannot be synthesized from the development owner's ignored directories. This
restriction is explicit in the installer documentation and release metadata.
