# Next recovery work after the scratch result

**Deferred:** after owner feedback about duplicating NLE, the default next step
is the [NLE integration milestone](nle-integration-focus-2026-10-31.md). The
unexecuted draft core/model is parked under ignored build storage. This design
and its source findings remain available if a concrete installation/recovery
requirement later needs them; they are not an automatic prerequisite to further
functional integration work.

The successful [single-page scratch experiment](scratch-result-2026-10-31.md)
measured hardware ECC programming and restoration of an originally empty block.
It did not restore a block containing programmed data/parity. The next recovery
measurement should exercise that distinction in the same fixed scratch region,
using synthetic contents rather than boot/root/configuration data. This is a
design direction, not an implemented or authorized-to-run new profile.

The pinned public NAND core was freshly matched byte for byte against the core
compiled in the successful profile. [Source identity](nand-raw-write-source-2026-10-31.json).
Static findings relevant to a future raw restore:

- `nand_write_oob` with both buffers routes to `nand_do_write_ops`. For RAW mode,
  `nand_fill_oob` copies the provided physical OOB, and `nand_write_page` selects
  the raw page writer. Under this source's HW ECC configuration, the selected
  standard raw writer sends data followed by OOB without regenerating parity.
  This is source evidence, not an observed RAW programming result.
- `nand_do_write_ops` can assign the requested full `oobretlen` even after its
  page writer returns an error. A future adapter must require zero status AND
  full data retlen AND full OOB retlen; OOB count alone is not evidence of success.
  Independently read/compare every restored byte afterward.
- Cached programming is explicitly disabled by the page writer. Its optional
  verify-write code checks data only; that option is disabled in the measured
  kernel anyway. Neither condition replaces independent physical OOB/ECC checks.
- Avoid multi-page requests with partial/offset OOB. Require exactly one aligned
  full data/OOB record per fixed page, and preserve the same WP, no-flash-BBT and
  no-arbitrary-address boundaries. No bad block migration/marking is demonstrated.

A prospective bounded rehearsal would back up the freshly empty original block,
erase it, program 64 generated pages with hardware ECC and explicit synthetic
free-OOB metadata, capture that programmed block in RAM, erase and restore it
through RAW data/OOB programming, verify both raw/normal reads independently,
then erase and restore the original empty-block cleanmarker. Its maximum normal
path would be 128 full-page programs, three block erases and one final marker
program. This avoids reprogramming data over a pre-existing page-zero marker;
the actual NAND partial-program limits remain unmeasured.

Before preparing such a run, define the failure/cleanup state machine and a
separate fixed-region rescue path tied to the preserved original input. Never
wait for another host instruction to clean up temporary programmed contents:
USB/host loss after the first ACK must not strand a transaction by design.
Any rescue must preserve the current failed region privately and must not turn
into an unrestricted writer or silently overwrite later native filesystem data.
Power interruption behavior and hardware failure cannot be proved by simulation.

No new writer or RAM image for this rehearsal has been built or executed. A
future prepared profile needs its own offline fault model, independent full-block
BCH/OOB comparison, fresh reproducible seal, exact danger notification and owner
restart timing. Even a successful synthetic programmed-block rehearsal would not
demonstrate boot selection/firmware restore, automatic rollback or HVAC behavior.
Native transport/TLS/time/credential commissioning remain independent blockers;
do not install the existing partial replacements as a shortcut.
