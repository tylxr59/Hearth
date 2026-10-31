# Native TLS callback matrix observed on the device

The second owner-supervised RAM attempt used source commit `cd3f9b1` and the
separate private `profile-launch-diagnostics` image. The ROM handshake and all
three uploads completed. The collector received and independently validated the
entire diagnostic result, then exited zero. No automatic retry occurred.

The private result is 1873 bytes, 22 JSON records, mode 0600. It reports successful
loopback setup (stage 3/result 0), RAM-clock setup (result 0), all 18 expected TLS
cases, zero wait statuses for both helpers and successful completion. There are
no stderr records. The original raw result and a separate attempt record/digest
remain private; neither proprietary bytes nor private fingerprints are published.

## Observed results

The original helper loads the recovered curl/OpenSSL libraries and native
SSL-context hook. The candidate helper loads the separately reviewed private
default-callback copy in a new process. Both use synthetic fixtures, explicit
peer/hostname checking and TLS 1.2 over device loopback with a fixed RAM clock.
The same custom kernel/bootstrap bytes were used for both supervised attempts.

| Synthetic case | Original native hook | Default-callback candidate |
| --- | --- | --- |
| Valid certificate and CRL | Accepted | Accepted |
| Wrong CA | Rejected, curl 60 | Rejected, curl 60 |
| Wrong IP SAN | Rejected, curl 51 | Rejected, curl 51 |
| Expired certificate | Rejected, curl 60 | Rejected, curl 60 |
| Future certificate | Accepted | Rejected, curl 60 |
| Missing issuer CRL | Accepted | Rejected, curl 60 |
| Expired CRL | Accepted | Rejected, curl 60 |
| Future CRL | Accepted | Rejected, curl 60 |
| Revoked certificate | Rejected, curl 60 | Rejected, curl 60 |

All 18 results matched their expected behavior; a timeout or connection failure
was not accepted as certificate rejection. The original's acceptance of invalid
time/CRL cases is the measured baseline vulnerability, not a security pass.
The candidate accepted the valid case and rejected all eight invalid cases in
this harness. This advances the earlier static review to an actual ARM/native-
library callback measurement.

## Native return and scope

After the command exited, the display initially remained black and still exposed
the probe's serial USB identity. The custom probe has no screen UI, so black
alone did not establish whether it restarted. The owner repeated the hold for a
full approximately ten seconds, released, then pressed/released once. The owner
confirmed the home icon; read-only preflight independently confirmed normal
Nest USB 2464:0002 on the reviewed port.

Google documents [the approximately ten-second manual restart](https://support.google.com/googlehome/answer/9247296?hl=en-GB).
That timing is useful when the display was already black; do not use a missing
screen transition as evidence of completed restart. No loader/retry was running
during native return. Native startup return is not a demonstrated flash restore.

The test did not run nlclient/osm, mount flash, install a library or CA, use real
credentials, contact a production endpoint or operate HVAC. Its kernel disables
MTD/block/physical-network/RTC support and hardware-clock synchronization. The
bootstrap stages still have unverified hardware/power side effects; this report
does not certify the whole boot chain as write-free or safe.

It also does not exercise the full native fetch class, effective configuration,
operational time bootstrap, credential persistence, native pairing/transport,
legacy protocol policy, battery behavior or an installation/recovery procedure.
The result supports this specific callback candidate under the recorded harness,
not a deployable secure thermostat image. Other legacy firmware vulnerabilities
remain outside this test.

Next: continue offline native settings/failure-path work and protocol mapping.
The [storage defects](native-storage-2026-10-30.md), transaction/rollback and
backup/restoration gates remain unresolved before any persistent modification.
Historical build checks and the first failed attempt remain preserved separately.
