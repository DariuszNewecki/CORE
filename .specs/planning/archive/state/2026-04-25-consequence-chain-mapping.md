# Consequence chain — current persistence and read-path mapping
**Date:** 2026-04-25
**Status:** Investigation
**Issue:** #110
**Method:** Live evidence only — schema, code, blackboard, logs.

## Summary table

| Edge | Persisted? | Attributed? | Read-path? |
|---|---|---|---|
| 1. Finding → Proposal | partial | partial (asymmetric) | partial (reverse only via finding payload) |
| 2. Proposal → Approval | partial (columns exist, rarely populated) | partial (no rule/authority) | yes (when populated) |
| 3. Approval → Execution claim | partial (status only) | no (no claimer attribution) | no |
| 4. Execution → AtomicAction dispatch | yes (in-row jsonb) | partial (per-row, not cross-row) | yes per proposal; no cross-proposal |
| 5. Execution → File changes | yes | yes (freeform commit-message + DB) | yes (brittle: orphan commits, prefix-only) |
| 6. File changes → New findings | yes (finding row) | **no** | **no** |

## Edge 1 — Finding → Proposal
### Persistence
On the **finding side**, the proposal id is stored in `core.blackboard_entries.payload` JSONB. Schema: `payload jsonb NOT NULL DEFAULT '{}'::jsonb` (psql `\d blackboard_entries`). Live sample of a deferred finding payload:
```
{"rule": "workflow.ruff_format_check", "status": "unprocessed", "dry_run": false,
 "message": "...", "severity": "warning",
 "file_path": "src/will/workers/proposal_consumer_worker.py",
 "proposal_id": "0b359369-00a4-43fa-bea6-f8ea8bbf5f2c", "rule_namespace": "style"}
```
Written by `src/will/workers/violation_remediator.py:244` via `_defer_to_proposal(entry_ids, proposal_id)` (defined at lines 570–600). Findings transition to `status='deferred_to_proposal'` with the proposal id embedded in payload.

On the **proposal side**, no `finding_ids` column or jsonb key is written. The remediator stores only:
```python
# src/will/workers/violation_remediator.py:488-492
constitutional_constraints={
    "source": "blackboard_findings",
    "rules": rules,
    "affected_files_count": len(affected_files),
},
```
The `rules` field captures *rule IDs*, not *finding IDs*. There is no per-proposal record of which specific findings were consumed.

### Attribution
**Asymmetric.** Finding payload names the proposal; proposal does not name the findings. Verified by inspection: no row in `autonomous_proposals` has `constitutional_constraints->>'finding_ids'` set:
```
SELECT COUNT(*) FILTER (WHERE constitutional_constraints ? 'finding_ids')
  FROM autonomous_proposals;  -- expected: 0
```
The downstream consumer at `src/will/autonomy/proposal_executor.py:265–266` reads:
```python
findings_resolved=proposal.constitutional_constraints.get("finding_ids", []),
```
…and writes the empty list to `proposal_consequences.findings_resolved`. The empirical result confirms this:
```
SELECT COUNT(*) FILTER (WHERE findings_resolved::text != '[]')
  FROM proposal_consequences;        -- 0 of 22 rows
```

### Read path
- **Forward** (finding → proposal): `SELECT payload->>'proposal_id' FROM blackboard_entries WHERE id = $1`. Works.
- **Reverse** (proposal → its findings): `SELECT * FROM blackboard_entries WHERE payload->>'proposal_id' = $1` — works, but relies on JSONB scan; no dedicated index. Would also miss any findings resolved on the dedup/subsume path (those are `resolved` without `proposal_id` in payload — see `_resolve_entries` at violation_remediator.py:544; entries are subsumed and not annotated).

## Edge 2 — Proposal → Approval
### Persistence
Columns exist on `core.autonomous_proposals`:
```
approved_by  text
approved_at  timestamp with time zone
```
(psql `\d autonomous_proposals`). They are populated by `ProposalStateManager.approve()`:
```python
# src/will/autonomy/proposal_state_manager.py:141-158
async def approve(self, proposal_id: str, approved_by: str) -> None:
    stmt = update(AutonomousProposal).where(...).values(
        status=ProposalStatus.APPROVED.value,
        approved_by=approved_by,
        approved_at=datetime.now(UTC),
    )
```

