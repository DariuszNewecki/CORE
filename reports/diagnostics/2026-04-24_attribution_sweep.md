# Attribution sweep — 2026-04-24

**Purpose**: Identify any remaining service-layer INSERT paths into
`core.blackboard_entries` following ADR-011 ("Workers own blackboard
attribution; services do not post").

## Methodology

Three ripgrep passes over `src/` only (`tests/`, `infra/sql/`, `.venv/`
out of scope). Case-insensitive matching is used because the codebase
mixes `INSERT INTO` and `insert into` for the same SQL semantic — the
original spec's case-sensitive pattern missed the canonical Worker
base-class site (which uses lowercase), so all three passes were run
with `rg -ni` and classification is over the union of the three
case-insensitive result sets.

| Grep | Pattern | Raw hit count |
|---|---|---|
| 1 | `rg -ni --type py 'INSERT INTO[[:space:]]+(core\.)?blackboard_entries' src/` | 3 |
| 2 | `rg -ni --type py 'session\.add\(BlackboardEntry\(' src/` | 0 |
| 3 | `rg -ni --type py 'BlackboardEntry\(' src/` | 1 |

Deduplicated across passes (grep 3's sole hit is a class definition,
distinct from any grep 1 hit): **4 unique site records**.

## Canonical site

`src/shared/workers/base.py` — contains the `async def _post_entry(`
definition (line 296) and the single attribution-preserving INSERT
into `core.blackboard_entries` (line 324). Every registered Worker
routes `post_finding` / `post_report` / `post_heartbeat` through this
method; `worker_uuid` and `phase` flow from `self` into the INSERT
parameters, satisfying the `blackboard_entries.worker_uuid` NOT NULL
constraint that no other path satisfies.

## Sites found

### Legitimate (Worker base class)

- `src/shared/workers/base.py:324` — inside `Worker._post_entry(...)`.
  INSERT supplies `(id, worker_uuid, entry_type, phase, status,
  subject, payload, resolved_at)` with `worker_uuid = self._worker_uuid`
  and `phase = self._phase`. Canonical attribution point; the one
  site ADR-011 sanctions.

### Violation candidates

- `src/body/services/blackboard_service.py:837` — inside
  `BlackboardService.revive_findings_for_failed_proposal(...)`. Raw
  SQL INSERT of a `report` entry with subject
  `proposal.failure.revival::{proposal_id}` to record §7a revival
  outcomes. Columns supplied: `(id, entry_type, subject, payload,
  status, created_at)` — no `worker_uuid`, no `phase`. Added in
  commit `62a84ff7` as part of the Finding→Proposal revival
  contract; the session running this code has no Worker identity to
  attribute to, and the call site is a BlackboardService method, not
  a Worker subclass.
- `src/body/atomic/remediate_cognitive_role.py:92` — inside an atomic
  action body that creates a `prompt.artifact` finding so
  `CallSiteRewriter` has something to claim. Raw SQL INSERT with
  `RETURNING id`, supplying `(entry_type, subject, payload, status,
  created_at)` — no `worker_uuid`, no `phase`. The atomic-action
  runtime has access to `service_registry` but not to a Worker
  instance; this INSERT bypasses Worker attribution entirely.

### Test infrastructure

(none)

### Schema / model definitions

- `src/shared/infrastructure/database/models/workers.py:61` — `class
  BlackboardEntry(Base):` ORM declaration with
  `__tablename__ = "blackboard_entries"` and `__table_args__ =
  {"schema": "core"}`. Definition only; no runtime INSERT.

## Summary

| Category              | Count |
|-----------------------|-------|
| Legitimate            | 1     |
| Violation candidates  | 2     |
| Test infrastructure   | 0     |
| Schema / model        | 1     |
| **Total sites**       | 4     |

Verification gate: 3 grep-1 hits + 0 grep-2 hits + 1 grep-3 hit = 4
raw matches across the three passes; after deduplication (grep 3's
schema-class hit is not also a grep-1 hit) = 4 distinct site
records. 1 + 2 + 0 + 1 = 4. Arithmetic ties.

## Next step

2 violation candidate(s) require governor review before
enforcement-rule authoring.
