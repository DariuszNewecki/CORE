---
kind: requirement
title: URS — Production Readiness
status: accepted
---

<!-- path: .specs/requirements/URS-production-readiness.md -->

# URS — Production Readiness

**Status:** Active — governor-ratified definition (2026-07-05; revised 2026-07-22).
**Authority:** Requirements
**Scope:** `core-runtime`. Defines the conditions under which `core-runtime` may be
described as production-ready. Platform concerns extracted to `core-platform` (authentication,
role enforcement, SaaS delivery) are assessed by a separate platform-readiness contract, not
here — see G12.
**Audience:** Governor, external evaluators, pilot customers.
**Relates:** `.specs/papers/CORE-Deployment-Readiness.md` (deployment mode prerequisites —
narrower; access-control scoped; a subset of G12 below).
`.specs/requirements/URS-mechanism-coherence.md` (G2 + G9 grounding).
`.specs/requirements/URS-consequence-chain.md` (G5, G10, G14 grounding).
`.specs/attestations/production-readiness.yaml` (the attestation manifest — current
per-gate verdict, evidence, and blockers; this URS defines the gates, the manifest records
their state).

---

## 1. Purpose

This document defines what "production-ready" means for CORE — not as a marketing label,
but as a set of measurable, falsifiable conditions. It exists because:

1. CORE's thesis is that claims must be verifiable. A production-readiness claim without a
   written definition is itself ungoverned.
2. External evaluators, pilot customers, and public followers deserve an honest, versioned
   status they can verify themselves — not a self-awarded badge.
3. The written definition creates pressure. That pressure is the point.

This URS is the authoritative source for the **definition** of production readiness. It does
not record the current verdict: the per-gate state, evidence, and blockers live in the
attestation manifest (`.specs/attestations/production-readiness.yaml`), and the status table
in `README.md` is generated from that manifest. Separating the stable definition (here) from
the volatile evidence (the manifest) is deliberate — it is why the earlier inline "Current
status" paragraphs went stale, and this revision removes them.

---

## 2. The threshold

CORE is production-ready when a third party can install it, run it against a real
repository, let governed autonomy execute for multiple days, and trust that every mutation
is:

- **authorised** — every file change passed through the governed proposal lifecycle (G5)
- **reproducible** — the same input produces the same governance decision (G2, G6)
- **auditable** — the full causal chain is queryable without reading source code (G10)
- **reversible** — a failed or unwanted execution can be diagnosed and rolled back (G14)
- **explainable** — every decision is attributed to a specific constitutional rule, and
  enforcement fails closed rather than passing silently (G3, G9)

Architectural impressiveness does not substitute for operational trust.
A system that impresses an expert reviewer but cannot be operated by a stranger
is not production-ready.

---

## 3. Production-readiness gates

Fifteen gates. All must hold simultaneously. Partial credit is informational only
and does not license a production-ready claim. Each gate below states a stable
**Requirement** and its **Acceptance criteria**; the current verdict for each lives in the
attestation manifest, not here.

---

### G1 — Fresh-install proof

**Requirement:** A person with no prior CORE knowledge can install CORE from public
documentation, run the consequence-chain demo successfully, and arrive at a `core-admin
code audit --offline` clean state — without operator assistance and without manual repair.

**Acceptance criteria:**
- `install-core.sh` completes on a clean machine (OS-level prerequisites only).
- `scripts/demo.sh` exercises the full loop: violation → audit → proposal → approval →
  execution → re-audit clean.
- A CI job reproduces the installation on each main-branch push or a documented periodic
  cadence. Manual cold-room verification alone does not satisfy this gate.

---

### G2 — Constitutional enforcement is deterministic and regression-tested

**Requirement:** Every blocking rule deterministically blocks the violation it targets and
does not fire on compliant input. Blocking behaviour is proven by a per-rule fixture pair,
not only by the rule's declaration. (Enforcement-integrity properties — silent-pass, unmapped
rules, vacuous green — are G9's concern, not G2's.)

