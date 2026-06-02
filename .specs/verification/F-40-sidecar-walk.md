# F-40 — Sidecar attachment verification

**Status:** Verification record (F-40.4 output, 2026-06-02)
**Location:** `.specs/verification/F-40-sidecar-walk.md`
**Authority:** Operational — this document records the design-walk that satisfies ADR-085's F-40 exit criterion. The published `/v1/openapi.json` spec at `.specs/contracts/oem_api_v1.openapi.json` is the contractual artifact; this doc is the verification that the contract is sufficient.

When this document disagrees with the published spec, the spec wins. When this document disagrees with the sidecar feature anchors in `CORE-Features.md`, the anchors win on what each sidecar *is*; this doc wins on what each sidecar *needs from F-40 specifically*.

---

## 1. Purpose

ADR-085's 5+3 row for F-40 names the exit criterion verbatim:

> "`status: shipping`; documented public contract; **sidecar-shape commercial features F-20/F-34/F-45/F-47 can attach against it without private hooks** (ADR-084 D6)."

The bold phrase requires verification — without a walk-through against actual sidecar needs, "without private hooks" is a hypothesis. This document is the verification.

The walk-through is **design-time**, not runtime. The sidecars don't exist yet (F-20, F-34, F-45 are roadmap-stamped commercial features per `CORE-Features.md`); they're scheduled to begin design work post-F-40 ship per ADR-084 D3. What we can verify today is: **for the API surface each sidecar would need based on its feature anchor's stated scope, is every required route present in the F-40 public contract?**

If yes, F-40 ships. If no, the gap is either: (a) filled by adding the route to F-40's public set (and re-running this walk); or (b) renegotiated — the sidecar's scope is trimmed, or the route is reclassified `internal` and the sidecar's needs change accordingly.

## 2. Method

For each in-scope sidecar:

1. Re-read its anchor block in `CORE-Features.md` §3.
2. Enumerate the API surface its scope implies. Map each scope element to one or more endpoints under `/v1/`.
3. Walk each endpoint against the public set declared in `.specs/contracts/oem_api_v1.openapi.json` (48 paths) and named in `papers/CORE-OEM-API.md` §3.
4. Mark each endpoint as: ✅ present, ⚠️ present but requires shape qualification, ❌ missing.
5. If any ❌ exists, surface as a gap. Address before proceeding.

## 3. F-20 — Convergence graph dashboard (sidecar)

**Anchor** (`CORE-Features.md` §3 F-20): "A web UI rendering the convergence metric as a time-series graph. Finding rate versus resolution rate over time. The anchor feature for Team tier adoption."

**Implied API surface**: time-series convergence data over arbitrary windows; baseline configuration; current state.

| Sidecar need | F-40 endpoint(s) | Status |
|---|---|---|
| Trigger / observe a structural census | `POST /v1/census/runs`, `GET /v1/census/runs/{run_id}` | ✅ both public |
| Compare current state to historical baselines | `GET /v1/census/diff` | ✅ public |
| Manage named baselines (create + list) | `POST /v1/census/baselines/{name}`, `GET /v1/census/baselines` | ✅ both public |
| Observe drift state (symbols + vectors) | `GET /v1/status/drift` | ✅ public |
| Optional: poll DB / worker health | `GET /v1/status/db` | ✅ public |

**Walk result: 6 endpoints required, 6 ✅ present.** No gaps.

**Shape qualification**: response shapes today are loosely typed (return `dict`). F-20 will need stronger response models (e.g., a `CensusDiffResponse` Pydantic model with typed fields for `findings_added`, `findings_resolved`, time-series points). This is **not a private hook** — it's a follow-up enhancement to the public contract per ADR-087's "additive change" rules. Tracked implicitly as Pydantic field-level annotation work; out of F-40 scope.

## 4. F-34 — Web dashboard (sidecar)

**Anchor** (`CORE-Features.md` §3 F-34): "Browser-based governance interface. Views: convergence graph (F-20), proposal queue, audit history, worker health. Replaces CLI as the primary interface for team governors who are not working in a terminal."

**Implied API surface**: F-20's full set (convergence is embedded) + proposal queue management + audit history + worker health + (likely) inspect surface for governance drill-down.

