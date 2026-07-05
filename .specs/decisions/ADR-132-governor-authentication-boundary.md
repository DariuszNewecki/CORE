---
kind: adr
id: ADR-132
title: ADR-132 — Governor Authentication Boundary
status: accepted
---

# ADR-132 — Governor Authentication Boundary

**Date:** 2026-06-28
**Governing paper:** `.specs/papers/CORE-Constitutional-Foundations.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Closes:** #670 (authentication mechanism distinguishing governor from user-facing callers,
ADR-110 D2 deferred)
**Grounding papers:** ADR-068 (principal role taxonomy, three-layer model, Single-Governor
Local posture); ADR-110 (exposure axis, trust tiers, completeness);
ADR-053 (deferred trust boundary), ADR-050 (API completeness)
**Related:** ADR-124 (refresh token rotation, deny-list), ADR-131 (governance application
data model), ADR-068 D4 (Single-Governor Local topology)

---

## Context

ADR-110 D2 established that every API endpoint carries an `exposure` tier
(`user-facing` or `governor-only`) and that `governor-only` endpoints require
governor authentication. It deferred the authentication mechanism to this ADR.
ADR-068 D4 established that in a Single-Governor Local deployment (localhost-only
binding, single principal), authentication may be deferred; when a remote access
path is opened, authentication becomes mandatory.

Two prior decisions bound the design space:

1. **ADR-068's three-layer model.** Layer 1 (taxonomy) declares four roles:
   `principal.governor`, `principal.operator`, `principal.auditor`,
   `principal.system`. Layer 2 (principal-to-role binding) maps actual users to
   those roles; in a Single-Governor Local deployment that binding is trivial. Layer
   3 (action-to-role enforcement) is what this ADR implements — specifically the
   enforcement gate on `governor-only` API routes.

2. **The current session model (ADR-124).** The API already issues JWTs in the
   `core_access` cookie carrying a `role` claim from the `core.user_role` DB enum:
   `visitor`, `analyst`, `auditor`, `org_admin`, `platform_admin`. A `require_role()`
   factory dependency exists in `src/api/dependencies.py` and is already wired to
   `get_current_user`, but is not yet called on any route. No new credential type
   is needed; the `role` claim in the existing JWT is the implementation vehicle.

The gap to close: the `ROUTER_EXPOSURE` metadata added by ADR-110 D5 (#671) is
live on all routes and routers, but `governor-only` routes are currently served to
any authenticated session. The enforcement layer — the Layer 3 gate from ADR-068 —
is absent.

---

## Decisions

### D1 — `platform_admin` is the DB-side implementation of `principal.governor`

The `core.user_role` enum value `platform_admin` is the Layer 2 binding of
`principal.governor` in the current deployment. No new enum value is introduced.
The mapping is:

| ADR-068 role | `core.user_role` value | Exposure tier served |
|---|---|---|
| `principal.governor` | `platform_admin` | user-facing + governor-only |
| `principal.operator` | `org_admin` | user-facing only |
| `principal.auditor` | `auditor` | user-facing only |
| (lower tiers) | `analyst`, `visitor` | user-facing only (reduced subset TBD) |
| `principal.system` | — | not an HTTP caller (see D5) |

This mapping is a deployment-time Layer 2 binding, not a Layer 1 constitution
change. It holds for Single-Governor and Team deployments. If a future topology
introduces a second governor role, this mapping is updated in a follow-on ADR —
Layer 1 (the taxonomy) does not change.

### D2 — `require_governor` is the enforcement dependency

A new dependency `require_governor` is added to `src/api/dependencies.py`:

```python
require_governor = require_role("platform_admin")
```

This is a one-liner alias. `require_role` already validates the JWT and checks the
`role` claim; `require_governor` gates on exactly `platform_admin`. No new code
path is introduced; the alias exists for semantic clarity and to isolate call sites
from the string literal `"platform_admin"`.

All current and future `governor-only` routes use `Depends(require_governor)`, not
`Depends(require_role("platform_admin"))` directly. This ensures a single
name in the codebase represents the boundary; renaming the sentinel only requires
updating `dependencies.py`.

### D3 — `governor-only` routers declare the dependency at router construction time

For route modules where every route is `governor-only` (seven modules: `auth_routes`,
`daemon_routes`, `development_routes`, `integrity_routes`, `refactor_routes`,
`sync_routes`, and the governor-only subset of operations) — the dependency is
declared on the `APIRouter` constructor:

```python
from api.dependencies import require_governor
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/...", dependencies=[Depends(require_governor)])
```

For mixed routers (`proposals_routes`: list/submit is user-facing; approve/execute
is governor-only) — the dependency is applied per-route on the restricted
operations. This avoids blanket-restricting user-facing operations on the same
router.

The `ROUTER_EXPOSURE` constant on each module remains the authoritative declaration
of intent; the `dependencies=[...]` on the `APIRouter` is the enforcement. Both
must agree. A future audit rule may verify this invariant.

### D4 — Single-Governor Local topology: gate is live, structurally satisfied

In a Single-Governor Local deployment (ADR-068 D4: localhost-only binding, one
principal), the `require_governor` gate is fully enforced — it is not bypassed,
relaxed, or conditional. Because the single principal holds `platform_admin`, the
gate passes for every legitimate call. The gate is structurally satisfied, not
disabled.

This distinction matters: a Single-Governor Local system that adds a second user
(e.g., `analyst` role) immediately benefits from the protection without any code
change — `governor-only` routes are already blocked for non-`platform_admin`
callers.

ADR-068 D4's "authentication deferred" posture applies to the credential issuance
ceremony (no mandatory multi-factor, no remote identity provider required), not to
the runtime enforcement gate. The gate must be live regardless of topology.

### D5 — System principals are not HTTP callers under this ADR

Workers (`principal.system`) access the database directly; they do not call the API
over HTTP. Issuing API credentials to workers is deferred. If a future design
requires a worker to POST to an API endpoint, it will authenticate with a
`platform_admin`-role service account JWT, issued and managed by the governor.
No DB schema change is needed; the `core.user_role` enum already accommodates this.

### D6 — Proposal approval authority gate closes ADR-068 D5 implementation gap

`POST /v1/proposals/{id}/approve` and `POST /v1/proposals/{id}/execute` are
`governor-only` operations. They acquire `Depends(require_governor)` per-route
(mixed router, D3). This enforces that only a `principal.governor`-tier caller may
approve or execute a proposal — the Layer 3 enforcement that ADR-068 D5 declared
but deferred.

The `approval_authority` field on the proposal record is stamped `principal.governor`
(not `human.cli_operator`) at approval time, per ADR-068 D5 vocabulary correction.
This ADR does not re-decide that correction; it closes the enforcement gap.

### D7 — Audit rule: `ROUTER_EXPOSURE` and `dependencies` must agree

A future enforcement rule (`cli.governor_gate_required` or similar) will verify
that every `APIRouter` declared `governor-only` in `ROUTER_EXPOSURE` carries
`Depends(require_governor)` in its constructor `dependencies` list, and that no
`user-facing` router carries `require_governor` at the router level (per-route
exceptions are permitted). This rule is not authored in this ADR; it is the
implementation gate for closing #670 fully.

### D8 — `ActionExecutor._check_authorization()` is intentionally pass-through

`ActionExecutor._check_authorization()` (`src/body/atomic/executor.py`) always returns
`authorized: True`. It is not an authorization gate and was not designed to be one.

The real authorization chain for autonomous actions is:

```
action_risk.yaml  →  Proposal.requires_approval  →  governor approval (API gate)
                                                            ↓
                                                     ActionExecutor.execute()
