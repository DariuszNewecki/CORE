---
kind: adr
id: ADR-054
title: 'ADR-054 — API Phase 1: /audit + /proposals'
status: accepted
---

<!-- path: .specs/decisions/ADR-054-api-phase-1-audit-proposals.md -->

# ADR-054 — API Phase 1: /audit + /proposals

**Status:** Accepted
**Date:** 2026-05-16
**Governing paper:** `.specs/papers/CORE-OEM-API.md`
**Authors:** Darek (Dariusz Newecki)
**Parent:** ADR-053 (API as Governance Interface)
**Closes:** #335
**Relates to:** ADR-050 (CLI positioning), ADR-010 (Finding/Proposal
contract), ADR-015 (consequence chain), ADR-038 (circuit breaker)

---

## Context

ADR-053 D4 defines Phase 1 as the first capability cluster to receive
API endpoints: `/audit` and `/proposals`. These namespaces back onto
`mind.governance` (audit) and `core.autonomous_proposals` (proposals)
— the two most mature and governance-critical backend surfaces in CORE.

ADR-053 D6 requires this ADR to be accepted before any Phase 1
endpoint is implemented.

**CLI files in scope (Phase 1 migration targets):**

`src/cli/resources/proposals/`:
- `integrate.py`
- `manage.py`
- `list.py`
- `create.py`

`src/cli/resources/code/` (audit-facing only):
- `audit.py`
- `lint.py`

All six carry direct imports from `mind.*`, `will.*`, `body.*`, or
`shared.*`. These are the suppress entries that must reach zero for
#335 to close (D4).

The remaining `src/cli/resources/code/` files (`docstrings.py`,
`format.py`, `fix_atomic.py`, `check_imports.py`, `actions.py`,
`logging.py`, `refactor.py`, `integrity.py`, `test.py`, `check_ui.py`)
are Phase 2/3 and are not in scope here.

---

## Decisions

### D1 — Audit runs are resources

`POST /audit/runs` creates an audit run and returns `{run_id,
verdict, finding_count}`. `GET /audit/runs/{id}` returns the full
result including findings. CORE already persists audit results to the
DB; the run-as-resource model maps onto existing persistence without
new infrastructure.

### D2 — `/proposals/{id}/execute` is included in the API

The architecture is CLI → API → CORE. Excluding execute from the API
would leave `src/cli/resources/proposals/manage.py` unable to migrate
off its direct `will.*` imports — a permanent `architecture.cli.api_only`
violation. The endpoint is included. It remains a governor-direct
override action; the API surface does not change its semantics.

Full proposals resource contract:
- `GET /proposals` — list with status filter
- `GET /proposals/{id}` — show
- `POST /proposals/{id}/approve` — approve
- `POST /proposals/{id}/reject` — reject
- `POST /proposals/{id}/execute` — governor-direct override

### D3 — No auth for Phase 1; loopback binding only

Single-operator, development phase, loopback-only deployment. No
authentication is required at this stage. The API binds to loopback
only (`127.0.0.1`); no external exposure is sanctioned while this
decision is in force.

Promotion trigger: bearer token authentication is required before CORE
exits single-operator deployment or binds to a non-loopback interface.
That promotion requires a dedicated ADR.

This decision is explicit and deliberate — see `_check_authorization`
stub precedent (commit 5c0ee6b0): deferral must be on record.

### D4 — Phase 1 completion is verified by suppress-entry removal

The following six files must have all `architecture.cli.api_only`
suppress entries removed when Phase 1 is complete. No suppress entries
may remain in these files at #335 closure:

```
src/cli/resources/proposals/integrate.py
src/cli/resources/proposals/manage.py
src/cli/resources/proposals/list.py
src/cli/resources/proposals/create.py
src/cli/resources/code/audit.py
src/cli/resources/code/lint.py
```

Source: `var/adr054-phase1-imports.txt` (grep run 2026-05-16).

---

## Verification

This ADR is verified when:

1. `GET /proposals`, `GET /proposals/{id}`, `POST
   /proposals/{id}/approve`, `POST /proposals/{id}/reject`, and `POST
   /proposals/{id}/execute` exist, are tested, and return governed
   responses.
2. `POST /audit/runs` and `GET /audit/runs/{id}` exist, are tested,
   and return at minimum `{run_id, verdict, finding_count}` and full
   finding list respectively.
3. All six files listed in D4 import exclusively from `api.*` — no
   `mind.*`, `will.*`, `body.*`, or `shared.*` imports remain.
4. A full audit run reports zero findings under
   `architecture.cli.api_only` attributable to the six D4 files.

---

## References

- ADR-053 — parent; D4 (phase map), D5 (suppress-then-drain), D6
  (phase ADR gate)
- ADR-050 — CLI positioning; inversion list source
- ADR-010 — Finding/Proposal contract (proposal state machine the API
  exposes)
- ADR-015 — consequence chain (`approval_authority` non-omittable,
  relevant to D3 promotion trigger)
- ADR-038 — circuit breaker (proposal creation gate; API must respect
  it)
- Issue #335 — phase tracking issue
- `var/adr054-phase1-imports.txt` — D4 source grep (2026-05-16)
- `src/api/` — current stub (7 files, health check only)
- Commit `5c0ee6b0` — `_check_authorization` deliberate-stub precedent
  for D3 rationale

---

## Amendment 2026-05-17 — findings persistence on `audit_runs`

The original schema captured by commit `7ac53960` (audit_runs +
audit_run_resources consolidation) preserved only counts on
`core.audit_runs`; the per-run finding list was not persisted. That
gap made it impossible for `GET /audit/runs/{id}` to satisfy
Verification criterion #2 ("full finding list") on the async path —
findings were only returned inline by the sync path (`wait=true`) and
discarded everywhere else. Tracked as #340.

Resolution: adds a single nullable JSONB column,
`core.audit_runs.findings`, written by both `run_and_persist_audit`
(async) and `run_sync_audit` (sync) at run completion, read by `GET
/audit/runs/{id}` and returned as the `findings` field. Pre-amendment
rows have `findings = NULL`; the GET handler returns `[]` in that case
so the response shape is stable. The "no new infrastructure"
constraint elsewhere in this ADR was authored before the persistence
hole was known and is now overridden for this column only — denormalized
JSONB is the smallest pragmatic fix that keeps `audit_runs` the
complete resource record per ADR-053's model.

A relational alternative (Option A — `audit_findings.run_id` foreign
key with append-only writes) is the correct long-term answer for GxP
audit-trail readiness (queryable per `rule_id` / `file_path` across
historical runs). It is parked as a Band E follow-up; this amendment
is the interim fix, not the terminal design.

Closes #340.
