# Exact replacement-plan and backup binding

After the 91-case ARM RAM pass and confirmed native USB return, the original
`provisioning/file_capsule.py` adds the next offline commissioning boundary. It
verifies the expected snapshot session/frame and complete original host custody
before creating any output. It requires separately observed primary/5.9.4-5
selection, the exact nine targets, the two new paths absent and the reviewed
replacement permission policy. This is a profile-specific first-install data
format, not a general upgrade or deployment interface.

A canonical plan binds every original/replacement byte digest and metadata,
fixed source-root label and snapshot session. The original files receive a
separate durable host custody receipt tied to that exact plan, rather than
promoting the old collection-scope receipt to installation approval. All private
outputs are owner-only and verified after fsync/readback. An external expected
plan pin is mandatory when checking the capsule; its complete inventory, bytes,
receipt and generated C data header must match. No arbitrary path or C text is
accepted into the header. The artifacts are unsigned local development data.

Nineteen host regressions cover wrong session/profile, altered source backup,
replacement ordering/modes/bounds, changed capsule/header/receipt, wrong plan
pin, disk failure, deterministic output and original-only ARM data-header
compilation. No proprietary firmware executes on the host. Make check and the
full suite pass: 672 tests, five unchanged optional integration skips.

The owner's private capsule is native-file-capsule-20261031-v1, with a separate
-v1-repro. All 23 files reproduce byte-for-byte. It binds the observed snapshot
and the existing nine-file offline review. All reviewed payload digests and
original modes were checked; settings, NTP and startup edits were regenerated
from the fresh originals and compared. The dedicated trust/CRL data successfully
verified the already deployed backend certificate with OpenSSL at host time.
The private generated data header is 876529 bytes. No identifier, credential,
certificate identity, firmware byte or firmware digest is published.

This capsule is explicitly offline-plan-bound-not-installable. There is no
executable installer, target-side receipt enforcement, writable filesystem
launcher or firmware installation result. The next integration must revalidate
the externally pinned plan/backup before USB execution and exact on-device
originals before any mutation, then confine the writer and restoration paths.
The passed RAM recovery matrix does not establish persistent JFFS2 durability
or hardware power-loss recovery. Advance notice remains required before writes.

## Bench power observation

The owner has only the display, unwired base and USB cable. With no loader
running, the owner disconnected USB and fitted the display onto the empty base;
the stock UI reached Wi-Fi setup on its internal battery. Wi-Fi was left
unconfigured and the unit returned to normal USB, independently observed.
This establishes a way to attempt a short setup session, not battery health or
sustained Wi-Fi runtime. No external power supply or wiring test was performed.
