# Four-file network snapshot result

The owner confirmed native primary/5.9.4-5 through a serial-filtered plist, then
authorized the prepared read-only RAM restart. The PTY-backed loader transferred
its three files and exited successfully. All four records and private backup
readbacks passed. No native firmware executed on the host or inside the RAM image;
flash writes were disabled in the unchanged proven kernel.

Fresh files match their preserved inputs exactly:

| File | Bytes |
| --- | ---: |
| Native client | 5122360 |
| ConnMan | 687028 |
| ConnMan configuration | 3063 |
| Installed client configuration | 10380 |

The total is 5822831 bytes. Root0 statfs reports 21782528 available bytes, including
reclaimable dirty space; this does not guarantee successful staging. Filesystem
identity, full bytes, metadata, hashes, sessions and receipts remain private.
Existing firmware captures and recovery archives are unchanged.

After command exit the owner confirmed the home icon and normal USB 2464:0002
was independently observed. The display remains on USB, detached from its base,
for charging. No loader or persistent operation is armed. Never rerun the executed
profile or its reproduction. Preparation, execution and separate immutable
attempt records remain independently preserved.

Preparation passed 929 host tests with five optional skips, `make check`, 49 new
focused reader/custody/transport checks and byte reproduction of all eight artifacts.
Trusted-host sanitizer cases cover links, special files, attributes, ownership,
permissions, interrupted/short/failed reads, reread differences and files larger
than the legacy 1 MiB bound. No proprietary firmware runs in those tests.

This closes acquisition of the four proposed targets, not large-file write/restore,
rewrite encoding, power-loss recovery or physical control. Next implement the
separate streaming replacement adapter and RAM/fault tests using these exact
originals. HA 0.2.1 remains unchanged. Google removal still requires a device
update and actual traffic verification.
