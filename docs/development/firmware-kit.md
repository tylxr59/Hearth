# Device-bound firmware kit

How `build-kit` turns one unit's acquisition and HA bundle into checked install
and restore images. Terms used below:

| Term | Meaning |
| --- | --- |
| **commissioning9** | Phase 1: nine files covering HA endpoint/settings, TLS trust (CA/CRL, credential) and startup |
| **cleanup3** | Phase 2: three files covering the native client probe, ConnMan probe and ConnMan NTP settings |
| **capacity preflight** | A no-commit run that proves root0 has space for both phases before either writes |
| **profile** | A single-use, plan-bound RAM image (action 1 = install, action 2 = restore) |
| **custody** | Receipts that bind the saved originals to the acquisition session |

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
and `acquire`. A fresh end-to-end source build passed offline, including the
host loader's USB simulation. Eight acquisition artifacts reproduce against its
protected base. The rebuilt bootstrap code/data match the earlier build, with
only version timestamps differing. A supervised corrected reader run acquired
both snapshots and four top-level groups, verified 136 private files and the
full 34-library closure, and returned to native UI/USB. That unit was already
commissioned, so this reader pass is not evidence of a stock installation.

`hearth check-inputs` independently reconstructs all saved frames, checks the
completion marker, exact corpus/index equality and both custody archives, then
resolves native ELF dependencies by filename/SONAME. It creates no host aliases
and executes no acquired code. Symlink-only names therefore need not be
exported.

The preparation stages are:

1. `installer.sources` fetches pinned public Git commits and hash-checks the
   historical compiler. `installer.build` builds the bootstrap/protected kernel
   in a rootless, isolated container, then `firmware.acquisition` packages the
   original bounded reader. `hearth acquire` requires a separately confirmed,
   owner-timed read-only boot and preserves all captured native files privately.
2. `provisioning.file_backup` verifies and preserves snapshot custody.
3. `installer.replacements` coordinates `provisioning.native_settings`,
   `native_startup`, `native_network`, `native_tls` and the GNU storage shim to
   prepare bounded replacements from originals.
   No proprietary original or patched binary is distributed by Hearth.
4. `provisioning.file_capsule.prepare` binds exactly nine files and a
   plan-specific rollback archive. Use the separately observed supported native
   selection.
5. `firmware.file_writer.prepare` binds the kernel to that exact plan/receipt;
   compile from the pinned public sources with the rootless builder.
6. `firmware.file_writer.compile` creates the bound action helpers.
7. `firmware.file_writer.profile.package` creates action 1 install and action 2
   restore images. `checked_pair` revalidates their source, custody and
   equality.
8. The guided CLI additionally checks the exact bundle
   credential/CA/CRL/endpoint before arming the writer. Fresh real files must
   still pass the device preflight.

The separate network-file update has its own source/backup/profile boundaries;
it is not silently included by pretending the nine-file plan covers other paths.
New kit preparation uses the disjoint three-file cleanup format: native client
probe, ConnMan probe and ConnMan NTP settings. The nine-file phase owns client
configuration. This avoids changing the expected original between phases. The
old four-file equal-width address migration remains a separately bound legacy
format, not a user address-length restriction. Both scopes pass host fault and
restore fixtures. The three-file scope has been installed and verified on the
measured unit as part of the combined install; its restore has not run on
hardware.

Writer packaging can now obtain the verified libc/interpreter pair directly
from acquisition custody rather than requiring an old TLS research profile.
The public GNU storage-shim build using the new builder image produced exactly
the bytes currently installed on the owner's measured unit. Acquired code was
not executed on the host or linked as a host input.

A changed settings serialization can invalidate a snapshot even when values look
identical. Preserve the failed zero-write attempt and use the reviewed bounded
RAM handoff path when appropriate. Never weaken exact original-byte comparison.

## Public orchestration and remaining measurements

`installer.kit` now coordinates the two source-built kernels, private native
library closure, helpers and four install/restore profiles. `check-kit`
reconstructs the replacements against the original acquisition and bundle,
checks source recipes, and verifies both bound profile pairs. Existing or
partially commissioned units are refused before replacement compilation.

New kits are single-boot (`single_boot` in `kit.json`). `installer.workflow`
runs one [`install_sequence`](../../firmware/install_sequence/README.md) image:
capacity, then commissioning9, then cleanup3, each write with its own `INSTALL`
confirmation. Commissioning must produce a complete, encoding-verified result
before cleanup is offered. Backup-to-install and acquisition-to-install
handoffs require sealed prior execution, custody, completion and known USB
identity; they do not infer success from an uploaded image. Restoration uses
separate standalone boots in reverse order. No automatic retry happens. Kits
without `single_boot` keep the older per-phase path, and the low-level
single-pair commands remain development tools.

The guarded TLS recipe changes only the callback-argument instruction after
validating the exported function, ARM call/PLT/GOT relocation and imported
`SSL_CTX_set_verify` symbol. The recipe uses the public
[Arm ELF ABI](https://github.com/ARM-software/abi-aa/blob/main/aaelf32/aaelf32.rst)
and an original synthetic ELF fixture; no vendor instructions or binary hashes
are included in public source. Applied privately to the owner's preserved
original, it reproduces the currently installed reviewed candidate exactly.

The complete stock workflow, including the automatic backup-to-install restart,
still requires target measurement. Review-only composed fixtures can exercise
source builds offline; their kit marker makes the supervised workflow refuse USB
access. Such fixtures are not fresh stock acquisitions and cannot establish
installation or recovery. USB port/ACL portability and a
configuration-preserving uninstall remain release gaps. Exact old-settings
restoration must refuse later unknown native changes. A new user's kit must come
from that user's own acquisition, never the developer's ignored directories.
Whole-firmware and power-loss recovery remain unverified.
