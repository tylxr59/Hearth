# Native protocol constraints and the next TLS measurement

This continues offline review of the privately reconstructed Display-2.6 /
5.9.4-5 client and pinned NLE source. No target program or protocol request ran.
The pinned backend files were fetched again into ignored build/ and verified
against [the existing source lock](upstreams.json); they were not executed or
copied into Hearth's implementation.

## Confirmed static constraints

- Registration uses a form builder and Basic credentials as described in the
  [bootstrap review](native-bootstrap-2026-10-30.md). The transport URL setter
  recognizes `transport_url`; this does not establish a complete entry reply.
- The subscription builder explicitly emits `chunked:true`, a session property
  and bucket metadata, targeting the transport base plus `/v7/subscribe` with
  a JSON POST. Its default JSON builder uses an `objects` array. It can subscribe
  to many more native bucket types than Hearth's strict two-bucket decoder.
- The native response parser handles numeric revision and timestamp fields
  separately. It retains them pending the following `object_key`, then applies
  them through bucket methods. This corroborates NLE's requirement to serialize
  **response** revision/timestamp before object_key. Outbound native requests can
  use another order; the constraint is directional.
- A preliminary object-extraction helper locates the objects text with substring
  search and counts braces/brackets without an evident JSON-string state in that
  scan. Fully valid JSON is not sufficient proof that every string, fragment or
  chunk boundary will work. The higher-level buffering/state-machine contract
  still needs review and fixtures; no generic stream compatibility is claimed.
- Pinned NLE sends JSON documents on HTTP chunked responses and contains timing,
  schedule/echo and conditional-write handling. Those are useful source reports,
  not measured behavior of this unit. Hearth still lacks complete entry,
  pairing, CAS, revision reconciliation and subscription/control delivery.

No speculative production route, permissive native identity parser or merged
state echo was enabled. The canonical laboratory API remains separate. A future
codec needs sanitized, direction-specific ordering/framing and stale-revision
fixtures rather than accepting all upstream shapes to make a simulator pass.

## Concrete next measurement

TLS validation precedes sending genuine credentials or attempting native
commissioning. The [private RAM-only TLS probe](../../firmware/tls_probe/README.md)
is now prepared to compare the actual original/default-callback native hooks
using the recovered curl/OpenSSL libraries, synthetic certificates/CRLs and only
device loopback. It does not run nlclient/osm or mount flash.

Version-matched public curl source confirms an important test detail: curl 7.49.1
distinguishes hostname failure (51) from certificate-chain failure (60).
Modern merged error-code assumptions would create a false failure on this target.
The original helper also follows the matched glibc ARM startup ABI; public
reference hashes are in [the probe source record](../../firmware/tls_probe/sources.json).
No third-party reference implementation is vendored.

The first target run remains pending an owner-supervised restart. Even if its
18-case matrix succeeds, native fetch setup, effective configuration, trusted
time bootstrap, storage correction, recovery and HVAC validation remain open.
The [storage findings](native-storage-2026-10-30.md) still block reliance on native
credential persistence. No persistent writes or broad device-control tests are
part of this next measurement.
