# CORE — External Adoption Gap Closure Plan

**Status:** Draft (2026-07-11)
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

**Priority:** High
**Effort:** Small (days)
**Value:** Highest per-unit effort of the four items

### What it is

A unified REST endpoint that answers: given a finding, show the complete
governance chain — which rule fired, what evidence, what proposal was
created, who approved it, what executed, which files changed, what the
resulting git SHAs are.

### Current state

All data exists in the database. The chain is:

```
core.blackboard_entries  (finding + evidence in payload JSONB)
  └─ proposal_id (in payload) →
core.autonomous_proposals  (approval, risk, execution_results)
  └─ proposal_id FK →
core.proposal_consequences  (files_changed, findings_resolved, pre/post SHA)
```

`ConsequenceLogService` (`src/body/services/consequence_log_service.py`)
has `find_cause_for_file()`, `get_recent_for_audit()`, and
`get_all_shas_with_status()` but none are exposed via any API route.
`proposals_routes.py` has no chain or consequence endpoint.

### What to build

**1. New API route — `GET /v1/proposals/{id}/chain`**

Returns the full chain for a proposal:
- proposal fields (goal, risk, approval_authority, approved_by, approved_at,
  execution_results, status)
- linked findings: entry_id, check_id, rule_id, file_path, severity,
  evidence (from payload.context), evidence_class
- consequence: files_changed, findings_resolved, authorized_by_rules,
  pre_execution_sha, post_execution_sha

**2. New API route — `GET /v1/findings/{entry_id}/chain`**

Reverse lookup: given a blackboard entry ID, find the proposal it was
deferred to (via payload.proposal_id), then return the same chain
structure as above.

**3. Response schema in `src/api/v1/schemas.py`**

`GovernanceChainResponse` with nested `FindingEvidence`, `ProposalSummary`,
`ConsequenceRecord` models. Add to the OEM API OpenAPI contract.

**4. Wire `ConsequenceLogService` into `api/dependencies.py`**

`ConsequenceLogService` takes a session; expose it via the existing
dependency injection pattern (`get_consequence_log_service`).

### Scope

- `src/api/v1/proposals_routes.py` — two new route handlers
- `src/api/v1/schemas.py` — three new response models
- `src/api/dependencies.py` — one new dependency
- `tests/api/test_proposals_routes.py` — chain query tests (mock DB layer)

### Acceptance criterion

`GET /v1/proposals/{id}/chain` returns a single JSON object tracing a
finding from detection through execution to file changes. A governance
reviewer with no CORE knowledge can follow it without consulting the
database directly.

---

## Item 2 — Governance Pack Abstraction

**Priority:** Medium-high
**Effort:** Medium (1–2 weeks)
**Value:** Unlocks external adoption without requiring manual rule authoring

### What it is

A formal abstraction for bundled, named, versioned rule sets that external
projects can adopt with a single declaration. Turns "learn CORE's rule
vocabulary and author enforcement mappings" into "apply this pack."

### Current state

The raw material exists:

- `examples/starter-intent/.intent/rules/starter.json` — four rules
  (`no_bare_except`, `docstrings`, `no_print`, `no_secrets`) in the exact
  schema needed; proven to work end-to-end via F-10 verification
- ~20–25 rules in the existing library are generic Python (imports, purity,
  test quality, modularity, secrets, channels) with no CORE-specific
  dependencies
- `IntentRepository` loads from declared directories in `intent_tree.yaml`;
  no hardcoding that would prevent a pack loader

What is missing: a pack metadata schema, a composition mechanism in
`intent_tree.yaml`, and any distribution story for core packs.

### What to build

**1. Pack metadata schema — `.intent/META/governance_pack.schema.json`**

```json
{
  "id": "core/starter-python",
  "version": "1.0.0",
  "title": "Starter Python Hygiene",
  "description": "...",
  "target_language": "python",
  "target_domain": "code",
  "level": "starter",
  "rules": [
    { "$ref": "rules/code/imports.json#/rules/import_order" },
    { "$ref": "rules/code/purity.json#/rules/no_bare_except" }
  ],
  "enforcement_mappings": [
    { "rule_id": "import_order", "engine": "workflow_gate" }
  ]
}
```

Schema fields: `id`, `version`, `title`, `description`, `target_language`,
`target_domain`, `level` (starter|intermediate|strict), `rules` (array of
$ref or inline), `enforcement_mappings`, `compatibility_floor` (minimum
core-runtime version), `supersedes` (for pack upgrades).

**2. `intent_tree.yaml` extension — `packs:` section**

```yaml
packs:
  - id: core/starter-python
    source: builtin
  - id: core/architectural-boundaries
    source: builtin
    overrides:
      - rule_id: "boundary.database_session_access"
        enforcement: reporting   # downgrade for gradual adoption
```

`IntentRepository` reads the `packs:` section and merges pack rules and
mappings into the loaded index before resolving custom (repo-authored) rules.
Custom rules always win over pack rules on conflict.

**3. Three initial packs (authored in CORE, bundled in `core-runtime` wheel)**

