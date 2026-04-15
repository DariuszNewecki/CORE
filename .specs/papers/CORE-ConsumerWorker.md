<!-- path: .intent/papers/CORE-ConsumerWorker.md -->

# CORE — ConsumerWorker

**Status:** Canonical
**Authority:** Policy
**Scope:** Proposal execution

---

## 1. Purpose

This paper defines the ConsumerWorker — the acting Worker that executes
approved Proposals via the ActionExecutor.

---

## 2. Definition

The ConsumerWorker polls for Proposals in `approved` status and executes
them. It does not create Proposals. It does not approve Proposals.
It only executes what has already been authorized.

---

## 3. Technical Flow

start → register → run → heartbeat → load approved proposals
→ for each: execute via ProposalExecutor → post report → end

**Step 1 — Load approved proposals**
Up to 5 approved Proposals per run (conservative limit — each Proposal
may touch multiple files).

**Step 2 — Execute via ProposalExecutor**
For each Proposal, `ProposalExecutor.execute(proposal, write=True)` runs:

1. Marks the Proposal `executing`.
2. For each ProposalAction in order:
   - Resolves the AtomicAction from the registry.
   - Calls `ActionExecutor.execute(action_id, write=True, **parameters)`.
   - Records the ActionResult.
3. If all actions succeed: marks Proposal `completed`.
4. If any action fails: marks Proposal `failed` with `failure_reason`.

**Step 3 — Post report**
A completion report is posted with: proposals executed, succeeded, failed.

---

## 4. Execution is Irreversible

The ConsumerWorker executes with `write=True`. Changes are applied to
the live codebase and committed to git.

There is no undo inside the ConsumerWorker. Rollback requires a git
revert. The rollback archive written by the ViolationExecutor provides
the pre-change state for manual recovery.

---

## 5. Non-Goals

This paper does not define:
- the ProposalExecutor implementation
- the ActionExecutor dispatch mechanism
- rollback procedures
