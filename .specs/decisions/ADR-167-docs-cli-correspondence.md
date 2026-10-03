---
kind: adr
id: ADR-167
title: 'ADR-167 — Documentation is sensed for correspondence with the live CLIs'
status: accepted
---

<!-- path: .specs/decisions/ADR-167-docs-cli-correspondence.md -->

# ADR-167 — Documentation is sensed for correspondence with the live CLIs

**Date:** 2026-10-03 (revision 3: released core-cli explicit; hidden-alias clause scoped to `core-admin`)
**Status:** Accepted 2026-10-03 (governor)
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-10-03)
**Grounds:** ADR-065 D1 (`docs/` is a governed communication surface); ADR-146 (two CLIs:
`core-admin` in core-runtime, `core` in core-cli); ADR-076 (context-level dispatch); `cli.help_required` (reporting).
**Relates:** `core-admin docs generate` / `shared.cli.reference_markdown` (b52af26a).

## Context

Documentation drifted from the CLIs it describes, and nothing noticed:

- `docs/cli-reference.md` documented ~25 `core-admin` commands that live in `core` (or nowhere)
  and omitted 47 live ones (replaced by generated pages on 2026-10-03).
- The starter and demo READMEs described a rule set retired three months earlier; the core-cli
  README used command names the CLI does not register.

ADR-065 decides *where* a document belongs. It does not decide whether a document is *true*.
This ADR adds that, for the claim docs make most often and that drifts fastest: which
commands exist.

## Decisions

### D1 — Command/docs correspondence is sensed, both ways

Docs and the live CLIs must agree in both directions:

- **CLI → docs (no gaps):** every visible command is documented. Met by the generated
  reference (D2) plus `cli.help_required` for content. Hand-written guides are not required
  to mention every command.
- **docs → CLI (no phantoms):** every command docs mention exists and is current (D3).

Both rules are `reporting` until their measured backlog is zero, then the governor promotes
each to `blocking` individually.

### D2 — `cli.reference_current`: the generated reference matches the live trees

`docs/reference/core-admin.md` and `docs/reference/core.md` must equal what
`render_cli_reference` produces from the live `core-admin` tree and the installed core-cli
tree. Deterministic, no false positives.

The released core-cli (from PyPI) is installed wherever this rule runs: CORE's development
environment (`make install`, which the daemon runs from) and CI. When it is missing anyway, the `core.md`
comparison is not performed and the rule emits a finding saying so, naming the remedy. It
never passes with the comparison skipped.

### D3 — `cli.docs_no_phantom_commands`: every mentioned command exists

Scope: `docs/**/*.md` except `docs/reference/` (generated), plus the paths listed in the
mapping params (initially `README.md`). A mention is `core-admin <group> <command>` or
`core <group> <command>` inside an inline code span or a fenced code block; prose is not
read, because "core" is an ordinary word.

- `core-admin` mentions resolve against the live tree.
- `core` mentions resolve against the headings of the committed `docs/reference/core.md`,
  the inventory of the released core-cli. No import is needed, so this check never
  degrades. It relies on D2 keeping that page current: a stale `core.md` can let a
  phantom `core` mention pass, and D2 flags the staleness.
- A `core-admin` mention of a hidden (deprecated) alias is a finding: it exists, but a reader
  should not copy it. (The generated `core.md` lists visible commands only, so a hidden `core`
  alias is reported as a phantom.)
- `allow_mentions` in the mapping params lists exact strings that are exempt, for migration
  notes that name removed commands on purpose.

### D4 — Placement

Both rules live in the `cli` rule namespace and run in `cli_gate` as context-level checks,
so the existing `audit_sensor_cli` senses them in the daemon; no new sensor or engine. The
engine reads the in-scope markdown and passes it to the checks with the walked command
registry; checks stay pure.

### D5 — Links and anchors are a tool gate, not a rule

Link and anchor validity in `docs/` is enforced by the docs build: Deploy Docs runs
`mkdocs build --strict` with anchor validation at `warn`, so a broken link fails the build.
That change lands in the same change-set as D2 and D3.

## Not decided here

- **Remediation** of docs findings (regenerating generated pages through a proposal, LLM
  prose drafts with governor approval). Requires consumer pipelines to claim non-`python::`
  subjects (`audit_namespaces.py`); a later decision once the backlog is measured.

## Consequences

- A CLI rename now shows up as findings on every doc that names the old command.
- `core-admin docs generate --write` becomes the remedy for D2 findings; until remediation is
  decided, an operator runs it.
- The `core` page is only as current as the installed core-cli; `make install` and CI
  install it so the D2 check runs.

---

## Amendment 2026-10-03 — declared core-cli version; both rules blocking (governor ruling)

**Status:** Accepted (governor ruling 2026-10-03)

**D2, corrected.** Where D2 says "the released core-cli (from PyPI)", read: **the core-cli
release CORE declares**. CORE declares the core-cli version its documentation corresponds
to in one place (the Makefile's `CORE_CLI_DOCS_VERSION`); `make install` and CI install
exactly that version. A blocking rule must not depend on whatever PyPI calls latest: an
unrelated core-cli release would turn CORE red without a byte of CORE changing, and an old
CORE commit would not reproduce. Moving the declared version is a deliberate change that
ships with the regenerated `docs/reference/core.md`.

**Promotion.** Both backlogs measured zero against the released core-cli 2.0.0, so per the
enforcement posture above: `cli.docs_no_phantom_commands` is `blocking`, and, with the
version declared, `cli.reference_current` is `blocking`.

**Scope, restated.** D3 senses which commands exist and are current, in the
command-shaped mentions it defines. It does not judge whether prose about a real command
is true, and this ADR does not extend it to.
