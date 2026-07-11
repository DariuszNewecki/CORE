# CORE — External Adoption Gap Closure Plan

**Status:** In progress (2026-07-11)
**Audience:** Governor — sequencing and scope decisions
**Companion analysis:** Strategic review verified against working tree 2026-07-11

---

## Background

A strategic review recommended CORE shift investment from capability to
external consumability. Verification against the codebase confirmed three
of the reviewer's claimed gaps are already closed (offline audit, machine-
readable output, OEM API contract). Four genuine gaps remain. This document
scopes them in priority order.

The ADR-085 constraint (capacity routes to the 5+3 operational-completeness
list) relaxes after #563 closes (~2026-07-29). The items below are intended
as the first post-relaxation sequence.

---

## Item 1 — Evidence Chain Query Endpoint

**Status: DONE** (committed this session)

**Priority:** High
**Effort:** Small (days)
**Value:** Highest per-unit effort of the four items

### What it is

A unified REST endpoint that answers: given a finding, show the complete
governance chain — which rule fired, what evidence, what proposal was
created, who approved it, what executed, which files changed, what the
resulting git SHAs are.

### What was built

- `GET /v1/proposals/{id}/chain` — full governance chain for a proposal
- `GET /v1/findings/{entry_id}/chain` — reverse lookup finding → proposal → chain
- `GovernanceChainResponse`, `FindingEvidence`, `ProposalSummary`,
  `ConsequenceRecord` Pydantic models in `src/api/v1/schemas.py`
- `get_consequence_log_service()` DI provider in `src/api/dependencies.py`
- `get_chain_for_proposal()` and `get_finding_proposal_link()` added to
  `src/body/services/consequence_log_service.py`
- `src/api/v1/findings_routes.py` — new route file registered in `main.py`
- `tests/api/v1/test_chain_routes.py` — 6 tests covering both endpoints

### Acceptance criterion

Met: `GET /v1/proposals/{id}/chain` returns a single JSON object tracing a
finding from detection through execution to file changes.

---

## Item 2 — Governance Pack Abstraction

**Status: DONE** (committed this session)

**Priority:** Medium-high
**Effort:** Medium (1–2 weeks)
**Value:** Unlocks external adoption without requiring manual rule authoring

### What was built

- `.intent/META/governance_pack.schema.json` — pack declaration schema
- `.intent/META/intent_tree.schema.json` — updated to include `packs:` section
- `.intent/META/intent_tree.yaml` — `packs` added to `optional_directories`
- Three builtin packs in `.intent/packs/`:
  - `core/starter-python` — 4 rules, zero-friction default for any Python repo
  - `core/python-hygiene` — 8 rules, intermediate baseline
  - `core/architectural-boundaries` — 4 rules, layered architecture targets
- `src/shared/infrastructure/intent/pack_loader.py` — `PackLoader` + `LoadedPack`
- `src/shared/infrastructure/intent/intent_repository.py` — `list_packs()` +
  `load_pack()` delegation methods added
- `src/cli/resources/project/adopt_pack.py` — consumer CLI command (migrates
  to `core-cli` in Item 3 Phase C)
- `tests/shared/infrastructure/intent/test_pack_loader.py` — 17 tests

### Acceptance criterion

Met: `core project adopt-pack core/starter-python --target-dir ./my-repo`
previews the rule and enforcement YAML that would be written. `--write` applies.

---

## Item 3 — ADR-146 Implementation (Consumer CLI Extraction)

**Priority:** High (structural; blocks the clean external distribution story)
**Effort:** Large (2–3 weeks)
**Value:** Eliminates in-process dependency drag from the external CLI package

### What it is

Execute the accepted split from ADR-146: extract the consumer CLI command
surface into a new `core-cli` repository that depends on `core-runtime` as
a PyPI package and communicates exclusively over HTTP. `core-admin` stays
in CORE with full in-process access.

### Current state

