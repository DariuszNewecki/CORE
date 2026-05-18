# ADR-053 — CORE API as Resource-Oriented Governance Interface

**Status:** Accepted (revised 2026-05-18 — D4 amended to assign unassigned capability map items)
**Date:** 2026-05-16
**Revised:** 2026-05-18
**Authors:** Darek (Dariusz Newecki)
**Closes:** API incompleteness gap identified by ADR-050 capability audit
**Relates to:** ADR-050 (CLI positioning), ADR-051 (file_handler shared/
excludes closure), ADR-049 (doctrine-rule parity),
CORE-Mind-Body-Will-Separation paper §6, EU AI Act Articles 9/17
traceability

---

## Context

ADR-050 established that CLI is an operator client outside CORE's closed
system, and that CLI's only sanctioned dependency on CORE internals is
`api.*`. The 2026-05-16 capability audit (58 files, 193 forbidden import
targets, 10 domain groups) revealed why the rule `architecture.cli.api_only`
produces 524 violations immediately: the API surface does not yet exist.
CLI reaches `will.*`, `body.*`, `mind.*`, and `shared.*` directly because
there is no governed HTTP boundary covering those capabilities.

The violation is not in CLI's imports. The violation is API incompleteness.

### How the industry solves this

Kubernetes, HashiCorp Vault, and the AWS control plane converge on one
pattern: **the API is the system**. `kubectl` has zero business logic — it
is a typed HTTP client. `kube-apiserver` is the single entry point.
Long-running operations are not RPC calls; they are **resources submitted
to a reconciliation loop**. The caller declares desired state; a controller
reconciles toward it; the caller polls for results.

CORE already implements this pattern internally:

- `core.autonomous_proposals` — resources with lifecycle state
- `core.audit_findings` — observation resources
- `core.blackboard_entries` — shared state resources
- Will workers — the reconciliation loop

The API build-out is not designing something new. It is exposing CORE's
existing resource model through a governed HTTP boundary.

### What the capability audit found

The 2026-05-16 scan produced a complete operator capability map: 58 CLI
modules reduce to approximately 40 endpoints across 10 domain namespaces.
Half the migration surface concentrates in two clusters: `/audit/*`
(8+ files, backed by `mind.governance.*`) and `/fix/*` (12 files, backed
by `body.self_healing.*`). Full capability map is retained in
`.specs/planning/CORE-API-capability-map-2026-05-16.md` as the phase
roadmap input.

Two files in the capability map — `components.py` and `search.py` — were
not assigned to any of the ten namespaces at the time of initial
acceptance. Their assignment is resolved by the 2026-05-18 revision to D4
below.

### Who calls this API

Three authorized callers exist now or in the near term:

1. **Governor (Darek)** — approving proposals, triggering audits, inspecting
   state. Today via CLI; after this ADR via CLI-over-HTTP.
2. **CI pipeline** — calling `POST /audit/runs` on every commit; comparing
   finding counts against baseline.
3. **Regulated-industry operator (Eve archetype)** — GxP traceability
   requires a documented, auditable request boundary with per-request
   logging. HTTP API with request-level attribution is the only
   defensible form for EU AI Act Articles 9/17 evidence.

All three callers use the same API. CLI is one client of this interface.
It is not a privileged one.

---

## Options considered

**Option A — Extend CLI in-process indefinitely.**
Continue adding CLI commands that import `will.*` / `body.*` directly.
Rejected: produces unbounded governance debt, makes CI and GxP callers
impossible, contradicts ADR-050.

**Option B — HTTP gateway shim (thin proxy over existing CLI).**
Wrap existing CLI commands behind FastAPI routes without restructuring
the import graph. Rejected: entrenches the composition-root problem in
API layer; the shim imports the same forbidden targets CLI does; audit
violations move one layer up, not away.

**Option C — Resource-oriented API exposing CORE's existing resource
model.** Operations are submitted as resources; the Will reconciliation
loop executes them; callers poll for results. This is the Kubernetes/
Vault/AWS pattern. Chosen.

---

## Decision

### D1 — The API is CORE's governance interface

`src/api/` is the sole governed entry point into CORE's closed system
(Mind / Body / Will), as ADR-050 D1 established. This ADR extends that
positioning: the API is not a developer convenience layer. It is
**CORE's governance interface** — the boundary through which any
authorized party observes and directs the system.

The interaction topology is:

