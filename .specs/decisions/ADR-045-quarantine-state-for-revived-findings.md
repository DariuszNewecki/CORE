---
kind: adr
id: ADR-045
title: ADR-045 — Quarantine state for findings revived after rejection
status: accepted
---

<!-- path: .specs/decisions/ADR-045-quarantine-state-for-revived-findings.md -->

# ADR-045 — Quarantine state for findings revived after rejection

**Status:** Accepted
**Date:** 2026-05-13
**Authors:** Darek (Dariusz Newecki)
**Closes:** #TBD
**Relates to:** ADR-010 (§7+§7a Finding/Proposal contract), ADR-015 (operator
attribution), ADR-038 (circuit breaker on repeated proposal failures),
ADR-042 (modularity governance recalibration)

---

## Context

The §7a revival contract from ADR-010 specifies that when a proposal fails or is
rejected, the findings it consumed must be restored to `open` so the remediation
loop can retry. This works for the case the contract was designed for: a proposal
that failed for *proposal-quality* reasons (bad plan, wrong action, execution
error) where the underlying violation is still real and a fresh proposal is
warranted.

It does not work when the proposal is rejected for *finding-staleness* reasons —
the file has been refactored, an ADR has changed the threshold, or the governor
judges the finding obsolete. In these cases, the revival flips the finding back
to `open` with its **original payload intact**. The audit sensor's next cycle is
responsible for re-evaluating, but the remediator's tick interval is typically
shorter than the audit cycle, so the remediator re-claims the stale finding
before the audit gets to sweep it. A new proposal is created from the unchanged
payload. The governor rejects it again. The loop repeats.

### Observed instance — 2026-05-13

Finding `eadd9450-b382-4d71-a544-761b260715ce`
(`audit.violation::modularity.needs_split::src/will/workers/violation_remediator.py`):

- Created 2026-05-12 19:15 UTC with payload message *"File has 485 lines (limit
  400)"*.
- File was refactored at 2026-05-12 21:20 UTC (commit `96645de9`) from 485 → 394
  lines.
- ADR-042 raised the rule's `max_lines` threshold from 400 → 500.
- Proposal `20d8dbc0-03e7-4c43-919f-793a1315dfa5` (built from the original
  payload) was rejected by the governor 2026-05-13 ~19:55 UTC with reason "Stale:
  file refactored 485→394 lines, threshold raised 400→500".
- §7a revival flipped the finding to `open`.
- ViolationRemediatorWorker re-claimed it at 2026-05-13 19:58 UTC and created
  proposal `3f569f78-e749-4f51-b524-8fe5b7847950` from the same unchanged
  payload.

The audit sensor between revival and re-claim would have correctly identified no
current violation (394 < 500), but the remediator's tick fired first. The loop
would have continued indefinitely without governor intervention.

### Why a lock-style primitive does not fit

The race is temporal, not concurrent. The remediator and audit sensor never
contend for the same row at the same instant — the remediator's transaction
simply runs first in wall-clock time, before the audit sensor's transaction runs
at all. A DB advisory lock or row-level mutex would serialise concurrent access
to the row but would not enforce ordering. The mechanism needed is "the
remediator must not see this finding until the audit sensor has had a chance to
adjudicate" — which is a state-machine property, not a concurrency primitive.

---

## Options considered

**Option A — `awaiting_reaudit` quarantine state.**
Add one status to the blackboard entry state machine. Revival flows (governor
rejection, §7a automatic revival on proposal failure) flip findings to
`awaiting_reaudit` instead of `open`. The remediator's claim query continues to
filter by `status = 'open'` and therefore does not see quarantined findings. The
audit sensor's next cycle is responsible for releasing each quarantined finding:
re-evaluate the rule against the current file state, transition to `open` if the
violation holds or to `resolved` if it does not.

**Option B — Pre-validation in ViolationRemediatorWorker.**
Before claiming an `open` finding, the worker re-runs the rule's audit logic to
confirm the violation still exists. If not, mark the finding resolved without
proposing. Closes the loop close to the symptom, but duplicates audit logic in
the worker layer — divergence between the remediator's validator and the audit
sensor's validator becomes its own correctness risk. Also makes every claim
heavier; the validator runs even on findings posted seconds ago by the audit
itself (the common case).

**Option C — Time-based quarantine via timestamp field.**
Add a `revived_at` column. The remediator's claim query excludes findings with
`revived_at` newer than `now() - <audit_cycle_interval>`. Same effect as A but
expressed as a timestamp rather than a state. Drawbacks: the threshold depends
on the audit cycle interval (a config coupling), the quarantine is invisible to
inspection (`SELECT status, count(*)` no longer shows the quarantine
population), and a stalled or delayed audit cycle silently extends the wait
without any explicit signal.

**Option D — Database advisory locks per finding.**
Use `pg_advisory_xact_lock` keyed by finding ID to serialise the remediator's
claim and the audit sensor's evaluation. Rejected: serialises concurrent access
but does not enforce temporal ordering (the actual race). Also fragile —
process death leaks lock state — and invisible to inspection.

