<!-- path: .specs/decisions/ADR-010-finding-proposal-contract.md -->
# ADR-010: Wire the §7+§7a Finding/Proposal contract

**Status:** Accepted
**Date:** 2026-04-24
**Authors:** Darek (Dariusz Newecki)

## Context

`.specs/papers/CORE-Finding.md` §7 defines `deferred_to_proposal` as the terminal finding status for the case where a Proposal has been created to address a Finding. §7a defines the revival obligation: when that Proposal fails, the Findings it consumed must be restored to `open` so the remediation loop can retry. The paper names this contract explicitly.

The code does not implement it. Three separate gaps, stacked:

**Gap 1 — Wrong terminal status.** `ViolationRemediatorWorker._resolve_entries` (at line 110130 in the live tree) marks findings `resolved` immediately after proposal creation. §7 names this exact transition as `deferred_to_proposal`. The enum value is declared in `.intent/META/enums.json` under `blackboard_entry_status` (line 113197 of the flattened context export); only the code-side usage is absent.

**Gap 2 — No forward link from finding to proposal.** §7 states: *"The `proposal_id` field in the payload MUST be set to the created Proposal's ID"* at the moment of transition. The worker's `_create_proposal` → `_resolve_entries` sequence has `proposal_id` available locally at line 110130 but never writes it into the finding's JSONB payload. No mechanism currently stores this linkage in either direction — proposals do not carry finding IDs, findings do not carry proposal IDs.

**Gap 3 — No revival on failure.** `ProposalStateManager.mark_failed` (at line 84659) updates the `autonomous_proposals` row and nothing else. The §7a obligation to query findings by `payload->>'proposal_id'` and reset them to `open` is not implemented. `grep` across `src/` for `revive` / `revival` / `reopen.*finding` returns zero hits in production code; all occurrences are in `.specs/papers/`.

These gaps are dependent. Revival logic (Gap 3) cannot function without the forward link (Gap 2). The forward link has no place to land without the correct terminal-status transition (Gap 1). A fix that addresses any one in isolation is inert.

### Empirical grounding

Pre-check against the live database on 2026-04-24 showed 285 `resolved` findings on a single subject — `audit.violation::purity.no_todo_placeholders::src/will/workers/violation_remediator.py` — spanning 2026-04-21 16:57 to 2026-04-23 16:54 UTC. At ~one finding per 10 minutes for 48 hours, this is the churn pattern the 2026-04-22 handoff named. The 2026-04-22 handoff attributed it to missing revival (Gap 3 alone), but that explanation accounts for at most 9 rows (the documented failure window). The remaining 276 are successful proposals whose action returned `ok=true` yet did not remove the violation the sensor was detecting. Under the §7 contract those findings would transition to `deferred_to_proposal` and remain there — dedup (`status NOT IN ('resolved')`) keeps the subject in the active set, sensor skips re-posting, churn stops.

The current code's behaviour on this file is therefore wrong on both success paths (churn via premature `resolved` + re-detection) and failure paths (governance debt via no revival). The §7 transition is load-bearing for both.

### Sensor dedup behaviour under the fixed contract

The dedup query (`BlackboardService.fetch_active_finding_subjects_by_prefix`, line 17956) excludes only `resolved`. Every other status — including `deferred_to_proposal` and the revived-to-`open` state — keeps the subject in the active set, causing the sensor to skip re-posting. This is already correct for the revival model. No sensor change is required.

## Decision

Close all three gaps in one coordinated change. Three files, one `.intent/` amendment (the enum is already declared; no amendment needed).

### Layer 1 — Data access: `src/body/services/blackboard_service.py`

Add a new method `defer_entries_to_proposal(entry_ids: list[str], proposal_id: str) -> int`. Single transaction:

```sql
UPDATE core.blackboard_entries
SET status = 'deferred_to_proposal',
    resolved_at = now(),
    updated_at = now(),
    payload = payload || jsonb_build_object('proposal_id', cast(:proposal_id as text))
WHERE id = cast(:entry_id as uuid)
  AND status IN ('open', 'claimed')
```

Returns count of rows updated. Sets `resolved_at` because `deferred_to_proposal` is a terminal status per the enum declaration's description (`"resolved, abandoned, deferred_to_proposal, dry_run_complete, and indeterminate are terminal"`). Matches the `resolved_at` hygiene tightening from the 2026-04-22 Option A+ work.

Also add `revive_findings_for_failed_proposal(proposal_id: str) -> list[str]`. Queries findings by `payload->>'proposal_id' = :proposal_id AND status = 'deferred_to_proposal'`, resets them in one transaction:

```sql
UPDATE core.blackboard_entries
SET status = 'open',
    claimed_by = NULL,
    claimed_at = NULL,
    resolved_at = NULL,
    updated_at = now()
WHERE entry_type = 'finding'
  AND status = 'deferred_to_proposal'
  AND payload->>'proposal_id' = :proposal_id
RETURNING id
```

