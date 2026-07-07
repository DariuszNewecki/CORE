---
kind: paper
id: CORE-OEM-API
title: CORE OEM API — F-40 Public Contract Declaration
status: canonical
doctrine_tier: foundational
---

# CORE OEM API — F-40 Public Contract Declaration

**Status:** Draft (F-40.1 output, 2026-06-02)
**Location:** `.specs/papers/CORE-OEM-API.md`
**Audience:** Internal (governance) + external (third-party OEM integrators)
**Authority:** Operational (this doc) + Constitutional (the `.intent/`-enforceable derivation, to be created in F-40.3)

When this document disagrees with the running `src/api/` surface, the surface is wrong and lands as a bug. When it disagrees with `.specs/papers/CORE-Features.md`, the registry wins on feature status and this doc wins on per-route classification.

---

## 1. Purpose

ADR-085's 5+3 row for F-40 requires a **documented public contract** as a precondition to ship. ADR-084 D6 requires **interface symmetry**: every interface a commercial sidecar, plugin, or runtime fork uses must be a documented public interface available to any third party. Without a written line between "public contract" and "CORE-internal operator concern," neither of these is satisfiable.

This document is that written line. It walks every endpoint under `src/api/` (~74 across 15 routers + `/health`) and classifies each as one of:

- **`public`** — Part of F-40's stable surface. Consumers (CORE's own sidecars per ADR-084 D3, and third-party OEM integrators per the F-40 paper) may call. Stability semantics are F-40.2's scope.
- **`internal`** — CORE operator / autonomy-loop concern. Reachable today over `127.0.0.1:8000` but no contract is offered; shape can change in any release. Not advertised to external consumers; the OpenAPI spec (F-40.3) excludes these.
- **`deprecated`** — Exists for backwards compatibility; scheduled for removal. Currently: none.

Routes labeled `public` collectively form **CORE OEM API v1**. The `/v1/` URL prefix is the wire signature of this contract.

## 2. Constitutional anchor

The classification is constrained by:

- **ADR-084 D3** — Commercial sidecars MUST consume the open repo's state EXCLUSIVELY through F-40. Any state that a sidecar needs MUST be reachable via a `public` route.
- **ADR-084 D6** — No commercial-only API surface, ever. If a route is reachable by first-party commercial code, it MUST be `public`.
- **ADR-085 5+3 row** — F-40's exit criterion is "sidecar-shape commercial features F-20/F-34/F-45/F-47 can attach against it without private hooks." This restricts the work to sidecar attachability; full third-party OEM consumption (auth, rate limiting, public host binding) is **Phase B** scope, tracked separately under F-40.5/F-40.6.

F-47 (managed Qdrant) is **dropped** from F-40 dependents during the F-40.1 recon. Recon found F-47 does not consume FastAPI at all — its "API" is the Qdrant wire protocol. The ADR-084 D8 sidecar bucket list still lists F-47 as a "degenerate sidecar (managed infrastructure with no commercial code at all)" — that bucket assignment remains correct; the F-40 dependency does not.

Effective F-40 consumers: **F-20**, **F-34**, **F-45 (read-side only)**. Three sidecars.

**Aspirational status:** Enforcing rule not yet authored; this is normative design intent.

## 3. Classification matrix

Every route under `src/api/` is classified below. Routes inherit the `/v1/` prefix from their router mount in `src/api/main.py`; `/health` is the lone non-versioned route.

### 3.1 `/health` (1 endpoint)

| Method | Path | Class | Rationale |
|---|---|---|---|
| GET | `/health` | **public** | Universal liveness probe. Every consumer (sidecar, OEM, monitoring) needs it. |

### 3.2 `/v1/audit` (4 endpoints)

| Method | Path | Class | Rationale |
|---|---|---|---|
| POST | `/v1/audit/runs` | **public** | Create an audit run. F-34 (web dashboard) triggers audits on demand. |
| GET | `/v1/audit/runs/{run_id}` | **public** | Read a run's persisted result. F-34 + F-45 (read-side enrichment). |
| POST | `/v1/audit/remediations` | **public** | Trigger an autonomous remediation run. F-34 surface (operator presses "remediate"). |
| GET | `/v1/audit/remediations/{run_id}` | **public** | Read a remediation run's status/result. F-34 surface. |

