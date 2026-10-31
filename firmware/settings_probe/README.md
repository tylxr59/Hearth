# Native settings RAM experiment

A bounded diagnostic for the privately recovered Display-2.6 / 5.9.4-5 settings
library. The first supervised boot produced five complete rows before native
diagnostics exhausted the initial reporting budget. Native startup returned.
The corrected profile is prepared and **unexecuted**; see the
[attempt/correction record](../../docs/research/settings-probe-attempt-2026-10-31.md).
It is not an installation, recovery procedure or storage fix.

The purpose is to measure the [reviewed writer defects](../../docs/research/native-storage-2026-10-30.md)
without touching real settings. Original helper code loads only the native base
settings class and its dependencies, never nlclient/osm or control/lifecycle
methods. It reads/writes public synthetic ID/secret strings under `/state` in the
external initramfs. This is RAM storage; no thermostat filesystem is mounted.

The private package reuses the integrity-checked kernel and bootstrap from the
successful TLS profile. MTD, block, physical network drivers and RTC/hardware-clock
updates remain disabled. The new PID 1 does not configure loopback or set a clock.
The inherited kernel still includes the IP stack. Bootloader hardware/power side
effects remain unverified; keep the display detached from the unwired base.

## Fixed measurements

Each case creates a separate owner-only synthetic directory, loads two old
values, sets two new values, calls native Write, reloads in a fresh object,
then calls Write again without setting a value and reloads again. Only readback
masks and bounded status/counter fields are reported; values are not printed.

Cases are normal operation and one-shot faults at temporary-file open, header
write, entry error, entry short write, footer write, file sync, file close,
rename, parent-directory open, directory sync and directory close. The short
write is an extra robustness case; documented PR_Write normally returns the
full count or -1, and a failure may have written a prefix. Close-failure injection
closes the actual RAM handle and then reports failure; it models that specific
outcome, not every kernel failure mode.

Instrumentation exports fixed PR_Open/Write/Sync/Close and rename wrappers from
the helper executable. It forwards unrelated operations unchanged and targets
only the currently selected synthetic temporary path/parent/descriptor. It uses
no preload installation, arbitrary command channel, production I/O shim or native
binary patch. This is single-threaded diagnostic instrumentation.

The ABI gate checks six exact exported methods/addresses/extents and reviewed
constructor flags. Private library/method hashes preserve their identity. The
48-byte native base object has an additional tail canary; its non-deleting
destructor is called before freeing the allocation. A canary is not a full native
memory-safety proof. Setter results, normal write/readback, one-shot fault arrival,
process status and all twelve rows are mandatory.

A complete report means **observations received**, including potentially broken
writer behavior. It does not label fault paths secure or require an erroneous
writer to pretend to succeed. Error/short writes and skipped retries must be
reviewed from the private results before designing a correction. RAM sync is not
flash durability or a power-loss test.

PID 1 accepts only `BEGIN_SETTINGS_TEST_V1`, runs one unprivileged helper once,
separates child stdout (8 KiB) from private stderr (2 KiB raw), explicitly counts
discarded diagnostic bytes, and repeats the cached result.
The helper has a 90-second alarm; the supervisor has a 120-second deadline and
kills its child process group on overflow or timeout. Native logs may include
synthetic values, so their hex-encoded diagnostics remain private and are never
decoded or echoed by the collector. The rootfs carries 34 unchanged baseline
libraries from the validated TLS package, including libraries not loaded by this
smaller dependency path; no TLS candidate, private key or original settings file
is carried forward.

## Preparation

From Hearth, with private artifacts from the successful TLS run available:

```sh
.venv/bin/python -m firmware.settings_probe.compile build/FRESH_SETTINGS_HELPERS
umask 077
.venv/bin/python -m firmware.settings_probe.artifact package \
  --base private/VALIDATED_TLS_PROFILE \
  --helpers build/FRESH_SETTINGS_HELPERS \
  --output private/FRESH_SETTINGS_PROFILE
sh firmware/settings_probe/boot.sh private/FRESH_SETTINGS_PROFILE
```

The last command is offline checking only. It does not open the device. Fresh
outputs are mandatory. Preserve the earlier TLS profiles/results unchanged.
The corrected prepared private image is 6,010,028 bytes; its RAM archive is
10,999,388 bytes, below the existing 6 MiB upload and 24 MiB root limits. It
preserves dynamic-interpreter execute mode 0555 and library mode 0444; `/state`
is mode 0700 owned by helper UID/GID 65534. Artifacts/results stay owner-only.

For a future owner-timed execution, notify the owner of experimental RAM execution,
check native USB, launch the wrapper with a PTY and the explicit
`--execute-experimental-settings-probe` flag, then prompt the manual restart only
when the loader is waiting. It waits at most 90 seconds for ROM and 180 seconds
for reporting. There is no automatic boot retry. Never reuse an existing result.

After command exit, hold the ring for approximately ten seconds even if already
black, release, press/release once and independently confirm home icon plus native
USB. No base connection, persistent write or HVAC operation is included.

## Host validation and provenance

Host checks cover ARM cross-compilation without firmware link inputs/execution,
bounded native ABI parsing, archive permissions/inventory/kernel exclusions,
fragmented serial results, fixed-token/private capture behavior, malformed or
incomplete reports, failed normal baselines, missed faults, failed process/canary
checks, and offline/no-overwrite/no-retry wrapper gates. An original host NSPR test
double exercises all fault wrappers, unrelated-file forwarding and one-shot
behavior under ASan/UBSan. That double is not the native writer or target evidence.

The [public NSPR API references](https://firefox-source-docs.mozilla.org/nspr/reference/i_o_functions.html)
and separately [pinned headers](sources.json) define the ABI/constants only.
No third-party implementation or proprietary source was copied. The helper uses
the existing original ARM/glibc startup/declarations and public API stubs; generated
stubs are never packed. Firmware provenance, restoration, transactional real
credential provisioning, remaining credential logs and HVAC remain separate gates.
