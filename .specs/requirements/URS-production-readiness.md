<!-- path: .specs/requirements/URS-production-readiness.md -->

# URS — Production Readiness

**Status:** Active — governor-ratified definition (2026-07-05)
**Authority:** Requirements
**Scope:** All CORE deployments; defines the conditions under which CORE may be described as production-ready.
**Audience:** Governor, external evaluators, pilot customers.
**Relates:** `.specs/papers/CORE-Deployment-Readiness.md` (deployment mode prerequisites — narrower; access-control scoped; a subset of G12 below). `.specs/requirements/URS-mechanism-coherence.md` (G9 grounding). `.specs/requirements/URS-consequence-chain.md` (G5, G10 grounding).

---

## 1. Purpose

This document defines what "production-ready" means for CORE — not as a marketing label,
but as a set of measurable, falsifiable conditions. It exists because:

1. CORE's thesis is that claims must be verifiable. A production-readiness claim without a
   written definition is itself ungoverned.
2. External evaluators, pilot customers, and public followers deserve an honest, versioned
   status they can verify themselves — not a self-awarded badge.
3. The written definition creates pressure. That pressure is the point.

This URS is the authoritative source for any production-readiness claim. The status table
in `README.md` is a derived artifact summarising the current state against this definition.
When the two conflict, this document wins.

---

## 2. The threshold

CORE is production-ready when a third party can install it, run it against a real
repository, let governed autonomy execute for multiple days, and trust that every mutation
is:

- **authorised** — every file change passed through the governed proposal lifecycle
- **reproducible** — the same input produces the same governance decision
- **auditable** — the full causal chain is queryable without reading source code
- **reversible** — a failed or unwanted execution can be diagnosed and rolled back
- **explainable** — every decision is attributed to a specific constitutional rule

Architectural impressiveness does not substitute for operational trust.
A system that impresses an expert reviewer but cannot be operated by a stranger
is not production-ready.

---

## 3. Production-readiness gates

Thirteen gates. All must hold simultaneously. Partial credit is informational only
and does not license a production-ready claim.

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

