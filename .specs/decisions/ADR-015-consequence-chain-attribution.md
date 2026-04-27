<!-- path: .specs/decisions/ADR-015-consequence-chain-attribution.md -->

# ADR-015 — Consequence Chain Attribution: Write Paths and Storage Shapes

**Date:** 2026-04-27
**Status:** Accepted
**Commits:** pending

## Decision

The six Band B child issues (#145, #146, #147, #148, #164, #165) close the consequence chain by adding attribution to writes that already happen. This ADR fixes the write paths and the storage shapes so the six implementations are coordinated, not independent. Forward-only enforcement; historical rows are preserved as ALCOA "Complete" requires.

The seven sub-decisions below are bound together: D2's column placement enables D6's signature change; D4 mirrors D1's payload pattern; D6 closes #146 and #165 in the same change-set.

### D1 — `finding_ids` lives in `constitutional_constraints` jsonb (#145)

`constitutional_constraints` is the jsonb container already present on `core.autonomous_proposals` and already read at the consequence-write path. `_create_proposal` writes the new key alongside `source`, `rules`, and `affected_files_count`. No schema migration.

**Change sites:** `src/will/workers/violation_remediator.py:488-492` (write); `src/will/autonomy/proposal_executor.py:265-267` (existing reader, unchanged behavior — already calls `.get("finding_ids", [])`).

### D2 — `approval_authority` is a new column with forward-only CHECK (#165)

`approval_authority text` is added to `core.autonomous_proposals` as a column, not a jsonb key. The column carries a structured reference to the rule or policy that authorized approval. A CHECK constraint requires it non-NULL when `status IN ('approved', 'executing', 'completed')`, with a created-at carve-out for rows that predate this ADR. NFR.5's "non-omittable at write path" is the structural form; jsonb keys cannot enforce structurally.

The carve-out is one-time migration concession. Going forward, the constraint is binding.

**Change sites:** new migration in `infra/` (column + CHECK); `src/will/autonomy/proposal_state_manager.py:141-158` (signature change — see D6).

### D3 — `claimed_by` mirrors the blackboard pattern onto proposals (#147)

`claimed_by uuid` is added to `core.autonomous_proposals` as a column, populated by `mark_executing()` in the same UPDATE that sets `status='executing'` and `execution_started_at`. The column mirrors the proven pattern at `core.blackboard_entries.claimed_by` (which also has `claimed_at`; the proposal's `execution_started_at` already serves the timestamp role and is not duplicated). Atomicity rides on the existing `autonomous_proposals_executing_once` unique constraint.

**Change sites:** new migration in `infra/`; `src/will/autonomy/proposal_state_manager.py:48-76` (`mark_executing` accepts `claimed_by: UUID` and writes it).

### D4 — Subsume-path attribution writes `proposal_id` into payload (#164)

`_resolve_entries` extends to receive the subsuming proposal's id and writes it into each resolved finding's `payload->>'proposal_id'`. This mirrors the deferred-to-proposal payload pattern that `_defer_to_proposal` already established. The helper that today returns active action ids changes to return action_id → proposal_id; the dedup-subsume branch in `run()` passes the subsuming proposal_id through.

A new blackboard service method `resolve_entries_with_attribution(entry_ids, proposal_id)` mirrors the existing `defer_entries_to_proposal(entry_ids, proposal_id)`. The current `resolve_entries(entry_ids)` is retained for non-proposal resolution causes (out of Band B scope per URS §6).

**Change sites:** `src/will/workers/violation_remediator.py:215-233` (call site, dedup-subsume branch); `src/will/workers/violation_remediator.py:544-567` (`_resolve_entries` signature); `src/will/workers/violation_remediator.py:416` (`_get_active_proposal_action_ids` return type).

### D5 — Sensor cause attribution is heuristic via `proposal_consequences` lookup (#148)

`AuditViolationSensor` consults `core.proposal_consequences` at finding-post time for rows whose `files_changed` jsonb overlaps the new finding's `file_path` AND `recorded_at` is within a recency window. On match, `causing_proposal_id` and `causing_commit_sha` are written into the new finding's payload. On no match, the payload omits those keys and downstream queries see NULL via `payload->>'causing_proposal_id'`.

The window is a heuristic — multiple recent proposals can touch the same file, and a finding can be older than the recent proposal. The most-recent-matching-proposal is the practical default. The ADR accepts the heuristic because the alternative (runtime tracking of execution-to-finding causation) requires infrastructure beyond Band B's scope.

The window value is a sensor configuration parameter, not a constant in the ADR. ADR-015 fixes the *shape* of the lookup; the *value* is tunable.

**Change sites:** `src/will/workers/audit_violation_sensor.py:210-222` (post_finding payload extension); `src/will/workers/audit_violation_sensor.py:194-208` (no change to dedup; the new payload keys do not affect subject-string matching).

### D6 — `ProposalStateManager.approve()` signature carries `approval_authority` (#146 + #165 jointly)

`approve(proposal_id, approved_by)` becomes `approve(proposal_id, approved_by, approval_authority)`. The autonomous self-promote block in `_create_proposal` stops mutating `proposal.status` directly and routes through `state_manager.approve(...)`, passing `approved_by="autonomous_self_promote"` (or equivalent) and `approval_authority` set to the rule that classified the proposal as auto-approvable (the impact-level rule per ADR-014's vocabulary; concrete value lives outside this ADR and tracks the issue that closes #165).

This change-set closes #146 and #165 together. Splitting them produces a window where #146 is landed but #165 is not, during which `approve()` could be called without an authority value — violating NFR.5.

**Change sites:** `src/will/autonomy/proposal_state_manager.py:141-158` (`approve` signature); `src/will/workers/violation_remediator.py:504-511` (self-promote block replaced with `state_manager.approve(...)` call).

### D7 — Forward-only; no historical backfill of `approval_authority`

The 159 existing rows in `core.autonomous_proposals` retain NULL `approval_authority`. The CHECK constraint admits a created-at carve-out for these rows. ALCOA "Complete" preserves originals; backfilling would manufacture history that did not occur. The 22 historical `proposal_consequences` rows with empty `findings_resolved` are partially recoverable (plan §4.3 C — backfill, out of Band B scope); `authorized_by_rules` on those rows is not recoverable and stays empty.

**Change sites:** migration in `infra/` (CHECK constraint with date carve-out); plan §4.3 C scope confirmed (findings_resolved only; authorized_by_rules permanently empty for pre-ADR rows).

## Rationale

The investigation surfaced two dominant patterns: asymmetric attribution and schema-without-population. Both arise from the same root — write paths that perform the structural work without performing the attribution work. Each child issue closes one such gap. Without coordination, six independent fixes risk inconsistent storage choices (jsonb here, column there, freeform somewhere else) and a chain that is technically queryable but inconsistent under any single index strategy.

Three principles guided the sub-decisions:

1. **Match existing readers.** D1's choice of `constitutional_constraints` is forced by `proposal_executor.py:265-267` already calling `.get("finding_ids", [])`. Choosing a column would create a write/read mismatch and require a reader change that has nothing to do with the write fix.

2. **Use columns for non-omittable attribution; jsonb for present-or-absent attribution.** D2 (approval_authority) is non-omittable per NFR.5 — column with CHECK. D1 (finding_ids), D4 (subsume payload proposal_id), D5 (causing_proposal_id) are present-when-applicable — jsonb keys with absence-as-NULL semantics. D3 (claimed_by) follows the blackboard precedent of column-with-FK-style discipline because it carries identity (worker UUID) that the schema already references via foreign key elsewhere.

3. **Preserve history; enforce forward.** D7 is the ALCOA-compliant treatment of the 159 rows that predate the constraint. Synthesizing values to satisfy a forward constraint would be an integrity failure of the same shape the chain exists to prevent.

The sub-decisions are coordinated, not independent. D2 and D6 land together. D1 and D4 share a payload-key convention. D3 and D6 share the `mark_executing` UPDATE shape. ADR-015 makes the coordination visible so the six children land coherently.

## What this does not remove

The three commit-time gates (ConservationGate, IntentGuard, Canary) remain in place. TestRunnerSensor remains. The `autonomous_proposals_executing_once` unique constraint remains. The `proposal_consequences.proposal_id` foreign key to `autonomous_proposals.proposal_id` remains. ADR-011's worker-only INSERT principle remains in force — every new attribution write described above is performed by a Worker (ViolationRemediatorWorker, AuditViolationSensor) or by services performing UPDATEs on already-attributed rows (ProposalStateManager), which is the partition ADR-011 established. ADR-010's Finding/Proposal contract remains; this ADR extends it with the proposal-side `finding_ids` and the subsume-path attribution that ADR-010's docstrings flagged as pending.

## Revisit triggers

- D5's heuristic produces measurable false positives or false negatives on the resolution chain. A causing_proposal_id is recorded on a finding the proposal did not actually cause, or a regression-class finding is missed because the window did not match.
- D5's `proposal_consequences` lookup at finding-post time becomes a performance bottleneck for `AuditViolationSensor` cycles.
- A non-jsonb storage for `finding_ids` becomes valuable because a query the URS does not currently specify (cross-proposal finding lookup, or join paths the optimizer cannot serve from a jsonb expression index) becomes important.
- ADR-008 (`impact_level` governance) unparks. The vocabulary D6 uses for `approval_authority` then migrates to whatever shape ADR-008 establishes; this ADR's column survives but its values change.
- Subsume-path resolution becomes the dominant path (currently the deferred-to-proposal path is dominant). At that point D4's helper signature change should be revisited for whether the helper deserves promotion to a first-class blackboard service operation rather than a remediator-only path.

## Relationship to predecessor ADRs

**ADR-010 (Finding/Proposal contract).** This ADR completes the contract on the proposal side. ADR-010 wired finding → proposal forward (`payload->>'proposal_id'`) and the deferred-to-proposal status. D1 and D4 extend the same contract: D1 wires proposal → finding reverse (`constitutional_constraints->'finding_ids'`); D4 closes the subsume-path gap that ADR-010's docstrings explicitly flagged as pending the consequence-logging work.

**ADR-011 (worker-only INSERTs into blackboard).** Preserved. Every new write described above is either an INSERT by a Worker (sensor postings, remediator postings) or an UPDATE by a service on a row that was already worker-attributed (proposal state transitions). The partition ADR-011 established is unchanged.

**ADR-013 (retire legacy `core.proposals`).** Confirmed. All write paths in this ADR target `core.autonomous_proposals` — the table that will rename to `core.proposals` per ADR-013's reservation. No write path resurrects the legacy table or its `proposal_signatures` companion.

**ADR-014 (development-phase priority).** Coordinated. ADR-014 reclassified `build.tests` from `moderate` to `safe`, putting it on the auto-approval path. D6 puts the auto-approval path through `ProposalStateManager.approve()` with `approval_authority` non-omittable. The vocabulary for `approval_authority` on the safe path tracks ADR-014's reasoning — the impact-level classification is the rule that authorizes auto-approval.

## Consequence

The six child issues now have specific implementation shapes. Each issue's closure is observable as a query against the URS:

- #145 closes when Q1.R returns `finding_ids` from `constitutional_constraints` for a recent autonomous proposal.
- #146 closes when Q2.F returns non-NULL `approved_by` and `approved_at` for an autonomous self-promoted proposal — and the path lands together with #165 per D6.
- #147 closes when Q3.F returns the worker UUID that claimed the proposal.
- #148 closes when Q6.F returns `causing_proposal_id` for a finding posted in proximity to a recent execution that touched the same file.
- #164 closes when Q1.F returns `resolving_proposal_id` for a finding resolved on the subsume path.
- #165 closes when Q2.A returns `approval_authority` and the write-path validation rejects an attempt to set `status='approved'` without it (URS acceptance criterion 4).

Backfill (plan §4.3 C) is now scoped: `findings_resolved` on the 22 historical `proposal_consequences` rows is reconstructable from blackboard payloads and within scope. `authorized_by_rules` on those same rows is permanently empty per D7. `approval_authority` on the 159 historical proposals is permanently NULL per D7. These are not gaps; they are recorded as the original state, which ALCOA requires.

The ADR closes when the six child issues close and the URS acceptance criteria are demonstrated. ADR-015's own validity is the question of whether the resulting chain reads coherently end-to-end (URS E2E.F and E2E.R) — if it does, the coordination this ADR enforced was correct; if it does not, the revisit triggers above name where to look first.
