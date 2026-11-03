# Hearth: agent instructions

Hearth connects a modified Nest Learning Thermostat (Gen 2) directly to Home
Assistant over the Nest's native local protocol. It has two parts: a HACS
integration (`custom_components/hearth/`) and a Linux USB setup wizard
(`provision.py` → `installer/`) that builds and installs per-device file
changes.

**A real thermostat wired to real heating is attached to this project.** Read
[docs/development/status.md](docs/development/status.md) before any work, and
the relevant source before changing it. Older material under
`docs/development/history/` is an archive, not current status.

## Live hardware: hard rules

- **Keep the Nest's native HVAC control loops.** HA sends bounded settings
  through native subscriptions. Never implement relay logic or replacement
  regulation.
- **Measured target only:** Gen 2, Display-2.6, primary firmware 5.9.4-5. Never
  claim Gen 1, other firmware, cooling, emergency heat or fan operation from
  simulation or reference code.
- **The owner's base is wired to real oil/baseboard heat.** Never assume an
  unwired base when the display is reattached.
- **Never re-run** an executed install/restore image, an attempted wizard phase
  or an old HA control action. Profiles are single-use evidence.
- **Before any persistent device write,** explain its concrete scope and
  recovery limits, and get explicit owner approval.
- **Before arming any ROM loader,** get owner readiness. Use a PTY, one
  owner-timed boot, no automatic retry, and a fresh private output/profile.
- **Physical controls** need a concrete supervised test plan first, and the
  saved original must be restored afterwards. Never infer equipment support from
  missing reported flags.
- **Never bypass restore refusals or blindly erase NAND.** Never delete on-device
  archives without explicit authorisation.
- **HA Core restarts need fresh owner approval every time.** Deliver
  integration updates through HACS. Never deploy by hand over the HACS install,
  and never recreate the old profile or the owner's current HA entry.
- **Recovery limits:** selected-file restore is measured. Whole-firmware restore
  and hardware power-loss recovery are not. No spare unit is required: the owner
  accepted same-unit work with one local recovery archive.

## Current authorisation

| Allowed without asking | Needs fresh owner approval |
| --- | --- |
| Local code, docs, packaging, tests | Any persistent device write |
| Commits and pushes | Arming a ROM loader |
| Building or reproducing private profiles (no execution) | An HA Core restart |
| | Any intentional HVAC call |
| | Deleting anything on the device |

Current device state, recent hardware results and the next optional step are in
[status](docs/development/status.md). In short: the display is detached, on USB
in native mode, no loader is armed, and the stock files have been
independently verified. Leave it that way.

## Source rules

- `backend/` is the canonical native transport. `custom_components/hearth/_backend/`
  is **generated**: run `python -m tools.sync_integration` and never hand-edit
  it. `--check` enforces an exact match.
- All runtime HA files stay inside `custom_components/hearth/`. HACS ships only
  that folder. Don't revive the retired laboratory add-on (`homeassistant/`,
  `Dockerfile`, MQTT backend).
- NoLongerEvil (NLE) is a pinned protocol/behaviour reference. Write original
  implementations, record behavioural sources and licensing
  (`docs/development/references/upstreams.json`, `THIRD_PARTY.md`), never copy
  proprietary firmware, and never present reference-code agreement as hardware
  validation.
- Firmware changes need the existing bounded source/ABI/RAM/backup checks for
  that writer. **Never remove a gate to make an installer pass.**
- The wizard's terminal output goes through `installer/ui.py`, which is stdlib
  only because the wizard runs before any venv exists. Tests feed `ask()`
  answers positionally, so adding or removing a prompt means updating the
  tests.
- Read the detected target OS before running package or service commands. Add
  no new system packages or host services without task authorisation.

## Privacy and release

- Identifiers, credentials, IP topology, native bytes, binary hashes,
  proprietary libraries and per-device kits live only in git-ignored
  `private/` or `build/`. Never publish a commissioning bundle, private key or
  restore capsule.
- Preserve executed profiles, manifests, results and backup evidence.
- Strip metadata from images before committing.
- Run `python build/review-source-push-20261030.py` before pushing, when it
  exists. Release artifacts contain public original source only.
- Release assets are `hearth.zip` (HACS; the name is fixed by `hacs.json`) and
  `hearth-nest-installer.zip`, whose contents `tools/installer_archive.py`
  computes. See [releases](docs/development/README.md#releases).
- No stable v1 tag, and no "turnkey stock-device installer" claims, until the
  [release checklist](docs/development/roadmap.md) is closed.

## Validation

```sh
make test
make check
python -m tools.check_native_ha build/<fresh-name> --engine podman   # pinned, network-isolated real HA
```

## Documentation conventions

- **User docs** (`README.md`, `docs/*.md`): plain language for a technical
  generalist. Lead with what to do, and keep internal jargon (diagnostic codes,
  profile names) out.
- **Developer docs** (`docs/development/`): [status](docs/development/status.md)
  (short and current), [findings](docs/development/findings.md) (lasting facts),
  [roadmap](docs/development/roadmap.md) (release gates).
- **New dated results** go in `docs/development/history/research/` (plus
  `validation/` for JSON records). Then update status and, if lasting, findings.
  Don't append dated diaries to this file or to the user docs.
- Keep [compatibility](docs/compatibility.md) in step with the evidence:
  hardware, simulation and not-tested are separate claims.
