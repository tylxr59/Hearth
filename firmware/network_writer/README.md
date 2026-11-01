# Four-file network update

This is a separate, fixed-plan root0 installer and matching restoration path.
It does not add HVAC commands, alter control loops or expose arbitrary paths.
The legacy nine-file writer retains its original limits and default behavior.

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
3. Check four complete originals, modes, plan/backup identity and resource bounds.
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
