# Fixed network cleanup and legacy update

This is a separate, fixed-plan root0 installer and matching restoration path.
It does not add HVAC commands, alter control loops or expose arbitrary paths.
The legacy nine-file writer retains its original limits and default behavior.

The public kit path adds a separate **three-file cleanup** format. It changes
only `nestlabs/sbin/nlclient`, `usr/sbin/connmand` and `etc/connman/main.conf`.
The nine-file commissioning phase owns the client configuration in full, so
these two phases have no overlapping target. No projected or synthetic original
snapshot is substituted for acquired custody. The four-file backup can retain
its original client config, but the cleanup plan/action/archive selects only
the first three files. The compiled action has no client-config path.

The legacy four-file transition remains available for the earlier measured
address migration. It is not a requirement that new users choose addresses of
matching string length. New plans bind their target count/format and produce a
matching install/restore pair, resource evidence and exact completion mask.
Unknown counts or mismatched receipts/scopes refuse before a commit.

Both scopes pass the host transaction/fault/restore suite and original ARM helper
compilation. The three-file action has not performed persistent hardware writes; source/host tests
do not authorize a persistent use or establish physical restoration.

The reviewed changes replace the two observed Google connectivity-probe slots
with the HA local204 URL, change ConnMan's preferred fallback time server to the
owner-selected NIST service, and move stored registration to the IoT HA address.
Every input has a fresh complete private backup; candidate length/mode and all
bytes outside each reviewed equal-width span remain unchanged.

Original binaries are opaque non-executable DATA in root-only RAM files, never
host executables or linker inputs. The action maps originals read-only and derives
candidates using private copy-on-write mappings. Complete SHA256/span checks run
before candidates are sealed read-only. This avoids two large independent RAM
copies on the 64MiB unit. Only original helpers and the verified native libc/loader
pair execute in the RAM image; no native control application runs there.

The root0-only kernel rejects user/config and all other flash regions. It retains
hardware WP, explicit plan/backup binding, forced NONE writes and the separate
NONE/ZERO active-fragment audit. Both root descriptors refer to the same root0;
the second holds its plan-specific recovery archive. Old recovery archives remain.

The supervised flow is:

1. Owner confirms primary native firmware and readiness. Arm a fresh one-use
   PTY loader and prompt for the manual restart; never retry automatically.
2. Run41 memory/hash/stream cases and20 isolated RAM filesystem cases. The host
   acknowledges only their complete, zero-status report. ACK launches a root
   read-only preflight, never a persistent commit.
3. Check all three/four selected complete originals, modes, plan/backup identity and resource bounds.
   Require at least24MiB free RAM. Install space reserve is three times total
   file bytes plus2MiB; restore reserve is largest file plus4MiB. JFFS2 available
   space includes reclaimable dirty bytes, so the check is not an allocation
   guarantee. Repeat the guards immediately before opening the write window.
4. Pause for a separate local commit/abort, bound to the live execution. Record
   intent durably before sending any commit bytes. No automatic decision/retry.
5. Use the existing journal/backups/temporary/sync/rename transaction. Release and
   unmount, seal WP, remount read-only, then verify complete bytes/modes and live
   fragment encoding of all selected files, backups and journal.
6. Restart only after checked evidence says it is safe. An incomplete persistent
   attempt requires review with USB power maintained, not a blanket restart.

Prepare and check a matching independent restore image before installation.
An interrupted transaction can leave original files with stock compressed
fragments; the strict final NONE/ZERO audit may conservatively refuse safety even
if original bytes match. Do not bypass that audit or install unsupported codecs.
Whole-firmware and power-loss recovery, and this large-file NAND restoration,
remain unverified until separately measured. Local archive loss remains possible
under the owner's accepted one-machine recovery exception.

`python -m firmware.network_writer.kernel` stages/checks offline kernel builds.
`python -m firmware.network_writer.profile` packages/checks private actions.
`python -m firmware.network_writer.run boot INSTALL RESTORE` checks offline only.
The explicit `--execute-supervised-network-update` flag arms the owner-timed loader;
`commit OUTPUT --action 1` is a separate persistent decision, never implied by boot.
No published image contains owner data, native firmware bytes or credentials.

The internal `preflight_only=True` profile is an install-scope diagnostic, not an
installer retry. Its compiled action has no READY/commit parser and always takes
the protected cancellation path after the same resource/file checks. The host
rejects decision events or any persistent activity for that profile. It reports
bounded RAM/space counters; diagnostic41 identifies the unchanged memory gate and
42 the unchanged space gate. Existing reports without counters remain supported.
Use fresh one-use profiles and reviewed prior custody; never rerun an attempted
image or interpret this diagnostic as installation success.


The normal kit can nominate an archive spec from its checked full-NAND view;
this is a candidate, never authority to reuse an inode. Only an exact, fully restored
network4 archive matching all current cleanup3 originals is eligible. It adds
verified references to the same original inodes under a fresh plan's journal;
source names/data/journal remain intact. Exact link counts, inode/device identity,
permissions, full hashes and encoding checks remain required. The install space
bound is replacement staging plus one largest rollback temporary plus2MiB;
copy-based installation and the largest-plus4MiB restoration bounds are unchanged.
The shared matrix adds20 synthetic cases before actual-file preflight. The normal
wizard now runs a separate no-commit combined-capacity profile before core9.
It reserves all new root0 core staging plus128KiB metadata allowance, in addition
to the network budget. Core9's backup/user-config space has its own preflight.
The compiled capacity binding is checked on the host and read at runtime; it
cannot be enabled on a commit-capable profile. A refused or incomplete check
starts neither write phase. Checked zero-write evidence and matching acquisition
custody are required for the direct RAM handoff to core9. This path has host/ARM
coverage but still needs supervised hardware validation before end-to-end claims.
