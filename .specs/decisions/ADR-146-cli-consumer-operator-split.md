---
kind: adr
id: ADR-146
title: 'ADR-146 — CLI Consumer/Operator Split'
status: accepted
depends_on: ["ADR-050", "ADR-054"]
---

<!-- path: .specs/decisions/ADR-146-cli-consumer-operator-split.md -->

# ADR-146 — CLI Consumer/Operator Split

**Status:** Accepted (governor decision 2026-07-07)
**Date:** 2026-07-07
**Governing paper:** `.specs/papers/CORE-Deliberate-Non-Goals.md`
**Authors:** Darek (Dariusz Newecki)
**Closes:** #317
**Relates to:** ADR-050 (CLI extraction), ADR-054 (package split)

---

## Context

ADR-050 D2 planned to extract all of `src/cli/` into a new `core-cli` repo.
Analysis of the actual command surface revealed that a blanket move is
incorrect: some commands require in-process access to CORE internals (database
sessions, worker infrastructure, governance engine) that cannot be satisfied
over HTTP. Moving those commands to a purely HTTP consumer CLI would either
break them or silently degrade them to best-effort stubs.

The user population splits cleanly along this boundary:

- **Consumer** — an external developer or team governing *their own* project
  via CORE-as-a-service. They never run CORE itself; they interact exclusively
  through the HTTP API that CORE exposes. Pure HTTP is both necessary and
  sufficient.
- **Operator** — the person running CORE itself (typically the governor). They
  need direct in-process access: daemon control, database ops, constitution
  introspection, governance workflows. HTTP is insufficient.

Conflating these two populations into one package forces the consumer package
to carry heavyweight in-process dependencies it does not need, and forces the
operator surface to expose internals over HTTP that should never leave the
process boundary.

---

## Decisions

### D1 — Two surfaces, not one

CORE's CLI is split into two independent surfaces along user-population lines:

| Surface | User | Transport | Package |
|---------|------|-----------|---------|
| Consumer | External project owner | Pure HTTP | `core-cli` (new repo) |
| Operator | CORE governor/operator | In-process | `core-admin` (stays in CORE) |

No command migrates in both directions. The split is exhaustive: every
`src/cli/` command belongs to exactly one surface.

### D2 — Consumer surface namespaces (extracted to `core-cli`)

The following `src/cli/commands/` subtrees are consumer surface and move to
`core-cli`:

- **Full namespaces:** `lane/`, `proposals/`, `secrets/`
- **Partial — `code/`:** `actions`, `audit_duplicates`, `bridges`,
  `check_imports`, `check_ui`, `docstrings`, `fix_atomic`, `format`,
  `integrity`, `lint`, `logging`, `test`. Excluded (operator): `audit.py`,
  `clarity.py`, `complexity.py`, `refactor.py`
- **Partial — `symbols/`:** `audit`, `fix_ids`, `resolve_duplicates`, `sync`.
  Excluded (operator): `tag.py`
- **Partial — `vectors/`:** `query`, `rebuild`, `status`, `sync`, `sync_code`.
  Excluded (operator): `cleanup.py`
- **Partial — `project/`:** `docs`, `onboard`, `scout`. Excluded (operator):
  `new.py`

All consumer commands communicate exclusively over HTTP; they MUST NOT import
from `body`, `mind`, or `will`.

### D3 — Operator surface stays in CORE (`core-admin`)

The following namespaces remain in CORE under `core-admin`:

- Full namespaces: `daemon/`, `database/`, `coherence/`, `constitution/`,
  `context/`, `dev/`, `grc/`, `workers/`, `runtime/`, `intent/`
- `admin/` subcommands: `meta`, `self_check`, `traces`
- Operator-only files excluded from D2: `code/audit.py`, `code/clarity.py`,
  `code/complexity.py`, `code/refactor.py`, `symbols/tag.py`,
  `vectors/cleanup.py`, `project/new.py`

These commands may freely import from any CORE layer. They are never packaged
into `core-cli`.

### D4 — `core-cli` depends on `core-runtime` as a PyPI dep

`core-cli` does not vendor or copy shared infrastructure. It declares
`core-runtime` as a PyPI dependency and imports:

- `cli.utils.*` — CLI utility helpers
- `api.cli.*` — HTTP client layer for CORE's API
- `shared.*` — cross-cutting substrate

Only the resource command files (`core_cli/resources/`) are new code in the
`core-cli` repo. This avoids import namespace collisions: `core-runtime`
provides the shared substrate; `core-cli` adds only the consumer resource
layer. No import renaming is required in the extracted files.

### D5 — Package namespace

`core-cli` uses `core_cli.*` for its own resource files (e.g.,
`core_cli.resources.lane`). Support files (`cli.utils`, `api.cli`,
`cli.logic`) remain in `core-runtime`'s `cli.*` namespace.

The two packages co-install cleanly:

- `core-runtime` provides `cli.*`
- `core-cli` provides `core_cli.*`

No namespace collision; no `__init__.py` surgery required.

### D6 — Entry points

| Entry point | Package | Target | Notes |
|-------------|---------|--------|-------|
| `core` | `core-cli` | `core_cli.main:app` | Consumer governance CLI |
| `core-admin` | CORE (`core-runtime`) | `cli.admin_cli:app` | Operator surface |

The `core = "cli.cli_user:app"` conversational entry point is **retired** from
`core-runtime`. It imports from `will` (conversational AI orchestration); that
interface is a separate future concern and does not belong in either the
consumer or operator CLI as defined here.

### D7 — ADR-050 D1 compliance timing

ADR-050 D1 requires that `core-cli` contain no imports from `src/` (body,
mind, will). This is achieved structurally:

- `core-cli` imports `cli.*` and `api.cli.*` via the `core-runtime` PyPI dep,
  not via direct source path.
- At the package boundary, `core-cli` is entirely independent of CORE's layer
  internals.

D1 is satisfied the moment `core-cli` is installed as a separate package.
No intermediate shim or import guard is required.

---

## Deliverables

| ID | Artifact | Change |
|----|----------|--------|
| D1 | `.specs/decisions/ADR-146-*.md` | This ADR — split decision recorded |
| D2 | `core-cli` repo | New repo; consumer resource commands extracted from D2 namespaces |
| D3 | `src/cli/` in CORE | Operator commands remain; consumer commands removed post-extraction |
| D4 | `core-cli/pyproject.toml` | Declares `core-runtime` as dep; no vendored shared code |
| D5 | `core-cli/core_cli/` | New package namespace for consumer resource modules |
| D6 | Entry point wiring | `core-cli` exposes `core`; CORE retains `core-admin`; `cli_user:app` retired |
| D7 | Import audit | Verify no `body`/`mind`/`will` import paths in extracted `core-cli` files |
