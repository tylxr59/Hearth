# Combined RAM file transaction / standalone settings lab

This diagnostic batches two concrete pre-installation checks into one owner-timed
USB session: the standalone GNU-linked settings correction without lab tracing
(36 original/candidate cases), and the original file transaction code against
32 synthetic filesystem scenarios. It is prepared, not executed. No actual
settings, native application, credentials, firmware files or mounted NAND appear
in its root. The inherited kernel disables MTD/block/RTC and physical networking;
PID 1 neither sets a clock nor configures a network interface.

The file cases cover successful nine-file replacement, original-byte/mode drift,
absent backup acknowledgement, symlink/hardlink/FIFO refusal, duplicate targets,
unsafe credential modes, staging/recovery conflicts, oversized data, short/failed
writes, permission/ownership/sync failures, rename failure, uncertain success
after rename, journal failures before and after activation, verification failure,
rollback refusal on unrelated modification and an explicitly incomplete rollback.
Both the ordinary host and ARM RAM builds use the same transaction/adapter and
scenario source. The ARM lab restricts roots to ramfs/tmpfs, and runs as UID/GID
65534. No ARM firmware executes on the development host.

The original startup wrapper editor is separately host-checked for byte
preservation, unchanged stop identity, correct exec PID, literal argument passing
and preload scope, using only trusted host fixtures. It is not placed in this
RAM image and does not launch nlclient.

The supervisor derives through exact checked substitutions from the measured
settings lab. It runs original/candidate/file helpers once with separate caches,
process deadlines and all-byte synthetic log scanning. Child stdout remains
8 KiB; raw diagnostic cache remains 2 KiB; the three-child report is bounded at
48 KiB. Success requires all 68 cases, three successful child statuses, settings
bindings/canaries/log checks, exact modes/readback and completion. Missing or
ambiguous evidence fails closed after private capture. Diagnostics from the file
helper are forbidden in a successful result.

Build/package with fresh outputs only:

```sh
.venv/bin/python -m firmware.file_install_probe.compile build/FRESH_HELPERS
.venv/bin/python -m firmware.file_install_probe.artifact package \
  --base private/VALIDATED_TLS_PROFILE --helpers build/FRESH_HELPERS \
  --review private/REVIEWED_STORAGE_ABI.json --output private/FRESH_FILE_LAB
sh firmware/file_install_probe/boot.sh private/FRESH_FILE_LAB
```

The wrapper above is offline only. A future supervised PTY-backed run requires
owner readiness and `--execute-experimental-file-ram-lab`. Notify before arming,
require native USB first and prompt for the reviewed restart only when waiting.
Never retry automatically or reuse a profile with file-result.jsonl. Keep base
detached and USB connected. After command exit restart manually and confirm
native startup/USB. Preserve every failed/completed private result and attempt
record. Same-unit whole-chain power/recovery limitations remain.

A pass would validate this bounded ARM RAM behavior and the exact standalone
settings build. It would not establish JFFS2 durability, installation, real
credentials, full native startup, authenticated device transport or HVAC control.

The first combined [attempt](../../docs/research/file-commissioning-attempt-2026-10-31.md)
transferred successfully but did not deliver a complete report. The cached sender
now retains its offset across USB backpressure, and the collector handles restarted
prefixes without concatenation. The wrapper also creates a durable execution marker;
never reuse a marked profile even if no result was saved. The corrected profile
is prepared separately. No 68-case hardware pass is claimed.