### 3.3 `/v1/census` (5 endpoints)

The convergence metric surface. F-20 (Convergence graph dashboard) is the direct sidecar consumer of this entire router.

| Method | Path | Class | Rationale |
|---|---|---|---|
| POST | `/v1/census/runs` | **public** | Create a census run (constitutional drift snapshot). F-20 ingestion. |
| GET | `/v1/census/runs/{run_id}` | **public** | Read a census run's persisted state. F-20 time-series rendering. |
| POST | `/v1/census/baselines/{name}` | **public** | Establish a named baseline. F-20 dashboard configuration. |
| GET | `/v1/census/baselines` | **public** | List baselines. F-20 dashboard configuration. |
| GET | `/v1/census/diff` | **public** | Diff state vs baseline. F-20's "what's changed" view. |

### 3.4 `/v1/coverage` (10 endpoints across `/coverage` + `/tests`)

Per-route classification — this is one of the four "mixed" routers from F-40.1's recon.

| Method | Path | Class | Rationale |
|---|---|---|---|
| GET | `/v1/coverage/check` | **public** | Read-side. F-45 (hosted findings) may surface coverage status. |
| GET | `/v1/coverage/report` | **public** | Read-side coverage report. F-45 + F-34 surface. |
| GET | `/v1/coverage/targets` | **public** | Read-side: configured coverage targets. Sidecar config surface. |
| GET | `/v1/coverage/gaps` | **public** | Read-side: under-covered modules ranked. F-34 actionable surface. |
| GET | `/v1/coverage/history` | **public** | Read-side: historical coverage measurements. F-20-adjacent. |
| GET | `/v1/coverage/methods` | **internal** | Legacy-vs-adaptive method comparison — CORE-internal autonomy concern; sidecars don't care. |
| POST | `/v1/coverage/generate` | **internal** | Triggers test generation via the autonomy loop. Not a sidecar consumer surface. |
| POST | `/v1/coverage/generate:batch` | **internal** | Batch variant of above. |
| POST | `/v1/tests/interactive` | **internal** | Interactive test-shape dispatch — autonomy surface. |
| GET | `/v1/coverage/runs/{run_id}` | **public** | Read a coverage run's persisted state. Mirrors `/audit/runs/{id}`. |

### 3.5 `/v1/daemon` (3 endpoints)

