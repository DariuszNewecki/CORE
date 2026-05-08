<!-- path: .specs/papers/CORE-ViolationRemediatorBody.md -->

# CORE — Violation Remediator (Body / CLI)

**Status:** Canonical
**Authority:** Policy
**Scope:** CLI-triggered per-rule LLM remediation

---

## 1. Purpose

This paper defines the `ViolationRemediator` (Body / CLI variant) — the acting
Worker invoked directly by the operator CLI for targeted, per-rule remediation
of a single violation namespace.

---

## 2. Relationship to the Daemon Path

Two remediation paths exist in CORE:

| Path | Entry point | Trigger | Discovery |
|---|---|---|---|
| **Daemon path** | `ViolationExecutorWorker` | Daemon cycle | Blackboard |
| **CLI path** | `ViolationRemediator` (this worker) | `core-admin workers remediate` | Operator-specified rule |

This paper covers the CLI path only. `ViolationRemediator` is not daemon-run.
It is instantiated directly by the `core-admin workers remediate` command.

---

## 3. Definition

`ViolationRemediator` is an acting Worker. Given a single declared `target_rule`,
it claims open violation findings for that rule, builds architectural context,
invokes `RemoteCoder` for a fix, validates via Crate/Canary ceremony, and
applies the result with a git commit. Supports dry-run mode for inspection
without writes.

---

## 4. Constitutional Identity

| Field | Value |
|---|---|
| Declaration | `.intent/workers/violation_remediator_body.yaml` |
| Class | `acting` |
| Phase | `execution` |
| Permitted tools | `llm.remote_coder`, `file.read`, `crate.create`, `canary.validate`, `crate.apply`, `git.commit` |
| Approval required | **true** |
| Trigger | CLI only — not daemon |

---

## 5. When to Use

`ViolationRemediator` (Body / CLI) is appropriate when:
- A specific rule namespace has accumulated violations that need targeted
  remediation in a single operator-supervised session.
- The governor wants to inspect the remediation plan in dry-run mode before
  any writes land.
- The daemon path (`ViolationExecutorWorker`) is not the right tool because
  the scope needs to be narrowed to one rule.

It is not appropriate for:
- Continuous autonomous operation (use the daemon path).
- Rules where the standard `auto_remediation.yaml` mapping applies (use
  `ViolationRemediatorWorker` + `ProposalConsumerWorker`).

---

## 6. Non-Goals

This paper does not define:
- the daemon remediation path (see `CORE-ViolationExecutor.md`)
- the mapping-based remediation path (see `CORE-RemediatorWorker.md` and
  `CORE-RemediationMap.md`)
- the Crate/Canary ceremony (see `CORE-Crate.md`, `CORE-Canary.md`)

---

## 7. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.