**However, the autonomous path bypasses `approve()` entirely.** When risk is `safe`, the remediator self-promotes the in-memory proposal:
```python
# src/will/workers/violation_remediator.py:504-511
if not proposal.approval_required:
    proposal.status = ProposalStatus.APPROVED
    logger.info(
        "ViolationRemediatorWorker: proposal for '%s' auto-approved "
        "(risk=%s, approval_required=False)", ...
    )
```
The proposal is then persisted in `APPROVED` state without `approved_by`/`approved_at` ever being written. Empirical confirmation:
```
SELECT status, COUNT(*), COUNT(*) FILTER (WHERE approved_by IS NOT NULL)
  FROM autonomous_proposals GROUP BY status;
-- completed | 22  | with_approver=1
-- failed    | 129 | with_approver=1
-- draft     | 5   | with_approver=0
-- rejected  | 3   | with_approver=0
```
Only 2 of 159 proposals carry an approver identity.

The legacy/parallel `core.proposals` (bigint id) and `core.proposal_signatures` tables — which include cryptographic-style `approver_identity`, `signature_base64`, `signed_at`, `is_valid` — are unused: both have 0 rows.

### Attribution
When populated, `approved_by` is a freeform text. The schema does not record:
- the rule or authority under which approval was granted
- the policy/role that authorized the approval

`autonomous_proposals.constitutional_constraints` jsonb is the structurally available place for this; today it holds only `source`, `rules`, `affected_files_count`.

### Read path
Where columns are populated, a direct query works (`WHERE approved_by = $x AND approved_at BETWEEN ...`). Indexed via `ix_autonomous_proposals_pending_approval` (partial, only `status='pending' AND approval_required=true`); a global query on `approved_by` is a sequential scan.

## Edge 3 — Approval → Execution claim
### Persistence
Claim semantics on the **proposal side** are encoded as a status transition, not a claim record:
```python
# src/will/autonomy/proposal_state_manager.py:48-75
async def mark_executing(self, proposal_id: str) -> None:
    stmt = (update(AutonomousProposal)
        .where(
            AutonomousProposal.proposal_id == proposal_id,
            AutonomousProposal.status == ProposalStatus.APPROVED.value,
        )
        .values(
            status=ProposalStatus.EXECUTING.value,
            execution_started_at=datetime.now(UTC),
        ))
    result = await self._session.execute(stmt)
    if result.rowcount == 0:
        await self._session.rollback()
        raise RuntimeError(f"Proposal {proposal_id} was already claimed ...")
```
Concurrency safety is provided by `autonomous_proposals_executing_once UNIQUE (proposal_id) WHERE status='executing'` (psql `\d autonomous_proposals`).

What is **not persisted**: the identity of the worker that performed the transition. `autonomous_proposals` has no `claimed_by`, `claim_worker_uuid`, or equivalent column. Compare to `core.blackboard_entries` which has `claimed_by uuid` and `claimed_at timestamp with time zone` — that pattern is not mirrored on the proposal table.

### Attribution
None. The DB record cannot answer "which worker claimed proposal X". `ProposalConsumerWorker` is the only known caller of `mark_executing` in the autonomous path (via `ProposalExecutor.execute()` at `proposal_executor.py:91-94`), so the answer is implicitly always that worker — but that is a code-knowledge inference, not a persisted fact.

### Read path
None for "who claimed this proposal". Available substitutes:
- `execution_started_at` (when claim happened)
- `status='executing' | 'completed' | 'failed'` (whether claim was made)
- A correlated daemon log scan keyed by `execution_started_at` ± window can identify the worker process — out-of-band, not queryable.

## Edge 4 — Execution → AtomicAction dispatch
### Persistence
**Action sequence (input):** `core.autonomous_proposals.actions jsonb NOT NULL` — set at draft time. Live shape:
```json
[
  {"order": 0, "action_id": "fix.format",
   "parameters": {"write": true,
                  "file_path": "src/will/workers/proposal_consumer_worker.py"}}
]
```
**Per-action results (output):** `core.autonomous_proposals.execution_results jsonb NOT NULL` — set by `mark_completed` (`proposal_state_manager.py:79-96`):
```python
.values(
    status=ProposalStatus.COMPLETED.value,
    execution_completed_at=datetime.now(UTC),
    execution_results=results,
)
```
Where `results = action_results` is built in `proposal_executor.py:144-149`:
```python
action_results[action_id] = {
    "ok": result.ok,
    "duration_sec": action_duration,
    "data": result.data,
    "order": action.order,
}
```
Live sample:
```
{"fix.format": {"ok": true,
                "data": {"write": true, "formatted": true},
                "order": 0,
                "duration_sec": 1.234022855758667}}
```

