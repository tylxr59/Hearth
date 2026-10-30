# Acquisition and diagnostic boot review — 2026-10-30

Status: host checks complete; experimental RAM-probe execution pending. No
firmware dump or recovery path has been acquired. This supplements the
[physical intake](device-intake-2026-10-30.md), not the historical validation
report. The owner authorizes device investigation and requests advance notice
before potentially dangerous work. No physical payload has been sent this turn.

## What NLE actually boots

Reviewed the existing thermostat pin `fabbe034f01cefdabe06b93d1c312068f563a177`.
The builder downloads Google's 5.9.4 x-loader, historical NestDFU Linux/U-Boot and
an old CodeSourcery compiler. Its generated rootme script mounts mtdblock7
writable, installs startup/CGI files, replaces configuration/trust material and
optionally installs fixed-password SSH access. It is unsuitable for acquisition
before a backup. Download/build scripts were read as text, not executed.

The pinned prebuilt uImage was downloaded to ignored build storage and checked
against the pre-existing SHA-256 inventory:
`4a1392c2c867a15e52cdee2eaadd252289f68aa60ab2b70a1fe79f48a2e89c52`.
Its 64-byte legacy header and payload CRCs passed. The header says Linux/ARM,
kernel, container compression none. Its zImage self-decompresses using LZMA;
this is distinct from header-level compression. The stream at payload offset
7348 decoded to 24,926,976 bytes. The uncompressed embedded newc archive began
at offset 141632, occupied 20,164,500 bytes and had 3331 non-trailer entries.
117 entries were ELF files. Nothing was executed or generically extracted.

The embedded init symlink targets `/bin/busybox`. Its inittab, rcS, start and
fstab hashes match the historical inputs already pinned in upstreams.json.
The embedded rootme SHA-256 is
`2f10d25e2a227dd0ed41c7cf67f2d3b9f286f2f9be898d3963004c137b14f9e7`.
Inspection confirms writable root mounting, SSH/default password setup, endpoint
and CA replacement, CGI startup installation and reboot. The chosen image is
therefore not an acquisition-only RAM payload, despite being loaded through RAM.
Its embedded archive also lacks the nlclient/osm paths sought by this project.
These facts narrow the acquisition plan; they do not establish binary authenticity
or reproducibility from NLE source.

## Independent minimal probe build

[firmware/probe/inputs.json](../../firmware/probe/inputs.json) pins all inputs.
The new x-loader input is Google's published 5.9.4 source at
`9b7bb7281b715544e6f5201390d8dac416a4a494`. The Linux/U-Boot input remains the
original NestDFU revision. Only those GPL source subtrees are staged; its
proprietary root, old initramfs, scripts and prebuilt programs are excluded.
The original ARM init uses direct EABI syscalls and links without libc.

The U-Boot fork defaults to `Display-2.0` and the J49 prototype branch. The
experimental build explicitly uses the reported `Display-2.6` and its source's
J49 PVT branch. This is a model-specific hypothesis, not a measured board revision.
No persistent environment is used (`CONFIG_ENV_IS_NOWHERE`); boot-count updating
is disabled. NAND command support and hardware initialization remain in the
bootloader, and their absence of physical side effects has not been measured.

The Linux configuration disables MTD, BLOCK, NET, WLAN, MMC, PCMCIA, JFFS2 and
the stock dynamic USB gadget. It enables the standard USB serial gadget.
Our fixed initramfs is 2440 bytes, containing only six entries: `.`, `dev`,
`proc`, `sys`, `dev/console` and the static ARM `init`. Its only output is a
fixed heartbeat. It mounts only virtual filesystems and accepts no commands.
The entire decompressed kernel is 2,672,800 bytes. Offline checks found the exact
minimal initramfs bytes in that kernel and checked the init ELF, image CRCs,
load/entry parameters and disabled subsystem configuration. These are integrity
checks, not a proof of safe execution or a backup/recovery capability.

Builds ran under rootless Podman 6.1.4, with the generated public-source directory
as the only bind mount, no USB/device access, network none, dropped capabilities,
no-new-privileges, 4 GiB RAM, four CPUs and a 256-process limit. The builder base
is pinned in Dockerfile; its observed OS was Ubuntu 20.04.6. Its initial assembly
installed build packages in the container, not the host. The compiler archive's
HTTPS mirror/digest are recorded; independent signature verification and compiler
reconstruction remain unresolved. Container/legacy OS CVE analysis is pending.

The final build is `build/ram-probe-final-20261030`; generated artifacts are
ignored and not included in source releases. Its current file hashes are:

