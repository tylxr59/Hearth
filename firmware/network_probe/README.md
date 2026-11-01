# Protected network RAM validation

This profile uses the unchanged proven read-only kernel. It has no installer,
write gate or persistent commit command. The root0 filesystem is mounted read-only
only after the synthetic tests pass.

The original static PID1 runs 41 deterministic hash/stream checks. It then launches
20 instances of the original synthetic filesystem harness as UID/GID65534 on fixed
RAM-only directories, checking each zero exit and absence of output. These include
large-file install/restore and injected read/write/rename/sync/space faults. Each
fixture removes only its known synthetic files, bounding peak RAM use. The native
libc/interpreter pair is passively checked and executes only on the device; public
ABI stubs are used for cross linking, with no firmware executed on the host.

Afterward, the protected reader captures each real network file and checks its
mode, full original hash, exact span and full derived-candidate hash. No nlclient,
osm, physical networking, settings values or HVAC operation is invoked. The
private plan is embedded only in root-readable PID1; the unprivileged child cannot
read it. Reports contain bounded counts/phase/error evidence, kept privately.

Profiles bind the separately reviewed plan pin, complete host backup custody,
source recipes, fresh session and exact artifact inventory. Reproductions are
offline evidence only. A first complete corrupt report is preserved and rejected;
there is no automatic boot retry or fallback to weaker checks.

Offline package/check:

```sh
.venv/bin/python -m firmware.network_probe.profile package \
  --base build/PROVEN_READONLY_KERNEL --libraries private/PROVEN_TLS_PROFILE \
  --plan private/REVIEWED_NETWORK_PLAN --backup private/VERIFIED_BACKUP \
  --pin private/SEPARATE_PLAN_PIN --build build/FRESH_BUILD --output private/FRESH_PROFILE
.venv/bin/python -m firmware.network_probe.run private/FRESH_PROFILE
```

Only after owner readiness and advance experimental-RAM notification, through a PTY:

```sh
.venv/bin/python -m firmware.network_probe.run private/FRESH_PROFILE \
  private/FRESH_OUTPUT --execute-read-only-network-preflight
```

Keep USB connected/base detached. After command exit perform the reviewed full
10-second hold/release/single-press return and verify native startup/USB. Never
rerun an executed profile or overwrite evidence. The first supervised v2 profile
passed all 61 synthetic cases and four real preflights, then returned to native
USB. This is not evidence of a persistent Google-dependency correction.