Returns the list of revived finding IDs. Caller (state manager) uses the count and list for the revival report.

### Layer 2 — Transition point: `src/will/workers/violation_remediator.py`

In `ViolationRemediatorWorker.run()` at line 110128-110131, replace:

```python
if proposal_id:
    proposals_created.append(action_id)
    resolved = await self._resolve_entries(entry_ids)
    entries_resolved += resolved
```

with a call to a new `_defer_to_proposal(entry_ids, proposal_id)` helper that delegates to the new BlackboardService method. The counter rename (`entries_resolved` → `entries_deferred`) and the corresponding report field (`entries_resolved` → `entries_deferred`) move together. Report shape for `violation_remediator.completed` gains `entries_deferred`; retains `entries_resolved_dedup` unchanged because dedup subsumption remains a `resolved` transition (the finding was not deferred to this proposal; it was subsumed into an existing one, and the paper does not specify otherwise).

The dedup branch at line 110115 stays as `_resolve_entries`. Semantics: dedup-subsumed findings are terminally closed because an active proposal already exists; they are not linked to that proposal's lifecycle from their own row, and attempting to link them retroactively introduces a second class of finding→proposal relationship the paper does not define. The first-wave findings that produced the active proposal are the ones carrying the link; subsumed duplicates are historical noise and close as `resolved`.

### Layer 3 — Revival: `src/will/autonomy/proposal_state_manager.py`

Extend `ProposalStateManager.mark_failed` to call `BlackboardService.revive_findings_for_failed_proposal(proposal_id)` after the `UPDATE core.autonomous_proposals` statement commits. Post a blackboard `report` entry with subject `proposal.failure.revival` and payload `{proposal_id, reason, revived_finding_ids, revived_count}`.

Revival runs after the proposal-state commit, not within the same transaction. Rationale: the proposal-state UPDATE is ORM-scoped to the injected session; the revival UPDATE is service-scoped and manages its own session. Merging into one transaction would require threading the session through BlackboardService for this one call, breaking the service's current interface contract (services own their sessions). Separate transactions are acceptable because revival is idempotent — a retry will find the findings already `open` and no-op. The revival report is the audit trail if reconciliation is ever needed.

Called-from-every-path coverage:
- `src/will/autonomy/proposal_executor.py` line 83698 (single-proposal actions-failed branch) — ✓
- `src/will/autonomy/proposal_executor.py` line 83964 (batch-proposal actions-failed branch) — ✓
- `src/will/autonomy/proposal_repository.py` line 84461 (exception handler in `execute_workflow`) — ✓

All three routes commit to `ProposalStateManager.mark_failed`. Placement in the state manager gives revival on every route without duplication.

## Alternatives Considered

**Revival-only (the 2026-04-22 framing).** Implement §7a in `mark_failed` without touching the transition status or adding `proposal_id` to the payload. Rejected: there is nothing to query. A `payload->>'proposal_id' = :proposal_id` filter against findings that never carry `proposal_id` returns empty forever. The revival logic would compile and run and do nothing. Also would not close the observed 276-row success-path churn.

**Worker-side revival in `ProposalConsumerWorker.run()`.** The §7a paper text names this worker explicitly. Rejected: `mark_failed` has three call sites (single-proposal executor, batch-proposal executor, `execute_workflow` exception handler), only one of which flows through `ProposalConsumerWorker`. Putting revival in the worker requires duplicating it at the other two sites or accepting that those failure paths leak governance debt. State-manager placement covers all three from one location. The paper's assignment of the obligation to "ProposalConsumerWorker" reads as specification of *what must happen when a proposal fails*, not a binding architectural location; the state manager is the layer where "proposal has failed" is actually observed. A follow-up to the paper to match the code is cleaner than fragmenting the revival logic across three call sites.

**Store finding IDs on the proposal (proposal → findings) instead of `proposal_id` on the finding.** Rejected for three reasons. First, the paper explicitly specifies the direction (finding payload carries `proposal_id`). Second, the query pattern required by §7a — "findings whose `proposal_id` matches a failed proposal" — is cleanly expressed against a JSONB index on `payload->>'proposal_id'`; the reverse requires unwinding an array on every revival. Third, findings can be revived; if a revived finding later gets consumed by a new proposal, the payload's `proposal_id` cleanly updates to the new one, whereas an array on the proposal side would need to track which findings it "still owns."

**Mark `deferred_to_proposal` without clearing `resolved_at` on revival.** Rejected: `resolved_at` semantics from the 2026-04-22 Option A+ work (terminal-state hygiene) require the column to mirror the current status — set on terminal transitions, null on active statuses. Leaving `resolved_at` populated on a revived-to-`open` row is the same class of inconsistency Option A+ was specifically tightened to prevent.

