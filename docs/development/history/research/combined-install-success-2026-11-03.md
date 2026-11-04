# Capacity and both installs passed in one boot, 2026-11-03

On the measured Gen 2 Display-2.6 / 5.9.4-5, one fresh owner-approved PTY loader
boot ran the corrected combined supervisor. The display remained detached on
USB. It ran capacity, commissioning9, and cleanup3 in that order, without an
intervening reboot or ring action. The owner separately approved each persistent
file group after its live read-only checks. The existing HA entry was preserved;
no intentional HVAC action, HA restart, archive deletion or restore occurred.

## Observed results

| Stage | Result | NAND page programs | Erases | Failed operations |
| --- | --- | ---: | ---: | ---: |
| Capacity | Passed; sealed, no-write check | 0 | 0 | 0 |
| Commissioning9 | Complete, readback and encoding verified, safe to restart | 131 | 0 | 0 |
| Cleanup3 | Complete, readback and encoding verified, safe to restart | 2,907 | 0 | 0 |

Capacity measured 13,201,408 bytes available against 12,461,733 required, with
44,580,864 bytes free RAM. Cleanup's own preflight measured 13,197,312 available
against 12,245,531 required. Both writer results reported zero action, rollback,
journal, release, unmount and seal errors, and protected state 1. The original
results retain diagnostic 21 alongside complete/verified/encoding/safe flags 1
and error 0; do not rewrite this marker or describe every numeric field as zero.

All three successful results were saved before their distinct terminal
acknowledgements. Both forward kernel slot transitions succeeded. The final
combined result reports both phases completed, encoding verified and safe to
restart. The worker and supervised host exited successfully. The owner was
instructed to restart normally, detached on USB. Native USB subsequently
returned and was confirmed by the host; HA readings remain to be confirmed. On-base behaviour has not been tested by this run.

## What this does and does not establish

The corrected supervisor's RAM hardlinks/renames, child bootstraps, capacity
slot, forward transitions and both real writes now have one successful hardware
run. The nominated shared-original archive path and lowered install margin
passed this case. The fresh standalone restore images were built and checked,
but no guided restore was executed. Restore margin measurement, whole-firmware
restore and power-loss recovery remain open.

This run used the protected live original-file reader because the preceding
accepted full backup contained a checksum-invalid settings inode fragment that
the offline extractor refused. No gate was loosened and no old original was
substituted. Thus archive-only extraction for this filesystem state remains
unresolved. Earlier automatic backup-to-successor transfer was observed, but the
successful combined boot here was manual. Do not claim the complete reduced-boot
wizard has passed end to end or that pristine-stock provisioning was measured.

Profiles, plans, restore capsules, source snapshots, separate owner approvals,
console and all stage evidence remain private and single-use. Preserve them.
Host validation remains 1,949 passing tests, seven optional skips and passing
static checks; the isolated HA checks were run earlier without touching the
owner's HA instance.

## HA verification correction

The owner subsequently reported no Hearth entry in HA and supplied an
integrations screenshot without one. Earlier statements that the entry was
preserved were based on reusing its matching saved commissioning bundle, not
a live inspection of HA. The bundle was preserved; current entry existence and
post-restart readings were not verified. Read-only authenticated diagnosis is
pending. Do not recreate an entry/profile or restart HA without authorization.

## Final return check

After the separately approved HA profile repair, the owner reattached the
display and confirmed the normal dial and live HA readings. Read-only HA
observation confirmed fresh temperature/humidity and availability. See the
[profile repair and final observation](ha-profile-repair-2026-11-03.md).
No HVAC command, HA Core restart or new device write was needed for that repair.
