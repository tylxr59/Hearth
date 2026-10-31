# Private native TLS RAM experiment

This is an experimental diagnostic for the owner's Display-2.6 / 5.9.4-5 unit.
It has passed offline build/integrity checks; **it has not run on the thermostat**.
It is not installable firmware, a recovery procedure or an HVAC controller.

The custom Linux profile has MTD, block storage, physical network devices and
RTC drivers disabled. Its only network interface is loopback. The OMAP Kconfig
automatically selected hardware-clock synchronization even with RTC_CLASS off;
the separate TLS recipe removes exactly those two selections and verifies that
GENERIC_CMOS_UPDATE stays disabled after oldconfig. The test sets a synthetic
**RAM** wall clock to 2030-01-01; it does not provide trusted product time bootstrap.

The previously reviewed x-loader/U-Boot stages still initialize hardware and
have not been proven write-free or power-safe. Keep the display detached from
its unwired base and connected only by USB. Native control is absent during this
experiment. Notify the owner before execution under the existing device-work
authorization. Existing backup/restoration gates remain required for any later
persistent modification. A successful matrix is not a restoration/HVAC test.

## What runs

An original static ARM PID 1 mounts only virtual filesystems, configures loopback,
sets the test clock, and waits for one fixed USB start token. It runs two bounded
instances of the original test helper as UID/GID 65534. There is no shell or raw
command receiver. Each helper loads the recovered curl/OpenSSL dependencies and
either the original web-service library or the separately reviewed private
default-callback candidate. Neither nlclient nor osm, native settings, actual
credentials, calibration or backplate firmware is included.

The helper starts a local TLS 1.2 server and client at 127.0.0.1:8443, using
synthetic keys/certificates/CRLs. Every request uses the native curl/OpenSSL
libraries and the actual native SSL-context hook, with peer/hostname checking
enabled. Separate processes prevent cross-variant library reuse. The parent
enforces deadlines, caches results in RAM and repeats a fixed result frame.
Successful or failed frames are retained privately by the collector, never echoed
as raw library output. Setup diagnostics contain only bounded loader errors.

`passed` means the observed result matched the case expectation. The original
callback is deliberately expected to accept its known invalid-time/CRL cases;
that is a baseline control, not an endorsement of its security.

| Synthetic case | Original hook expected | Default-callback candidate expected |
| --- | --- | --- |
| Valid certificate and CRL | Accept | Accept |
| Wrong CA | Reject | Reject |
| Wrong IP SAN | Reject | Reject |
| Expired certificate | Reject | Reject |
| Future certificate | Accept | Reject |
| Missing issuer CRL | Accept | Reject |
| Expired CRL | Accept | Reject |
| Future CRL | Accept | Reject |
| Revoked certificate | Reject | Reject |

Curl 7.49.1 uses error 51 for hostname mismatch and 60 for certificate-chain
verification failures. Timeouts, connection errors, missing files, malformed
results or missing cases cannot count as successful certificate rejection.

This test does **not** invoke the full native fetch class, native startup/config,
credential installation, pairing, transport subscriptions or physical control.
Its explicit curl options model the previously reviewed setup, but do not prove
every native networking path, cipher policy or operational trust configuration.

## Build and privacy separation

Only public source enters the rootless kernel builder. The existing pinned
Ubuntu/probe-builder image, Linux source archive and validated bootstrap artifacts
are reused; see [the heartbeat profile](../probe/README.md) for provenance and
compiler-authenticity limits. The separate profile does not weaken its gates.

Installed host Clang/LLD cross-compile the original helper and PID 1. Tiny public
ABI stub libraries satisfy the helper's link-time libc/libdl imports; those stubs
are never executed and are **not** packed into the device image. No recovered
firmware is used as a compiler/link input or executed on the host. The original
ARM startup follows the version-matched glibc ABI. Public reference URLs/hashes
are in [sources.json](sources.json); reference files stay under ignored build/.

The private packager verifies library bytes against the private acquisition
report and resolves their dependency closure without following firmware links.
It verifies the candidate against its separate private one-word review record,
and verifies synthetic fixture hashes after host OpenSSL baseline checks.
It packs regular library aliases, the two original helpers and only the listed
test fixtures. The synthetic server key belongs to UID 65534 in RAM; CA private
keys remain on the host. No links or block devices are allowed in the archive.

The boot image is a two-component legacy uImage: the bounded ARM zImage plus a
gzip newc RAM filesystem. The pinned U-Boot source supports this form and passes
its second component as an initrd. The image stays below 6 MiB at the existing
0x80a00000 upload address, below 0x81000000. CRCs, component boundaries, bounded
decompression, exact archive inventory/permissions, source recipes and hashes
are checked before device access. If the external root does not start, the
built-in fixed heartbeat is detected as a failure rather than a TLS success.

All generated images, libraries, fixture keys, Ghidra exports and captures belong
under ignored owner-only `private/`. **Never publish or upload that image.**
Only original tooling/source, public reference hashes and sanitized research
belong in Git. Preserve raw capture inputs and earlier failed artifacts.

Public build staging:

```sh
.venv/bin/python -m firmware.tls_probe.stage \
  --base-build build/ram-probe-reliability-20261030 \
  --sources build/ram-probe-final-20261030 --output FRESH_PUBLIC_BUILD
podman run --rm --network none --cap-drop all --security-opt no-new-privileges \
  --pids-limit 256 --memory 4g --cpus 4 -v ABSOLUTE_PUBLIC_BUILD:/work:Z \
  localhost/hearth-probe-builder:20261030
.venv/bin/python -m firmware.tls_probe.compile FRESH_PUBLIC_HELPERS
.venv/bin/python -m firmware.tls_probe.fixtures FRESH_PRIVATE_FIXTURES
```

`firmware.tls_probe.package --help` lists the explicit private input/report,
candidate, fixture and fresh-output arguments. No downloads, device access or
installation occur during packaging. Fresh paths are required; inspect existing
attempts instead of deleting them to reuse a name.

## Supervised device step

Run from the Hearth checkout. The default performs offline checks only:

```sh
sh firmware/tls_probe/boot.sh PRIVATE_PROFILE
```

Only the explicit `--execute-experimental-tls-probe` argument opens the reviewed
ROM/serial interfaces. The wrapper first requires normal Nest USB on physical
port 1-1, then waits for the owner to perform the reviewed manual restart while
the loader is waiting. Use a PTY for immediate loader output. Do not start it
before the owner is ready for that timing-sensitive action.

The collector sends only `BEGIN_TLS_TEST_V1` after the ready marker and writes
a fresh mode-0600 `tls-result.jsonl` under the private profile. There is no
automatic boot retry. After success or failure, manually restart with the loader
exited and confirm native startup. Do not reconnect the base for this test.

Host regression checks cover profile boundaries, exact clock-selection patching,
result forgery/timeout rejection, serial fragmentation/fixed-token behavior,
private failure capture, archive corruption/permissions and original helper
cross-compilation. These supplement the source review; they cannot establish
hardware safety or predict that the first target run will succeed.