```

By the time `execute()` is reached on the autonomous path, the action's authority to
run has already been adjudicated. `action_risk.yaml` classifies every action as
`safe | moderate | dangerous`; `Proposal.requires_approval` gates execution on that
classification — only `safe` auto-executes; `moderate` and `dangerous` (and any
unmapped action, which fails closed to `moderate`) require explicit governor approval
before a proposal can reach execution. Duplicating that check in the executor would not
add safety; it would add two conflicting authorization surfaces.

**The one uncovered path** is a direct CLI invocation (no proposal, no
`requires_approval` check). That path is governor-operated and trusted-operator today.
The executor logs a warning on `dangerous` + `write` via the CLI path. The activation
criterion for replacing the pass-through with a real deny: a dangerous action becoming
reachable by a non-governor caller (API-exposed action execution endpoint, or
non-governor CLI users). Until then, the pass-through is the correct design.

This decision corrects a prior docstring that cited ADR-015/017/019 as the deferral
basis; those are consequence-chain attribution decisions with no authorization deferral
semantics. The correction is recorded at #633.

---

## Consequences

- **Governor-only routes are no longer accessible to any authenticated session.**
  Any caller without `platform_admin` role receives HTTP 403 on `governor-only`
  endpoints. This is the intended posture.
- **No credential infrastructure change.** The existing JWT/cookie session model
  and `require_role()` factory are the complete implementation vehicle. No new
  tables, no new token types.
- **Mixed-router routes require per-route annotation.** `proposals_routes.py` (and
  any future mixed router) must be audited for which operations belong to which
  tier. The split is explicit in the route function, not inferred from a naming
  convention.
- **SoD constraint (ADR-068 D3) remains deferred.** The Single-Governor Local
  topology structurally cannot satisfy "governor ≠ auditor for the same action" —
  there is one principal. The constraint exists on record; enforcement requires a
  multi-operator deployment.

---

## Verification

This ADR closes #670 when:

1. `require_governor` is declared in `src/api/dependencies.py`.
2. All seven `governor-only` routers carry `dependencies=[Depends(require_governor)]`
   on their `APIRouter` constructor.
3. `proposals_routes.py` approve/execute routes carry `Depends(require_governor)`
   per-route.
4. An integration test verifies: a request with `analyst`-role JWT to a
   `governor-only` route returns HTTP 403; the same request with `platform_admin`
   JWT returns 2xx.
5. `require_governor` is the only call site in `src/api/` that hardcodes
   `"platform_admin"` — no other route or file uses `require_role("platform_admin")`
   directly.

---

## References

- ADR-068 — Principal role taxonomy; D1 (three-layer model), D2 (four roles),
  D3 (SoD constraint), D4 (Single-Governor Local posture), D5 (approval authority
  vocabulary).
- ADR-110 — Exposure axis; D2 (`governor-only` requires governor auth, deferred
  here), D3 (write-safety binds to operation), D5 (exposure metadata field).
- ADR-124 — Refresh token rotation, deny-list, JWT payload structure.
- ADR-050 — CLI as standalone HTTP client; API completeness mandate.
- ADR-053 — API as resource-oriented governance interface; deferred trust boundary
  (now closed by this ADR).
- `src/api/dependencies.py` — `get_current_user`, `require_role` factory.
- `src/api/v1/*/ROUTER_EXPOSURE` — module-level exposure declarations (ADR-110 D5).
- Issue #670 — authentication mechanism (this ADR's target).
- Issue #671 — exposure backfill (ADR-110 D5 implementation, prerequisite; closed).
