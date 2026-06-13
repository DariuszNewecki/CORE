---
kind: adr
id: ADR-057
title: 'ADR-057 — API Phase 3: /coverage + /refactor + /inspect'
status: accepted
---

# ADR-057 — API Phase 3: /coverage + /refactor + /inspect

**Status:** Accepted (revised 2026-05-18 — D5 amended to add three `/inspect` endpoints
for unassigned capability map items; migration scope in Context updated accordingly)
**Date:** 2026-05-18
**Revised:** 2026-05-18
**Authors:** Darek (Dariusz Newecki)
**Parent:** ADR-053 (API as Governance Interface)
**Relates to:** ADR-054 (Phase 1), ADR-055 (Phase 2), ADR-038 (circuit
breaker), ADR-014 (dev-phase priority)

---

## Context

ADR-053 D4 defines Phase 3 as the `/coverage`, `/refactor`, and `/inspect`
namespaces. These back onto `body.self_healing.*` (coverage analysis and
test generation), `mind.*` modularity engine (refactor scoring and
autonomous cycle), and the shared observation layer (drift, decision
traces, refusals, semantic analysis).

ADR-055 deferred `POST /audit/remediations` (`src/cli/commands/fix/audit.py`)
to Phase 3 on the grounds that its resource model must extend `audit_runs`,
not `fix_runs`, to avoid cross-namespace coupling. That deferral resolves
here.

ADR-053 D6 requires this ADR to be accepted before any Phase 3 endpoint
is implemented.

**Phase 3 character:** Phases 1 and 2 each introduced a new resource table
(`audit_runs`, `fix_runs`) to track stateful operations. Phase 3 is
predominantly read-only: the `/inspect` namespace has no stateful operations
at all, and `/coverage` and `/refactor` introduce stateful operations only for
their generation/autonomous-cycle paths. New tables are introduced conservatively
per ADR-053 D2 ("reuse existing resource tables before creating new ones").

**CLI files in scope (Phase 3 migration targets):**

Source: capability map at `.specs/planning/CORE-API-capability-map-2026-05-16.md`.
Exact import verification must be confirmed by a live grep before Phase 3
implementation begins (see D7).

`src/cli/commands/coverage/`:
- `check_commands.py` — coverage compliance check, report, targets, gaps
- `analysis_commands.py` — coverage history, legacy-vs-adaptive comparison
- `generation_commands.py` — adaptive test generation (single file, batch)
- `services/coverage_checker.py` — `mind.governance.run_filtered_audit` call
- `services/coverage_reporter.py` — subprocess coverage.py wrapper
- `services/gaps_analyzer.py` — `body.self_healing.CoverageAnalyzer` call

`src/cli/commands/refactor.py` and `src/cli/commands/refactor_support/`:
- `refactor.py` — modularity score per file, candidates, stats
- `refactor_support/analyzer.py` — per-file/codebase modularity scores; `mind.*` import
- `refactor_support/config.py` — threshold from constitution; `mind.*`, `shared.*` imports
- `refactor_support/display.py` — Rich rendering; presentation only, kept client-side
- `refactor_support/recommendations.py` — recommendation strings; `shared.*` import
- `src/cli/commands/develop.py` — autonomous refactor cycle (A3 loop)

`src/cli/commands/inspect/` (excluding `repo_census.py` — Phase 4):
- `status.py` — DB connection and migration status
- `drift.py` — symbol drift, vector drift; `mind.*`, `shared.*` imports via `cli.logic`
- `decisions.py` — decision trace inspection; `body.*`, `shared.*` imports
- `patterns.py` — pattern classification stats; `shared.*` import
- `refusals.py` — constitutional refusal records; `shared.*` import via `cli.logic`
- `analysis.py` — semantic clusters, duplicates, DRY candidates; `shared.*` via `cli.logic`
- `diagnostics.py` — command-tree and test-target classification; `body.*`, `shared.*`
- `src/cli/commands/status.py` — DB/drift consolidated; `shared.*` via `cli.logic`
- `src/cli/commands/guard.py` — drift guard commands; `mind.*`, `shared.*`

Audit remediations (deferred from ADR-055 Phase 2):
- `src/cli/commands/fix/audit.py` — autonomous remediation of findings; `body.*`,
  `shared.*`, `will.*` imports