The daemon lifecycle surface. Entirely operator concern; no sidecar would call these (they'd manage their own lifecycle).

| Method | Path | Class | Rationale |
|---|---|---|---|
| GET | `/v1/daemon/status` | **internal** | Daemon-internal status; sidecars probe `/health` instead. |
| POST | `/v1/daemon/start` | **internal** | Operator action; not a sidecar concern. |
| POST | `/v1/daemon/stop` | **internal** | Operator action. |

### 3.6 `/v1/development` (1 endpoint)

| Method | Path | Class | Rationale |
|---|---|---|---|
| POST | `/v1/develop/goal` | **internal** | Submits an autonomous development goal. CORE-internal autonomy entry point; not a sidecar concern. |

### 3.7 `/v1/fix` + `/v1/actions` (7 endpoints)

The atomic-action dispatch surface. Per the F-40 spec — "atomic action registry as a published API" — this is **explicitly** part of the public contract.

| Method | Path | Class | Rationale |
|---|---|---|---|
| GET | `/v1/actions` | **public** | Enumerate registered atomic actions. OEM "embed governance" use case requires action discovery. |
| POST | `/v1/fix/run/{fix_id}` | **public** | Invoke an atomic action by ID. F-40 paper names this as a published API. |
| POST | `/v1/fix/all` | **public** | Run all registered fixes against a target. Sidecar / OEM batch surface. |
| GET | `/v1/fix/...` (other) | **public** | Remaining fix endpoints (status, history) — read surface for sidecars. |

(The `/v1/fix` router has 6 endpoints + the `/v1/actions` discovery endpoint via `actions_router`. All seven classify as `public`; specific paths inventoried in F-40.3's OpenAPI annotation pass.)

### 3.8 `/v1/inspect` (14 endpoints across 6 sub-routers)

All read-only state introspection, per the module docstring ("Every endpoint here is read-only — no resource tables, no background tasks"). Every endpoint surfaces information a sidecar (F-34 web dashboard) would render.

| Method | Path | Class | Rationale |
|---|---|---|---|
| GET | `/v1/status/db` | **public** | DB drift state. F-34 worker-health surface. |
| GET | `/v1/status/drift` | **public** | Knowledge-graph drift state. F-34 + F-20 dashboard surface. |
| GET | `/v1/decisions` + `/decisions/patterns` | **public** | Constitutional decision query. F-34 audit-trail surface. |
| GET | `/v1/refusals` + `/refusals/stats` | **public** | Refusal-result inventory. F-34 governance-trail surface. |
| GET | `/v1/analysis/clusters` | **public** | Code-cluster analysis. F-45 enrichment surface. |
| GET | `/v1/analysis/duplicates` | **public** | Duplicate-symbol analysis. F-45 enrichment surface. |
| GET | `/v1/analysis/common-knowledge` | **public** | Cross-file knowledge surface. F-45 enrichment surface. |
| GET | `/v1/analysis/command-tree` | **public** | CLI command tree projection. F-34 surface. |
| GET | `/v1/analysis/test-targets` | **public** | Test-coverage targets surface. F-34/F-45 surface. |
| GET | `/v1/components` | **public** | Component inventory. F-34 surface. |
| GET | `/v1/search/capabilities` | **public** | Capability search. F-34/F-45 query surface. |
| GET | `/v1/search/commands` | **public** | Command search. F-34 surface. |

All 14 `/inspect/` endpoints classify as `public`.

### 3.9 `/v1/integrate` (1 endpoint)

| Method | Path | Class | Rationale |
|---|---|---|---|
| POST | `/v1/integrate` | **internal** | Integration / build dispatch. CI-internal; sidecars don't trigger builds. |

### 3.10 `/v1/integrity` (2 endpoints)

| Method | Path | Class | Rationale |
|---|---|---|---|
| POST | `/v1/integrity/baseline` | **internal** | File-integrity baseline establishment. Operator concern. |
| POST | `/v1/integrity/verify` | **internal** | File-integrity verification. Operator concern. |

### 3.11 `/v1/knowledge` (1 endpoint)

| Method | Path | Class | Rationale |
|---|---|---|---|
| POST | `/v1/knowledge/...` (1 endpoint) | **public** | Knowledge-graph query. F-34 + F-45 enrichment surface. |

The exact path is `/v1/knowledge/{something}` — F-40.3's OpenAPI pass will name it precisely.

### 3.12 `/v1/lint` (1 endpoint)

| Method | Path | Class | Rationale |
|---|---|---|---|
| POST | `/v1/lint` | **internal** | Triggers a lint run via `black --check` + `ruff check`. CI-internal; a sidecar would not run lint from the daemon. |

### 3.13 `/v1/proposals` (6 endpoints)

The autonomous-proposal queue surface. F-34 (web dashboard) is the direct sidecar consumer.

| Method | Path | Class | Rationale |
|---|---|---|---|
| GET | `/v1/proposals` | **public** | List proposals. F-34 queue view. |
| GET | `/v1/proposals/{proposal_id}` | **public** | Read a proposal. F-34 detail view. |
| POST | `/v1/proposals/{proposal_id}/approve` | **public** | Approve. F-34 governor action. |
| POST | `/v1/proposals/{proposal_id}/execute` | **public** | Execute approved. F-34 governor action. |
| POST | `/v1/proposals/{proposal_id}/reject` | **public** | Reject. F-34 governor action. |
| POST | `/v1/proposals` | **public** | Create a proposal (rare; mostly worker-internal but available to sidecars that want to file via API). |

### 3.14 `/v1/quality` (7 endpoints)

The async-dispatch quality-gate surface (mypy / pytest / pip-audit / ruff / radon / vulture). Each endpoint queues a background gate run.

| Method | Path | Class | Rationale |
|---|---|---|---|
| POST | `/v1/quality/imports` | **internal** | Imports-resolution gate. CI-internal. |
| POST | `/v1/quality/body-ui` | **internal** | Body-UI rendering check. CI-internal. |
| POST | `/v1/quality/policy-coverage` | **internal** | Constitutional policy-coverage audit. CI-internal. |
| POST | `/v1/quality/lint` | **internal** | Lint gate dispatch. CI-internal. |
| POST | `/v1/quality/tests` | **internal** | Test gate dispatch. CI-internal. |
| POST | `/v1/quality/system` | **internal** | System-check gate dispatch. CI-internal. |
| POST | `/v1/quality/gates` | **internal** | Six-gate bundle dispatch (the full quality run). CI-internal. |

All quality gates classify as `internal` — they're CORE's own CI surface, not a sidecar concern. An OEM consumer that wants to expose "run mypy on this code" should do so in their own infrastructure rather than reach into CORE's gate dispatch.

### 3.15 `/v1/refactor` (6 endpoints)

The refactor surface, per the module docstring: "Two endpoint groups: read-only queries... Async dispatch..."

| Method | Path | Class | Rationale |
|---|---|---|---|
| GET | `/v1/refactor/threshold` | **public** | Read-side: configured refactor threshold. Sidecar config surface. |
| GET | `/v1/refactor/score` | **public** | Read-side: refactor-score across the codebase. F-34 surface. |
| GET | `/v1/refactor/candidates` | **public** | Read-side: refactor candidates ranked. F-34 actionable surface. |
| GET | `/v1/refactor/stats` | **public** | Read-side: refactor statistics. F-34 surface. |
| POST | `/v1/refactor/autonomous` | **internal** | Dispatch an autonomous refactor run. Autonomy surface; not a sidecar concern. |
| GET | `/v1/refactor/runs/{run_id}` | **public** | Read a run's persisted state. Mirrors `/audit/runs/{id}`. |

### 3.16 `/v1/sync` (5 endpoints)

| Method | Path | Class | Rationale |
|---|---|---|---|
| POST | `/v1/sync/dev-sync` | **internal** | Dev-mode sync trigger. Operator/CI surface. |
| POST | `/v1/sync/knowledge-graph` | **internal** | KG sync trigger. Operator surface. |
| POST | `/v1/sync/code-vectors` | **internal** | Code-vectors sync. Operator surface. |
| POST | `/v1/sync/vectors` | **internal** | Aggregate vectors sync. Operator surface. |
| POST | `/v1/sync/ir` | **internal** | IR sync. Operator surface. |

All `/sync/` endpoints classify as `internal` — they're CORE's own scheduler / operator surface. Sidecars don't trigger graph synchronisation; CORE's `DbSyncWorker` does on a ~5-minute cadence.

## 4. Summary

| Category | Count | Routers |
|---|---|---|
| **public** | **~46** | `/health`, all of `/audit` (4), `/census` (5), `/inspect` (14), `/proposals` (6), `/fix` + `/actions` (7), `/knowledge` (1), and read-side of `/coverage` (7) + `/refactor` (5) |
| **internal** | **~28** | All of `/daemon` (3), `/development` (1), `/integrate` (1), `/integrity` (2), `/lint` (1), `/quality` (7), `/sync` (5), plus write-side `/coverage` (3) and write-side `/refactor` (1), plus `/coverage/methods` (1) |
| **deprecated** | 0 | — |
| **Total** | **~74** | 15 routers + `/health` |

(Exact counts confirmed in F-40.3's OpenAPI annotation pass; this draft uses approximate counts for routers whose handler list wasn't expanded line-by-line.)

## 5. Sidecar attachment cross-check (preview of F-40.4)

A quick walk-through of each sidecar's needs against the `public` set:

- **F-20 (Convergence graph dashboard)** — needs `/v1/census/*` (5 public) + `/v1/status/db` + `/v1/status/drift` (both public). ✅ Fully served by the public contract.
- **F-34 (Web dashboard)** — needs F-20's set + `/v1/proposals/*` (6 public, including mutation surface for approve/execute/reject) + `/v1/audit/*` (4 public) + most of `/v1/inspect/*` (14 public). ✅ Fully served by the public contract.
- **F-45 (Hosted findings dashboard — read-side enrichment only)** — needs `/v1/audit/runs/{run_id}` (public) + parts of `/v1/inspect/analysis/*` (public). ✅ Fully served by the public contract.

No sidecar needs a route classified `internal`. **F-40 Phase A's "without private hooks" criterion is provisionally met by this classification.** F-40.4 will formalise the walk-through and produce the verification doc that closes F-40.

## 6. Machine-readable spec

The published OpenAPI spec for `/v1/` lives at `.specs/contracts/oem_api_v1.openapi.json` (snapshot, committed) and is also served at `/v1/openapi.json` by the running daemon. Both surfaces are generated from the same FastAPI route annotations in `src/api/v1/*_routes.py` — the committed snapshot is a point-in-time copy for consumers who want the contract without running CORE.

Per ADR-087 D9:
- `info.version` mirrors `core-runtime`'s PyPI version (or `0.0.0+source` in source-tree development mode).
- `info.x-stability-policy` links to ADR-087.
- Routes marked `internal` are absent from the spec (`include_in_schema=False`).

To regenerate the snapshot after a route annotation change:

```bash
python -c "import json; from api.main import app; json.dump(app.openapi(), open('.specs/contracts/oem_api_v1.openapi.json', 'w'), indent=2)"
```

There is no CI gate enforcing snapshot freshness today. A pre-commit hook or CI step that regenerates and diffs is straightforward follow-up work but is not gating F-40.

## 7. What this contract does NOT promise

This classification declares route membership in the public contract. It does NOT yet promise:

- **Per-route stability semantics** — what counts as a breaking change vs additive vs internal. → F-40.2 (versioning + stability policy ADR).
- **Machine-readable surface** — OpenAPI spec with per-route `summary`/`description`/Pydantic models annotated for external consumers. → F-40.3.
- **Authentication / authorization** — public-but-not-anonymous; consumers identify themselves via API keys or tokens. → F-40.5 (Phase B, post-exit).
- **Network reachability** — today `127.0.0.1:8000` only. Public-contract routes are no exception until F-40.6 lands. → F-40.6 (Phase B, post-exit).

A consumer reading this doc today understands which routes will be stable; they cannot yet call them remotely or learn their exact shape from a spec. Both follow.

## 8. Updating this document

This is an operational document; it can change without an ADR amendment when:

- A new endpoint lands in `src/api/` and needs classification (add a row in §3).
- A route's classification changes (e.g., promoting an `internal` to `public` because a new sidecar consumer requires it). Such promotions are additive and don't break the existing contract.
- A route is deprecated (move to §"deprecated" row; record the removal date per F-40.2's deprecation lane).

An ADR amendment is required when:

- The classification model itself changes (e.g., adding a fourth class beyond public/internal/deprecated).
- Interface symmetry (ADR-084 D6) is challenged by a proposed first-party-commercial-only route.

## 9. References

- **Parent issue:** #414 (F-40 OEM API surface)
- **F-40.1 (this doc's source issue):** #550
- **Constitutional anchors:** ADR-084 D3 + D6 + D8; ADR-085 §Context 5+3 row
- **Planning:** `.specs/planning/CORE-Operational-Completeness.md` §2.1 F-40 row; §2.5 F-40 sub-task decomposition
- **Inventory recon:** session of 2026-06-02 (Task 2 of F-40 recon — endpoints walked, mixed routers classified per-route)