ADR-146 is fully specified (governor decision 2026-07-07, closes #317). The
command-level split is documented precisely:

- **Consumer → `core-cli` (new repo):** `lane/`, `proposals/`, `secrets/`,
  most of `code/`, `symbols/`, `vectors/`, `project/` (see ADR-146 D2 for
  full list)
- **Operator → `core-admin` (stays):** `daemon/`, `database/`, `coherence/`,
  `constitution/`, `context/`, `dev/`, `grc/`, `workers/`, `runtime/`,
  `intent/`, operator-only subcommands (ADR-146 D3)

The `api/cli/` HTTP client layer already exists in `core-runtime`
(`src/api/cli/`). Consumer commands must be rewired to call it instead of
importing `body`/`mind`/`will` directly.

### Phase A — Audit and classify

**Status: DONE** (completed this session)

**Key finding:** The ADR-146 D2 consumer commands do not exist in CORE's
`src/cli/resources/` — all files in those namespaces are operator-only or
empty. Consumer commands must be written from scratch for `core-cli`. The
Phase A audit maps which HTTP routes and `api/cli/` clients are already in
place to determine Phase B–C execution order.

#### Migration table — ADR-146 D2 consumer surface

| Namespace | Planned commands | HTTP route | `api/cli/` client | Status |
|-----------|-----------------|------------|-------------------|--------|
| `lane/` | `list`, `next`, `get`, `claim`, `propose-diff` | `GET/POST /v1/lane/…` | `lane_client.py` | ✓ ROUTE READY |
| `proposals/` | `create`, `list`, `get`, `chain`, `approve`, `reject`, `execute` | `GET/POST /v1/proposals/…` | `proposals_client.py` | ✓ ROUTE READY |
| `project/adopt_pack` | `adopt-pack` | reads from installed wheel | shared layer only | ✓ DONE (Item 2) |
| `code/lint` | `lint` | `POST /v1/lint` | `audit_client.py` | ✓ ROUTE READY |
| `code/integrity` | `integrity` | `POST /v1/integrity/{baseline,verify}` | `integrity_client.py` | ✓ ROUTE READY |
| `code/actions` | `actions` | `GET /v1/fix/actions` | `fix_client.py` | ✓ ROUTE READY |
| `code/fix_atomic` | `fix-atomic` | `POST /v1/fix` | `fix_client.py` | ✓ ROUTE READY |
| `code/logging` | `logging` | `POST /v1/fix` | `fix_client.py` | ✓ ROUTE READY |
| `code/check_imports` | `check-imports` | `POST /v1/lint` | `audit_client.py` | ✓ ROUTE READY |
| `vectors/sync` | `sync` | `POST /v1/sync/vectors` | `sync_client.py` | ✓ ROUTE READY |
| `vectors/sync_code` | `sync-code` | `POST /v1/sync/code-vectors` | `sync_client.py` | ✓ ROUTE READY |
| `secrets/` | `set`, `get`, `list`, `delete` | **None** | **None** | ✗ BLOCKER |
| `code/audit_duplicates` | `audit-duplicates` | **None** | — | ✗ BLOCKER |
| `code/bridges` | `bridges` | **None** | — | ✗ BLOCKER |
| `code/check_ui` | `check-ui` | **None** | — | ✗ BLOCKER |
| `code/docstrings` | `docstrings` | **None** | — | ✗ BLOCKER |
| `code/format` | `format` | **None** | — | ✗ BLOCKER |
| `code/test` | `test` | **None** | — | ✗ BLOCKER |
| `symbols/audit` | `audit` | **None** | **None** | ✗ BLOCKER |
| `symbols/fix_ids` | `fix-ids` | **None** | **None** | ✗ BLOCKER |
| `symbols/resolve_duplicates` | `resolve-duplicates` | **None** | **None** | ✗ BLOCKER |
| `symbols/sync` | `sync` | **None** | **None** | ✗ BLOCKER |
| `vectors/query` | `query` | **None** | **None** | ✗ BLOCKER |
| `vectors/rebuild` | `rebuild` | **None** | **None** | ✗ BLOCKER |
| `vectors/status` | `status` | **None** | **None** | ✗ BLOCKER |
| `project/docs` | `docs` | **None** | — | ✗ BLOCKER |
| `project/onboard` | `onboard` | **None** | — | ✗ BLOCKER |
| `project/scout` | `scout` | **None** | — | ✗ BLOCKER (waits Item 4) |

#### Gap clusters

| Gap cluster | Commands blocked | Route file to add |
|-------------|-----------------|-------------------|
| `secrets/*` | 4 | `src/api/v1/secrets_routes.py` (new) |
| `symbols/*` | 4 | `src/api/v1/symbols_routes.py` (new) |
| `code/` partial | 6 | Add to `audit_routes.py` or new `code_routes.py` |
| `vectors/` partial | 3 | Add to `sync_routes.py` |
| `project/docs`, `project/onboard` | 2 | `src/api/v1/project_routes.py` (new) |
| `project/scout` | 1 | Part of Item 4 |

### Phase B — New `core-cli` repository scaffold

**Status: DONE** (prior session, commit `06b38c0 feat: initial extraction —
consumer governance CLI (ADR-146)` at `/opt/dev/core-cli`)

The repo exists at `/opt/dev/core-cli` with the structure from the plan.
CI workflow added this session (`.github/workflows/ci.yml`). All namespace
directories and command files are present.

**D7 violation catalog** (files requiring migration; `body`/`mind`/`will` or
direct-DB imports per ADR-146 D7):

| File | Violation | Blocks on |
|------|-----------|-----------|
| `proposals/list.py` | `cli.logic.autonomy.views` (color/render dicts) | Fix now — inline Rich rendering |
| `proposals/manage.py` | `cli.logic.autonomy.views` (render functions) | Fix now — inline Rich rendering |
| `proposals/create.py` | `cli.logic.autonomy.actions` (arg parser) | Fix now — inline parsing |
| `secrets/manage.py` | `get_session`, `secrets_service` (direct DB) | `secrets_routes.py` route |
| `vectors/rebuild.py` | `get_session` (direct DB) | `vectors/rebuild` route |
| `vectors/query.py` | `QdrantService`, `CognitiveEmbedderAdapter` (direct infra) | `vectors/query` route |
| `code/audit_duplicates.py` | `cli.logic.duplicates` | `audit_duplicates` route |
| `project/onboard.py` | `cli.logic.byor` | `project/onboard` route |
| `project/scout.py` | `cli.logic.scout` | Item 4 |
| `project/docs.py` | `cli.logic.project_docs` | `project/docs` route |
| `symbols/audit.py` | `cli.logic.diagnostics`, `cli.logic.symbol_drift` | `symbols_routes.py` route |

The `proposals/*` violations are fixable now (routes exist). All others
require their blocking API routes to be added to CORE first.

### Phase C — Migrate commands one namespace at a time

**Status: IN PROGRESS**

Sprint 1 (unblocked — routes exist):
- [ ] Fix `proposals/list.py`, `proposals/manage.py`, `proposals/create.py` D7 violations
- [ ] Add tests for `lane/*`, `proposals/*` that stub the HTTP client layer

Sprint 2 (requires new API routes in CORE):
- [ ] Add `src/api/v1/secrets_routes.py` to CORE → fix `secrets/manage.py`
- [ ] Add `src/api/v1/symbols_routes.py` to CORE → fix `symbols/*`
- [ ] Add `vectors/query`, `vectors/rebuild`, `vectors/status` routes to CORE →
  fix `vectors/rebuild.py`, `vectors/query.py`
- [ ] Add `project/onboard`, `project/docs` routes to CORE →
  fix `project/onboard.py`, `project/docs.py`

Sprint 3 (Item 4 dependency):
- [ ] `project/scout.py` — blocked on Item 4 Scout implementation

### Phase D — Remove consumer commands from CORE

Once `core-cli` reaches green for a namespace, the corresponding operator
stub files in `src/cli/resources/` are removed (or kept as operator-only if
they serve both populations).

### Phase E — CI/CD for `core-cli`

PyPI Trusted-Publisher OIDC pattern; semver tags trigger wheel publication.
`core-cli` version tracks `core-runtime` major version for compatibility signal.

### Blocking prereqs

Phase A identified the exact gaps. Approximate ordering by impact:

1. `secrets_routes.py` — new; design question: what does secrets management
   look like over HTTP? (key CRUD, scoped to the governed project)
2. `symbols_routes.py` — new; symbol audit and ID management endpoints
3. Vector read routes (`/v1/vectors/query`, `/v1/vectors/rebuild`,
   `/v1/vectors/status`) — add to `sync_routes.py` or new `vectors_routes.py`
4. `project_routes.py` — `onboard` and `docs` endpoints; Scout waits on Item 4

### Acceptance criterion

`pip install core-cli` installs a package with no database or CORE-internal
dependencies. `core code lint` calls `core-runtime`'s API and returns
findings. `core-admin` continues to work in CORE unchanged. The two
binaries co-install without namespace collision (ADR-146 D5).

---

## Item 4 — Scout Phase B (Rule Induction UX)

**Priority:** Medium (post-ADR-146 in sequence; enables zero-prep foreign repo)
**Effort:** Large (2–4 weeks)
**Value:** Closes the "author rules manually" friction for new adopters

### What it is

`project scout <target>` analyzes a foreign repository's source code, infers
candidate rules using CORE's enforcement vocabulary, and presents a
ratification menu. After ratification, the adopter's `.intent/rules/` and
`.intent/enforcement/mappings/` are populated. No manual rule authoring
required.

This is the missing UX layer between "machinery floor delivered by `project
onboard`" and "functioning audit gate." Without it, adopters who don't want
to write rules from scratch are stuck with the four-rule fallback.

### Current state

- `project onboard <target>` — Phase A — delivers the machinery floor (~27
  system files from `examples/starter-intent/`) into the target repo's
  `.intent/`. Dry-runs by default; `--write` applies. Complete.
- `project scout` — Phase B — does not exist. ADR-119 scopes it but
  implementation is post-milestone.
- The four-rule fallback (`examples/starter-intent/rules/starter.json`) is
  available as a no-LLM floor but is not automatically inducted.
- `ContextService` and `CoderAgent` infrastructure is available for LLM
  analysis tasks. Scout uses these rather than raw LLM calls.

### What to build

**1. Source analysis step**

`ScoutAnalyzer` (`src/body/analyzers/scout_analyzer.py`) reads the target
repo's Python source using the existing `RepoCrawler` / `FileHandler`
pattern. It identifies:

- Language and framework signals (FastAPI, Django, SQLAlchemy, pytest, etc.)
- Existing linting/formatting config (ruff, black, mypy configs present)
- Rough layering evidence (directory naming, import graph shape)
- Risk signals (bare excepts, hardcoded secrets, direct subprocess calls,
  unchecked writes)

Returns a `ComponentResult` with structured `ScoutObservations`.

**2. Rule candidate generation**

`ScoutStrategist` (`src/body/strategists/scout_strategist.py`) maps
observations to candidate rules from CORE's published rule vocabulary.
Uses `llm_gate` for judgment calls on ambiguous patterns.
Output: an ordered list of `RuleCandidate` with id, statement, enforcement
level, rationale, and confidence score.

Falls back to the four-rule starter set when confidence is below threshold
or no LLM is available (ADR-119 D5 fallback).

**3. Ratification loop (CLI)**

`src/cli/commands/project/scout.py` (consumer surface per ADR-146 D2):

```
core scout ./my-project

Analyzing source... 847 files scanned.

Proposed rules (12 candidates):

  [1] import_order (blocking) — 23 violations found
      "Import order must follow isort convention."
      > Accept / Downgrade to reporting / Skip: _

  [2] no_bare_except (blocking) — 4 violations found
      "Bare except clauses must not be used."
      > Accept / Downgrade to reporting / Skip: _

  ...

Apply 8 accepted rules? [y/N]:
```

Rules the user accepts are written to `.intent/rules/scout_inducted.json`
and `.intent/enforcement/mappings/scout_inducted.yaml` in the target repo.
Dry-run by default; `--write` applies. Per UR-08, ratification is mandatory
— Scout never writes rules without human confirmation.

**4. Inducted rule file structure**

The inducted file follows the same schema as any other rule document. The
`id` field uses `rules.scout.<adopter-slug>` to namespace it away from
CORE's own rules. The adopter owns these files after induction and can edit
or extend them freely.

**5. HTTP route for Scout (prerequisite for ADR-146 Phase C migration)**

`POST /v1/project/scout` accepts a repo path and returns `ScoutObservations`
and `RuleCandidate[]` as JSON. The CLI calls this route. This route must
exist before the Scout command can migrate to `core-cli`.

### Dependencies

- Item 2 (Governance Packs) should land first. Scout's ratification step
  should offer pack adoption ("this repo looks like `core/python-hygiene`
  — ratify that pack?") before enumerating individual rules. The pack
  abstraction shapes Scout's output format. **Done.**
- Item 3 (ADR-146) Phase A audit must confirm Scout needs an HTTP route
  before CLI extraction. It does — confirmed.

### Scope

- `src/body/analyzers/scout_analyzer.py` — new analyzer
- `src/body/strategists/scout_strategist.py` — new strategist
- `src/api/v1/project_routes.py` — new route (or extend existing)
- `src/cli/commands/project/scout.py` — consumer CLI command (migrates to
  `core-cli` in Item 3 Phase C)
- `tests/body/analyzers/test_scout_analyzer.py`
- `tests/body/strategists/test_scout_strategist.py`

### Acceptance criterion

`core scout ./some-foreign-python-repo --write` completes in under 60
seconds on a 500-file repo, presents at least 4 candidate rules, writes
valid `.intent/rules/scout_inducted.json`, and `core-admin code audit
--offline` subsequently finds violations against the inducted rules.

---

## What is not being built

These were raised in the strategic review and verified as already done or
explicitly decided against:

| Item | Status |
|---|---|
| `core audit <foreign-repo>` | Done — `core-admin code audit --offline`; stateless; no repo prep required; verified against `core-audit-demo` |
| Machine-readable output (JSON, exit codes, annotations) | Done — F-10 complete; `--json`, `--format=github-annotations`, 0/1/2 exit codes |
| GitHub Actions integration | Done — F-10.3; `DariuszNewecki/CORE@main` action; `examples/starter-intent/.github/workflows/audit.yml` |
| OEM API contract | Done — F-40 complete; ADR-087 stability guarantee; 46 public routes; OpenAPI spec at `.specs/contracts/oem_api_v1.openapi.json` |
| Web Console | Non-goal — ADR-125; UI belongs in downstream distributions |

---

## Recommended sequence

```
Items 1 + 2: DONE (this session)
  → Item 3 Phase A: DONE — migration table produced
    → Item 3 Phase B: DONE — core-cli scaffold at /opt/dev/core-cli (06b38c0)
      → Item 3 Phase C Sprint 1: Fix proposals/* D7 violations (unblocked)
        → Item 3 Phase C Sprint 2: Add missing API routes to CORE, fix remaining violations
          → Item 4: Scout Phase B (depends on project_routes.py from Sprint 2)
            → Item 3 Phase C Sprint 3: Migrate project/scout.py
```

Item 3 Phase C Sprint 1 (`proposals/*` fixes) is the next unblocked action.
Sprint 2 route additions are independent and can be tackled in any order by
gap cluster. Item 4 is unblocked once `project_routes.py` exists.
