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

---

## Addendum — D9: per-route "intentionally ungated" marker (2026-07-17, accepted)

**Status of this addendum:** Accepted (governor confirmed 2026-07-17, Path A
confirmation naming this file).

**Grounding note, corrected during drafting:** `architecture.api.sensitive_route_
must_be_gated` (the rule this addendum gives an escape hatch to) is not itself a
decision this ADR made — it was added to `.intent/` citing issue #770, with no
ADR anchor of its own found anywhere in `.specs/decisions/`. This addendum homes
here anyway because ADR-132 is the closest existing decision on record for the
adjacent vocabulary the new marker extends: D3/D7 own the `ROUTER_EXPOSURE`-
consuming, router-level gate-consistency shape (`ROUTER_EXPOSURE` itself
originates in ADR-110 D5); a per-route sibling marker for the per-route
completeness rule is a natural, closely-related extension of that same posture,
not a mechanical application of a decision already made word-for-word here.
Recorded as a genuine (if narrowly-scoped) new decision, per the same append-only
shape as ADR-127 D7 / ADR-148 D7.

### The gap (issue #808 triage)

`sensitive_route_must_be_gated`'s own finding text says a route can be resolved
by confirming it "intentionally ungated" — but `check_sensitive_route_must_be_
gated` (`src/mind/logic/engines/ast_gate/checks/api_auth_checks.py`) is a pure
AST scan for `require_governor` presence: no exclusion list, no marker it
recognizes, no code path implementing that prose. #808's triage found 11 routes
that are read-shaped (analysis dispatch — no `src/`, `.intent/`, or git writes;
nothing dereferenced as governing state by a later decision) sitting in
`status='indeterminate'` on the blackboard with no way to close them that means
anything durable.

### Why `governed_exclusions` (ADR-152) is the wrong tool here

The obvious reach — reuse the generalized exemption register ADR-152 just
built — doesn't fit, for two independent reasons, both verified against source
before rejecting it:

1. **Wrong grain.** `governed_exclusions` entries are keyed on `file`
   (`enforcement_mapping.schema.json`: `required: [file, rationale,
   closure_type]`; `class`/`category`/`removal_condition` apply only to the
   `condition` shape and describe a *class*, not a function). The audit pipeline
   honors a `governed_exclusions` entry's `file` value "as if it were listed
   under `scope.excludes`" — i.e. it suppresses the rule for the **whole file**.
   `sensitive_route_must_be_gated` findings are per-route-function; there is no
   field in this schema that names a function.
2. **The routes co-habit files with real mutations.** `census_routes.py`
   contains both `create_census_run` (read-shaped) and `create_census_baseline`
   (the mutation gated in `84ebb387`) at module scope. `coverage_routes.py`
   contains `request_coverage_report` (read-shaped) alongside `generate_
   coverage`/`generate_coverage_batch`/`interactive_tests` (mutations, same
   commit). `quality_routes.py` contains six read-shaped checks alongside
   `quality_lint` (mutation, same commit). A file-level exclusion silencing the
   read-shaped route would also silence the check for its mutating siblings in
   the same file — trading a benign false positive for a genuine blind spot: if
   `require_governor` were later stripped from `create_census_baseline`, nothing
   would catch it. That is exactly the labeled-silent-green pattern ADR-148 D7
   closed for `proposal_consequences` rows, one governance surface over.

### D9 — `INTENTIONALLY_UNGATED`, a route-level marker the check consults

A module-level constant, parallel to `ROUTER_EXPOSURE`, mapping route function
name to a required, non-empty rationale:

```python
ROUTER_EXPOSURE = "user-facing"

INTENTIONALLY_UNGATED: dict[str, str] = {
    "create_census_run": (
        "Read-shaped: INSERTs a core.census_runs tracking row (status="
        "'pending'), same shape as create_audit_run. No src/, .intent/, or "
        "git writes. Nothing is ever dereferenced against a census_run as "
        "governing state (contrast create_census_baseline, gated)."
    ),
}
```

`check_sensitive_route_must_be_gated` gains a parallel `_find_intentionally_
ungated(tree) -> dict[str, str]` helper (same AST shape as the existing
`_find_router_exposure`), and skips a route's finding when `node.name` is a key
in that dict with a non-empty string value — the confirmation and its reason
live beside the route it excuses, survive a refactor that moves the file, and
stay greppable, matching the reasoning ADR-095 gave for preferring the in-file
`CORE_ROLE` marker over `governed_exclusions` for co-located, function-scoped
acknowledgments.

