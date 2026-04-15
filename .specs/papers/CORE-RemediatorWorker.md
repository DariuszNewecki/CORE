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
→ load remediation map → filter to mapped rules → group by action
→ deduplicate proposals → create proposals → mark findings deferred
→ post report → end

**Step 1 — Claim findings**
The Worker atomically claims open findings with subject prefix
`audit.violation::` whose rule has an active RemediationMap entry.
Up to 50 findings per run (claim limit).

Findings whose rule has no active RemediationMap entry are not claimed
and are left `open` for ViolationExecutor. RemediatorWorker never marks
unmapped findings `abandoned` — that would close them incorrectly.

**Step 2 — Load RemediationMap**
The RemediationMap is loaded from the path declared in
`governance_paths.yaml`. Only ACTIVE entries with confidence >= 0.80
are considered.

**Step 3 — Filter to mapped rules**
Any finding claimed whose rule does not appear in the loaded
RemediationMap (e.g. the map changed between the claim query and the
load) is released back to `open` via `release_claimed_entries`. This
is a safety check, not the normal path.

**Step 4 — Group by action**
Findings are grouped by the action declared in the RemediationMap for
their rule.

**Step 5 — Deduplicate proposals**
For each action group, the Worker checks whether an active Proposal
already exists for that action. Active proposal statuses are `draft`,
`pending`, `approved`, and `executing` — as declared in
`.intent/META/enums.json` under `proposal_status_active`.
If one exists: the group is skipped. The findings remain claimed.

**Step 6 — Create Proposals**
For each non-duplicate action group, one Proposal is created:

```
goal:    "Autonomous remediation: {action_id} ({n} violation(s) —
          rules: {rule_ids})"
actions: [{action_id: {action}, parameters: {write: true,
           file_path: {affected_files[0]}}, order: 0}]
scope:   {files: [affected_files]}
```

Safe proposals (`approval_required=false`) are created in `approved`
status. Moderate/high risk proposals are created in `draft` status.

**Step 7 — Mark findings deferred**
After a Proposal is persisted, each consumed Finding is marked
`deferred_to_proposal`. The Finding's payload `proposal_id` field MUST
be set to the created Proposal's ID. This is required for revival on
proposal failure — see `CORE-Finding.md` section 7a.

**Step 8 — Post report**
A completion report is posted summarizing: proposals created, findings
deferred, findings released (race condition recoveries).

---

## 4. Receiving Deferred Findings

RemediatorWorker does not distinguish between a freshly-sensed Finding
and one released back to `open` by ViolationExecutor after a race
condition. Both have `status = 'open'` and are claimed by the same
prefix filter. The Blackboard status contract is sufficient — no
special handling is required.

---

## 5. Non-Goals

This paper does not define:
- what happens after a Proposal is created
- the Proposal execution mechanism
- how rules without mappings are handled long-term
