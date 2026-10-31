# Offline recovery-layout follow-up

This review reads the preserved raw captures and BCH-derived data view. No device,
mount, firmware executable or flash writer was opened. Original inputs and earlier
reports remain unchanged. New private records are under
`private/nand-marker-review-20261031`; experimental recipes remain in ignored build/.

Both raw file digests freshly matched the original private acquisition record.
Across all 2048 erase blocks and every page, OOB bytes zero and one remain FF in
both passes; first, first-two and last-page surveys agree. This is evidence about
those marker positions, not proof that every block is healthy or that every
manufacturer/runtime bad-block convention has been established. Other OOB bytes
contain valid metadata and must not be interpreted as generic bad-block flags.
The published large-page driver conventions remain source evidence, not a stock
runtime dump of chip options or partition registration.

The independently corrected view contains CRC-valid redundant boot environments
at source-corresponding blocks 26 and 29. Both have 35 fields. The captured primary
and alternate boot commands reference both NAND boot targets in opposite order
and an MMC target; the NAND targets name root block devices 7 and 9. This
corroborates the published whole-chip-overlay partition numbering and the two
root ranges. It does not demonstrate boot selection, automatic rollback or recovery.
Environment fields include credential material, so values remain private. No
boot/environment command was run or edited. Published configuration defaults must
not be substituted for these captured environments.

All four embedded image headers and payload CRCs were freshly verified in the
corrected view: the two SPL locations and two kernel locations agree with the
published layout. The secondary root range was independently reconstructed with
the earlier bounded CRC-checking JFFS2 recipe, changing only range/output paths.
It yields 2567 regular files with zero scanned common/inode/data/dirent CRC
failures. Symlinks and special nodes were not created. Primary and secondary
regular-file maps differ; their nlclient, osm, libnlappcore and libnlwebservice
bytes match. Preserve both originals rather than treating either entire bank as
an interchangeable copy or a demonstrated rollback image.

Within the source-corresponding 736-block scratch range, 725 blocks have erased
data and only the expected eight-byte JFFS2 cleanmarker in the first page's OOB.
The remaining eleven blocks are not classified as empty by that test. Even an
apparently empty filesystem block therefore has metadata to preserve; erasing
the scratch range or assuming all-FF OOB would destroy evidence/state. This is a
historical capture survey, not a measurement of current contents after later
native startups, and it does not select a block for writing.

Before any persistent test: identify the exact live chip/partition/write-ECC
contract, freshly acquire the proposed region under exclusive guarded RAM access,
preserve complete data/OOB and verify the original restoration input. Prepare one
concrete bounded operation and its failure handling, notify the owner of its
risks/limits, then distinguish any scratch-block write/erase test from firmware
restoration. Boot stages, configuration/credentials, unknown filesystem contents
and backplate firmware remain protected. No flash writer/apply command has been
created or executed, and no installation or restoration is claimed here.

A separate [controller metadata profile](../../firmware/nand_contract/README.md)
is now fully prepared offline to measure the custom kernel's detected bus width,
marker flags/descriptor and ECC/OOB layout before designing a writer. It includes
no NAND contents or mutation interface, retains the geometry protection gates,
and has not executed. Six artifacts reproduce exactly after pinning nonsemantic
legacy build metadata. The [prepared scope](../security/validation-2026-10-31-nand-contract-prepared.json)
distinguishes those host/build checks from a target observation or restoration.