**Coupling revival into the same transaction as the proposal-state UPDATE.** Rejected as covered in Layer 3 above. Breaks the service-owns-session contract. Idempotent revival + audit-log report is sufficient.

## Consequences

**Positive:**

- The paper↔code gap the handoff named for Option B is closed for both the failure path (Gap 3) and the success-but-ineffective path (Gaps 1 and 2), matching the empirical evidence from the pre-check rather than a narrower theoretical subset.
- The churn pattern documented on 2026-04-22 (285 resolved findings for one subject) is structurally prevented: subsequent rounds find the subject in the dedup's active set via `deferred_to_proposal`, and stop re-posting.
- The finding's payload gains a cryptographic-strength forward link (`proposal_id` UUID) — the first time CORE's blackboard has had a direct finding→proposal trace. This closes part of the two-log problem for the subset of proposals that originate from findings.
- Revival is placed at the single convergence point (`ProposalStateManager.mark_failed`) that every proposal-failure route already flows through. No duplication.
- The `violation_remediator.completed` report gains `entries_deferred`, making the finding→proposal handoff visible in blackboard audit without a schema change.

**Negative:**

- A new terminal status value enters active use in the runtime. Any code path that filters blackboard entries by status must be audited for correct handling of `deferred_to_proposal`. The dedup query (line 17956) is the load-bearing case and is already correct; other filter sites are not enumerated in this ADR.
- Revival is eventually-consistent across two transactions (proposal-state commit, then blackboard-revival commit). A crash between the two leaves findings stranded at `deferred_to_proposal` while the proposal is `failed`. Mitigation: the revival is idempotent and can be re-triggered by a maintenance command; the hazard is named here rather than buried in code.
- Pre-existing `resolved` rows from before this change carry no `proposal_id` and cannot be reconciled. Pre-change churn findings stay in history as they are. No backfill.
- The `ProposalConsumerWorker.run()` exception branch (line 107600) does not call `mark_failed` — an unhandled executor exception leaves the proposal stuck at `executing` and revival never fires. This is a pre-existing bug, not introduced by this ADR, but the new revival path makes its consequences more visible. Named as a follow-up in References.

**Neutral:**

- Dedup-subsumed findings (line 110115 path) remain `resolved`, not `deferred_to_proposal`. They are subsumed duplicates, not the originating findings of the referenced proposal. The paper does not define their handling; this ADR freezes current behaviour for that branch.
- The revival report (subject `proposal.failure.revival`) is a new `report` entry shape on the blackboard. Consumers of blackboard reports that filter by subject are unaffected; consumers that scan all reports gain one new subject string to tolerate.
- No `.intent/` change. `deferred_to_proposal` is already declared in `.intent/META/enums.json`; `fetch_active_finding_subjects_by_prefix`'s dedup semantics already tolerate it.

## References

- `.specs/papers/CORE-Finding.md` §7 (terminal transitions table, `deferred_to_proposal` row) and §7a (revival obligation).
- `.intent/META/enums.json` — `blackboard_entry_status` enum including `deferred_to_proposal`.
- `src/body/services/blackboard_service.py` — existing methods `resolve_entries` (line 18292), `release_claimed_entries` (line 18339), `update_entry_status` (line 18513); payload-merge SQL pattern (line 25387). Targets for extension: new `defer_entries_to_proposal` and `revive_findings_for_failed_proposal`.
- `src/will/workers/violation_remediator.py` — `ViolationRemediatorWorker.run` (line 110047), `_create_proposal` (line 110320), `_resolve_entries` (line 110422). Target for modification: line 110128-110131 transition point.
- `src/will/autonomy/proposal_state_manager.py` — `mark_failed` (line 84659). Target for extension.
- `src/will/autonomy/proposal_executor.py` — `mark_failed` call sites (line 83698, 83964).
- `src/will/autonomy/proposal_repository.py` — `mark_failed` call site (line 84461, `execute_workflow` exception handler).
- ADR-008 — `impact_level` parking. Precedent for "paper has a contract, code implements a narrower reality, ADR documents the decision about closing vs parking."
- ADR-009 — CLI-depth block passive instrumentation. Precedent for grounding a decision in live diagnostic evidence.
- Pre-check evidence, 2026-04-24: empirical query results showing 285 historical resolved findings on one subject and zero fix.placeholders activity in the current daemon's lifetime. Drives the "success-path churn, not just failure-path revival" reframe.
- Follow-up (separate session): `ProposalConsumerWorker.run()` exception branch at line 107600 does not call `mark_failed`. Unhandled executor exceptions leave proposals stuck at `executing`. Revival never fires for this path. Not introduced by this ADR; made more visible by it. Warrants its own fix.
- Follow-up (separate session): retroactive audit of pre-ADR-010 `resolved` findings for rules with remediation-map entries. Reconciliation is not mechanical (no `proposal_id` in payload for historical rows); human review if needed.
