---
kind: paper
id: CORE-SelfHealingAgent
title: CORE — Self-Healing Agent
status: canonical
doctrine_tier: informational
---

<!-- path: .specs/papers/CORE-SelfHealingAgent.md -->

# CORE — Self-Healing Agent

**Status:** Canonical
**Authority:** Policy
**Scope:** Bespoke linkage violation detection (superseded)

---

## 1. Purpose

This paper defines the `SelfHealingAgent` — the sensing Worker that detected
source symbols missing `# ID:` tags via a bespoke AST scan.

---

## 2. Status: Superseded

`SelfHealingAgent` is paused and superseded by `audit_sensor_linkage`
(`AuditViolationSensor` scoped to the `linkage.*` namespace).

The original design had this worker scan `src/**/*.py` directly for public
symbols missing `# ID:` tags and post one Blackboard finding per affected file.
The approach worked but duplicated detection logic that the constitutional audit
engine already handles.

`audit_sensor_linkage` covers the same `linkage.assign_ids` rule through the
standard audit loop. Running both workers produces duplicate Blackboard findings
for the same violations, which causes churn and inflates the finding count without
adding information. The general-purpose sensor is the correct path; the
bespoke scanner is retired.

`SelfHealingAgent` is retained in the worker registry as a paused declaration.
It is not activated in the daemon.

---

## 3. Constitutional Identity (Historical)

| Field | Value |
|---|---|
| Declaration | `.intent/workers/self_healing_agent.yaml` |
| Class | `sensing` |
| Phase | `audit` |
| Permitted tools | none |
| Approval required | false |
| Rule | `linkage.assign_ids` |

---

## 4. Why It Was Superseded

The `AuditViolationSensor` pattern (one class, one namespace, many declarations)
is the constitutional mechanism for violation detection. Bespoke scanning
workers that duplicate a rule the sensor already covers:

- Produce duplicate findings that require deduplication logic downstream.
- Diverge from the audit engine's rule evaluation over time.
- Add a second code path to maintain for the same invariant.

The correct design is a rule in `.intent/rules/` plus a sensor declaration
scoped to its namespace. `SelfHealingAgent` predates this pattern; its
successor `audit_sensor_linkage` implements it correctly.

---

## 5. Non-Goals

This paper does not define:
- the `linkage.assign_ids` rule (see `.intent/rules/code/linkage.json`)
- how the `ViolationRemediatorWorker` routes `linkage.assign_ids` findings
  to the `assign_missing_ids` action

---

## 6. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.
