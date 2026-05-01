<!-- path: .specs/papers/CORE-Canary.md -->

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

## 4. Baseline Definition

The Canary compares the sandbox audit result against a baseline. The
baseline is defined as follows:

**The baseline is a snapshot of blocking violations present in the live
repository taken at the moment the Crate is submitted for validation —
immediately before Step 3 (sandbox creation).**

This means:
- Violations that existed before the Crate was created are in the baseline
  and do not count against it.
- Violations introduced by the Crate's changes that were not in the baseline
  cause the Canary to fail.
- Pre-existing violations that the Crate happens to fix reduce the violation
  count but do not affect the pass condition.

The baseline is computed once per Canary invocation and is not shared
between invocations. It reflects the live tree at the time of validation,
not at the time the Crate was authored.

---

## 5. Sandbox Mechanism

**Step 1 — Locate the Crate**
The Crate is read from `var/workflows/crates/inbox/{crate_id}/`.
The manifest is loaded and validated against the Crate schema.

**Step 2 — Snapshot the baseline**
The constitutional audit runs against the live repository.
The set of blocking violations is recorded as the baseline.

**Step 3 — Create sandbox**
A fresh sandbox is created at `work/canary/{crate_id}/`.
If a sandbox with the same ID already exists, it is deleted first.

**Step 4 — Snapshot the repository**
The live repository is copied into the sandbox, excluding:
`var/`, `.git/`, `__pycache__/`, `.venv/`, `work/`, `reports/`

**Step 5 — Apply Crate changes**
Each payload file in the Crate is written to its target path
within the sandbox.

**Step 6 — Run the audit**
The constitutional audit runs against the sandbox.
New blocking violations are identified by comparing against the baseline.

**Step 7 — Evaluate**
If the sandbox audit produces no blocking violations absent from the
baseline: Canary passes.
If the sandbox audit produces any blocking violations absent from the
baseline: Canary fails.

**Step 8 — Clean up**
The sandbox is deleted regardless of outcome.

---

## 6. Pass Condition

The Canary passes if the sandbox audit produces no new blocking
violations that were not present in the baseline captured at Step 2.

The Canary does not require zero violations. It requires that the
Crate does not make the constitutional health of the codebase worse.

---

## 7. Failure Response

When the Canary fails:
- `validate_crate_by_id` returns `(False, [findings])`
- The Crate is moved from `inbox/` to `var/workflows/crates/rejected/{crate_id}/`
- The rejection is recorded in the Crate manifest with the blocking violations listed
- The calling Worker marks the Finding `abandoned`
- The failure is posted to the Blackboard as a report entry

The Crate is not automatically retried. A failed Crate is a signal that
the fix is wrong, not that the process failed. The Finding re-enters the
remediation loop as a new open violation on the next sensor cycle.

---

## 8. Non-Goals

This paper does not define:
- the audit engine used inside the sandbox
- the specific rules evaluated
- long-term retention of rejected Crates
