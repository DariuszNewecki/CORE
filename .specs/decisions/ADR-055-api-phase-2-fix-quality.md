<!-- path: .specs/decisions/ADR-055-api-phase-2-fix-quality.md -->

# ADR-055 — API Phase 2: /fix + /quality

**Status:** Accepted
**Date:** 2026-05-17 (revised 2026-05-18)
**Authors:** Darek (Dariusz Newecki)
**Parent:** ADR-053 (API as Governance Interface)
**Relates to:** ADR-054 (Phase 1), ADR-046 (flow risk), ADR-038 (circuit
breaker), ADR-014 (dev-phase priority)

---

## Context

ADR-053 D4 defines Phase 2 as the `/fix` and `/quality` namespaces. These
back onto `body.self_healing.*` (fix operations) and Will quality-gate
workflows (quality checks). ADR-053 D6 requires this ADR to be accepted
before any Phase 2 endpoint is implemented.

ADR-050 D1 establishes the physical extraction boundary: `src/cli/` is a
standalone repository (`core-cli`) that communicates with CORE exclusively
over HTTP. No Python import from any `src/` module — `body.*`, `will.*`,
`mind.*`, or `shared.*` — is permitted in CLI after extraction. Phase 2
completion is one milestone within that larger extraction arc.

---

## Decisions

### D1 — Fix operations are resources backed by `fix_runs`

A new table `core.fix_runs` is introduced following the `audit_runs` pattern.
Each row represents one fix operation submitted via the API.

Schema (minimum):
```
fix_runs(
  id           uuid PRIMARY KEY,
  kind         text NOT NULL,        -- 'atomic' | 'flow' | 'modularity' | 'ir'
  fix_id       text,                 -- action_id or flow_id; NULL for 'all'
  target_files jsonb,                -- null = repo-wide
  write        boolean NOT NULL,
  status       text NOT NULL,        -- pending | executing | completed | failed
  requested_by text NOT NULL,        -- ADR-053 D7
  requested_at timestamptz NOT NULL, -- ADR-053 D7
  started_at   timestamptz,
  finished_at  timestamptz,
  result       jsonb,
  error        text
)
```

`fix_runs` is also used as the backing resource for async `/quality`
operations (kind = `quality_check`). A single table with a `kind`
discriminator avoids a speculative second table while keeping the resource
model clean. The governing principle from ADR-053 D2 is satisfied: no new
table is created for quality operations.

### D2 — `/fix` endpoint contract

#### List and discovery

```
GET  /fix/commands
```
Returns the registered fix commands and their metadata from the action
registry. Synchronous; no resource ID. Backed by `body.atomic.registry`.

```
GET  /actions
```
Returns all registered atomic actions. Synchronous. Backed by
`body.atomic.registry.action_registry`.

#### Generic atomic dispatch

```
POST /fix/run/{fix_id}
Body: { "target_files": [str] | null, "write": bool }

→ 202 { "run_id": uuid, "status": "pending", "href": "/fix/runs/{id}" }

GET  /fix/runs/{id}
→ 200 { "run_id", "status", "fix_id", "write", "result": {...} | null, "error" }
```

`fix_id` must map to a registered atomic action ID in
`body.atomic.registry`. The route handler validates the ID at request time;
unknown IDs return 422. `ActionExecutor` is the backend.

#### Curated fix sequence

```
POST /fix/all
Body: { "write": bool }

→ 202 { "run_id": uuid, "status": "pending", "href": "/fix/runs/{id}" }
```

Executes the governed fix sequence defined in `flow.fix_code`. Uses
`FlowExecutor`; risk is derived per ADR-046. Kind = `flow` in `fix_runs`.

#### Modularity

```
POST /fix/modularity
Body: { "write": bool }

→ 202 { "run_id": uuid, "status": "pending", "href": "/fix/runs/{id}" }
```

Triggers the autonomous modularity remediation cycle. Kind = `modularity`.
Will-layer wiring: existing `will.workflows` modularity path; no new worker
required.

#### Incident-response bootstrap

```
POST /fix/ir
Body: { "kind": "triage" | "log" }

→ 200 { "path": str }
```

Synchronous; creates YAML scaffold files. No resource ID needed — the
output is a file path, operation completes inline.

### D3 — `/quality` endpoint contract

Quality checks divide into two execution models:

**Synchronous (fast, ≤ ~2s):** Return results inline, no resource ID.

```
POST /quality/imports
Body: { "target_files": [str] | null }
→ 200 { "status": "ok" | "failed", "violations": [...] }

POST /quality/body-ui
Body: { "target_files": [str] | null }
→ 200 { "status": "ok" | "failed", "violations": [...] }
```

**Asynchronous (slow, subprocess-backed):** Return 202 + resource ID.
Backed by `fix_runs` with kind = `quality_check`.

```
POST /quality/lint
Body: { "fix": bool }   -- fix=true runs ruff --fix in-process
→ 202 { "run_id": uuid, "status": "pending", "href": "/fix/runs/{id}" }

POST /quality/tests
Body: { "path": str | null }
→ 202 { "run_id": uuid, "status": "pending", "href": "/fix/runs/{id}" }

POST /quality/system
Body: {}   -- lint + tests + audit bundle
→ 202 { "run_id": uuid, "status": "pending", "href": "/fix/runs/{id}" }

POST /quality/gates
Body: {}   -- six industry gates: ruff/mypy/pytest/pip-audit/radon/vulture
→ 202 { "run_id": uuid, "status": "pending", "href": "/fix/runs/{id}" }
```

