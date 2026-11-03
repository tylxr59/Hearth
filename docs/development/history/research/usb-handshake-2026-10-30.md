# First ROM handshake failure and paced retry — 2026-10-30

## Physical evidence

The owner ran the guarded experimental RAM-probe command from commit `c721c71`
and supplied the terminal output. The loader opened `0451:d00e` on the known
USB port, then failed sending the four-byte first-stage length:

```text
device timed out while transfering out 4 bytes (0 made it)
failed to length specifier of 27856 to OMAP BootROM
failed to transfer the first stage file 'x-load-gen2.bin'
```

The pinned native source reaches that length send only after its ASIC-reply
check and peripheral-boot command have succeeded. Its file-data send is after
the failed length check and was not reached. These are software-flow inferences,
not a wire capture: zero bytes reported by libusb is not independent proof of
what the peripheral consumed. No custom x-loader/kernel execution or heartbeat
was observed, and no flash write was requested.

Immediately afterward, host sysfs still showed `0451:d00e`. With the loader
exited, the owner performed one manual restart and reported the home icon.
Host sysfs then confirmed `2464:0002`. This establishes return to native startup
and normal USB identity, not firmware restoration or HVAC functionality.

## Evidence behind the transport change

The current USB host controller reports driver `xhci_hcd`. NLE's pinned
TypeScript loader uses the same command/length/data sequence as our native
loader; it chunks writes but has no explicit pause before each short control
transfer. The native loader originally had neither pacing nor chunking.