`src/cli/commands/inspect/_helpers.py` — pure presentation; kept client-side
after migration. No migration required; it renders JSON the API returns.
`src/cli/commands/refactor_support/display.py` — same; pure Rich rendering.

**Unassigned capability map items added to Phase 3 scope (2026-05-18):**
Two files not assigned in the original capability audit are assigned to
`/inspect` by the 2026-05-18 revision to ADR-053 D4, and are therefore
in scope for this ADR:

- `src/cli/commands/components.py` — V2 component discovery by package;
  `shared.*` imports only
- `src/cli/commands/search.py` — semantic search over capability vectors +
  fuzzy CLI registry search; `shared.*` imports only

Both files are presentation-only wrappers over `shared.*` infrastructure.
Both endpoints are read-only. No new resource table is introduced. These
are folded into the D3 (inspect operations, all read-only, no new tables)
characterisation without modification to D3's governing text.

---

## Decisions

### D1 — Coverage operations: read-only queries + `coverage_runs` for generation

`/coverage` has two characters:

**Read-only queries** (`GET`): compliance check result, text/HTML report,
constitutional targets, coverage gaps, history, method comparison. These query
existing data (`mind.governance` via filtered audit, `body.self_healing.CoverageAnalyzer`,
subprocess `coverage.py`). No new table.

**Stateful generation** (`POST`): adaptive test generation for a single file or a
prioritised batch. These are async operations — test generation can take seconds to
minutes depending on file count. A new table `core.coverage_runs` is introduced,
following the `audit_runs` / `fix_runs` pattern. Each row represents one generation
request; the result payload holds the list of generated test file paths.

`POST /tests/interactive` is synchronous (it drives a step-by-step interactive
session). It returns a `200 OK` with inline content, not a `202 Accepted`. No
resource table needed.

`core.coverage_runs` schema (minimum):
```
coverage_run_id   uuid PRIMARY KEY DEFAULT gen_random_uuid()
status            text NOT NULL DEFAULT 'pending'
target_file       text                        -- null for batch
batch_priority    text                        -- 'high' | 'all' | null
created_at        timestamptz NOT NULL DEFAULT now()
updated_at        timestamptz NOT NULL DEFAULT now()
result            jsonb                       -- generated test paths + counts
error             text
requested_by      text NOT NULL DEFAULT 'system'
requested_at      timestamptz NOT NULL DEFAULT now()
request_ref       text
```

### D2 — Refactor operations: read-only queries + `refactor_runs` for autonomous cycle

`/refactor` has two characters:

**Read-only queries** (`GET`): per-file modularity score, files exceeding threshold,
aggregate distribution, threshold from constitution. These query `mind.*` modularity
engine and return synchronously. No new table.

**Stateful autonomous cycle** (`POST /refactor/autonomous`): triggers the A3
autonomous refactor loop (`develop.py` backend). This is an async operation that
produces one or more proposals via the existing `autonomous_proposals` table. A new
table `core.refactor_runs` is introduced to track the cycle request and its outcome
(the set of proposal IDs produced). This keeps the cycle record separate from the
proposals it generates.

`core.refactor_runs` schema (minimum):
```
refactor_run_id   uuid PRIMARY KEY DEFAULT gen_random_uuid()
status            text NOT NULL DEFAULT 'pending'
goal              text NOT NULL              -- forwarded to A3 loop
write             boolean NOT NULL DEFAULT false
created_at        timestamptz NOT NULL DEFAULT now()
updated_at        timestamptz NOT NULL DEFAULT now()
proposal_ids      uuid[]                     -- proposals produced
error             text
requested_by      text NOT NULL DEFAULT 'system'
requested_at      timestamptz NOT NULL DEFAULT now()
request_ref       text
```

The A3 loop is guarded by the circuit breaker (ADR-038) on the autonomous path.

### D3 — Inspect operations: all read-only, no new tables

Every `/inspect`, `/decisions`, `/refusals`, `/analysis`, `/status`, and
`GET /v1/components` + `GET /v1/search/*` endpoint is a read-only query
against existing data surfaces: `decision_traces`, blackboard entries, DB
connection state, Qdrant vector store, in-memory CLI introspection, V2
component registry, and capability/command vector stores. No new tables are
introduced.