```
Governor / CI / GxP Auditor
         ↓
     src/api/         ← sole governed entry point
         ↓
  Will (workers)      ← reconciliation loop
    ↙       ↘
 Body       Mind      ← execution and intelligence
         ↑
      shared/         ← internal nervous system; invisible above api/
```

`shared/` serves Mind, Body, and Will as internal infrastructure.
It is not reachable from `src/api/` routes directly; API routes depend
on Will-layer services, which depend on shared internally. `shared/`
is never visible to any external caller.

### D2 — Operations are resources, not RPC calls

Long-running operations (audit runs, fix executions, test generation,
refactor cycles) are submitted as **resources** and reconciled
asynchronously by the Will layer. The caller receives a resource ID and
polls for lifecycle state. Synchronous blocking HTTP is reserved for
read-only queries and instantaneous state checks only.

Resource lifecycle states follow the existing CORE pattern:

```
pending → executing → completed | failed
```

No new job table is introduced speculatively. Each phase ADR determines
whether an operation maps to an existing resource type
(`autonomous_proposals`, `audit_findings`) or requires a new one.
Governing principle: **reuse existing resource tables before creating
new ones.**

### D3 — Standard protocol contract

All API endpoints conform to a single protocol contract defined here.
Phase ADRs reference this contract; they do not redefine it.

#### Resource submission (long-running operation)

```
POST /domain/resources
Body: { ...typed request schema... }

→ 202 Accepted
  {
    "resource_id": "<uuid>",
    "status": "pending",
    "href": "/domain/resources/<uuid>"
  }
```

#### Resource polling

```
GET /domain/resources/<uuid>

→ 200 OK
  {
    "resource_id": "<uuid>",
    "status": "pending | executing | completed | failed",
    "created_at": "<iso8601>",
    "updated_at": "<iso8601>",
    "result": { ...typed result schema... } | null,
    "error": "<message>" | null
  }
```

#### Read queries (collections)

```
GET /domain/resources[?filter=value&page=N&page_size=50]

→ 200 OK
  {
    "items": [ ...typed item schemas... ],
    "total": N,
    "page": N,
    "page_size": 50
  }
```

Default page_size: 50. Maximum page_size: 200.

#### Error shape (all endpoints, all status codes ≥ 400)

```
{
  "error": "<machine-readable snake_case code>",
  "message": "<human-readable description>",
  "detail": { ...structured context... } | null
}
```

#### Schema discipline

All request and response bodies are typed Pydantic v2 schemas defined
in `src/api/schemas/`. No ad-hoc dicts in route handlers. Schemas are
the API contract. A schema change is a contract change and requires a
phase ADR amendment or a new phase ADR.

### D4 — Ten domain namespaces (revised 2026-05-18)

The API surface is organised into ten namespaces derived from the
capability audit. Each namespace maps to a cohesive Will/Body/Mind
backend. Each namespace is implemented under a dedicated phase ADR
before any code is written for that namespace.

| Namespace    | Primary backend            | Phase |
|--------------|----------------------------|-------|
| `/audit`     | `mind.governance.*`        | 1     |
| `/proposals` | `core.autonomous_proposals`| 1     |
| `/fix`       | `body.self_healing.*`      | 2     |
| `/quality`   | Will quality-gate workflows| 2     |
| `/coverage`  | Body coverage services     | 3     |
| `/refactor`  | Mind modularity engine     | 3     |
| `/inspect`   | Shared observation layer   | 3     |
| `/census`    | Body CIM services          | 4     |
| `/sync`      | Will sync workflows        | 4     |
| `/daemon`    | Worker lifecycle           | 4     |

Phase 1 is chosen because `/audit` and `/proposals` already have
complete resource backing in the database and the most cohesive Will-
layer services. They are also the capabilities most critical to the
governor's daily loop and the GxP audit trail.

**Unassigned items resolved (2026-05-18).** Two CLI files —
`src/cli/commands/components.py` (`GET /components`) and
`src/cli/commands/search.py` (`GET /search/capabilities`,
`GET /search/commands`) — were not assigned to a namespace in the
original capability audit. They are formally assigned to `/inspect`
here. The assignment decision and the elimination of the two
alternative candidates are recorded below.

**Why `/inspect`, not `/audit` or `/meta`.**

`/audit`'s declared primary backend is `mind.governance.*`. Neither
`components.py` nor `search.py` touches `mind.governance.*`; both
import exclusively from `shared.*`. Assigning `shared.*`-only files to
a `mind.governance.*` namespace misrepresents the backend dependency
and would create a false categorisation that a future maintainer cannot
verify mechanically. `/audit` is eliminated.

