# Protected startup evidence acquisition

This diagnostic investigates the native UI remaining at the home icon after the
first nine-file install. The owner reports a steady icon with blinking green LED
on the completely unwired base; Wi-Fi setup cannot be reached. Native USB remains
available. These observations do not identify a root cause or prove app health.

The static original syscall-only reader runs on the unchanged, previously
measured protected JFFS2 snapshot kernel. Hardware WP, denied write callbacks,
no MTD character/block interface, and no networking remain enforced. No native
application/library executes. The raw external newc archive works with the
kernel's enabled BLK_DEV_INITRD and disabled RD_GZIP; no gzip or new kernel build
is required. Failure to start the external archive cannot enable flash writes.

It captures the nine fixed commissioning files using the original read-only
snapshot guards and a separate bounded read-only `mtd:log` tree. At most64 regular
files,64KiB tail each,512 scanned entries, four directory levels and239-byte paths
are retained. It opens relative descriptors with NOFOLLOW/NONBLOCK, never follows
symlinks or reads device/FIFO contents, checks metadata before/after reads and
reports partial acquisition/limits explicitly. It does not mount the data partition.
All potentially identifying/credential-bearing logs stay private; never print
raw lines, upload them or put them in source. Host parsing uses the stored frame,
not a command interface on the thermostat.

`profile package` compiles only original C and statically checks exact archive,
kernel/config/bootstrap and source provenance. It opens no device. `run` defaults
to those offline checks. Execution requires a fresh private output and explicit
`--execute-read-only-startup-diagnostic`, a normal-mode preflight, PTY and one
owner-timed restart. No serial input/start token, installer, automatic retry or
native program launch exists. Both session-bound CRC frames must complete before
snapshot custody is declared preserved; partial frames remain private evidence.

Host sanitizer checks cover nested files, bounded tails, symlinks, FIFOs, file and
depth limits; receiver checks cover wrong sessions, corrupt evidence and path
substitution. These are original trusted host fixtures, not firmware execution.
Preserve prior installation/backup/recovery evidence. A startup failure must not
be treated as a reason to weaken original-file or restoration checks.
