# Documentation style guide

How to write Hearth docs, for people and AI agents alike. Read this before
adding or changing any `.md` file.

## Who reads what

| Audience | Files | Write for |
| --- | --- | --- |
| **Users** | `README.md`, `docs/*.md`, `installer/README.md` | A technical generalist: comfortable with a terminal and Home Assistant, not with NAND, JFFS2 or this project's internals |
| **Developers and agents** | `AGENTS.md`, `docs/development/*.md`, `firmware/*/README.md` | Someone about to change code who needs the current facts and the rules |
| **The record** | `docs/development/history/` | Future investigators. Dated, preserved as written |

If a sentence would confuse a user, it belongs in the developer docs.

## Where things go

| You have… | Put it in | Not in |
| --- | --- | --- |
| A new hardware result, attempt or refusal | A new note in `history/research/<topic>-<YYYY-MM-DD>.md` (plus `history/validation/` for JSON) | `status.md`, `findings.md`, AGENTS.md or user docs |
| A change to the current device state or what's next | `status.md`, by **replacing** the old text | A new bullet on top of old ones |
| A fact that stays true and shapes the code | `findings.md`, with a link to the dated note | A narrative of how it was found |
| A release gate or future work | `roadmap.md` as a checkbox | `status.md` |
| Something users can now do, or must do differently | The relevant user guide | `status.md` only |
| What is or isn't verified on hardware | `compatibility.md` | Scattered caveats |
| What changed in a release | The commit message and release notes | `status.md` |
| A rule agents must follow | AGENTS.md, as one short bullet | A paragraph of history |

When you add a dated note, also update `status.md`, and `findings.md` if the
fact is lasting, in the same change.

## Writing for users

- **Lead with the action.** Say what to do first, then why. Use numbered steps
  for sequences and tables for comparisons or symptom → fix.
- **Plain words.** Use the user's terms, not ours:

  | Don't write | Write |
  | --- | --- |
  | RAM boot, loader armed | the Nest restarts into setup mode, the wizard waits for the Nest |
  | commissioning9 / cleanup3 | the first part (Home Assistant settings, trust and startup) / the second part (connectivity check and time server) |
  | capacity preflight | free-space check |
  | readback, encoding audit | the wizard checks every file it wrote |
  | profile, kit, custody | the wizard's install files, your private folder |
  | diagnostic 42, `safe_to_restart 1` | not enough space; the wizard says it's safe to restart |
  | root0, NAND, OOB | the Nest's storage, its flash memory |

- **Be honest and short about limits.** Say once, plainly, what hasn't been
  tested ("hasn't been tested on a thermostat yet"). Don't repeat the caveat in
  every paragraph, and don't hide it.
- **Safety instructions are concrete.** "Keep USB connected. Don't restart the
  Nest." beats "preserve the session pending review".
- No dates, version diaries or internal history in user docs. Mention an old
  name only when users will meet it, e.g. a renamed release asset.

## Writing developer docs

- **`status.md` stays short and current**, aiming for one screen per section:
  device state now, what's authorised, what's unreleased, what's next, what's
  unmeasured. Each update **replaces** stale text. Move older events into their
  dated notes, and delete release history (it lives in the release notes). Keep
  only the latest few hardware events, newest first, each with one link.
- **`findings.md` holds facts, not stories.** Use present tense ("The native
  kernel cannot read LZO nodes"), with a link to the dated note for the
  evidence. No "in this session", "one run", "later" or "earlier".
- **Research notes** start with a title ending in the date, then a short
  paragraph saying what was and wasn't done on the device (loader, writes,
  HVAC, HA restarts). Follow with sections such as *Result*, *Analysis*,
  *Changes* and *Follow-ups*. Numbers go in tables. Never edit a note after the
  fact. Write a new one that links back.
- **Firmware READMEs** describe what the component is and its current role.
  Update the repo map in `docs/development/README.md` whenever a component is
  added, retired or first measured.
- **AGENTS.md** holds rules and a one-paragraph state summary that points to
  `status.md`. Never append events to it.

## Evidence words

Use the same three claims everywhere: docs, commit messages and release notes.

| Claim | Meaning | Marker in tables |
| --- | --- | --- |
| **Verified on hardware** | Ran on the measured Gen 2 and the result was checked | ✅ |
| **Automated / simulated only** | Host tests, synthetic fixtures, HA sandbox or reference-code agreement | 🧪 |
| **Not tested** | No evidence yet | ❌ |

- Say what was measured, on what, and what wasn't: "passed on one unit",
  "built but not run on a thermostat".
- A successful write is not a working install, and a protocol acknowledgement is
  not a confirmed value. Name the step that actually passed.
- When the evidence changes, update `compatibility.md` and the user guides in
  the same change.

## Formatting

- GitHub-flavoured Markdown. One `#` title per file and sentence-case headings.
- Wrap prose at about 80 columns. Don't reflow untouched paragraphs.
- Relative links between repo files (`[status](status.md)`). Full URLs only for
  external pages. Every link must resolve.
- Code, paths, commands, typed answers and identifiers go in backticks:
  `python3 provision.py`, `INSTALL`, `/config/.storage/hearth`.
- **Numbers:** use a space between word and number ("port 1-1", "version
  0.11.2", "5 MiB"), and thousands separators in prose and tables
  (13,217,792 bytes). Use MB for user-facing sizes and MiB/KiB for exact binary
  limits.
- Callouts (`> [!WARNING]`) are for genuine risk, at most one or two per page.
- Strip metadata from images before committing. Use descriptive alt text.

## Privacy

Never put serial numbers, device IDs, credentials, IP addresses of the owner's
network, native firmware bytes, binary hashes, private paths' contents or
per-device kits in any doc. Use placeholders like `YOUR_HA_IP` and
`/dev/sdX`. Aggregate measurements (sizes, counts, timings) are fine.

## Before you commit docs

- [ ] Each change is in the right file (see "Where things go").
- [ ] User docs pass the plain-words table, with no internal terms or dates.
- [ ] `status.md` was replaced, not appended to, and still fits its purpose.
- [ ] Hardware, simulation and not-tested claims are kept apart, and
      `compatibility.md` matches.
- [ ] Links resolve, the repo map is current and nothing private is included.