`/meta` appears in the capability map sketch (`GET /meta/validation`
covers `mind.py`) but has no phase ADR. D6 of this ADR requires a
phase ADR to be accepted before any endpoint in a namespace is
implemented. Assigning files to `/meta` now would either block their
implementation until `/meta` receives a phase ADR, or require
implementing them before their governing ADR exists — both of which
violate D6. `/meta` is eliminated.

`/inspect`'s declared primary backend is "Shared observation layer."
Both files are `shared.*`-only and both endpoints are read-only
structural queries. This matches the `/inspect` profile on two
independent constraints (backend dependency and operation character),
not on a vibes-level similarity claim. The assignment is auditable.

**Assignment:**

`/inspect` is the OpenAPI tag applied to this group, not a URL segment.
Existing inspect endpoints follow the pattern `/v1/status/*`, `/v1/decisions`,
`/v1/analysis/*` — no `/v1/inspect/` prefix. These three assignments conform
to the same convention:

```
GET /v1/components               — V2 component discovery by package        [Phase 3]
GET /v1/search/capabilities      — semantic search over capability vectors   [Phase 3]
GET /v1/search/commands          — fuzzy CLI registry search                 [Phase 3b — deferred]
```

`GET /v1/components` and `GET /v1/search/capabilities` are implemented by the
2026-05-18 amendment to ADR-057 D5.

`GET /v1/search/commands` is deferred: its backend (`cli.logic.hub.hub_search_cmd`)
is a CLI-layer artifact that the API layer cannot import. Follow-up issue
**#363** (Phase 3b, Band D — Engine Integrity milestone) tracks lifting the
fuzzy-search logic out of `cli.logic.hub` into a `shared.*` or `will.*`
service before this endpoint can be implemented. The ADR-050 extraction
blocker is resolved by the first two endpoints; this deferral does not
reopen it.

**Seam note.** `GET /v1/components` is structural anatomy —
squarely within the Inspect group. `GET /v1/search/*` is capability
discovery over the CLI registry, which is closer to the
OpenAPI-adjacent surface that `/meta` would cover if formalized. Both
pass the `shared.*`-only static-import test and the read-only test, so
the Inspect grouping is correct under the current profile. If `/meta`
is later formalized per the capability map sketch, `GET /v1/search/*`
is the candidate for reassignment; `GET /v1/components` stays.

### D5 — CLI becomes a typed HTTP client

Upon completion of all phase implementations, `src/cli/` contains no
imports from `will.*`, `body.*`, `mind.*`, or `shared.*`. Every operator
capability is exercised by constructing an HTTP request and rendering
the response as Rich output.

`CoreContext` is not instantiated in CLI. The CLI composition root is
replaced by an HTTP client configuration (base URL, auth token,
timeout). `shared.logger` and `shared.context` are not imported in CLI;
CLI uses its own logging setup independent of CORE internals.

The `architecture.cli.api_only` rule (ADR-050 D4) transitions from
migration-backlog enforcement to permanent enforcement at Phase 4
completion.

### D6 — Papers first, always

No endpoint is implemented before its phase ADR is accepted. Phase ADRs
define: the resource model (new or reused table), the request/response
schemas, the Will-layer wiring (new workflow or existing worker
dispatch), and the CLI command(s) being migrated. Implementation begins
only after governor acceptance of the phase ADR.

### D7 — Request-level attribution for GxP readiness

Every API request that submits or mutates a resource records:

- `requested_by` — caller identity (operator token or system identifier)
- `requested_at` — UTC timestamp
- `request_ref` — caller-supplied idempotency/correlation key (optional)

These fields are persisted on the resource row, not in a separate log.
They satisfy the per-request audit trail required for EU AI Act Articles
9/17 evidence without a separate logging infrastructure.

---

## Consequences

### Positive

- **API incompleteness is the migration.** Once the API surface exists,
  CLI import violations resolve by replacing direct calls with HTTP
  client calls — no architectural surgery on CLI itself.
- **All callers are equal.** Governor CLI, CI pipeline, and GxP auditor
  use the same interface. No privileged in-process bypass exists.
- **CORE's existing resource model does the heavy lifting.** Proposals,
  findings, and blackboard entries are already resources with lifecycle
  state. The API exposes what already exists; it does not invent a
  parallel execution model.
- **GxP readiness is structural.** Request-level attribution (D7) is
  built into the resource model from Phase 1, not retrofitted later.