| Artifact | SHA-256 |
|---|---|
| `kernel.config` | `273e5d6a27617982e7d450167bef42eba4dbabc081868b790f341c14bdde7826` |
| `omap_loader` | `8a821dcf4a82d7cca27391f57f88c7f445abf7276e305adf502014046d3f6dbd` |
| `probe-init` | `5004278472b8623995c05e9b4c4c55c69ad422a09cb0676b853710cc61653557` |
| `u-boot.bin` | `5f924a02508eb0360645ea71228934f854f8310370808b82108a58fa672b443f` |
| `uImage` | `538d9da6c78b671a1261413fd0ab45678a4d7191bdc86ab365b8f55c8cf59ebb` |
| `x-load-gen2.bin` | `e9f543e77636961a9acd6723e6b6cf7392a7a33b02ad6f61b97ab85157d8939e` |

These locally generated hashes are unsigned integrity records, not independent
binary authentication. `sources.json` preserves the actual source archives and
recipe hashes from staging. Host helper files finalized after the kernel build
are separately hashed in `probe-manifest.json`; they are not kernel inputs.
Kernel/bootloader bit-for-bit reproducibility has not been established.

## Referenced native USB loader

The ajb142/grant-h loader points to the same commit
`dc0758f91a4698054b0629a05f1b38b9b8b13de3`. It is GPL-2.0-or-later. Source inspection
found both `realloc(args->files, fileCount)` allocations reserve bytes instead
of pointer-array elements, and the debug handler passes potentially unterminated
USB data to strlen. An ASan test of the original parser reproduced the heap
buffer overflow before any USB initialization. The checked-in patch fixes those
paths, omits device-specific ASIC/debug logging, claims/releases interface zero,
rejects zero-progress transfers and protocol-oversized inputs, and closes input
files after successful reads. The patched loader also binds uploads to USB bus 1,
direct port 1, and sends the
12-byte jump frame expected by Google's reviewed x-loader (the original sends
eight bytes). Header opcode names for NAND dumping have no matching handler in
that x-loader and are not acquisition evidence. Hardware upload/re-enumeration
compatibility is
still untested. These fixes are not a complete audit of the old loader.

The host-only harness mocks USB initialization/bulk transfer. It tests a three-file
argument list plus an unterminated 512-byte debug message followed by a synthetic
file request/size/data/12-byte jump exchange. It also rejects simulated wrong
bus, wrong port and nested-port paths. It neither sends real USB traffic nor
executes a firmware image. Reproduce against the staged, patched public source:

```sh
gcc -std=gnu11 -Wall -Wextra -O1 -g -fsanitize=address,undefined \
  -fno-omit-frame-pointer $(pkg-config --cflags libusb-1.0) \
  -I build/ram-probe-final-20261030/loader firmware/probe/test_loader.c \
  -Wl,--wrap=libusb_init -Wl,--wrap=libusb_bulk_transfer \
  -Wl,--wrap=libusb_get_bus_number -Wl,--wrap=libusb_get_port_numbers \
  $(pkg-config --libs libusb-1.0) -o build/ram-probe-final-20261030/loader/sanitizer-tests
ASAN_OPTIONS=detect_leaks=0 build/ram-probe-final-20261030/loader/sanitizer-tests
```

Leak checking is disabled for the historical parser's process-lifetime argument
allocations; address/undefined-behavior checks remain enabled. The native
host loader was built with `-O2 -Wall -Wextra -Werror -D_FORTIFY_SOURCE=3
-fstack-protector-strong -Wl,-z,relro,-z,now` and the installed libusb 1.0.30.
Its --help path and the build's no-argument boot.sh dry run completed without
opening USB. No loader execution with a real payload has occurred.

## Next device action and remaining gates

[The probe instructions](../../firmware/probe/README.md) specify the exact local
command, fixed RAM addresses, known USB port, single manual restart, fixed
heartbeat observation and return to native startup. The reader suppresses
unknown received bytes and does not send application commands. The owner has
been told that this next stage runs experimental RAM code and may hang or reset;
keep the display detached from its unwired base. There is no user task involving
wiring, factory reset, flash offsets or proprietary firmware installation.

A passing heartbeat would establish this probe's runtime/USB path only. Confirm
native startup afterward, then separately design read-only raw NAND/OOB and ECC
acquisition with bounded power/watchdog behavior. The old OMAP NAND driver sets
NAND_SKIP_BBTSCAN; the generic NAND code can otherwise write flash BBT metadata
when permitted. A future acquisition kernel needs a full write-path review,
not merely read-only mounts. Source-defined partitions in a custom kernel are
not evidence of the stock runtime MTD layout. No raw flash writes may occur until
backups, their limits and demonstrated restoration meet hardware.md.

Secure native IPC/transport, TLS/bootstrap, provisioning and HVAC behavior remain
unresolved. Host tests and a RAM heartbeat cannot establish those properties.