### D4 — Will-layer wiring

| Endpoint | Backend | New wiring required? |
|---|---|---|
| `POST /fix/run/{fix_id}` | `ActionExecutor.execute(fix_id, ...)` | No — already exists |
| `POST /fix/all` | `FlowExecutor` on `flow.fix_code` | No — ADR-046 already wires this |
| `POST /fix/modularity` | `will.workflows` modularity path | No — path exists |
| `POST /quality/lint` | ruff subprocess via existing check path | No |
| `POST /quality/tests` | pytest subprocess | No |
| `POST /quality/gates` | `check/quality_gates.py` logic | No — extract to service |
| `POST /quality/imports` | `body.*` import checker | No |
| `POST /quality/body-ui` | `body_contracts_service` | No |

No new workers, no new flows. The Will-layer already has all required entry
points; Phase 2 is HTTP wiring over existing backend logic.

### D5 — No auth; loopback binding (inherited from ADR-054 D3)

Phase 2 inherits the ADR-054 D3 auth posture. No authentication for Phase
2. Loopback-only binding. The promotion trigger is unchanged: first use
case requiring per-request auth, remote access, or multi-operator
deployment.

### D6 — Phase 2 completion verified by the boundary rule, not a file list

Phase 2 is complete when no file under `src/cli/` imports from any `src/`
module. The rule is:

> Every Python file under `src/cli/` MUST import exclusively from `api.*`
> (via HTTP through `CoreApiClient`) or from the Python standard library.
> Imports from `body.*`, `will.*`, `mind.*`, and `shared.*` are
> unconditionally forbidden.

This rule derives from ADR-050 D1 (physical extraction boundary). It
applies to the entire `src/cli/` tree, not to a named subset of files.

The original revision of this ADR listed 22 specific files as the D6
scope. That list was a snapshot of the known violation surface at authoring
time — it was a description of where violations existed, not a definition
of the rule. The list was incorrect as a scope definition because it named
files instead of the condition. The correct scope is the rule above; the
current violation count is an operational metric, not an architectural
boundary.

**Tracked exceptions (blocked on missing endpoints):**

The following files cannot satisfy the rule until a dedicated endpoint is
designed. They are excluded from Phase 2 closure and tracked under their
own issues:

- `src/cli/resources/code/integrity.py` — no endpoint for
  `IntegrityService.create_baseline` / `verify_integrity` (issue #353)
- `src/cli/commands/fix/all_commands.py` (sync half) — db sync, vector
  sync, command sync, capability tagging have no API endpoint (issue #354)
- `src/cli/commands/fix/metadata.py` (policy/tag steps) —
  `add_missing_policy_ids` and `purge_legacy_tags` are not registered
  atomic actions and have no endpoint (issue #355)

These exceptions are temporary. Phase 2 closes when the rule is satisfied
for all files not covered by an open tracked exception. Each exception
closes when its endpoint exists and the file is migrated.

---

## Deferred to Phase 3

`fix/audit.py` (`POST /audit/remediations`) is deferred to Phase 3: it
overlaps the `/audit` namespace and its resource model should extend
`audit_runs`, not `fix_runs`. Including it in Phase 2 would create
cross-namespace resource coupling.

---

## Verification

This ADR is verified when:

1. All endpoints in D2 and D3 exist, start without error, and return
   governed responses per ADR-053 D3 protocol contract.
2. `POST /fix/run/{fix_id}` is covered by tests for at least 3 distinct
   `fix_id` values including an unknown-id 422 case.
3. All async `/quality` endpoints are covered by tests.
4. `GET /fix/commands` and `GET /actions` are covered by tests.
5. `grep -rn "from body\.\|from will\.\|from mind\.\|from shared\." src/cli/`
   returns zero hits, excluding files covered by open tracked exceptions
   (#353, #354, #355).
6. `core-admin code audit` reports no new findings introduced by Phase 2.
7. `core.fix_runs` table exists in `db_schema_live.sql` and the ORM.

---

## References

- ADR-050 — physical extraction boundary; source of the D6 rule
- ADR-053 — parent; D2 (resource model), D3 (protocol contract), D4
  (phase map), D5 (CLI migration), D6 (papers-first gate)
- ADR-054 — Phase 1 pattern; `audit_runs` as resource table template
- ADR-046 — flow risk derivation; applies to `POST /fix/all`
- ADR-038 — circuit breaker; wiring intact on autonomous paths; not
  extended to governor-direct fix operations (same rationale as ADR-054)
- ADR-014 — dev-phase priority; `write` flag on fix endpoints honors
  dry-run-first discipline
- `src/body/atomic/registry.py` — authoritative source for valid `fix_id`
  values
- `src/body/flows/executor.py` — FlowExecutor backend for `/fix/all`

---

*Revised 2026-05-18: D6 rewritten. The original file enumeration (22
files) was a snapshot of the known violation surface at authoring time, not
a scope definition. D6 now states the boundary rule derived from ADR-050
D1: no file under `src/cli/` may import from any `src/` module. The
original file list is removed. Three tracked exceptions added (#353, #354,
#355) for files blocked on missing endpoints. Verification condition 5
updated to reference the grep assertion rather than the file list. Context
section updated to surface the ADR-050 D1 dependency explicitly.*