**Option E — Make rejection terminal (no revival).**
Rejection transitions the finding to `suppressed` directly; no revival, no
retry, no quarantine needed. Eliminates the race entirely for the rejection
path. Drawback: collapses two distinct rejection semantics — "this finding is
stale, close it" and "this proposal was wrong, retry with a different plan" —
into one. The latter case (proposal-quality rejection of a still-real
violation) needs the finding to remain actionable, and Option E breaks that
case. Could be combined with A (revival-via-quarantine for retry-worthy
rejections, terminal-suppression for staleness rejections), but the contract
becomes operator-facing (the operator must classify each rejection), which is a
governance burden.

---

## Decision

**Option A — `awaiting_reaudit` quarantine state.**

Add one status to the existing blackboard state machine: `awaiting_reaudit`.

**Transitions in:**

- `BlackboardService.revive_findings_for_failed_proposal(proposal_id)` (§7a on
  proposal failure): transition matched findings from `deferred_to_proposal` to
  `awaiting_reaudit` instead of `open`.
- `core-admin proposals reject` (governor manual rejection): the rejection path
  already invokes `revive_findings_for_failed_proposal`; same transition applies.

**Transitions out (audit sensor):**

`AuditViolationSensor.run()` adds a new pass to each cycle:

1. Fetch all findings in `awaiting_reaudit` for the sensor's rule namespace.
2. For each finding, re-evaluate the rule against the current file state using
   the same audit engine path that posts fresh violations.
3. If the violation still holds → transition to `open` (claimable by the
   remediator).
4. If the violation no longer holds → transition to `resolved` with
   `payload.resolution = {reason: "audit re-evaluation: condition no longer
   present", resolved_by: "audit_violation_sensor", resolution_authority:
   "system.audit"}`, mirroring the operator-attribution shape introduced for
   manual resolution.

This pass runs at the start of `run()`, before the new-violations pass, so that
findings released to `open` in this cycle are immediately eligible for the
remediator on its next tick.

**Sensor-scope guarantee.** `AuditViolationSensor` performs a full-repo sweep
each cycle (`rglob("*.py")` across the repo root, no incremental scoping). The
"every file is visited each cycle" property is structural, and the quarantine
release pass naturally inherits it: every file with an `awaiting_reaudit`
finding will be re-evaluated each cycle. If the sensor architecture is later
changed to incremental file-scoping (ADR-039 already touches related ground),
the quarantine release pass must remain full-scope or be explicitly hoisted to
visit pending-reaudit files unconditionally.

**Dedup interaction.** The dedup query
(`BlackboardService.fetch_active_finding_subjects_by_prefix`, ADR-010 §Layer 1)
already excludes only `resolved`. `awaiting_reaudit` naturally stays in the
"active subject" set, so the new-violations pass continues to skip re-posting
for files already represented by a quarantined finding. The release pass is
authoritative for those rows; no duplicate finding is created.

**Schema migration.** Update the `blackboard_entry_status_closed_set` CHECK
constraint to include `'awaiting_reaudit'`. Set `resolved_at` to `NULL` on
entry into this state (it is non-terminal); the existing terminal-state hygiene
list in `BlackboardService.update_entry_status` remains unchanged.

Rejected: Option B duplicates audit logic and burdens every claim with a
validator pass. Option C is functionally equivalent to A but invisible to
inspection. Option D addresses concurrency, not ordering. Option E loses the
proposal-quality retry semantics and forces operators to classify rejections.

---

## Consequences

**Positive:**

- The reject-revive-reclaim divergence loop is structurally closed. A revived
  finding is not actionable until the audit sensor has explicitly re-evaluated
  it; if the underlying condition has cleared, the finding closes itself.
- The audit sensor becomes the single owner of finding truth across the
  lifecycle. Today it owns *posting*; under this ADR it also owns *closure for
  conditions that have cleared*. This is symmetric and matches the paper's
  framing of sensors as the truth-keeper for their rule namespace.
- Quarantine population is inspectable: `SELECT subject, created_at FROM
  blackboard_entries WHERE status = 'awaiting_reaudit'` shows what is waiting,
  for how long. Operators can spot a stalled sensor without inferring it from
  proposal churn.
- Subsumes the symmetric counterpart-CLI gap closed by the
  `core-admin workers resolve` command (added 2026-05-13): with quarantine in
  place, stale findings close themselves on the next audit cycle and the manual
  closure CLI becomes a rarely-needed escape hatch rather than the regular path.

**Negative:**

- Adds one state to the blackboard state machine. Every consumer of the
  `status` column must consider whether `awaiting_reaudit` is in or out of its
  filter set. The dedup query, the dashboard's open-findings count, the
  governor inbox count, the stale-alert sweep, the worker registry's
  status-style map — each must be reviewed. Most will treat `awaiting_reaudit`
  as "active but not actionable" (same bucket as `deferred_to_proposal`).