**Orphan-entry check, cheap to add while touching this function anyway:** after
walking the module for mutation routes, any `INTENTIONALLY_UNGATED` key that
never matched an actual route-function name is itself flagged — a stale entry
(renamed or removed route) looks like coverage but is inert, the same "declared
but nothing validates it" gap ADR-152 D4 closed for `governed_exclusions`
entries. Keeps the marker from silently rotting.

### The 10 routes, with one-line read-shaped rationales

**Retirement note (architectural retirement, current main):** `quality_body_ui`
(`/v1/quality/body-ui`) was removed along with its backing
`body_contracts_service`/`fix.body_ui` machinery — the checker enforced
`body.*` policy semantics archived at `ca398a2e` and never had a valid
current-law successor. Its row is struck from this table rather than left
describing a route that no longer exists; the surrounding gating decision
for the other 10 routes is unaffected.

| Route | File | Why read-shaped |
|---|---|---|
| `create_audit_run` | `audit_routes.py` | INSERTs `core.audit_runs`; writes disposable analysis output (`findings.json`, evidence ledger) to `reports/`, never `src/`/`.intent/`/git. |
| `create_census_run` | `census_routes.py` | INSERTs `core.census_runs`; `snapshot=True` writes a disposable snapshot to a history dir, same class as audit's `reports/` output. |
| `request_coverage_report` | `coverage_routes.py` | Runs `pytest --cov`, persists report output to `core.coverage_runs`. No source files touched. |
| `lint_endpoint` | `lint_routes.py` | Runs `black --check` + `ruff check` only — no `--fix` path exists on this route. |
| `quality_imports` | `quality_routes.py` | Wraps `action_check_imports`, a pure import-resolution scan. |
| `quality_policy_coverage` | `quality_routes.py` | `PolicyCoverageService.run()` is a read-only audit report. |
| `quality_tests` | `quality_routes.py` | Runs `pytest -q --no-cov` only. |
| `quality_system` | `quality_routes.py` | Runs `ruff check src/` (no `--fix`) + pytest — analysis only. |
| `quality_gates` | `quality_routes.py` | Runs six analysis subprocesses (ruff/mypy/pytest/pip-audit/radon/vulture); none pass fix/write flags. |
| `vector_query` | `vectors_routes.py` | Embeds the query and reads nearest vectors from Qdrant; no writes (contrast sibling `/vectors/rebuild`, already gated). |

### Governed surfaces this touches

| Surface | Authority | Change |
|---|---|---|
| `src/mind/logic/engines/ast_gate/checks/api_auth_checks.py` | code | `_find_intentionally_ungated()` helper; `check_sensitive_route_must_be_gated` consults it; orphan-entry check |
| `src/api/v1/audit_routes.py`, `census_routes.py`, `coverage_routes.py`, `lint_routes.py`, `quality_routes.py`, `vectors_routes.py` | code | add `INTENTIONALLY_UNGATED` with the 11 routes' rationales |

### Consequences

**Positive.** The 11 blackboard findings close and *stay* closed for a real
reason, checked by the same mechanism that raised them — not a one-time
blackboard resolve that reopens next cycle. The mutations co-located in the same
files keep full coverage; no blind spot traded in.

**Costs.** A second module-level marker convention alongside `ROUTER_EXPOSURE`
(both are small, greppable dicts/strings — consistent surface, not sprawl). A
future contributor adding a new mutation route to one of these six files must
know not to add themselves to `INTENTIONALLY_UNGATED` by copy-paste without
reading it — mitigated by the orphan-check catching a stale entry, not a
misapplied one, so this residual risk is accepted rather than fully closed.

---

## Addendum — D10: the governor is the OS account, read by the kernel (2026-10-04, accepted)

**Status of this addendum:** Accepted (governor reviewed and approved 2026-10-04). Closes #942 when its Verification list passes.

### The gap