**Acceptance criteria:**
- Every blocking rule has at least one known-violating fixture that proves the block fires.
- Every blocking rule has at least one known-compliant fixture that proves no false positive.
- A fixture regression (block stops firing, or a false positive appears) fails CI.

---

### G3 — Layer integrity is machine-enforced and blocking

**Requirement:** Mind / Body / Will / Shared / API boundaries are machine-checked. All
boundary violations that represent production risk — unauthorised execution, data access,
governance bypass — are blocking, not reporting.

**Acceptance criteria:**
- All layer-boundary rules that could allow production-risk violations are at blocking
  severity.
- The remaining reporting-only layer rules are documented with explicit rationale for why
  each is not blocking.

---

### G4 — Autonomous loop reliability demonstrated by soak

**Requirement:** Workers run against a non-trivial repository for ≥ 72 hours without
silent stalls, duplicate proposals, stuck drafts, zombie leases, or unclaimed failures.

**Acceptance criteria:**
- A soak run of ≥ 72 hours completes with workers and autonomous proposals enabled.
- All workers post blackboard entries within their declared `max_interval` throughout
  the run (no silent stalls).
- No runaway duplicate proposals: the same finding does not generate unbounded proposals.
- No unauthorized writes during the run.
- All failures during the run are classified; no proposal ends the run in an ambiguous
  state.

---

### G5 — Mutation-lane equivalence and lifecycle safety

**Requirement:** Every production mutation enters the governed proposal lifecycle — there
is no write lane that bypasses it — and within that lifecycle every proposal has a valid,
auditable transition chain with no bypass.

