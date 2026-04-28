<!-- path: .intent/papers/CORE-OptimizerWorker.md -->

# CORE — OptimizerWorker

**Status:** Not Yet Designed
**Authority:** Policy
**Scope:** Rule graduation from ViolationExecutor to Proposal Path

---

## 1. Purpose

This paper reserves the constitutional standing of the OptimizerWorker
and declares its intended role. It contains no implementation detail
because the OptimizerWorker has not been designed.

---

## 2. What It Will Do

The OptimizerWorker is an acting Worker. It observes repeated successful
patterns produced by ViolationExecutor and proposes the codification of
those patterns into AtomicActions.

It is the bridge between the ViolationExecutor Path (discovery) and the
Proposal Path (constitutional). Without it, a successful LLM-reasoned fix
remains a one-off event. With it, that fix becomes a declared, deterministic
AtomicAction available to RemediatorWorker for all future occurrences of
the same rule violation.

---

## 3. Why It Does Not Exist Yet

ViolationExecutor is implemented and active. The OptimizerWorker depends
on ViolationExecutor producing candidate patterns *at scale* — enough
accumulated discovery data that pattern recognition has substrate to
work on. Designing the OptimizerWorker before that data exists would
be premature.

The graduation path is therefore currently manual:

1. ViolationExecutor surfaces a candidate fix.
2. The human architect observes the pattern.
3. The human authors an AtomicAction and adds it to the RemediationMap.

The OptimizerWorker automates step 2. Until it exists, the human
performs that step directly.

---

## 4. Constitutional Constraints (Pre-Design)

When designed, the OptimizerWorker MUST:

- Operate as an acting Worker declared in `.intent/workers/`
- Read ViolationExecutor candidate postings from the Blackboard only
- Propose AtomicActions for human review — never register them autonomously
- Never write to `.intent/` — suggestions are advisory, the human authors
  the final AtomicAction and RemediationMap entry

---

## 5. Non-Goals

This paper does not define:
- the algorithm for pattern recognition
- confidence thresholds for proposal
- the candidate posting format from ViolationExecutor
- implementation location

Those are design decisions for when this component is ready to be built.

The rollback archive written by ViolationExecutor to `var/mind/rollbacks/`
has no constitutional contract in this paper. Its format, retention, and
recovery procedure belong to ViolationExecutor's governance, not to
OptimizerWorker's. The OptimizerWorker's contract for reading rollback
data, if any, is deferred to the OptimizerWorker design milestone.