`principal.governor` is the mark CORE treats as a human decision. It is stamped on proposal approvals (`approval_authority`) and on finding closures (`payload.resolution.resolution_authority`). Since ADR-104 D9 amended, a finding closure with it re-arms an exhausted remediation cap. Nothing verifies who writes it (#942, recon in `var/reports/issue-942-recon-20261004.md`):

1. `core-admin workers resolve`: `--authority` defaults to `principal.governor`, and `--by` is free text.
2. `POST /v1/proposals/{id}/approve` takes `approval_authority` from the request body. `require_governor` is `_oss_passthrough`, so `approved_by` is `"unknown"`.
3. Every OS account in `core-dev` (governor, services, coding assistant) reads `.env` and holds the same production DB credential.

**D4 has diverged from the code.** D4 says the gate "is fully enforced — it is not bypassed, relaxed, or conditional." The code makes it a pass-through in OSS mode. This addendum resolves the divergence in D4's favour, with a different identity source than D1's JWT for local callers.

**Why now.** On 2026-10-04 the shared `core` login was split: `core-darek` (governor), `core` (services) and `core-claude` (coding assistant). For the first time, the OS can tell the governor apart from the assistant. CORE's claim is that AI output is not trusted by default. That claim has to hold for the assistant that builds CORE.

### D10.1 — Identity of a local caller comes from the kernel

For a caller on the same host, the API learns its identity from the peer credentials of a Unix-domain socket connection (`SO_PEERCRED`: uid, gid, pid). The kernel supplies them; the caller cannot choose them.

The identity is never taken from a request body or header, a CLI flag, an environment variable, or a free-text field.

A TCP connection carries no peer identity. On TCP, D1–D2 (JWT, `platform_admin`) remain the only route to governor authority. Anonymous TCP is user-facing only.

### D10.2 — The principal binding lives where the assistant cannot write

ADR-068's Layer 2 binding maps OS account to principal role. For local callers it is a deployment file outside the repository, owned by root and not writable by the services account or the assistant account (proposed: `/etc/core/principals.yaml`).

It is not `.intent/`: the assistant has write access to the working tree, and a binding it can edit binds nothing.

A missing, unreadable or malformed binding fails closed: no caller is `principal.governor`. This follows the fail-closed-on-unknown-authority principle.

### D10.3 — `require_governor` is live (resolves the D4 divergence)

`_oss_passthrough` is removed. `require_governor` passes only when one of these holds:
- the peer uid on the Unix socket is bound to `principal.governor` (D10.1–D10.2);
- the request carries a valid `platform_admin` JWT (D1–D2).

Otherwise it returns 403. OSS mode changes the credential ceremony (no JWT needed locally), not the gate.

### D10.4 — Governor stamps are written by the server, from the authenticated identity

Wherever a record claims `principal.governor`, the API writes the claim and the actor from the identity established in D10.3:
- proposal `approval_authority` and `approved_by`;
- `payload.resolution.resolution_authority` and `resolved_by`;
- any future governor act.

Request bodies cannot supply them. `approve`'s `approval_authority` body field is dropped or must equal the server's value. Governor acts that exist only as DB-direct CLI commands today, starting with `workers resolve`, gain an API route and call it.

### D10.5 — The production DB credential belongs to the services account only

The production database credential is readable only by the services account (`core`) and by root. The coding assistant account holds no production DB credential. It reaches CORE through the API, and later through the MCP surface (direction in the ADR-168 draft).

Unchanged by this addendum:
- the `core_test` credential (`.env.test`), which tests need;
- the assistant's read and write access to the working tree;
- git, and the offline audit used by the ADR-168 pre-commit hook.

### D10.6 — Order of work: the assistant keeps working at every step

The credential is revoked last. Each step lands on its own.

1. #943: the routing field is renamed, so only one field means "resolved under this authority".
2. Spike: uvicorn 0.38 does not put peer credentials in the ASGI scope. Prove that a protocol subclass or listener wrapper can supply them. If it can't, this addendum returns to the governor before step 3.
3. The API also listens on a Unix socket. Add the binding file, make `require_governor` live (D10.3), stamp server-side (D10.4), add the resolve route, and point `workers resolve` at it.
4. Inventory: list each `core-admin` command the assistant uses that opens a DB session directly (28 CLI files do today). Each gets an API route or is marked governor-only.
5. Governor act: tighten `.env` to `core` only (for example `0600 core:core`) and confirm the services still start.

### D10.7 — What this does not cover

- **The services account.** `core` still holds the DB credential, so a code path running as `core` can still write a stamp. That code is CORE's own, subject to its gates and review. The threat model here is the assistant, not the runtime.
- **`system.*` closures** (for example `system.audit`, which also re-arms caps) are written by services and are not authenticated by this addendum. They are covered by the point above.
- **Root.** Root is the governor's own power, by design.
- **Remote and multi-governor topologies.** These stay with D1–D2 (JWT), and with ADR-068 D3 SoD when it activates.

### Verification

Closes #942 when:
1. As `core-claude`: `POST /v1/proposals/{id}/approve` and the resolve route return 403 over both the socket and TCP.
2. As `core-darek` over the socket, both succeed, and the stored `approved_by` / `resolved_by` name `core-darek`.
3. With the binding file missing, both return 403 for everyone.
4. As `core-claude`, reading `.env` gives permission denied, and its CLI commands from the step 4 inventory still work.
5. `_oss_passthrough` no longer exists in `src/`.

### Governed surfaces this touches

| Surface | Authority | Change |
|---|---|---|
| `src/api/dependencies.py` | code | live `require_governor`; peer-credential identity |
| `src/api/v1/proposals_routes.py` | code | server-side `approval_authority` / `approved_by` |
| new resolve route; `src/cli/resources/workers/blackboard.py` | code | `workers resolve` goes through the API and becomes `dangerous=True` |
| API launch (unit / entry point) | deployment | Unix-socket listener |
| `/etc/core/principals.yaml` | deployment, governor-owned | the Layer 2 binding |
| `.env` mode | deployment, governor act | `core` only |

---

## Amendment to D10 — runtime isolation, socket-only governor, revised order (2026-10-04, accepted)

**Status:** Accepted (governor approved 2026-10-04, after an external review of D10's step-3 plan).

### Why

The external review (ChatGPT, with read access to `develop`) confirmed one gap D10 missed, and it was then verified on the host:
- `/opt/dev/CORE`, `src/`, `.venv/` and `site-packages` are owned `core:core-dev`, mode `2775`.
- The `core` services run from that tree through an editable install (`core_runtime.pth`).
- The assistant (`core-claude`, in `core-dev`) can write all of it, and can restart the services through the `core-services` wrapper.

So taking away the assistant's database credential (D10.5) only moves the forgery one step: the assistant changes code that runs as `core`, and the database sees `core`.

The review also showed that D10.6 step 3b had a fault. Stamping `principal.governor` server-side while `require_governor` is still a pass-through makes a forged stamp look more authoritative.

### D10.8 — The assistant cannot change what runs with production authority

An identity that does not hold the production credential must not be able to modify anything consumed by a process that does:
- the executable code;
- the Python path and venv (including `.pth` files and dependencies);
- the environment;
- the service unit definitions.

Concretely:
- The services run a release build (a wheel) installed into a venv outside the development tree, owned by `core` or root, and not writable by the assistant (proposed: `/opt/core/`).
- The units carry `User=core` / `Group=core` where they are system units, or remain `core`-user units. Either way, their definitions are not writable by the assistant.
- The checked-in `infra/systemd/` copies state this, and they drop the `/home/lira/.local/bin` residue.

Moving development bytes into the runtime is a **deployment act performed by the governor**. The assistant may change source, build it and test it. It cannot make its own output live. This is CORE's claim ("AI cannot authorize its own output") applied to the repository that builds CORE.

Consequence for the development loop: the assistant no longer restarts services to make its own changes live. Changes take effect on the governor's next deployment.

### D10.3 as amended — governor authority only over the Unix socket

For Single-Governor Local, the only route to governor authority is a Unix-socket peer uid that the binding maps to `principal.governor`. TCP is user-facing only and can never perform a governor act.

D10.3's "or a valid `platform_admin` JWT" clause is withdrawn: the code it names (`require_role`, `get_current_user`) no longer exists. A remote or multi-governor topology re-opens the question in its own decision.

The socket is defence in depth beyond the peer-uid check:
- It lives in a `core`-owned directory (proposed: `/run/core/api.sock`).
- Its group does not include the assistant, and is not `core-dev`.
- An assistant that cannot connect at all (`EACCES`) satisfies Verification as well as one that gets 403.

### D10.6 as amended — revised order

Code landing is separate from security activation. A governor-capable stamp never exists without the check that guards it.

1. **Identity, dormant.** Unix-socket listener with the peer-credential protocol, a fail-closed binding loader, and a `caller_principal` dependency. Nothing enforced.
2. **core-cli learns Unix sockets** (`CORE_API_URL=unix:///…`). Governor operations need it; user-facing calls may stay on TCP.
3. **Runtime isolation (D10.8).** Release-build runtime outside the development tree, the unit definitions, and the deployment act.
4. **Stamps and enforcement together.** Server-side governor stamps (D10.4) land in the same change as the live `require_governor`. `_oss_passthrough` is removed.
5. **Activation (governor).** Install the binding file and socket permissions; deploy.
6. **Inventory.** Give each DB-direct `core-admin` command the assistant uses an API route, or mark it governor-only.
7. **Credential isolation (D10.5).** `.env` readable by the services only. Confirm `core_test_db` has no privileges on the production database.

### D10.7 as amended — the claim is narrow

What D10 proves is that **the assistant cannot impersonate the governor**. It does not prove that the assistant cannot cause a remediation cap to re-arm.

`system.audit` closures also re-arm caps (`_max_abandoned_count_since_rearm`) and are not authenticated here. After D10.8 they can only come from code the assistant cannot change. The re-arm writers get their own tests, and the gap is recorded rather than closed by D10.

### Verification as amended

#942 closes only when all of these hold:
1. **As `core-claude`:** governor routes are refused over the socket (`EACCES` or 403) and over TCP (403).
2. **As `core-darek` over the socket:** governor routes succeed, and the stored actor is `core-darek`.
3. **With the binding missing:** nobody is governor.
4. **As `core-claude`:**
   - reading `.env` gives permission denied;
   - writing to the runtime tree, its venv or its unit definitions gives permission denied;
   - the inventoried commands still work.
5. `_oss_passthrough` is gone from `src/`.
6. `core_test_db` cannot connect to the production database, or holds no privileges on it.

## Addendum — D10 activation parked until D10.8 is complete (2026-10-04, accepted)

**Status:** Accepted (governor chose "park" 2026-10-04).

### What was found after the amendment

The D10.8 design pass (`var/reports/adr132-d10-8-runtime-isolation-design-20261004.md`) found two more routes by which bytes the assistant writes run as `core`. D10.8's text does not cover them:

- **R3, git configuration.** Services run git in the development tree. `.git/` must stay group-writable so that the assistant can commit. A group-writable directory without the sticky bit lets a member replace any file in it, `.git/config` and hooks included, whoever owns that file. Changing the file's ownership or mode does not close this.
- **R4, repo-provided code that CORE runs on purpose.** The services run the repository's tests and `conftest.py` as `core`. The assistant writes those files. This route is by design and can only be closed by changing the identity that executes repository code.

The routes are equivalent. While any one of R1–R4 is open, closing the others gives no protection against the assistant, and only adds deployment friction.

### Decision

1. **D10.8 is all-or-nothing.** It is satisfied only when R1–R4 are all closed:
   - the release runtime (R1, R2);
   - the services' git separated from the development tree (R3);
   - repository code executed under an identity without the production credential (R4).
   Partial isolation is not recorded as progress toward #942.
2. **Activation is parked.** Steps 3–7 of D10.6 as amended wait for D10.8 to be complete. Step 1 (dormant identity) stays as landed; it enforces nothing and claims nothing. Step 2 (core-cli Unix sockets) may land independently, because it is transport only.
3. **Trigger to unpark.** Either a third principal (a second human or another agent) works on the deployment, or the daemon executes generated code at a volume where R4 is a practical rather than a theoretical route.
4. **The current claim, stated narrowly.** For as long as D10 is parked:
   - Governor attribution rests on the OS account split: commit authorship and journald/file ownership distinguish `core-darek`, `core-claude` and `core`.
   - Governor attribution also rests on trust.
   - It does **not** rest on enforcement.
   - No record, report or release note may describe governor stamps as authenticated.
   - #942 stays open, labelled parked.

### Consequences

- Development loop unchanged: the assistant may still restart services to make its changes live.
- D10.5 (credential isolation) is also parked; it is meaningful only after D10.8.
- `.intent/` writability by the assistant is tracked separately; same shape, one level up.
