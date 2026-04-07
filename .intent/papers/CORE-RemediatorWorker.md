<!-- path: .intent/papers/CORE-RemediatorWorker.md -->

# CORE — RemediatorWorker

**Status:** Canonical
**Authority:** Policy
**Scope:** Autonomous remediation routing

---

## 1. Purpose

This paper defines the RemediatorWorker — the acting Worker that claims
Findings and creates Proposals via the RemediationMap.

---

## 2. Definition

The RemediatorWorker is an acting Worker. It consumes open audit violation
Findings from the Blackboard, looks up each Finding's rule in the
RemediationMap, groups Findings by action, and creates one Proposal per
unique action group.

It calls no LLM. It writes no files. It creates Proposals only.

---

## 3. Technical Flow

start → register → run → heartbeat → claim findings
→ load remediation map → group by action → deduplicate proposals
→ create proposals → mark findings resolved → post report → end

**Step 1 — Claim findings**
The Worker atomically claims open findings with subject prefix
`audit.violation::`. Up to 50 findings per run (claim limit).

**Step 2 — Load RemediationMap**
The RemediationMap is loaded from the path declared in
`governance_paths.yaml`. Only ACTIVE entries with confidence >= 0.80
are considered.

**Step 3 — Group by action**
Findings are grouped by the action declared in the RemediationMap for
their rule. Findings whose rule has no active mapping are marked
`abandoned` — the RemediatorWorker cannot handle them.

**Step 4 — Deduplicate proposals**
For each action group, the Worker checks whether an active Proposal
already exists for that action (status: draft, approved, or executing).
If one exists: the group is skipped. The findings remain claimed.

**Step 5 — Create Proposals**
For each non-duplicate action group, one Proposal is created:

goal:    "Autonomous remediation: {action_id} ({n} violation(s) —
rules: {rule_ids})"
actions: [{action_id: {action}, parameters: {write: true,
file_path: {affected_files[0]}}, order: 0}]
scope:   {files: [affected_files]}

Safe proposals (`approval_required=false`) are created in `approved`
status. Moderate/high risk proposals are created in `draft` status.

**Step 6 — Mark findings**
After a Proposal is persisted, the consumed Findings are marked
`deferred_to_proposal`.

**Step 7 — Post report**
A completion report is posted summarizing: proposals created, findings
deferred, findings abandoned.

---

## 4. Non-Goals

This paper does not define:
- what happens after a Proposal is created
- the Proposal execution mechanism
- how rules without mappings are handled long-term
