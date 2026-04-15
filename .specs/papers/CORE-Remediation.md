<!-- path: .intent/papers/CORE-Remediation.md -->

# CORE — Remediation

**Status:** Canonical
**Authority:** Constitution
**Scope:** The autonomous healing loop

---

## 1. Purpose

This paper defines Remediation — the governed process of resolving a Finding
by applying a fix — and Convergence, the operational health metric it produces.

---

## 2. Definition

Remediation is the resolution of a Finding by applying a governed fix.

Remediation is not repair. Repair is ad hoc. Remediation is governed:
every step is declared, authorized, traced, and reversible.

---

## 3. The Remediation Loop

Audit → Finding → RemediationMap lookup → Proposal →
AtomicAction → Crate → Gates → Apply → Audit

**Audit** — the ViolationSensor runs the constitutional auditor and posts
Findings to the Blackboard.

**Finding** — a violation is recorded on the Blackboard. It names the rule,
the file, and the severity.

**RemediationMap lookup** — the RemediatorWorker looks up the Finding's
rule in the RemediationMap. If a mapping exists with sufficient confidence,
a Proposal is created routing to the declared AtomicAction.

**Proposal** — the RemediatorWorker creates a Proposal. Safe proposals are
auto-approved. Proposals requiring human review wait.

**AtomicAction** — the ConsumerWorker executes the approved Proposal.
The AtomicAction runs, produces an ActionResult, and creates a Crate.

**Gates** — ConservationGate, IntentGuard, and Canary validate the Crate.
Gates execute in this order: ConservationGate first, then IntentGuard,
then Canary. A failure at any gate halts the pipeline. Later gates do
not run if an earlier gate fails.

**Apply** — if all Gates pass, the Crate is applied to production.

**Audit** — the ViolationSensor runs again. If the Finding is gone,
the loop succeeded. If it persists, a new Finding is posted.

---

## 4. The Two Paths

CORE has two remediation paths. They are not peers and do not compete.
The RemediationMap is the partition key that determines which path handles
a given Finding.

**The Proposal Path** (constitutional) — Finding → RemediationMap →
Proposal → AtomicAction. No LLM in the remediation logic itself.
Deterministic. Traceable. The target state. Handles all rules for which
an AtomicAction has been declared in the RemediationMap.

**The ViolationExecutor Path** (legacy fallback) — Finding → LLM invocation →
Crate. Handles only rules with no active RemediationMap entry. Every rule
handled by this path is a rule that has not yet been given proper constitutional
remediation. The goal is to reduce this path to zero.

### 4a. Path priority and claim routing

RemediatorWorker has priority. On each run cycle:

1. RemediatorWorker claims all open Findings whose rule has an active
   RemediationMap entry. It creates Proposals for them and marks them
   `deferred_to_proposal`.

2. ViolationExecutor claims open Findings whose rule has NO active
   RemediationMap entry. Before invoking the LLM, it re-checks the
   RemediationMap. If an entry now exists (race condition), it releases
   the claim back to `open` so RemediatorWorker can reclaim it on the
   next cycle.

3. A Finding MUST NOT be processed by both paths. The RemediationMap
   is the sole authority on which path owns a given rule.

### 4b. Receiving deferred Findings

RemediatorWorker does not distinguish between a freshly-sensed Finding
and one released back to `open` by ViolationExecutor. Both have
`status = 'open'` and are claimed by the same prefix filter. No special
handling is required. The Blackboard status contract is sufficient.

---

## 5. Convergence

Convergence is the state where the rate of Finding resolution exceeds the
rate of Finding creation.

A converging system is healing. A diverging system is accumulating governance
debt. Debt that is not addressed eventually makes autonomous operation
impossible.

Convergence is not binary. It is a direction. CORE is always either converging
or diverging. The direction is the metric that matters, not the absolute count.

**Convergence is the operational goal of CORE's autonomous loop.**

---

## 6. RemediationMap

The RemediationMap is the routing table of the remediation loop. It lives
in `.intent/enforcement/remediation/auto_remediation.yaml` under policy
authority.

Every entry declares:
- the rule being remediated
- the AtomicAction that remediates it
- a confidence score
- a risk level
- a status (ACTIVE or PENDING)

Only ACTIVE entries with confidence >= 0.80 produce Proposals automatically.
PENDING entries are documented for roadmap visibility and do not dispatch.

---

## 7. Non-Goals

This paper does not define:
- the internal format of the RemediationMap
- AtomicAction implementation details
- ViolationExecutor's LLM invocation strategy
- the OptimizerWorker's codification logic — see `CORE-OptimizerWorker.md`
- rollback procedures
