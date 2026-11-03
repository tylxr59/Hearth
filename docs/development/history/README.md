# History archive

> [!IMPORTANT]
> **Nothing here is current status or instructions.** This is the dated lab
> notebook from the investigation (October to November 2026). For the current
> state, see [status](../status.md). For facts that still matter, see
> [findings](../findings.md).

Files are kept unchanged as evidence, apart from relative links that were
updated when the docs were reorganised on 2026-11-03. Paths written as plain
text *inside* these files (for example `docs/research/...` in a JSON record)
refer to the old layout:

| Old path | New path |
| --- | --- |
| `docs/research/*.md` | `docs/development/history/research/` |
| `docs/research/*.json` (source pins) | `docs/development/references/` |
| `docs/security/validation*.json` | `docs/development/history/validation/` |
| `docs/security/*-audit.json`, `python-dependencies.json` | `docs/development/references/` |
| `docs/security/{audit,threat-model,network}.md` | `docs/development/history/security/` |
| `docs/architecture/` | `docs/development/architecture/` |
| `docs/hardware.md` | `hardware-gates.md` |
| `docs/protocol/nest.md` | `laboratory-protocol.md` |

## Contents

| Path | What it is |
| --- | --- |
| `research/` | Dated notes for each experiment: preparation, attempt and result |
| `validation/` | Machine-readable validation records for each prepared/observed run and HA release |
| `security/` | The original security audit, threat model and network model. Written for the retired MQTT laboratory backend; still a useful reference for isolation |
| `agent-handoff-2026-11-02.md` | The full running agent handoff log up to 2 Nov (large) |
| `native-ha-development.md` | HA integration development walkthrough, versions 0.3–0.6 |
| `hardware-gates.md` | The original bench validation and recovery gate plan |
| `laboratory-protocol.md` | The retired laboratory API/MQTT protocol, and early native protocol notes |
| `laboratory-readme.md`, `laboratory-roadmap.md`, `retired-app-docs.md` | The README, roadmap and add-on docs from the laboratory era |
| `implementation-plan.md` | The very first iteration plan |

When you add a new dated result, put it in `research/` (and `validation/` if
it's machine-readable), then summarise any lasting fact in
[findings](../findings.md) and update [status](../status.md).