- §7a revival semantics shift from "revival is immediate" to "revival is
  delayed by up to one audit cycle". On a 600s audit cadence this is a real
  delay. Proposals rejected for proposal-quality reasons (where the violation
  is still real) now wait one cycle before the remediator can re-attempt.
  Acceptable: the previous immediate-revival behaviour is the source of the
  bug.
- The audit sensor's `run()` becomes longer per cycle (an additional pass over
  quarantined findings). In steady state on a stable codebase this pass should
  be empty or near-empty, so the cost is negligible; on a churning codebase
  with many recent rejections it is bounded by the rejection rate.
- Constitutional CHECK constraint migration touches a hot table. Migration
  must be online-compatible (PostgreSQL allows adding values to a CHECK
  constraint via DROP + ADD NOT VALID + VALIDATE, but the operation should be
  scheduled carefully).

**Neutral:**

- ADR-038's circuit breaker on repeated proposal failures continues to operate
  on the same proposal-failure events; this ADR does not change failure
  detection.
- Operator-facing CLI vocabulary is unchanged: `proposals reject` still does
  what it did; the difference is purely in the post-rejection lifecycle.

---

## Implementation guidance

Six sites, in order:

1. **DB migration (`infra/migrations/`):** drop and recreate
   `blackboard_entry_status_closed_set` CHECK constraint to include
   `'awaiting_reaudit'`. Use `NOT VALID` + `VALIDATE` to avoid a full-table
   lock during constraint addition. Verify no in-flight workers post invalid
   statuses during the window between drop and recreate.

2. **`BlackboardService.revive_findings_for_failed_proposal`
   (`src/body/services/blackboard_service/...`):** change the target status in
   the UPDATE from `'open'` to `'awaiting_reaudit'`. The function's name
   remains accurate ("revive" still describes the lifecycle move from terminal
   to active); the comment in `src/cli/resources/proposals/manage.py:103-109`
   referring to "revival to open" needs an update to "revival to
   awaiting_reaudit".

3. **`AuditViolationSensor.run()`
   (`src/will/workers/audit_violation_sensor.py`):** add a new pass at the
   start of `run()`, after the heartbeat and intent reload but before
   `_resolve_rule_ids`. The pass:
   - Queries `core.blackboard_entries` for findings with
     `status = 'awaiting_reaudit'` whose `payload->>'rule'` is in this
     sensor's namespace.
   - For each, runs the rule against the file (single-file evaluation via the
     existing audit engine path).
   - Issues UPDATE: `status = 'open'` if violation present;
     `status = 'resolved'` with the system-authority resolution payload if not.
   - Posts a single `audit.reaudit.complete` blackboard report at the end with
     counts of released and resolved.

4. **Dedup query review (`BlackboardService.fetch_active_finding_subjects_by_prefix`):**
   verify the existing "exclude only `resolved`" predicate naturally keeps
   `awaiting_reaudit` in the active set. No change expected, but the
   verification belongs in the implementation PR.

5. **Dashboard panel (`src/cli/resources/runtime/health.py`):** the
   convergence-direction panel queries `open_findings`. Decide whether
   `awaiting_reaudit` counts as open for trajectory purposes. Recommendation:
   include it (the finding still represents unresolved work; excluding it
   would understate the backlog and mask quarantine-tarpit conditions). Also
   add a small visibility row to the Governor Inbox or a sibling panel
   showing the `awaiting_reaudit` count, so operators can see when the
   quarantine is growing.

6. **Acceptance conditions:**
   - Rejecting a proposal whose underlying violation has cleared transitions
     the finding through `awaiting_reaudit` → `resolved` within one audit
     cycle, without any new proposal being created.
   - Rejecting a proposal whose underlying violation still holds transitions
     the finding through `awaiting_reaudit` → `open` within one audit cycle,
     and the remediator's next tick creates a fresh proposal.
   - Concurrent governor rejection and audit sensor run produce a consistent
     terminal state (the test is for transactional correctness of the
     status-machine, not for race-window length).
   - The `awaiting_reaudit` count visible in the dashboard / blackboard query
     is bounded by the number of rejections since the last audit cycle, and
     drains to zero on a stable codebase within one cycle after the rejection
     burst ends.

---

## References

- ADR-010 — §7+§7a Finding/Proposal contract (revival obligation)
- ADR-015 — Operator attribution shape (`approval_authority`,
  `human.cli_operator`)
- ADR-038 — Circuit breaker on repeated proposal failures
- ADR-042 — Modularity governance recalibration (threshold raise from 400 to
  500, the change that made the observed 2026-05-13 instance stale)
- `.specs/papers/CORE-Finding.md` §7, §7a — the original Finding/Proposal
  lifecycle paper
- 2026-05-13 observed loop: finding
  `eadd9450-b382-4d71-a544-761b260715ce`; proposals
  `20d8dbc0-03e7-4c43-919f-793a1315dfa5` (rejected) and
  `3f569f78-e749-4f51-b524-8fe5b7847950` (re-created from same payload)