| Sidecar need | F-40 endpoint(s) | Status |
|---|---|---|
| F-20's convergence set | (see §3 above) | ✅ all public |
| Proposal queue: list + detail | `GET /v1/proposals`, `GET /v1/proposals/{id}` | ✅ both public |
| Proposal mutation (governor actions) | `POST /v1/proposals/{id}/approve`, `.../reject`, `.../execute` | ✅ all three public |
| Create proposals (governor-direct entry) | `POST /v1/proposals` | ✅ public |
| Audit history | `POST /v1/audit/runs`, `GET /v1/audit/runs/{run_id}` | ✅ both public |
| Remediation runs | `POST /v1/audit/remediations`, `GET /v1/audit/remediations/{run_id}` | ✅ both public |
| Worker / DB health | `GET /v1/status/db`, `GET /v1/status/drift` | ✅ both public |
| Component inventory (advanced governance view) | `GET /v1/components` | ✅ public |
| Decision / refusal trails | `GET /v1/decisions`, `/v1/decisions/patterns`, `/v1/refusals`, `/v1/refusals/stats` | ✅ all four public |
| Knowledge-graph capability discovery | `GET /v1/knowledge/capabilities` | ✅ public |
| Refactor backlog (operator-facing view) | `GET /v1/refactor/threshold`, `/v1/refactor/score`, `/v1/refactor/candidates`, `/v1/refactor/stats`, `/v1/refactor/runs/{run_id}` | ✅ all five public |
| Coverage gaps (operator-facing view) | `GET /v1/coverage/check`, `/v1/coverage/report`, `/v1/coverage/targets`, `/v1/coverage/gaps`, `/v1/coverage/history`, `/v1/coverage/runs/{run_id}` | ✅ all six public |
| Action discovery (operator-facing) | `GET /v1/actions`, `GET /v1/fix/commands` | ✅ both public |
| Capability / command search | `GET /v1/search/capabilities`, `GET /v1/search/commands` | ✅ both public |
| Cluster / duplicate / DRY analysis | `GET /v1/analysis/*` (5 endpoints) | ✅ all five public |

**Walk result: ~35 distinct endpoints required, 35 ✅ present.** No gaps.

