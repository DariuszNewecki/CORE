<!-- path: .intent/papers/CORE-Canary.md -->

# CORE — The Canary

**Status:** Canonical
**Authority:** Constitution
**Scope:** All Crate validation before application

---

## 1. Purpose

This paper defines the Canary — the execution Gate that validates a
Crate in a sandbox before it is applied to production.

---

## 2. Definition

The Canary creates a complete replica of the repository in a sandbox
directory, applies the Crate's changes to the replica, and runs the
constitutional audit against the modified replica.

A Crate that produces new violations in the sandbox does not reach
production. The sandbox is discarded. The Crate is rejected.

---

## 3. Invocation

The Canary is invoked via `CrateProcessingService.validate_crate_by_id(crate_id)`.

It returns `(passed: bool, findings: list[AuditFinding])`.

A Proposal's execution ceremony calls the Canary after packing the Crate
and before applying it.

---

## 4. Sandbox Mechanism

**Step 1 — Locate the Crate**
The Crate is read from `var/workflows/crates/inbox/{crate_id}/`.
The manifest is loaded and validated against the Crate schema.

**Step 2 — Create sandbox**
A fresh sandbox is created at `work/canary/{crate_id}/`.
If a sandbox with the same ID already exists, it is deleted first.

**Step 3 — Snapshot the repository**
The live repository is copied into the sandbox, excluding:
`var/`, `.git/`, `__pycache__/`, `.venv/`, `work/`, `reports/`

**Step 4 — Apply Crate changes**
Each payload file in the Crate is written to its target path
within the sandbox.

**Step 5 — Run the audit**
The constitutional audit runs against the sandbox.
New violations introduced by the Crate's changes are recorded.

**Step 6 — Evaluate**
If the audit produces no new blocking violations: Canary passes.
If the audit produces new blocking violations: Canary fails.

**Step 7 — Clean up**
The sandbox is deleted regardless of outcome.

---

## 5. Pass Condition

The Canary passes if the sandbox audit produces no new blocking
violations that were not present before the Crate was applied.

The Canary does not require zero violations. It requires that the
Crate does not make the constitutional health of the codebase worse.

---

## 6. Failure Response

When the Canary fails:
- `validate_crate_by_id` returns `(False, [findings])`
- The Crate remains in `inbox/` — it is not applied
- The calling Worker marks the Finding `abandoned`
- The failure is posted to the Blackboard

The Crate is not automatically retried. A failed Crate is a Finding
that re-enters the remediation loop as a new violation.

---

## 7. Non-Goals

This paper does not define:
- the audit engine used inside the sandbox
- the specific rules evaluated
- retention of failed sandboxes