**Current status:** ⚠️ Partial. Scripts exist and are manually verified (Proxmox
cold-room, 4 clean runs, 2026-06-14). CI-automated fresh-install is absent (#562).

---

### G2 — Constitutional enforcement is deterministic and regression-tested

**Requirement:** Every blocking rule deterministically blocks the violation it targets.
Blocking behaviour is proven by a test, not only by the rule's declaration.

**Acceptance criteria:**
- All 35 blocking rules have at least one known-violating fixture that proves the block
  fires.
- All 35 blocking rules have at least one known-compliant fixture that proves no false
  positive.
- The `Unmapped: N` count in audit output is 0 for blocking-tier rules.

**Current status:** ⚠️ Partial. Enforcement structure is strong (35 blocking rules,
machine-checked, CI-gated). Fixture discipline (per-rule known-violating + known-compliant
tests) is not universally applied. 7 passive_gate rules remain unmapped.

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

**Current status:** ⚠️ Partial. ADR-140 closed the cognitive/write separation gap.
Several layer rules remain at reporting severity (`architecture.layers.no_body_to_will`,
`architecture.will.no_direct_database_access`). The reporting-only set is not formally
documented with rationale.

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

**Current status:** ❌ Not demonstrated. Two loop bugs fixed 2026-07-05 (cognitive-step
risk classification silently blocked auto-approval since ADR-140; per-symbol circuit
breaker was per-file). No soak test has been run against either the old or the fixed code.

---

### G5 — Proposal lifecycle safety

**Requirement:** Every proposal has a valid, auditable transition chain with no bypass.

**Acceptance criteria:**
- Every state transition (`DRAFT → APPROVED → EXECUTING → COMPLETE / FAILED / ABANDONED`)
  is atomic and rowcount-guarded.
- `claim.proposal` is confirmed as the only claim-transition entry point (formal audit).
- A rejected or failed proposal is distinguishable from a completed proposal without
  reading source code.
- `approval_authority` is populated on every approved proposal (per URS-consequence-chain
  Q2.A and ADR-015).

**Current status:** ⚠️ Partial. State transition guards exist and are rowcount-checked.
`claim.proposal` path has not been formally audited this cycle. `approval_authority`
population status requires verification against live data.

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

**Current status:** ⚠️ Mostly met. Cognitive-step fallthrough bug fixed 2026-07-05
(commit `4c104dea`), regression-tested. The `else: impact = "moderate"` fallthrough
branch still exists as a safety net for genuinely unknown future kinds; the acceptance
criterion requires that the known set be exhaustively handled, which it now is.

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

**Current status:** ⚠️ Mostly met. Per-symbol fix shipped 2026-07-05 (commit `4c104dea`),
regression-tested (`test_test_remediator_symbol_query.py`). Per-file cap exists and is
tested. Flow-level and worker-level circuit breakers have not been formally audited.

---

### G8 — Integration tests for the governed mutation chain

**Requirement:** The complete governed mutation chain is exercised by integration tests
that cross component boundaries — not only unit tests of isolated components.

**Acceptance criteria:**
- At minimum, `flow.build_test_for_symbol` is covered by an integration test that
  exercises: cognitive delegate → `generated_code` threading → write action →
  sandbox validation → blackboard evidence posted.
- At minimum one failure path is tested: cognitive delegate returns no output → flow
  fails closed with no file written.
- At minimum one negative path is tested: sandbox validation fails → file is not
  committed.

**Current status:** ❌ Not started. All existing tests are unit tests. ADR-140's
cognitive-write chain has a static boundary test (`test_build_tests_flow_risk_is_safe`)
but no integration test of the runtime composition.

---

### G9 — Negative-path tests (the blockers actually block)

**Requirement:** Each blocking constitutional rule is proven to block on a known-violating
input — not merely declared to block.

**Acceptance criteria:**
- For each of the 35 blocking rules, a known-violating fixture exists and is executed
  in CI (per mechanism-coherence discipline, URS-mechanism-coherence R-005).
- A fixture failure causes CI to fail.
- The fixture set is enumerated in a coverage manifest; gaps are visible, not implied
  as covered.

**Current status:** ❌ Not started systematically. Individual tests exist for some rules
(e.g., `test_role_enforcement.py` for ADR-132 auth boundary). No systematic fixture per
blocking rule; no coverage manifest.

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

**Current status:** ⚠️ Partial. `core-admin runtime dashboard`, `core-admin proposals show`,
and the consequence-chain query exist. Questions 4 and 5 (failure diagnosis and rollback
guidance) are not confirmed answerable by a non-author without source access.

---

### G11 — Upgrade and migration safety

**Requirement:** Schema changes between CORE versions are versioned, delta-applied,
idempotent, and recoverable without losing governance history.

**Acceptance criteria:**
- A formal upgrade path exists from each released schema version to the next.
- Applying a delta migration on an existing database does not require `DROP SCHEMA CASCADE`.
- Governance history (`blackboard_entries`, `autonomous_proposals`,
  `proposal_consequences`) is preserved across upgrades.
- A failed migration can be rolled back to the prior schema state.

**Current status:** ❌ Not started. Schema-as-truth model (`db_schema_live.sql` as a
full dump) is a fresh-install model only. `core._migrations` records only `(id, applied_at)`
— no migration names, no version sequence, no delta path. This is the most critical
structural gap: a governance system that loses its audit trail on upgrade cannot claim
production-readiness.

---

### G12 — Security posture is audited and documented

**Requirement:** Authentication, authorisation, and rate limiting are applied consistently
across all API routes, with the security boundary documented.

**Acceptance criteria:**
- Every API route carries an `exposure` tier (`user-facing` | `governor-only`) per
  ADR-110 D5 (#671 closed).
- Rate limiting is wired to all routes, not only auth routes.
- `SECURITY.md` at the repo root covers: supported versions, vulnerability reporting,
  known security boundaries, and secrets-handling expectations.
- `knowledge_routes` and other user-facing routes are confirmed safe for all
  authenticated (non-governor) callers, or restricted to governor-only.

**Current status:** ⚠️ Partial. ADR-132 governor authentication exists and is tested.
Rate limiting (`rate_limiter.py`, Redis-backed) is wired only to auth routes. `SECURITY.md`
is absent. #671 (exposure tier metadata) is open.

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

**Current status:** ⚠️ Partial. `install-core.sh` and `scripts/demo.sh` are
self-documenting and demonstrate the install and demo paths. CLAUDE.md is comprehensive
for Claude Code but is not an operator document. No operator runbook exists.

---

## 4. Scoring model

The gates are binary: each either holds or does not. All thirteen must hold for the
production-ready claim to be valid. A partial count is informational only.

For communication, the external review calibration used on 2026-07-05:

| Band    | Label                               | Typical gate state                            |
|---------|-------------------------------------|-----------------------------------------------|
| 7.0–7.9 | Architecturally promising           | G2, G6 partial; most gates not started        |
| 8.0–8.6 | Advanced prototype / internal alpha | G2, G3, G5, G6, G7 mostly met; G4/G8/G9/G11 open |
| 8.7–9.1 | Pilot-ready                         | Above + G1, G10, G12, G13 substantially met   |
| **9.2–9.5** | **Production-ready**            | **All 13 gates hold**                         |
| 9.6+    | Enterprise-grade                    | All 13 + multi-user hardening, compliance pkg |

**Assessed position as of 2026-07-05: 8.5 — advanced internal alpha, approaching
pilot-ready.** Primary open gates: G4 (soak), G8 (integration tests), G9
(negative-path tests), G11 (migration safety).

---

## 5. What this URS does not specify

- The sequencing in which gates are closed. That is a planning decision recorded in
  `.specs/planning/CORE-Operational-Completeness.md`.
- The timeline for closing each gate. Gate closure is driven by governor commitment, not
  calendar.
- Gates specific to multi-user or enterprise deployment. Those are extensions of the
  production-ready baseline, not prerequisites to it.
- The internal implementation of each gate. Requirements are observable outcomes; the
  approach is an ADR-level decision.

---

## 6. References

- `.specs/papers/CORE-Deployment-Readiness.md` — deployment mode prerequisites (G12 subset)
- `.specs/requirements/URS-consequence-chain.md` — G5 and G10 consequence-chain requirements
- `.specs/requirements/URS-mechanism-coherence.md` — G9 fixture discipline grounding
- `.specs/planning/CORE-Operational-Completeness.md` — gate-closure sequencing tracker
- `.specs/planning/CORE-Maturity-Audit-Actions.md` — prior maturity audit inputs
- ADR-110 — Exposure trust tiers (G12)
- ADR-132 — Governor authentication boundary (G12)
- ADR-133 — Test gap evaluator (G7, G8)
- ADR-140 — Cognitive-write separation (G3, G8)
- External review, 2026-07-05 — architecture + ADR-140 focus; scored 8.5 / 10
