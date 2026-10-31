# Protected read-only JFFS2 file snapshot

A separate experimental RAM profile for the fixed nine commissioning targets.
It mounts the custom kernel's root0 and user-config views read-only, noatime,
nodev, nosuid and noexec. No mounted executable, native application, shell,
physical network, installer or writable flash mount is present. This is not
evidence that root0 was the native active root.

The existing hardware WP/protected-status, NAND_ROM, skipped BBT scan and denied
mutation callbacks remain. Block/MTD character interfaces, UBI and command-line
partition overrides remain disabled. Partitions use the pinned board table.
JFFS2 NAND buffering/compression and xattr/ACL/security handlers are enabled so
metadata remains observable. RTC and forced hardware-clock synchronization are
disabled using the already reviewed OMAP selection patch. The unmodified older
diagnostic profile verifiers remain strict.

The original freestanding reader follows only a fixed root-relative allowlist,
checks root/ancestor ownership and permissions, requires read-only JFFS2 in the
production build, rejects links/special files/attributes and reads each file
twice into bounded RAM. Only the two new target files may be absent. Files,
identifiers and digests are never printed. Original metadata and binary bytes
travel in a bounded session-specific CRC frame; completion/footer are required.
Children are not retried; cached bytes may be retransmitted.

The host saves the complete frame privately, validates the fixed scope and
preserves all originals plus a manifest under a fresh owner-only directory.
Files/directories are fsynced and every byte read back before a host custody
receipt is created. The receipt binds the session, read-only collection scope,
source-root label and manifest. It is not a target-writer acknowledgment, active
root proof or restoration proof. A future installer must separately bind the
fresh snapshot to its actual replacement plan and implement interrupted-install
recovery. No persistent commissioning is implemented by this profile.

## Preparation and checks

Use the existing pinned NestDFU/x-loader/original loader sources, validated
heartbeat bootstrap and isolated rootless builder. All paths must be fresh:

```sh
python3 -m firmware.file_snapshot.prepare BUILD --base VALIDATED_HEARTBEAT_BUILD \
  --nestdfu PINNED_NESTDFU --xloader PINNED_XLOADER --loader ORIGINAL_LOADER_SOURCE
podman run --rm --network none --cap-drop all --security-opt no-new-privileges \
  --pids-limit 256 --memory 4g --cpus 4 -v ABSOLUTE_BUILD:/work:Z \
  localhost/hearth-probe-builder:20261030
python3 -m firmware.file_snapshot.prepare BUILD --base VALIDATED_HEARTBEAT_BUILD --finalize
python3 -m firmware.file_snapshot.run BUILD
```

The final command is offline only. Finalization checks generated guards, clock
and raw-tty edits, exact source/artifact copies, kernel configuration and reused
bootstrap bytes. The generated checker also validates image CRCs, decompression
and the exact original-only initramfs. Host sanitizer/ARM-link and binary-frame
regressions do not execute firmware on the host.

Future supervised PTY execution explicitly requires
`python3 -m firmware.file_snapshot.run BUILD FRESH_PRIVATE_OUTPUT --execute-read-only-file-snapshot`.
Do not run without owner restart readiness and advance experimental-RAM notice.
The native USB preflight is required and an exclusive fsynced execution marker
prevents profile reuse. No automatic boot retry. Keep USB connected and the base
detached; after command exit perform the full ten-second hold/release/single-press
and confirm the home icon and normal USB separately. Preserve failed output.
Never flash this image. Whole boot-chain power/hardware effects and recovery
remain unverified despite the protected filesystem design.