**Note on the legacy `actions` / `action_results` tables:** Both are empty (0 rows). `core.actions.task_id` references `core.tasks(id)` (bigint pk on `proposals`), an alternate cognitive-task schema that the autonomous loop does not write to.

### Attribution
Within a proposal row, each action is keyed by `action_id` and ordered by `order`. There is no FK from action records to `autonomous_proposals.proposal_id` — the relationship is a JSONB-by-containment.

### Read path
- **Per proposal**: `SELECT execution_results FROM autonomous_proposals WHERE proposal_id = $1` — direct.
- **Cross-proposal "all executions of action X"**: only by GIN scan on `autonomous_proposals.actions` (index `idx_actions_payload_gin` exists on the legacy `actions` table, not on `autonomous_proposals.actions`). No dedicated query path.

## Edge 5 — Execution → File changes
### Persistence
**`core.proposal_consequences`** (one row per completed proposal, FK to `autonomous_proposals.proposal_id`):
```
proposal_id          text  PK, FK
recorded_at          timestamptz
pre_execution_sha    text
post_execution_sha   text
files_changed        jsonb (array of {"path": str})
findings_resolved    jsonb (always empty — see Edge 1)
authorized_by_rules  jsonb (always empty — see below)
```
Population: 22 rows; 20 have non-empty `files_changed`; 0 have non-empty `findings_resolved`; 0 have non-empty `authorized_by_rules`.

`authorized_by_rules` is sourced from `proposal.scope.policies` at `proposal_executor.py:268`. The remediator does not populate `scope.policies` (`violation_remediator.py:486` writes `scope=ProposalScope(files=affected_files)` with no policies), so it is always empty.

**Git commit:** the executor calls `git_service.commit(...)` with a hard-coded subject pattern at `proposal_executor.py:203`:
```python
self.core_context.git_service.commit(
    f"fix({proposal.proposal_id[:8]}): {proposal.goal}"
)
```
Cross-checked against actual git history:
```
62a84ff7 fix(d99f5919): Autonomous remediation: fix.placeholders (1 violation(s) — rules: purity.no_todo_placeholders)
15c8ae3e fix(63d47846): Autonomous remediation: fix.placeholders (...)
c8b51ca5 fix(e690c374): Autonomous remediation: fix.format (...)
fbf50247 fix(e1a8cade): Autonomous remediation: fix.format (...)
14bde1ce fix(f9ab85c8): Autonomous test remediation: build.tests (...)
```
The 8-character prefix in the commit subject matches `LEFT(proposal_id, 8)` in `autonomous_proposals`.

### Attribution
**Bidirectional but freeform.** The proposal id appears in two places:
1. `proposal_consequences.post_execution_sha` (structured field)
2. The commit message subject (string convention enforced only by the executor; not a git trailer)