Doug Brown's [first-hand USB-sniffer investigation](https://www.downtowndougbrown.com/2025/11/debugging-beagleboard-usb-boot-with-a-sniffer-fixing-omap_loader-on-modern-pcs/)
describes early OMAP upload stalls on newer controllers and a working timing
adjustment on OMAP3530 BeagleBoards. His [upstream PR #7](https://github.com/grant-h/omap_loader/pull/7)
provides the corresponding source changes. The reviewed PR source is pinned at
`dougg3/omap_loader` commit `a33d75376f56f54285cdf6933e312b856146593b` in
upstreams.json and the probe input lock.

This is a plausible explanation for the observed Nest failure, not a confirmed
root cause. The upstream measurements concern different hardware. No USB wire
capture, changed timing measurement or successful paced upload exists here yet.

The local GPL patch now includes:

- A 1 ms interval before every bulk input/output call.
- At most 512 bytes per output transfer, including a short final chunk.
- A 20 ms settling interval after the first-stage payload transfer, before
  requesting x-loader data. This is inside transfer_first_stage in our backport.
- Non-identifying progress messages for ASIC reply length, boot command, file
  length and payload transfer; raw ASIC/debug data remain omitted.

The wrapper also refuses an already-active ROM device at startup. A new attempt
must begin at normal Nest USB mode and wait for the owner's physical restart.
Neither a timeout nor a missing heartbeat triggers an automatic second boot.
Failures now explicitly tell the operator to exit and restore native startup.

## Offline validation and prepared artifacts

The native ASan/UBSan harness now additionally exercises a synthetic 69-byte ASIC
reply, exact little-endian boot/length words, a 1030-byte payload split into
512/512/6 bytes, required pacing before each bulk call, the settling interval,
and a repeated length timeout that must prevent the file-data path. Existing
argument-allocation, unterminated debug message, port binding and 12-byte jump
checks remain. All libusb calls used by the harness are mocked. Its timing
assertions check calls/ordering, not physical controller behavior.

The native test build adds `-Wl,--wrap=usleep` to the earlier harness command.
The updated native loader compiles with the previous warning/hardening flags.
No newly compiled native loader has opened physical USB during preparation.

The current build is `build/ram-probe-reliability-20261030`. Its kernel,
bootloaders, init and configuration are copied only after matching all five
hashes from the preserved first build. Only host transport/helpers changed.
The new manifest records that relationship and the updated loader/patch hashes.
The original build and dated validation report remain intact.

Fresh validation: 97 host tests passed, including the rootless Podman TLS
broker/container tests; make check and the guarded dry run passed. The source
release's archive/reproducibility checks also passed after adding .gitattributes
to preserve exact upstream whitespace inside the patch. No new dependency or
compiler/kernel build occurred for this transport-only change. Python dependency
audit results from the earlier same-day report retain their original scope.

## Automation permissions

`/dev/sdb` is the normal-mode diagnostic block device. Writable access there
does not grant the ROM loader access and can enable unintended persistent
filesystem changes. Do not grant it merely to automate this boot test.

The required access is instead the ROM USB node beneath `/dev/bus/usb`, followed
by the expected CDC ACM heartbeat tty. A local rule was prepared under ignored
`build/usb-access-20261030/70-hearth-probe-local.rules`; it is user-specific and
is not a source/release artifact. It grants a named ACL only to the current
owner's UID, on physical port `1-1`, for ROM `0451:d00e` and expected probe tty
`0525:a4a7`. Root ownership is retained and other access is restricted. It has no
normal Nest USB or block-device rule. udevadm 262 verified the rule; setfacl is
available. The ACL approach avoids deprecated non-system OWNER assignments and
does not depend on a graphical/logind active-seat session.

The owner confirmed installation/reload of this root-managed rule. The agent
verified the installed bytes match the reviewed file, with root ownership and
no group/other write permission. No rule was installed by the agent. No broad
udev trigger is required: the next ROM/tty enumeration applies the rule.
The assistant started one guarded paced attempt without sudo from confirmed
normal USB mode and prompted for the manual restart; its result will be recorded
below. Host helpers still collect only the expected fixed heartbeat. The manual display restart remains a human
step. Permission changes do not waive advance risk notice or the backup/recovery
gates; no acquisition, flash or HVAC capability is added by this rule.

The first unprivileged paced wait expired with exit 124. Its native output was
buffered in a pipe, so there is insufficient stage evidence to classify the
physical handshake. The owner reports a restart and return to the home icon.
At the owner's explicit request to try again, a second paced wait was started
with a PTY for immediate native progress output, again from confirmed normal
USB mode. Its result is pending; do not infer successful payload execution from
the prior timeout. Next: record that result and verify native startup afterward. Experimental RAM-code risk
remains as described in the probe README. If it fails, stop for diagnosis.


## Successful paced boot and return to native startup

The owner triggered the PTY-backed attempt while the loader was waiting. It ran
without sudo. The native trace reported:

```text
ROM ASIC reply received (69 bytes; identifying data omitted)
ROM boot command transferred
ROM first-stage length transferred (27856 bytes)
ROM first-stage payload transferred (27856 bytes)
successfully transfered 3 files
```

The scoped serial observer then returned `probe-heartbeat-observed`, with
`flash_access=disabled-in-probe-kernel` and `recovery=unverified`. The wrapper
exited successfully. A separate sysfs read observed `0525:a4a7` on port `1-1`
while the probe was running. These observations establish execution of the
custom diagnostic kernel/init and its USB serial path on this unit. The timing
change worked on this attempt; the original failure's exact electrical cause
remains an inference without a wire capture.

With the loader exited, the owner performed another manual restart and reported
the home icon. The short return monitor observed serial gadget -> disconnect ->
OMAP ROM -> disconnect, then expired before normal USB re-enumeration. A follow-up
read confirmed `2464:0002`. Do not report the monitor itself as capturing a normal
mode transition that its bounded window missed.

No NAND acquisition or restore occurred. The running Linux probe has no MTD,
block or network support. This is a custom-boot/USB milestone, not a native control,
power-safety, backup, firmware recovery or deployment result. Next: separately
review a NAND geometry-only kernel with hardware write protection, scan/write-path
constraints and no filesystem mounts or user-accessible flash write interface.
