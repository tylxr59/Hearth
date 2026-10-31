# Protected JFFS2 file snapshot observed

One owner-timed execution used source `c73904e` and the previously checked
`build/file-snapshot-20261031-v4`. The three RAM boot files transferred; loader
and collector exited zero. The complete session/CRC/footer-checked frame is
81320 bytes and remains private with all originals, metadata and receipts.

All nine targets were classified: seven existing files and two absent new
targets. The read-only adapter accepted the JFFS2/mount/ownership/path/metadata
guards and read every existing file twice. The host fsynced and read back all
backup bytes before issuing its custody receipt. A separate post-run decode
and complete backup verification passed. All seven existing originals also
match the preserved offline review byte-for-byte; no fresh differences were
found. This observation does not authorize blindly reusing an old snapshot in
a later writer: the writer still needs a fresh exact preflight.

No file was installed or changed. The profile has hardware WP and mutation
callback guards, no writable flash mount, no native applications and no physical
networking. This establishes this bounded read-only JFFS2 capture and private
host custody path, not JFFS2 write durability, installation/rollback, full native
startup/transport, firmware restoration or HVAC behavior. The root0 source
label describes the custom kernel view. The owner separately reported a fresh
native plist selection of primary and firmware 5.9.4-5 before the run.

The execution marker and original preparation manifest remain intact; never
reuse this build as another execution profile. A private immutable observation
and comparison record preserve the result. The owner has been prompted for the
manual restart after command exit; native return is pending confirmation.
No loader or collector remains running.

Next: bind the fresh export/receipt to the exact replacement plan, implement
interrupted-install journal inspection/restoration and integrate the bounded
filesystem writer. Notify the owner before any persistent commissioning. The
previous 623 host tests/five optional skips and make check are preparation
evidence; no new host test run is claimed by this hardware result.
