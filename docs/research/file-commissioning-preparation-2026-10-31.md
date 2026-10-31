# File commissioning engine and combined ARM preparation

The commissioning follow-up now has an original nine-file transaction core and
Linux file adapter under firmware/file_install, plus a narrowly checked startup
editor. This advances the NLE-style filesystem path; the parked generic raw-NAND
framework is unchanged. No loader was armed, device file changed or actual unit
enrolled during this preparation. The previously observed native USB return is
the latest device state.

The adapter accepts fixed canonical targets, checks all originals before writing,
stages and verifies replacements, durably records rename intent, and restores
attempted files in reverse order on failure. Unexpected modifications are not
clobbered; incomplete rollback and journal/cleanup errors remain explicit. Private
originals live outside library/startup search paths. There is no general apply
CLI and no actual filesystem/kernel/USB integration yet. A caller boolean is not
a verified host backup receipt: fresh snapshot/export and receipt enforcement
remain required before hardware writes. See its README for exact limits.

A new startup wrapper exports the shim only immediately before exec of nlclient.
The stock start-as argument points at it; the existing native executable path,
PID file, stop matching and config argument construction are preserved. Putting
LD_PRELOAD before start-stop-daemon would instead preload the shim into that
launcher and fail its native symbol binding. The editor rejects ambiguous or
pre-modified scripts. Trusted host fixtures check PID/argument/preload behavior;
no recovered binary executes on the host.

Offline file attributes were reconstructed from the preserved JFFS2 metadata:
selected originals are root-owned; the native startup script is 0750, the web
library 0644 and the settings file 0644. Intended startup/library modes are
preserved, the new wrapper is 0750, the shim 0444, and assigned settings 0600.
These are captured attributes, not fresh mounted/runtime observations.

The private v2 review bundle now contains all nine original/replacement files,
with the registration endpoint ordered last. It uses the exact previously
loopback-measured TLS candidate and the GNU standalone storage candidate. Existing
captures and v1 review remain unchanged. The standalone shim matches the new RAM
profile bytes. There are no owner CA private keys in replacements. Unique device
credentials remain uninstalled and unenrolled. The bundle is explicitly
non-installable pending current-root/current-file checks, a fresh settings merge,
CRL renewal/verification, actual backup receipts and filesystem/write integration.
No owner addresses, SSID, identities, credentials or binary hashes enter source.

To avoid separate restarts for each pre-installation check, the new RAM diagnostic
combines 36 standalone-settings cases with 32 actual file-transaction scenarios.
The inherited kernel/bootstrap and 34 native baseline libraries are unchanged.
File operations run only on synthetic RAM roots and cannot accept a JFFS2 root in
this lab build. The normal adapter's JFFS2 guard remains separate and unexecuted.
Only original code with public ABI stubs is built on the host; native libraries
run only in a future explicitly supervised device diagnostic.

Final prepared private profile: `private/file-commissioning-ram-20261031/profile-v6`.
Separate reproducible profile: `profile-v6-repro`. Helpers:
`build/file-commissioning-ram-20261031/helpers-v4` and `helpers-v4-repro`.
All seven artifacts and complete RAM inventories reproduce: rootfs 11045312
bytes, image 6033988 bytes. All 29 imported libc symbols were found in the retained
native libc. Earlier unexecuted preparation outputs remain private; none is an
attempt or result. The final wrapper checks offline and opens no device.

The new focused host checks pass 62 cases, including 33 real filesystem scenarios
under ASan/UBSan, ARM cross-compilation, strict result/archive/protocol checks and
startup editing/exec behavior. Ruff/format and Bandit pass. The full default host
suite passes 564 cases with five optional integrations skipped. Actual HAOS runtime/backend code did
not change; prior broker/container evidence is retained without repeating it.
No JFFS2 write, power-loss restoration, physical native exchange or HVAC claim.