`GET /analysis/command-tree` currently returns the CLI command hierarchy by
introspecting the CLI Typer application. Once `src/cli/` is extracted (ADR-050),
this endpoint's semantics shift to returning the API endpoint tree. For Phase 3, the
endpoint is wired to the existing `diagnostics_logic.build_cli_tree_data` backend.
A follow-up ADR will redefine it post-extraction.

### D4 — Audit remediations: new `audit_remediation_runs` table

`POST /audit/remediations` deferred from ADR-055. It triggers autonomous remediation
of findings from a prior audit run. Resource model: new table
`core.audit_remediation_runs`, linked to `core.audit_runs` by `audit_run_id`. This
keeps audit execution and remediation execution as separate resource records, each
with their own lifecycle state.

`core.audit_remediation_runs` schema (minimum):
```
remediation_run_id  uuid PRIMARY KEY DEFAULT gen_random_uuid()
audit_run_id        uuid REFERENCES core.audit_runs(audit_run_id)
status              text NOT NULL DEFAULT 'pending'
mode                text NOT NULL              -- 'safe' | 'medium' | 'all'
write               boolean NOT NULL DEFAULT false
created_at          timestamptz NOT NULL DEFAULT now()
updated_at          timestamptz NOT NULL DEFAULT now()
result              jsonb                      -- proposal_ids, counts, summary
error               text
requested_by        text NOT NULL DEFAULT 'system'
requested_at        timestamptz NOT NULL DEFAULT now()
request_ref         text
```

The remediation path respects the circuit breaker (ADR-038) and the dev-phase write
flag (ADR-014).

### D5 — Endpoint surface (revised 2026-05-18)

Full endpoint list for Phase 3, grouped by namespace:

```
# /coverage
GET  /coverage/check                Compliance vs constitutional rules
GET  /coverage/report               Text coverage report (show_missing param)
GET  /coverage/targets              Constitutional coverage targets
GET  /coverage/gaps?threshold=N     Low-coverage modules ranked
GET  /coverage/history?limit=N      Coverage trends
GET  /coverage/methods              Legacy vs adaptive comparison
POST /coverage/generate             Async: adaptive test generation, single file
GET  /coverage/runs/{id}            Poll coverage_run status and result
POST /coverage/generate:batch       Async: prioritised batch generation
POST /tests/interactive             Sync: interactive step-by-step session

# /refactor
GET  /refactor/score?file=...       Per-file modularity score
GET  /refactor/candidates           Files exceeding threshold
GET  /refactor/stats                Aggregate modularity distribution
GET  /refactor/threshold            Threshold from constitution
POST /refactor/autonomous           Async: trigger A3 autonomous refactor cycle
GET  /refactor/runs/{id}            Poll refactor_run status and produced proposals

# /inspect (read-only, no polling needed)
GET  /status/db                     DB connection and migration status
GET  /status/drift?scope=...        Consolidated drift report (symbols, vectors, guard)
GET  /decisions?session=&agent=&pattern=&limit=   Decision traces
GET  /decisions/patterns            Pattern classification stats
GET  /refusals?type=&session=&limit= Constitutional refusal records
GET  /refusals/stats                Refusal statistics by type
GET  /analysis/clusters             Semantic capability clusters
GET  /analysis/duplicates           Semantic code duplication
GET  /analysis/common-knowledge     DRY-violation candidates
GET  /analysis/command-tree         CLI hierarchy (pre-extraction) / API tree (post)
GET  /analysis/test-targets         SIMPLE/COMPLEX classification
GET  /v1/components                 V2 component discovery by package
GET  /v1/search/capabilities        Semantic search over capability vectors
GET  /v1/search/commands            Fuzzy CLI registry search [Phase 3b deferred — #363]

# /audit (deferred from Phase 2)
POST /audit/remediations            Async: autonomously remediate findings
GET  /audit/remediations/{id}       Poll audit_remediation_run status
```

All endpoints conform to the ADR-053 D3 protocol contract: `202 Accepted` for
async operations, `200 OK` for synchronous reads, standard error shape for `≥ 400`.

### D6 — No auth; loopback binding (inherited from ADR-054 D3)

Phase 3 inherits the ADR-054 D3 auth posture unchanged. No authentication.
Loopback-only binding. Promotion trigger unchanged: first use case requiring
per-request auth, remote access, or multi-operator deployment.

