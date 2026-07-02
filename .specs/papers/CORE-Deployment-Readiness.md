---
kind: paper
id: CORE-Deployment-Readiness
title: CORE — Deployment Mode and Multi-User Prerequisites
status: canonical
doctrine_tier: policy
---

<!-- path: .specs/papers/CORE-Deployment-Readiness.md -->

# CORE — Deployment Mode and Multi-User Prerequisites

**Status:** Canonical
**Authority:** ADR-110 (exposure trust tiers); ADR-086 (installation architecture)
**Scope:** All CORE deployments; operator and governor readiness
**Machine-readable declaration:** `.intent/enforcement/config/deployment_mode.yaml`

---

## 1. Current deployment mode

CORE currently operates in **`solo` mode**: a single governor, local-only trust,
no external user access. This is the declared mode as of 2026-07-02.

Solo mode is the constitutionally safe default. It was chosen deliberately:
multi-user access requires prerequisite work that has not yet been completed.
Operating in multi-user mode before the prerequisites close is a violation of
ADR-110 D1.

---

## 2. What solo mode means

- One governor operates the system.
- Mutation endpoints (proposal approval, fix dispatch, daemon control, `.intent/`
  writes) are gated by governor authentication only, not by role differentiation.
- The `require_role('platform_admin')` guard applied in commit `86ce613a` is
  sufficient for solo: there is only one role class.
- The API is local-access only; no remote or external user traffic is expected.
- ADR-053's deferred trust-boundary (local-only trust in Phase 1) remains in force.

---

## 3. Prerequisites before multi-user

The machine-readable prerequisite list lives in
`.intent/enforcement/config/deployment_mode.yaml`. The canonical list is there;
this paper explains the reasoning.

**Prerequisite 1 — #671: ADR-110 D5 exposure metadata**

Every CLI command and API endpoint must carry an `exposure` tier
(`user-facing` | `governor-only`) before role-differentiated access can
be applied correctly. Without this metadata:

- There is no machine-readable census of what is safe to serve to a
  lower-trust caller.
- Role checks cannot be applied consistently — each endpoint requires manual
  inspection to determine what level of trust it requires.
- The API accessibility overview (the derived artifact ADR-110 D5 mandates)
  cannot be generated.

Until #671 closes: do not grant non-governor users API access.

**Prerequisite 2 — #672: ADR-110 D3/D4 write-safety rails on directed mutation**

The directed AI-mutation path (`StrategicAuditor`, `dev refactor`, the API dev
routes) currently commits directly with no per-execution sandbox (ADR-106) and
no declared-production commit-set (ADR-107). Under multi-user:

- A lower-trust caller exercising this path would produce commits with no
  sandbox isolation and no attribution guarantee.
- ADR-101 D1 (commit authorship integrity) cannot be met if the path bypasses
  the sandbox that produces the declared production set.

Until #672 closes: do not expose the directed mutation path to non-governor callers.

---

## 4. What does "graduation" to multi-user look like?

When both prerequisites are closed and verified:

1. Change `mode: solo → mode: multi_user` in
   `.intent/enforcement/config/deployment_mode.yaml`.
2. This change requires a governor commit with an explicit rationale referencing
   the closed issue numbers and their verification commits.
3. `core-admin health` (or the API `/v1/health` endpoint) reads the deployment
   mode and surfaces it to the operator. A mode change from solo to multi_user
   is a visible, audited event.
4. The constitutional rule `architecture.api.no_direct_database_access` reporting
   tier — currently carried as architectural debt per ADR-053 deferral — is
   re-evaluated for promotion to blocking in the multi-user context.

---

## 5. Relationship to ADR-110

ADR-110 D1 defines the exposure trust tiers (`user-facing` / `governor-only`).
ADR-110 D2 establishes that exposure is enforced on the API, not by withholding
capabilities from it. ADR-110 D5 mandates the derived accessibility overview.

This paper and the companion `.intent/` flag operationalize ADR-110's framing:
the trust boundary is now specified (ADR-110 closes ADR-053's deferral), and
the prerequisites name the remaining work before the boundary can be enforced
at the access-control layer rather than by local-only deployment.

---

## 6. References

- `.intent/enforcement/config/deployment_mode.yaml` — machine-readable mode flag
- ADR-110 — Exposure is a trust tier on the API; write-safety binds to the operation
- ADR-086 D3 — Pre-flight checks including single-owner state assertion
- ADR-053 — API as governance interface (original local-only trust deferral)
- ADR-101 — Commit authorship integrity
- ADR-106 — Per-execution sandbox
- ADR-107 — Declared-production commit-set
- #671 — ADR-110 D5 exposure metadata (prerequisite 1)
- #672 — ADR-110 D3/D4 write-safety rails (prerequisite 2)
