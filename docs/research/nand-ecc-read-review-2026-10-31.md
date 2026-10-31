# Normal-ECC read path and bounded comparison preparation

The [controller observation](nand-contract-result-2026-10-31.md) establishes the
custom kernel's configured bus/ECC/OOB tuple, but the earlier acquisitions used
raw reads. A separate normal-read measurement is now prepared under
[firmware/nand_ecc_sample](../../firmware/nand_ecc_sample/README.md). No target
execution, programming or restoration has occurred for this profile.

The fixed read range is block 190 inside the source-corroborated primary root
range, including the earlier padding case at page 12209. The new sysfs reader
uses `MTD_OOB_PLACE` in `read_oob` with both data/OOB buffers. In the pinned public
NAND implementation, this selects normal `read_page` and transfers physical OOB;
requesting OOB also avoids satisfying subsequent reads from the data-only page
cache. Only full successful or full `-EUCLEAN` results are accepted by the wrapper.
The registration and per-read guards retain hardware WP, exact geometry/layout,
zero capability flags and denied mutation interfaces. No writer is added.

Source review found a limit in this published OMAP BCH4 callback: its decoder
result controls a RAM bit-flip loop, but a negative decode result is not propagated
and corrected counts are not returned; the function ends with zero. Consequently
normal status/ECC statistics alone cannot establish integrity. This is a finding
about the pinned source compiled into this diagnostic, not a demonstrated
source/binary correspondence or vulnerability claim about the stock kernel.
No change to that callback is included in the comparison.

The host therefore requires exact matches to an independent private reference,
as well as matching two received passes. Preparation freshly verified both raw
capture identities against their acquisition record and both corrected-view
identities against the earlier BCH report. The reference combines matching
corrected data with OOB matching both original raw passes; it preserves padding
bits and is not embedded in the RAM image or sent to the target. No source input
was changed. Data, hashes, source provenance and later captures stay private.

Transport has distinct magic and absolute page indices. A CRC-framed failure
record retains only bounded stage/pass/page/result, allowing a failed open/read
to be diagnosed without transmitting partial cached firmware. Collector checks
cover scope, reference privacy/identity, pass/reference mismatch, fragmented
transport, CRC/order failures, failure metadata and storage sync errors. An
original host-only sysfs fixture under sanitizers verifies the normal read mode,
exact range, WP/shape/layout guards, full cleaned reads and failure framing;
no target firmware executes on the host. Three wrapper tests instrument USB
selection to prove offline/invalid-input paths stop before it.

The first build and separate reproduction have six byte-identical artifacts;
configuration choices match the observed controller profile and bootstrap bytes
are unchanged. Make check and 371 host tests pass, with three unchanged optional
broker/container integrations skipped for this firmware-only addition. The earlier
328-test full backend/broker/container result remains separately scoped. Offline
image and private-reference/output preflights pass without opening a device.

Future success would establish this bounded normal-read/reference match, including
the padding case. It would not measure the number of corrected faults, test
deliberate ECC fault injection, generalize to arbitrary flash contents or validate
programming/encoding, restoration, mounted native filesystems or HVAC behavior.