| Pack ID | Rules drawn from | Target |
|---|---|---|
| `core/starter-python` | `starter.{no_bare_except,docstrings,no_print,no_secrets}` + import order | Any Python repo; zero-friction default |
| `core/python-hygiene` | Code purity, test quality, modularity, channels | Teams wanting a stricter baseline |
| `core/architectural-boundaries` | Privileged-boundary imports, layer separation | Layered architectures (FastAPI/Django etc.) |

**4. `project adopt-pack <pack-id>` consumer CLI command**

Writes the `packs:` entry to the adopter's `intent_tree.yaml`. Dry-runs by
default. Does not copy rule files (packs are resolved from the installed
`core-runtime` wheel at audit time, not copied into the repo). Follows the
existing `project onboard` pattern.

**5. Pack validation in `IntentRepository.initialize()`**

On load: verify all referenced rule IDs exist in the loaded rule index,
all enforcement mappings reference known engines, no two packs declare
conflicting `blocking` enforcement on the same rule ID without an explicit
override. Fail closed — unknown pack ID is a loader error.

### Scope

- `.intent/META/governance_pack.schema.json` — new schema file
  (`.intent/` write; governor applies)
- `src/shared/infrastructure/intent/intent_repository.py` — extend loader
  to read `packs:` from `intent_tree.yaml`
- `src/shared/infrastructure/intent/pack_loader.py` — new module
- Three `.intent/packs/` YAML declarations (new governance-data files;
  governor applies)
- `src/cli/commands/project/adopt_pack.py` — new consumer CLI command
  (consumer surface per ADR-146 D2)
- `tests/shared/infrastructure/intent/test_pack_loader.py`

### Acceptance criterion

A fresh Python project can add `core/starter-python` to `intent_tree.yaml`
(or run `core adopt-pack core/starter-python`), run `core-admin code audit
--offline`, and receive findings against the four starter rules without
authoring any rule JSON or enforcement mapping.

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

This is the structural precondition for a clean external distribution: today
`core-cli` and `core-admin` are the same binary with heavyweight dependencies
that external consumers should not carry.

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

### What to build

**Phase A — Audit and classify (prerequisite, ~2 days)**

For each command in the ADR-146 D2 consumer list: read the file, identify
every `body`/`mind`/`will` import, and map it to the HTTP endpoint that
replaces it. Produce a per-command migration table. Flag any command that
has no matching HTTP endpoint — those are blockers requiring an API route
before migration.

**Phase B — New `core-cli` repository scaffold**

```
core-cli/
  core_cli/
    resources/           # migrated consumer command files
      lane/
      proposals/
      code/
      symbols/
      vectors/
      project/
      secrets/
    __init__.py
    app.py               # Typer app registration
  pyproject.toml         # declares core-runtime as dep
  .github/workflows/ci.yml
```

`pyproject.toml` declares `core-runtime>=X.Y.Z` as the sole internal
dependency. No rule files, no `.intent/`, no database drivers. The repo is
pure CLI consumer code.

**Phase C — Migrate commands one namespace at a time**

Per namespace: copy file, replace in-process imports with HTTP client calls,
verify the corresponding API route exists, add a test that stubs the HTTP
layer. Merge when green. The consumer command logic should be largely
mechanical; the work is replacing import paths and adapting response shapes.

**Phase D — Remove consumer commands from CORE**

Once `core-cli` is publishing and the commands pass tests there, delete
the migrated files from `src/cli/commands/` in CORE. The Typer app
registration in `src/cli/app.py` drops the consumer namespaces.

**Phase E — CI/CD for `core-cli`**

Same PyPI Trusted-Publisher OIDC pattern as `core-runtime`. Semver tags
trigger wheel publication. `core-cli` version tracks `core-runtime` major
version for compatibility signal.

### Blocking prereqs

Phase A will surface the exact API coverage gaps. Known likely gaps based
on current `src/api/v1/` coverage:

- `lane/`, `proposals/` — covered by existing routes
- `code/audit` (online path) — covered by `audit_routes.py`
- `vectors/` — check `sync_routes.py` for coverage
- `project/scout` — no HTTP route yet; Scout command migration waits on
  Item 4

### Acceptance criterion

`pip install core-cli` installs a package with no database or CORE-internal
dependencies. `core-cli code lint .` calls `core-runtime`'s API and returns
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
  abstraction shapes Scout's output format.
- Item 3 (ADR-146) Phase A audit must confirm Scout needs an HTTP route
  before CLI extraction. It does — see above.

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
#563 closes (~2026-07-29)
  → ADR-085 constraint relaxation act (governor)
    → Item 1: Evidence Chain Query Endpoint      (days; independent)
    → Item 2: Governance Pack Abstraction        (parallel with Item 1)
      → Item 3: ADR-146 Phase A audit            (low-cost; surfaces API gaps)
        → Item 3: ADR-146 Phase B–E extraction   (weeks; structural)
          → Item 4: Scout Phase B                (follows Item 2 + Item 3 HTTP route)
```

Items 1 and 2 are independent and can run in parallel. Item 3 Phase A
(audit and classification) is low-cost and should precede Phase B–E to
surface API coverage gaps before the structural refactor begins. Item 4
logically follows Item 2 (pack abstraction shapes Scout's output format)
and Item 3 (Scout command migrates to `core-cli`, which requires an HTTP
route that Item 4 must add first).