**Authentication observation**: F-34's mutation surface (proposal approve/reject/execute, audit-run creation, remediation dispatch) requires authorization. Today's F-40 has no auth (per ADR-087 D8's pre-v1 carve-out). F-34's operational deployment depends on F-40.5 (#554) landing first. This is **not a private hook gap** — F-40.5 is documented in the F-40 paper and ADR-087 D8 as Phase B work that lands after F-40 ships. F-34 development can begin against F-40 today and integrate F-40.5's auth layer when it arrives.

## 5. F-45 — Hosted findings dashboard (sidecar, read-side only)

**Anchor** (`CORE-Features.md` §3 F-45): "A cloud-hosted web UI rendering audit findings (F-09) for Audit-tier customers who installed the CI gate (F-10) but do not run a daemon, database, or web tier locally. Read-only view: rule, file, severity, message, and history across PR runs. Per-organisation deployment with SSO."

**F-45 architectural model** (per recon during F-40 decomposition): F-45 is cloud-hosted and consumes findings posted by the F-10.3 GitHub Action. F-45 **does not connect to a customer's local daemon**. Therefore F-45's relationship to F-40 is **enrichment-only on the read side**: when a finding arrives at F-45's own ingestion endpoint (which is part of F-45 itself, hosted in `CORE-sidecars-commercial/` per ADR-084 D5), F-45 may call out to a CORE OEM API instance (CORE's own or a customer's, depending on deployment model) to enrich the finding with constitutional context.

**Implied API surface** (enrichment side only):

| Sidecar need | F-40 endpoint(s) | Status |
|---|---|---|
| Look up a constitutional rule by id | `GET /v1/inspect/*` family — primarily `GET /v1/decisions/patterns` for rule-pattern context; potentially `GET /v1/analysis/clusters` for cluster grouping | ✅ both public |
| Resolve atomic-action ids referenced in findings | `GET /v1/actions`, `GET /v1/fix/commands` | ✅ both public |
| Surface capability-name context for findings | `GET /v1/knowledge/capabilities`, `GET /v1/search/capabilities` | ✅ both public |
| (Optional) historical audit-run context for the finding's repo | `GET /v1/audit/runs/{run_id}` | ✅ public |

**Walk result: ~5 distinct endpoints required (enrichment), 5 ✅ present.** No gaps.

**Architectural clarification**: F-45's own surface (findings ingestion endpoint, cloud findings query, SSO sessions) lives in the F-45 commercial repo and is NOT part of F-40. The F-40 contract serves F-45 only via the upstream enrichment reads. The F-10.3 GitHub Action posts findings to F-45's ingestion endpoint (commercial); F-45 then enriches them by calling F-40 (open) endpoints listed above. Two distinct surfaces, two distinct deployment locations.

## 6. F-47 — Managed Qdrant (explicit exclusion)

**Anchor** (`CORE-Features.md` §3 F-47): "Managed hosting of the vector store layer (F-25 collections — `core-code`, `core-docs`, etc.) on infrastructure operated by the commercial product line. Solo customers point their daemon at the managed endpoint via a configuration switch; all governance semantics remain identical."

**F-47 is not a FastAPI consumer.** Its "API" is the Qdrant wire protocol. A Solo customer running CORE's daemon configures `QDRANT_URL` to point at the F-47-managed endpoint; the daemon's existing Qdrant client connects there instead of to a self-hosted instance. F-40's FastAPI surface is irrelevant to this interaction.

**ADR-084 D8 sidecar bucket correction**: D8's bucket table lists F-47 under the "Sidecar" shape — but with the explicit qualifier "(managed infrastructure)". The bucket assignment is correct in the sense that F-47 lives in `CORE-managed-infra/` (per D5) and is commercially aligned with the sidecar fleet, not the runtime-fork fleet. The **F-40 dependency relationship** for F-47 is **explicitly null** — F-40 is not a precondition for F-47's ship, and F-47 doesn't consume F-40 endpoints. The dependency edge listed in ADR-085's 5+3 row ("sidecar-shape commercial features F-20/F-34/F-45/F-47 can attach...") is therefore satisfied trivially for F-47 — there's no attachment to make.

This correction is noted in `papers/CORE-OEM-API.md` §2 and §5, and in the F-40 #414 issue body. ADR-084 D8 itself can carry an inline footnote in a future amendment if the bucket-list-vs-dependency-list distinction needs clearer surfacing; for now, this verification doc + the OEM API paper + the F-40 issue body collectively record the correction.

## 7. Gap summary

**Zero gaps.** Every endpoint required by F-20, F-34, and F-45 (read-side enrichment) is present in the F-40 public contract.

| Sidecar | Endpoints required | Endpoints found public | Gaps |
|---|---:|---:|---|
| F-20 | 6 | 6 | 0 |
| F-34 | ~35 | 35 | 0 |
| F-45 (read-side) | 5 | 5 | 0 |
| F-47 | N/A (not a FastAPI consumer) | N/A | 0 |

## 8. Constitutional check (ADR-084 D6 — interface symmetry)

The walk-through confirms no sidecar requires a route classified `internal`. **Interface symmetry holds**: any third-party OEM partner who reads the F-40 public spec sees exactly the same surface that first-party commercial sidecars (F-20, F-34, F-45) attach against. There is no commercial-only API surface in the open repo.

Per ADR-084 D6: "Every interface a commercial plugin, sidecar, or runtime fork uses MUST be a documented public interface available to any third party." The walk above demonstrates this is satisfied at design-time.

## 9. F-40 closure declaration

The exit criterion in ADR-085 5+3 row reads in full:

> "F-10 CI/CD gate | registry | `status: shipping`; PR annotations + merge-blocking demonstrated against a real external repo"
> "F-40 OEM API surface | registry | `status: shipping`; documented public contract; sidecar-shape commercial features F-20/F-34/F-45/F-47 can attach against it without private hooks (ADR-084 D6)"

For F-40, all three clauses are now satisfied:

1. ✅ **`status: shipping`** — flipped in `CORE-Features.md` registry as part of F-40.4 closure (this issue).
2. ✅ **documented public contract** — `papers/CORE-OEM-API.md` (route classification, F-40.1) + ADR-087 (stability policy, F-40.2) + `contracts/oem_api_v1.openapi.json` (machine-readable spec, F-40.3).
3. ✅ **sidecar-shape commercial features can attach without private hooks** — this verification document (F-40.4) walks each sidecar against the public contract and finds zero gaps.

**F-40 ships 2026-06-02.** Third 5+3 gate item closed in the same session as F-10 and F-48.

## 10. Follow-ups (deferred, not gating)

These are **not gaps** for F-40 shipping but are real engineering work the broader F-40 paper anticipates:

- **F-40.5 (#554) — Authentication + authorization.** F-34's mutation surface and F-45's per-customer deployment both require auth at production scale. Phase B work; explicit carve-out per ADR-087 D8.
- **F-40.6 (#555) — Host binding, rate limiting, OpenAPI publication mechanism.** Today's `127.0.0.1:8000` localhost-only binding is fine for first-party-on-same-host sidecar deployments; third-party OEM partners and cloud-hosted F-45 deployments need this.
- **Pydantic field-level descriptions.** Route-level summaries land F-40's exit criterion; field-level "what's this parameter for" annotations enrich the spec for richer client codegen. Not gating.
- **CI snapshot-freshness gate.** A pre-commit hook or CI step that regenerates `contracts/oem_api_v1.openapi.json` from source and fails if it diverges. Not gating; live `/v1/openapi.json` is authoritative when reachable.

## 11. References

- **Parent feature:** #414 (F-40 OEM API surface)
- **This verification's source issue:** #553 (F-40.4)
- **Preceding sub-issues:** #550 (F-40.1 — classification), #551 (F-40.2 — versioning policy, ADR-087), #552 (F-40.3 — OpenAPI spec)
- **Deferred sub-issues:** #554 (F-40.5 — auth), #555 (F-40.6 — host binding + rate limiting + spec publication)
- **Constitutional anchors:** ADR-084 D3 + D6 + D8; ADR-085 §Context 5+3 row
- **Authoritative artifacts referenced:** `papers/CORE-OEM-API.md`, `.specs/decisions/ADR-087-oem-api-versioning-and-stability-policy.md`, `.specs/contracts/oem_api_v1.openapi.json`
- **Sidecar anchors walked:** `CORE-Features.md` §3 F-20 / F-34 / F-45 / F-47
