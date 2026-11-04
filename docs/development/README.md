# Developer guide

Read [AGENTS.md](../../AGENTS.md) (the safety rules) and [status](status.md)
before changing anything that can reach a real thermostat. How Hearth works,
and the hardware facts behind it, are in [internals](internals.md).

## Setup and checks

```sh
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.lock

make test        # pytest (~2,000 tests)
make check       # integration sync check, ruff lint+format, bandit
make audit       # pip-audit against the lock files
.venv/bin/python -m tools.check_native_ha build/<fresh-name> --engine podman
```

`check_native_ha` runs the integration inside a pinned, network-isolated real
Home Assistant container and exercises the control round trips and onboarding.
Use a fresh `build/` name each time.

## Repository map

| Path | What it is |
| --- | --- |
| `custom_components/hearth/` | The Home Assistant integration (what HACS installs) |
| `custom_components/hearth/_backend/` | **Generated** copy of `backend/`. Never hand-edit |
| `backend/` | Canonical native Nest transport: protocol, TLS listener, state, schedules |
| `installer/` | The USB setup wizard and CLI (`provision.py`, `python -m installer.cli`) |
| `installer/ui.py` | Terminal formatting for the wizards (stdlib only) |
| `provisioning/` | Builds the replacement files: settings, TLS trust, startup, network, time |
| `firmware/` | RAM-boot programs and bounded flash writers (see below) |
| `tools/` | Packaging, release, integration sync, HA sandbox check, NAND archive verifier |
| `tests/` | pytest suite, plus C fault fixtures that ship as writer compiler inputs |
| `provision.py` | Entry point inside the released installer ZIP |
| `docs/` | User docs at the top level, developer docs in `docs/development/` |
| `homeassistant/`, `Dockerfile`, `tools/package_addon.py` | **Retired** laboratory add-on and MQTT backend. Kept for tests. Don't revive it |

### `firmware/`

Each subproject began as a single-purpose RAM-boot experiment. Later ones reuse
earlier ones' kernel configs, C sources and profile code, so most of them are
now build inputs to the install path, even when their name says "probe". Never
re-run an executed profile.

| Subproject | Role today |
| --- | --- |
| `probe/` | Base Display-2.6 RAM-boot kernel and loader recipe; everything builds on it |
| `nand_capture/` | Whole-chip read-only NAND backup (wizard step 3) |
| `nand_handoff/` | Restartable backup reader: after the backup, restarts the Nest into the install without a ring press (wizard steps 3 to 6). The restart and transfer passed on hardware; the full path has not |
| `acquisition/` | Snapshot encodings and custody checks. Wizard step 4 reconstructs inputs offline via `installer/nand_inputs.py`, and falls back to this live read-only reader if extraction refuses |
| `install_sequence/` | One RAM boot for capacity, commissioning and cleanup (wizard step 6); passed on hardware |
| `rom_restart/` | Standalone warm-restart experiment that first showed a software restart reaches USB ROM; not used by normal setup |
| `file_writer/` | Fixed-plan JFFS2 writer: nine-file commissioning phase and its restore |
| `network_writer/` | Three-file connectivity/time phase, capacity preflight and restore |
| `file_install/`, `file_reencode/`, `network_update/` | Transaction, encoding and data contracts the writers compile in |
| `nand_contract/`, `nand_metadata/`, `nand_sample/`, `file_snapshot/`, `network_*`, `settings_*`, `startup_diagnostic/`, `tls_probe/`, `file_install_probe/` | Earlier diagnostics whose kernels, sources or profile code the writers reuse |
| `scratch_test/`, `nand_ecc_sample/`, `encoding_audit/` | Standalone diagnostics, not in the install path |
| `harden.py`, `prepare.py` | Shared offline preparation helpers |

