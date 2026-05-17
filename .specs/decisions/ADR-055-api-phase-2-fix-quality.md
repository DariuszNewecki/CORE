<!-- path: .specs/decisions/ADR-055-api-phase-2-fix-quality.md -->

# ADR-055 — API Phase 2: /fix + /quality

**Status:** Accepted
**Date:** 2026-05-17
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

**CLI files in scope (Phase 2 migration targets):**

`src/cli/resources/code/` (Phase 2 subset):
- `fix_atomic.py` — atomic action dispatch
- `format.py` — import sort / ruff format
- `docstrings.py` — docstring fixer
- `logging.py` — logging fixer
- `actions.py` — action registry listing
- `check_imports.py` — import resolution check
- `integrity.py` — quality gate bundle
- `test.py` — pytest runner
- `check_ui.py` — Body-layer UI/env contract check

`src/cli/commands/fix/` (contributing):
- `all_commands.py`, `atomic_actions.py`, `code_style.py`, `metadata.py`,
  `handler_discovery.py`, `list_commands.py`, `imports.py`, `body_ui.py`,
  `settings_access.py`, `fix_ir.py`, `modularity.py`

`src/cli/commands/check/`:
- `quality.py`, `quality_gates.py`, `imports.py`, `diagnostics_commands.py`

All carry direct imports from `body.*`, `will.*`, `mind.*`, or `shared.*`.

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

### D6 — Phase 2 completion verified by suppress-entry removal

The following files must have all direct `body.*`, `will.*`, `mind.*`, and
`shared.*` imports replaced by `api.*` HTTP calls when Phase 2 is
complete. No suppress entries may remain in these files at Phase 2 closure:

```
src/cli/resources/code/fix_atomic.py
src/cli/resources/code/format.py
src/cli/resources/code/docstrings.py
src/cli/resources/code/logging.py
src/cli/resources/code/actions.py
src/cli/resources/code/check_imports.py
src/cli/resources/code/integrity.py
src/cli/resources/code/test.py
src/cli/resources/code/check_ui.py
src/cli/commands/fix/all_commands.py
src/cli/commands/fix/atomic_actions.py
src/cli/commands/fix/code_style.py
src/cli/commands/fix/metadata.py
src/cli/commands/fix/handler_discovery.py
src/cli/commands/fix/list_commands.py
src/cli/commands/fix/imports.py
src/cli/commands/fix/body_ui.py
src/cli/commands/fix/settings_access.py
src/cli/commands/check/quality.py
src/cli/commands/check/quality_gates.py
src/cli/commands/check/imports.py
src/cli/commands/check/diagnostics_commands.py
```

`fix/fix_ir.py`, `fix/modularity.py` are included above and must also
reach zero direct CORE imports at Phase 2 closure.

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
5. All files listed in D6 import exclusively from `api.*` — no `body.*`,
   `will.*`, `mind.*`, or `shared.*` imports remain.
6. `core-admin code audit` reports no new findings introduced by Phase 2.
7. `core.fix_runs` table exists in `db_schema_live.sql` and the ORM.

---

## References

- ADR-053 — parent; D2 (resource model), D3 (protocol contract), D4
  (phase map), D5 (CLI migration), D6 (papers-first gate)
- ADR-054 — Phase 1 pattern; `audit_runs` as resource table template
- ADR-046 — flow risk derivation; applies to `POST /fix/all`
- ADR-038 — circuit breaker; wiring intact on autonomous paths; not
  extended to governor-direct fix operations (same rationale as ADR-054)
- ADR-014 — dev-phase priority; `write` flag on fix endpoints honors
  dry-run-first discipline
- `.specs/planning/CORE-API-capability-map-2026-05-16.md` — source for
  endpoint-to-CLI-file mapping
- `src/body/atomic/registry.py` — authoritative source for valid `fix_id`
  values
- `src/body/flows/executor.py` — FlowExecutor backend for `/fix/all`