- **`architecture.cli.api_only` becomes enforceable.** The rule has
  524 violations today because the API it requires does not exist.
  As each phase lands, violations drain. The rule becomes fully active
  at Phase 4 completion.

### Negative

- **Phase 1 requires new API endpoints before any CLI migration
  occurs.** The 524 violations do not decrease until Phase 1 ships.
  This is a deliberate sequencing choice: build the governed boundary
  first, migrate callers second.
- **Will-layer wiring is non-trivial for some namespaces.** `/fix` and
  `/coverage` require Will workflows that do not currently have HTTP-
  callable entry points. Phase ADRs for those namespaces must design
  the wiring explicitly.
- **CLI user experience is unchanged during migration.** Commands
  continue to work throughout; the change is internal. This is correct
  but means the migration is invisible to the operator until complete.

### Neutral

- `src/cli/` is not deleted or restructured. It remains the operator
  interface; only its import dependencies change.
- The daemon interaction topology is unchanged. The daemon continues to
  run the Will reconciliation loop; the API is a new entry point into
  that loop, not a replacement for it.
- Total rule count is unchanged by this ADR. No new constitutional
  rules are introduced here; rule additions are scoped to phase ADRs.

---

## Verification

This ADR is verified when:

1. **Phase 1 is complete** — `/audit/*` and `/proposals/*` endpoints
   exist, are tested, and are callable via HTTP. At least one CLI
   command in each namespace has been migrated to call API instead of
   importing `will.*` or `mind.*` directly.

2. **Protocol contract is uniform** — all Phase 1 endpoints return the
   error shape defined in D3. A non-200 response from any Phase 1
   endpoint contains `error`, `message`, `detail`.

3. **Request attribution is persisted** — `requested_by` and
   `requested_at` are non-null on all resource rows created through
   the API after Phase 1 lands.

4. **Phase ADR discipline holds** — no Phase 2 implementation begins
   before its phase ADR is accepted. The ADR log is the migration
   ledger.

5. **`architecture.cli.api_only` finding count decreases monotonically**
   across phases — from 524 at ADR-053 acceptance toward 0 at Phase 4
   completion. Convergence on this rule is the operational metric for
   the migration.

---

## Deferred

- **Authentication model** — API currently has no auth layer. A
  separate ADR will define the auth model (token, mTLS, or local-only
  trust boundary) before any multi-user or remote-access deployment.
  Phase 1 operates under local-only trust (daemon and CLI on same host).
- **API versioning** — URL-based versioning (`/v1/`) is the default
  pattern. Deferred to Phase 1 ADR to decide whether versioning is
  needed before the API is exposed beyond localhost.
- **Network boundary (ADR-050 deferred section)** — transitioning from
  logical import boundary to physical HTTP boundary is deferred per
  ADR-050. The trigger remains: first use case requiring per-request
  auth, remote CLI, or request-level audit logging beyond what D7
  provides in-process.

---

## References

- `.specs/decisions/ADR-050-cli-positioning.md` — CLI positioning;
  establishes `architecture.cli.api_only` and the 4-step resolution
  sequence this ADR implements.
- `.specs/decisions/ADR-051-file-handler-shared-excludes-closure.md`
- `.specs/decisions/ADR-049-*` — doctrine-rule parity; governs how
  ADRs relate to live rules.
- `.specs/planning/CORE-API-capability-map-2026-05-16.md` — full
  capability audit output; 58 files, 40 endpoints, 10 namespaces.
  Input to phase ADR sequencing.
- `CORE-Mind-Body-Will-Separation.md §6` — API as entry-point boundary;
  this ADR extends §6 to name the governance interface role explicitly.
- EU AI Act Articles 9, 17 — risk management and quality management
  system requirements; D7 request attribution is the traceability
  evidence mechanism for these articles.
- Kubernetes `kube-apiserver` architecture — industry reference for
  resource-oriented control plane over reconciliation loop.

---

*Revised 2026-05-18: D4 amended to assign `components.py` and `search.py`
to the Inspect namespace group (Phase 3, ADR-057). The two alternative candidates
(`/audit`, `/meta`) are eliminated in D4 with explicit constraint reasoning.
A seam note records `GET /v1/search/*` as the candidate for reassignment
if `/meta` is later formalized. `GET /v1/search/commands` is deferred Phase 3b
pending extraction of `hub_search_cmd` from `cli.logic.hub`. URL paths use the
existing Inspect convention (`/v1/<resource>`, not `/v1/inspect/<resource>`).
Context section updated to name the unassigned items and their resolution. No
other decisions changed.*
