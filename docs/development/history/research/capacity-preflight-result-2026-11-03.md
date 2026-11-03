# Combined capacity preflight and root0 space analysis — 2026-11-03

## Hardware result (v0.11.1 wizard, owner-run)

Steps 1–5 of the public wizard completed on the owner's unit: HA onboarding,
reader build, full-NAND backup, original-file acquisition and kit build. The
kit nominated the existing restored network4 archive for shared-original
rollback. The combined no-commit capacity preflight (cleanup3 profile,
`preflight_only`) then refused:

| Counter | Value |
| --- | --- |
| `space_available` (root0 `f_bavail` × `f_bsize`) | 13,217,792 |
| `space_required` | 13,248,165 |
| Shortfall | 30,373 |
| `diagnostic` | 42 (space) |
| `program`, `erase`, `marker`, `rw_attempted`, `committed` | 0 |
| `protected`, `safe_to_restart` | 1 |
| `memory_free` | 45,006,848 |

No write occurred. This is the first hardware measurement of the shared-original
bound. The copy-based bound previously required 19,534,505 bytes on this unit.

Requirement composition, using the kit's real sizes:

- cleanup3 data: `nlclient` 5,122,360 + `connmand` 687,028 + `main.conf` 3,063
  = 5,812,451 bytes of staging, plus the largest file again as the rollback
  temporary: 10,934,811 in total;
- the shared-mode margin of 2 MiB;
- the core9 root0 reservation of 216,202 (85,130 replacement bytes, excluding
  target 7, plus 128 KiB).

## Kernel accounting (pinned NestDFU 2.6.37 source)

`jffs2_statfs` reports `f_bavail = dirty_size + free_size −
sector_size × resv_blocks_write`. `jffs2_calc_trigger_levels` sets
`resv_blocks_deletion = 2` and `resv_blocks_write = 2 + ceil((flash/50 +
100 × nr_blocks) / sector_size)`. For the 46 MiB root0 (368 × 128 KiB) that is
10 blocks, or 1,310,720 bytes. The kernel therefore already withholds its own
garbage-collection and deletion headroom from `f_bavail`, and refuses ordinary
writes below it.

## Offline root0 analysis (fresh corrected NAND view)

An offline node scan of the 46 MiB root0 range (offset 12 MiB) classified
latest-version dirents and inode coverage. It predicted `f_bavail` at
13,435,923 against 13,217,792 measured, within 1.6%.

| | 2026-10-30 (stock) | 2026-11-03 |
| --- | --- | --- |
| Predicted `f_bavail` | 21,995,119 | 13,435,923 |
| Live `nlclient` node bytes | 2,919,348 (factory ZLIB) | 5,210,080 (NONE) |
| Live `/usr` node bytes | 11,936,692 | 12,246,052 |
| `.hearth-rollback-…` (network4 originals) | absent | 5,922,636 (NONE) |

Hearth writes NONE/ZERO only (the LZO incident). So the stock return replaced
factory-compressed originals with uncompressed copies. Together with the
retained uncompressed rollback archive, this explains the roughly 8.5 MB lost
since the first network install (21,774,336 bytes available on 2026-11-01).

Measured NONE-node overhead: `nlclient` occupies 5,210,080 bytes for 5,122,360
bytes of data, which is 1.71% (about 70 bytes per 4 KiB node).

## Margin change (development, v0.11.2)

From the measured overhead:

- worst-case install overhead is about 190 KB of node headers, plus about 30 KB
  of block-split and wbuf padding, plus journal and dirents: about 250 KB;
- the largest restore needs about 90 KB of overhead.

`firmware/network_writer/data.c` now names the margins. The shared install margin
is 2 MiB → 1.25 MiB and the restore margin is 4 MiB → 1 MiB. A preprocessor
check keeps the install margin at least 256 KiB above the restore margin, so a
passing install leaves room for its own guided restore. The install keeps the
originals and adds the replacements.

The previous 4 MiB restore margin would have made the guided restore refuse on
this unit after a successful install: predicted post-install `f_bavail` is about
7.27 MB against a 9.32 MB requirement. With the new margins this unit's predicted
figures are:

- install: 12,461,733 required against 13,217,792 available;
- restore afterwards: 6,170,936 required against about 7.27 MB.

The copy-based install bound (3 × total + 2 MiB) is unchanged. Neither new
margin has been measured on hardware.

## Follow-ups

- Writing native-supported ZLIB (never LZO) would recover several MB, but needs
  writer kernel and encoding-audit changes plus a hardware measurement.
- NLE does not patch `nlclient`/`connmand`. Hearth patches them only to redirect
  the Google `generate_204` connectivity URL to HA, which is about 98% of
  cleanup3's space cost.
