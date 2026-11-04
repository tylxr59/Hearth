# Fresh supervised backup refused, 2026-11-03

Following the combined supervisor RAM setup correction, the owner approved one
fresh backup boot. One PTY loader transferred the protected restartable reader
with one owner-timed ring boot. Both complete fixed raw/OOB passes were saved.

Independent verification refused archive quality. The corrected data views
matched; neither pass contained uncorrectable chunks; the three unclassified
chunks matched. However, one bit in one spare-area byte differed between the
two reads. It was offset 44, inside the configured ECC parity area, not a
bad-block marker. The verifier requires exact spare-area equality as well as
corrected data equality. The gate was retained unchanged. The observation does
not establish why the read differed or diagnose hardware failure.

The driver exited before extracting originals or building a kit. No successor
loader was armed, no software restart token was sent, and no installer write
was requested. The corrected combined supervisor did not execute. Raw passes,
quality report, source snapshot, profile and console remain in the separate
private session. This attempt must not be replayed or relabelled accepted.

The owner was told to restart normally with USB connected and the display
detached. Confirmation is pending; no loader is armed. A separate fresh profile
has been prepared and checked offline, with no execution. Any further boot requires fresh owner readiness;
there is no automatic retry. Installation still requires separate approvals
for both file groups, and full-chip/power-loss recovery remains unverified.