### D7 — Phase 3 completion verified by suppress-entry removal

Before implementation begins, a live grep is run on lira to enumerate all files
in the Phase 3 scope that carry direct `body.*`, `will.*`, `mind.*`, or
`shared.*` imports. The result is saved to `var/adr057-phase3-imports.txt` and
becomes the authoritative D7 file list. The list in the Context section above is
derived from the capability map and is an approximation; the grep output governs.

At Phase 3 closure, no suppress entries for `architecture.cli.api_only` may
remain in any file from the D7 list. All direct CORE imports in those files must
be replaced by `api.*` HTTP client calls.

Files confirmed as **presentation-only** (`refactor_support/display.py`,
`inspect/_helpers.py`) are excluded from the D7 list — they stay client-side and
do not require migration.

`src/cli/commands/components.py` and `src/cli/commands/search.py` are in D7
scope. Both carry `shared.*` imports; both must be migrated to `api.*` HTTP
client calls before Phase 3 is marked closed.

---

## Deferred to Phase 4

`src/cli/commands/inspect/repo_census.py` and its corresponding `/census`
namespace (`POST /census/runs`, `POST /census/baselines/{name}`,
`GET /census/diff`) are Phase 4 per ADR-053 D4. Although `repo_census.py`
lives under `src/cli/commands/inspect/`, its resource model is distinct (CIM
census is a Body service, not a shared observation query) and warrants its own
phase ADR.

---

## Verification

This ADR is verified when:

1. All endpoints in D5 exist, start without error, and return governed
   responses per the ADR-053 D3 protocol contract.
2. `POST /coverage/generate` is covered by tests for at least 2 distinct
   `target_file` values and one batch path.
3. `POST /refactor/autonomous` is covered by tests including a dry-run
   (`write=false`) and at least one circuit-breaker boundary case.
4. `POST /audit/remediations` is covered by tests for all three modes
   (`safe`, `medium`, `all`) and a missing-`audit_run_id` 422 case.
5. All files enumerated in the live `var/adr057-phase3-imports.txt` grep import
   exclusively from `api.*` — no `body.*`, `will.*`, `mind.*`, or `shared.*`
   imports remain. This includes `components.py` and `search.py`.
6. `core-admin code audit` reports no new findings introduced by Phase 3.
7. `core.coverage_runs`, `core.refactor_runs`, and
   `core.audit_remediation_runs` exist in `db_schema_live.sql` and the ORM.

---

## References

- ADR-053 — parent; D2 (resource model), D3 (protocol contract), D4
  (phase map), D5 (CLI migration), D6 (papers-first gate)
- ADR-054 — Phase 1 pattern; `audit_runs` as resource table template
- ADR-055 — Phase 2; `POST /audit/remediations` deferral in final section
- ADR-050 — CLI positioning; `architecture.cli.api_only` rule; extraction sequence
- ADR-038 — circuit breaker; applies to `/refactor/autonomous` and
  `/audit/remediations` autonomous paths
- ADR-014 — dev-phase priority; `write` flag on generation and remediation
  endpoints honors dry-run-first discipline
- `.specs/planning/CORE-API-capability-map-2026-05-16.md` — source for
  endpoint-to-CLI-file mapping
- `src/body/self_healing/coverage_analyzer.py` — backend for `/coverage/gaps`
- `src/cli/commands/fix/audit.py` — backend for `POST /audit/remediations`
- `src/cli/commands/develop.py` — A3 loop backend for `POST /refactor/autonomous`

---

*Revised 2026-05-18: D5 amended to add `GET /v1/components` and
`GET /v1/search/capabilities` for `components.py` and `search.py`, per the
2026-05-18 amendment to ADR-053 D4 that assigned those files to the Inspect
namespace group. `GET /v1/search/commands` listed as Phase 3b deferred pending
extraction of `hub_search_cmd` from `cli.logic.hub` (tracked as #363). URL paths use the existing
Inspect convention (`/v1/<resource>`, tagged `Inspect`; no `/v1/inspect/` prefix).
Context section updated to name the two files as added to Phase 3 scope. D3
updated to name `GET /v1/components` and `GET /v1/search/*` explicitly. D7
updated to confirm `components.py` and `search.py` are in the D7 suppression
list. No resource tables added; no other decisions changed.*
