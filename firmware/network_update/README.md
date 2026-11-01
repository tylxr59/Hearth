# Fixed network update data and transaction contract

This module prepares a four-file correction, not a deployable firmware installer.
There is currently no persistent execution command here. Proprietary originals,
candidate bytes, endpoint addresses, hashes, plan headers and pins stay private.

The independently written bounded SHA-256 implementation follows the mathematical
algorithm in [NIST FIPS 180-4](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf).
It accepts at most 6 MiB, which bounds the length arithmetic. It is checked against
independent hashlib results and synthetic ARM vectors, not NIST module validation.
No third-party hash implementation was copied.

`stream.c` verifies the complete original and derived candidate, as well as the
exact equal-width span, using a 4 KiB buffer. Preflight calls no write callback.
Copies target only caller-owned memory/temporaries; they provide no path lookup,
rename, authorization or flash access. Unexpected data outside the span also fails.
Short/interrupted I/O, error/zero returns, overruns and retry exhaustion fail closed.

The separate `HEARTH_NETWORK_ADAPTER` contract instantiates the existing POSIX
transaction under four fixed root0 paths and per-target 6 MiB/1 MiB/64 KiB/64 KiB
limits. Every file must exist, preserve length/mode, and use a plan-derived recovery
archive. The legacy header and its 1 MiB limit remain unchanged. Original ordering,
journal and interrupted-restore logic are reused. `roots[1]` must be a second
descriptor for root0, never the user-state partition. Kernel enforcement must also
restrict the physical write range to root0 before any persistent attempt.

The chosen wrapper design reuses this tested byte-comparison adapter with bounded
RAM-backed originals/candidates, rather than introducing another journal format.
Originals can be opaque non-executable root-only files in the private initramfs,
mapped read-only and hash checked; candidates are derived in a bounded RAM arena.
The complete-file writes still use owned temporaries and the forced-NONE kernel,
followed by exact readback and the existing active-fragment encoding audit. This
wrapper, its memory/space guards and persistent kernel gate are still pending.

`provisioning.network_plan` reconstructs candidates only from fully verified fresh
custody, generates deterministic private DATA, and independently rechecks all
bytes against a separate reviewed plan pin. It grants no device authorization.

The [protected RAM preflight](../network_probe/README.md) passed 41 memory/stream
checks, 20 synthetic filesystem transactions and all four real original/candidate
preflights. That measured only RAM writes and read-only real files. Large-file NAND
write/restore, power-loss recovery and physical HVAC remain unverified.
