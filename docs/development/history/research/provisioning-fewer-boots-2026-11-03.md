# Provisioning with fewer RAM boots: implementation and offline checks

No USB loader was armed, no thermostat command was sent, no flash was written,
and no HA entry or Core process was changed during this work.

## Implemented

- `installer/nand_inputs.py` reconstructs the two fixed snapshots and four
  passive library groups from the checked full-NAND data view. It preserves
  a separate offline provenance receipt and re-extracts when custody is checked.
  Existing frame encodings are compatibility containers, not claimed live USB
  captures. Free-space statistics are unknown/zero; only device preflight can
  admit space. Unsupported compression, missing fragments, unsafe fixed targets,
  attributes and ambiguous metadata refuse; there is no automatic reader boot.
- `firmware/install_sequence/` combines capacity, commissioning9 and cleanup3
  under one supervisor. Original-file device checks, synthetic tests, separate
  commit prompts, individual transactions, seals and readback remain. Three
  distinct, ordered kernel slots replace repeated kernel boots; none is reopened.
- Standalone restore images remain available. Durable per-stage write intent
  selects reverse-order restoration after an interrupted combined attempt.
- `firmware/rom_restart/` prepares a separate one-shot, nonce-bound warm-reset
  experiment and concrete supervised plan. It is not enabled in setup and has
  not been executed. It tests a normal kernel reset, not an undocumented forced
  ROM boot order.

## Offline evidence and limits

A preserved NAND data view (matched to its saved quality digest) reconstructed
13 fixed records and 126 regular library/executable files. This was a parser
exercise, not a fresh device read or re-admission of the historical backup under
changed recipes. Its files and reports were left unchanged.

The three-slot kernel compiled in the existing network-isolated Podman builder
and passed the normal source, partition, binding, protection and image checks.
Both original writer helper sets and both supervisors compiled for ARM. A
private offline composition using preserved input data produced a 7,664,736-byte
RAM archive and 4,296,220-byte USB image, below the unchanged 24 MiB and 6 MiB
bounds. This composition is not an executable install profile and was not run.

The warm-reset profile built and passed offline checks. Its first USB boot still
requires owner readiness; warm-reset USB ROM enumeration, loading a successor
image, combined persistent installation/rollback, and failure/power-loss behavior
remain unmeasured. No whole-chip recovery claim follows from these checks.

Final validation: 1,928 tests passed with seven optional skips; static checks
passed. The network-isolated HA 2026.10.4 sandbox passed 24 native control
round trips and automatic onboarding. Its initial onboarding run exposed a
stale `SETUP` test answer; the fixture now answers the existing `[y/N]` prompt
with `y`. Original failed logs were preserved. See the public
[validation record](../validation/validation-2026-11-03-provisioning-fewer-boots.json).