Each subproject's code and `profile.py` are its documentation. How the pieces
fit together is in [internals](internals.md). The old per-component READMEs and
dated lab notes are in the
[history archive](https://github.com/tylxr59/Hearth/tree/history-archive-2026-11/docs/development/history).

## Rules that matter

- **`backend/` is canonical.** After editing it, run
  `python -m tools.sync_integration`. `make check` fails if `_backend/` drifts.
- **Keep runtime HA files inside `custom_components/hearth/`.** HACS ships only
  that folder.
- **NoLongerEvil is a protocol reference, not a code source.** Write original
  implementations and record behavioural sources in
  [references](references/upstreams.json) and `THIRD_PARTY.md`.
- **Keep evidence types apart.** Simulation, reference-code agreement and
  real-hardware results are different claims. Update
  [what's tested](../technical.md#whats-tested) only when the evidence
  changes.
- **Never weaken a gate** (source/plan binding, custody, exact-original
  comparison, encoding audit, typed confirmations) to make something pass.
- **Private material stays in `private/` and `build/`** (both git-ignored):
  identifiers, IPs, native bytes, binary hashes, proprietary libraries, kits.

## Releases

1. Bump the version in `custom_components/hearth/manifest.json` **and**
   `pyproject.toml`. They must match.
2. `make check test`, the HA sandbox check, and
   `python -m tools.public_release build/<name>` (twice, then compare: the build
   is deterministic).
3. Run `python build/review-source-push-20261030.py` if it exists locally.
4. Push a `v0.x.y` tag. The release workflow publishes an ordinary
   (non-prerelease) GitHub release, so HACS's default selection picks it up.

### Release assets

| Asset | Built by | Contents |
| --- | --- | --- |
| `hearth.zip` | `tools/package_native_ha.py` | The HA integration (about 50 files). The name is fixed by `hacs.json`: **don't rename it** |
| `hearth-nest-installer.zip` | `tools/installer_archive.py` | The USB wizard inside a `hearth-nest-installer-<version>/` folder |
| `SHA256SUMS` | `tools/public_release.py` | Checksums for both |

`RELEASE-NOTES.md`, which explains each asset, becomes the top of the release
body. `release.json` is build metadata. Neither is uploaded as an asset.

The installer's contents are **computed**:
`python -m tools.installer_archive x --list` prints them. The selection starts
from `provision.py` and `installer/*.py`, then repeats until nothing new is
found:

- it follows Python imports;
- it includes whole `firmware/<component>` and `tools/<component>` directories
  for any module it reaches;
- it follows string constants that name repo files or components;
- it follows C `#include`s;
- it picks up the `tests/*.c|h` fixtures that builders compile.

Developer tools, retired lab code, pytest-only harnesses and lockfiles stay
out. Prose (`.md`) never pulls code in. Nothing outside the package
directories and `tests/` can be selected, so `private/` and `build/` can never
leak in. The extracted archive re-snapshots itself byte-identically, minus the
folder prefix, which the wizard relies on for restores.

If you add a file that a builder reads through a computed path, check that
`--list` includes it. The release test also checks that every recipe file is
present.

`tools/public_release.py` refuses any version not starting with `0.`. Don't
publish a stable v1 or advertise a turnkey installer until the
[release checklist](roadmap.md) is closed.

## Documentation

There are only a few docs, and each has one job:

| File | Holds | Write for |
| --- | --- | --- |
| `README.md`, `docs/*.md` | What users do: install, use, fix, undo, and what's tested | A technical generalist, comfortable with a terminal and HA |
| `AGENTS.md` | Rules for agents, plus a one-paragraph state summary | Agents |
| [status.md](status.md) | Device state now, what's authorised, what's next, what's unmeasured | Whoever touches the hardware next |
| [internals.md](internals.md) | How Hearth works and lasting hardware/protocol facts | Developers |
| [roadmap.md](roadmap.md) | Release gates, as checkboxes | Developers |
| [device-settings.md](device-settings.md) | Every setting field and its bounds | Developers and curious users |

Keep the user guide file names (`installation`, `usage`, `troubleshooting`,
`recovery`). Released wizards link to them.

**How to write them:**

- **Users:** lead with the action, then why. Use plain words: "the Nest
  restarts into setup mode", not "RAM boot"; "the wizard checks every file it
  wrote", not "readback". No dates or internal history. Say each limit once,
  plainly. Safety steps are concrete ("Keep USB connected. Don't restart the
  Nest.").
- **Status:** replace, never append. Keep the latest few hardware events,
  newest first. Release history lives in the release notes.
- **Internals:** present-tense facts, no stories ("in this session",
  "later"). There are no dated notes in the repo any more. Put a hardware
  result's details in the commit message, and link existing evidence through
  the history archive tag.
- **Evidence words**, everywhere: ✅ verified on hardware (say on what, and
  which step passed), 🧪 automated/simulated only, ❌ not tested. A successful
  write is not a working install, and an acknowledgement is not a confirmed
  value. When evidence changes, update `docs/technical.md` in the same change.
- **Format:** GitHub-flavoured Markdown, one `#` title, sentence-case headings,
  about 80 columns, relative links that resolve, backticks for code, paths and
  typed answers. Space between number and unit ("5 MiB"), thousands separators
  (13,217,792 bytes). One or two callouts per page at most.
- **Privacy:** no serial numbers, device IDs, credentials, owner IP addresses,
  native bytes, binary hashes or kit contents. Use placeholders like
  `YOUR_HA_IP` and `/dev/sdX`. Strip metadata from images.

Brand assets: `assets/logo.png` (README) and
`custom_components/hearth/brand/icon.png` (served locally by HA). Both have
their metadata stripped. Strip metadata from any new image before committing.