**Acceptance criteria:**
- **Lane equivalence:** every code-mutating path in production (autonomous remediation,
  operator-triggered ceremony, self-healing) routes through the same governed
  proposal/consequence lifecycle. No `write=True` path bypasses proposal creation, approval,
  and consequence recording. (ADR-154 mutation-lane equivalence; #818 is the open bypass.)
- Every state transition (`DRAFT → APPROVED → EXECUTING → COMPLETE / FAILED / ABANDONED`)
  is atomic and rowcount-guarded.
- `claim.proposal` is confirmed as the only claim-transition entry point (formal audit).
- A rejected or failed proposal is distinguishable from a completed proposal without
  reading source code.
- `approval_authority` is populated on every approved proposal (per URS-consequence-chain
  Q2.A and ADR-015).

---

### G6 — Risk model is governed, correct, and regression-tested

**Requirement:** Flow and action risk is governed by `action_risk.yaml`, deterministic,
and regression-tested for all current and future step kinds.

**Acceptance criteria:**
- All `StepKind` variants are explicitly handled in `_compute_flow_risk` — no implicit
  fallthrough to a default for any variant in the closed set.
- Every active flow computes the correct risk level, verified by test.
- Adding a new `StepKind` requires an explicit `_compute_flow_risk` branch and a
  regression test before the kind may appear in a production flow.

---

### G7 — Circuit breakers operate at the correct granularity

**Requirement:** Repeated failure is contained at declared granularity — per-symbol,
per-file — with no infinite retry paths.

**Acceptance criteria:**
- Per-symbol circuit breaker filters by `(source_file, symbol_name)` and is
  regression-tested.
- Per-file cap-N applies per source file and is regression-tested.
- No execution path can retry a failed proposal indefinitely without incrementing the
  failure count.

---

### G8 — Integration tests for the governed mutation chain

**Requirement:** The complete governed mutation chain is exercised by integration tests
that cross component boundaries — not only unit tests of isolated components. (Integration
infrastructure already exists: CI provisions PostgreSQL + Qdrant and the suite carries
`@pytest.mark.integration` tests. The gap this gate targets is the specific end-to-end
governed-mutation-chain test, not the absence of integration testing.)

**Acceptance criteria:**
- At minimum, `flow.build_test_for_symbol` is covered by an integration test that
  exercises: cognitive delegate → `generated_code` threading → write action →
  sandbox validation → blackboard evidence posted.
- At minimum one failure path is tested: cognitive delegate returns no output → flow
  fails closed with no file written.
- At minimum one negative path is tested: sandbox validation fails → file is not
  committed.

---

### G9 — Enforcement integrity fails closed

**Requirement:** The audit pipeline cannot report success while enforcement is silently
degraded. Any condition that would make a blocking rule's verdict unreliable produces a
non-passing result (`DEGRADED` / block), never a vacuous green.

**Acceptance criteria:**
- **No silent dispatch pass:** a rule whose `check_type` is unsupported or undispatched
  BLOCKs; it cannot be treated as satisfied (#820).
- **Unmapped non-advisory blocks PASS:** if any non-advisory rule lacks an enforcement
  mapping, the audit verdict cannot be `PASS` (#822).
- **Skipped blocking rules cannot attest:** a blocking rule that was skipped (e.g. filtered
  out of a stateless run) cannot support a production-readiness attestation; the skip is
  visible, not implied as covered.
- **No vacuous green on empty state:** an empty knowledge graph (or other empty backing
  state) cannot cause a check to pass by iterating nothing; empty backing state fails or
  degrades, it does not pass.
- **Crashes degrade, never comply:** an engine crash or unavailable dependency yields
  `DEGRADED`, never a compliant verdict.
- Each of the above is proven by a fixture that is executed in CI.

---

### G10 — Operator observability

**Requirement:** An operator can answer the following five questions without reading
source code:

1. What is the system currently doing?
2. What did it change, and when?
3. Why did it change that (which rule, which proposal, which authority)?
4. What failed, and why?
5. Can I safely re-run or roll back?

**Acceptance criteria:**
- All five questions are answerable via `core-admin` commands or the runtime dashboard.
- A non-author operator verifies this — documented as part of the G1 cold-room run
  or a separate operator trial.

---

### G11 — Upgrade and migration safety

**Requirement:** Schema changes between CORE versions are versioned, delta-applied,
idempotent, and recoverable without losing governance history. (Database schema only;
repository-source reversibility of a single mutation is G14.)

**Acceptance criteria:**
- A formal upgrade path exists from each released schema version to the next.
- Applying a delta migration on an existing database does not require `DROP SCHEMA CASCADE`.
- Governance history (`blackboard_entries`, `autonomous_proposals`,
  `proposal_consequences`) is preserved across upgrades.
- A failed migration can be rolled back to the prior schema state.

---

### G12 — Runtime trust boundary is audited and documented

**Requirement:** `core-runtime`'s own trust boundary is defined, audited, and documented.
Authentication and role enforcement are `core-platform` responsibilities (extracted per
SECURITY.md) and are assessed by the platform-readiness contract, not this gate — but the
runtime must state where external authentication is required when it is deployed remotely.

**Acceptance criteria:**
- Every API route carries an `exposure` tier (`user-facing` | `governor-only`) per
  ADR-110 D5.
- `user-facing` routes are confirmed safe for all authenticated (non-governor) callers, or
  restricted to governor-only (per-route gate completeness).
- `SECURITY.md` at the repo root covers: supported versions, vulnerability reporting, the
  runtime/platform trust boundary (the runtime API is unauthenticated by design; external
  authentication is required for remote deployment), and secrets-handling expectations.
- Rate limiting posture is documented: which routes are rate-limited at the runtime layer
  and which rely on the platform layer.

---

### G13 — Documentation for operators

**Requirement:** A skeptical engineer can install, understand, operate, diagnose, and
recover CORE from public documentation alone — without the original author present.

**Acceptance criteria:**
- An operator runbook covers: starting/stopping services, reading the dashboard,
  investigating a stuck proposal, diagnosing a failed worker, recovering from a failed
  execution.
- The governance model (rules → enforcement → findings → proposals → execution) is
  documented at a level accessible to a non-architect.
- The install and demo paths document prerequisites, expected output, and first
  troubleshooting steps.

---

### G14 — Source reversibility

**Requirement:** Any completed production mutation to the repository can be reversed —
the pre-mutation source state restored — without losing the governance evidence of what
happened. (Distinct from G5, which proves the lifecycle is correct, and from G11, which
covers database-schema migration.)

**Acceptance criteria:**
- After a completed mutation, CORE can restore the pre-mutation repository state (the
  bytes as they were before the proposal executed).
- Restoration preserves the original proposal and its consequence evidence (git SHAs,
  changed files, resolved findings) — reversal is auditable, not a silent discard.
- A failed or unwanted execution can be safely retried or abandoned without corrupting
  state or double-applying.
- Rollback is distinguishable from ordinary forward execution in the audit trail — a
  reversal is recorded as a reversal, not as a new mutation.

---

### G15 — Release integrity

**Requirement:** A published release is traceable to a green, immutable commit that passed
enforced checks. (This gate governs the publish boundary only; it does not require pull
requests for ordinary development — direct-to-main development remains permitted.)

**Acceptance criteria:**
- A release is cut only from a commit on which the full enforced check set (constitutional
  audit at blocking severity, tests, security scan) passed.
- The release commit is immutable and traceable: a semver tag pins the exact commit, and
  the published artifact's version matches the tagged commit (`publish-pypi.yml` verifies
  tag == `pyproject` version).
- The checks that gate a release are declared and enforced, not advisory — a red check
  blocks the publish.
- Release provenance (tag, commit SHA, check run) is recorded and queryable.

---

## 4. Production-readiness verdict

The gates are binary: each either holds or does not. **All fifteen must hold for the
production-ready claim to be valid.** A partial count is informational only and does not
license the claim. There is no composite score — a decimal maturity number is false
precision that contradicts the binary model and is not used.

The current verdict is recorded in the attestation manifest
(`.specs/attestations/production-readiness.yaml`) and surfaced in the generated README
table. Until every gate holds and each `met` gate carries dated, human-signed evidence, the
authoritative verdict is:

> **Production readiness: NOT ATTESTED**

Progress is communicated as a per-gate breakdown — `met` / `not met` / `unverified` — derived
from the manifest, never as a single score. A gate may be reported `met` only when the
manifest carries evidence and a human attestation for it; an AI-produced status is never an
attestation.

---

## 5. What this URS does not specify

- The current verdict, per-gate evidence, or blockers — those live in the attestation
  manifest (`.specs/attestations/production-readiness.yaml`), not here.
- The sequencing in which gates are closed. That is a planning decision recorded in
  `.specs/planning/CORE-Operational-Completeness.md`.
- The timeline for closing each gate. Gate closure is driven by governor commitment, not
  calendar.
- Gates specific to multi-user or enterprise deployment, or to `core-platform`
  (authentication, SaaS delivery). Those are extensions of, or separate from, the
  `core-runtime` production-ready baseline, not prerequisites within it.
- The internal implementation of each gate. Requirements are observable outcomes; the
  approach is an ADR-level decision.

---

## 6. References

- `.specs/attestations/production-readiness.yaml` — attestation manifest (current verdict + evidence)
- `.specs/papers/CORE-Deployment-Readiness.md` — deployment mode prerequisites (G12 subset)
- `.specs/requirements/URS-consequence-chain.md` — G5, G10, G14 consequence-chain requirements
- `.specs/requirements/URS-mechanism-coherence.md` — G2 fixture discipline + G9 enforcement-integrity grounding
- `.specs/planning/CORE-Operational-Completeness.md` — gate-closure sequencing tracker
- `SECURITY.md` — runtime/platform trust boundary (G12)
- ADR-110 — Exposure trust tiers (G12)
- ADR-132 — Governor authentication boundary (core-platform; G12 context)
- ADR-133 — Test gap evaluator (G7, G8)
- ADR-140 — Cognitive-write separation (G3, G8)
- ADR-148 — Proposal finalization barrier (G5, G14)
- ADR-154 — Mutation-lane equivalence (G5)
- #818 — open mutation-lane bypass (G5); #820 / #822 — enforcement-integrity defects (G9)