The convention is unenforced by the schema or by any audit rule (cross-ref: issue #124 — autonomous commit-message fidelity).

### Read path
- **Forward** (proposal → commit): `SELECT post_execution_sha FROM proposal_consequences WHERE proposal_id = $1`, then `git show $sha`. Works for the 22 recorded proposals.
- **Reverse** (commit → proposal): two routes:
  - `git log --grep '^fix([0-9a-f]\{8\}):' --format='%H %s'`, parse the prefix, then `SELECT * FROM autonomous_proposals WHERE proposal_id LIKE '<prefix>%'`. Works.
  - `SELECT proposal_id FROM proposal_consequences WHERE post_execution_sha = $sha`. Works only for in-DB SHAs.
- **Brittleness**:
  - Proposal `0b359369`'s recorded `post_execution_sha=211c2dd2` exists in git but is an **orphan commit** — not on any branch (verified: `git branch --contains 211c2dd2` returns nothing). The link survives in `proposal_consequences` but the commit is GC-eligible. The 8-char prefix scheme assumes commit reachability; orphan commits break that assumption silently.
  - The 8-char prefix has only 32 bits of distinguishability against the proposal_id space; collisions become possible (though unlikely at current scale).

## Edge 6 — File changes → New findings
### Persistence
Sensors post fresh blackboard findings via `Worker.post_finding(subject, payload)`. Sample from `src/will/workers/audit_violation_sensor.py:210-222`:
```python
await self.post_finding(
    subject=subject,                         # f"audit.violation::{rule_id}::{v['file_path']}"
    payload={
        "rule_namespace": self._rule_namespace,
        "rule": rule_id,
        "file_path": v["file_path"],
        "line_number": v.get("line_number"),
        "message": v["message"],
        "severity": v["severity"],
        "dry_run": self._dry_run,
        "status": "unprocessed",
    },
)
```
The audit sensor runs the constitutional auditor in-process (`_run_audit(rule_ids)` at line 142) — it does not read `core.audit_findings` (which is empty since the daemon does not invoke the CLI ingest path; `core.audit_findings` is populated by `cli/commands/check/audit.py:50-79` via `core-admin code audit`, which TRUNCATEs and re-inserts).

### Attribution
**None.** The payload schema above carries no field linking the new finding back to:
- the commit that introduced the regression
- the proposal whose execution preceded this scan
- any prior finding it might supersede

The dedup mechanism is by **subject string only** (`audit_violation_sensor.py:194-208` — `existing = await self._fetch_existing_subjects()`); a re-occurrence of the same `audit.violation::rule::file` across cycles is suppressed but not annotated as "the previous one was at proposal X".

**Partial counter-example:** `ProposalConsumerWorker` *does* post `test.run_required::<path>` findings with attribution at `proposal_consumer_worker.py:165-172`:
```python
await self.post_finding(
    subject=f"test.run_required::{path}",
    payload={
        "source_file": path,
        "proposal_id": proposal_id,
        "post_execution_sha": post_execution_sha,
    },
)
```
This is the only place in the worker code where a sensor-class finding carries a forward `proposal_id`. It applies only to test-coverage findings, not to audit-violation findings.

### Read path
**None for audit-violation findings.** Cannot answer "this finding at HEAD was caused by commit X" or "which prior proposal regressed this rule". The only available signal is timing — `created_at` ordering of findings vs `recorded_at` of `proposal_consequences` rows — which is correlation, not causation.

## Cross-cutting observations

- **Asymmetric attribution is the dominant pattern.** Where two artifacts are linked, the link is consistently stored on **one side only**:
  - Edge 1: link on finding side (payload), absent on proposal side (no `finding_ids`).
  - Edge 3: no link at all on proposal side; the worker that claimed is implicit.
  - Edge 6: no link from new finding to its causing proposal/commit (test.run_required is the lone exception).
- **Schema-without-population is the second pattern.** Columns exist for several edges but are not written by the autonomous path:
  - `autonomous_proposals.approved_by` / `approved_at` (Edge 2): populated for 2 of 159 rows.
  - `proposal_consequences.findings_resolved` (Edge 1, recorded at Edge 5): always `[]` because the upstream remediator never writes `constitutional_constraints["finding_ids"]`.
  - `proposal_consequences.authorized_by_rules` (Edge 5): always `[]` because `proposal.scope.policies` is never set.
  - `core.proposals` and `core.proposal_signatures` tables: 0 rows; the autonomous loop does not write to them.
- **Convention-only attribution at the git boundary.** The commit-message prefix `fix({proposal_id[:8]}):` is the only Edge 5 link not in a structured column. Issue #124 is the existing tracker for this risk.
- **Edge 6 is the weakest edge end-to-end.** It is the only edge with neither persistence nor read path for proposal/commit causation. A finding posted by `AuditViolationSensor` after a proposal-induced regression is indistinguishable from a finding posted on a fresh, unmodified file.

## Explicit unverifieds

- The recon document `.specs/state/2026-04-20-daemon-reactivation-recon.md` was referenced but not read for this mapping; conclusions about historical claim-leak behavior come from current code, not historical evidence.
- `validation_results jsonb` on `autonomous_proposals` was inspected for one completed row and found empty `{}`; not exhaustively sampled. If validation hooks exist elsewhere, they may populate this column for some proposals.
- The relationship between `core.constitutional_violations` (with `task_id`, `symbol_id`) and the autonomous loop was not investigated — that table appears to be part of the cognitive-task schema (alongside `tasks` and `actions`), which is empty for the autonomous loop, but it might be populated by a separate path not surveyed here.
- The dedup/subsume code path in `_resolve_entries` (`violation_remediator.py:544`) resolves subsumed findings without recording the subsuming proposal id. Whether this should be considered a partial Edge-1 break (findings resolved without attribution to the resolver) was not pursued — flagged as adjacent to but distinct from #110.
