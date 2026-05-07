# ADR-027 — Sensor-fixer coherence detection via consequence chain query

| Field | Value |
|-------|-------|
| **Date** | 2026-05-07 |
| **Status** | Accepted |
| **Authority** | Architecture |
| **Closes** | Issue #114 |

---

## Context

The autonomous remediation loop is:

```
AuditViolationSensor → Blackboard finding → ViolationRemediatorWorker
  → Proposal → ProposalConsumerWorker → ProposalExecutor
  → AuditViolationSensor (next cycle)
```

A fixer (AtomicAction or Flow) is considered coherent with its sensor if, after the fixer runs successfully, the sensor does not re-detect the same violation on the same target file in the next cycle.

Incoherence has two observable manifestations:

1. **Silent churn** — the fixer runs, the proposal completes with `ok=True`, but the sensor re-posts the same `check_id + file_path` finding on the next cycle. The system appears to be working (proposals created, executed) but the violation never resolves.
2. **Loop stall** — the finding re-enters the blackboard, is claimed again by ViolationRemediatorWorker, and the cycle repeats indefinitely. Convergence is impossible.

Neither is detectable from proposal status alone. A completed proposal tells you the fixer ran; it does not tell you whether the fix held.

The consequence chain (G3, ADR-015) materialised the data needed to detect this: `core.proposal_consequences.findings_resolved` links each executed proposal to the finding IDs it addressed, and `recorded_at` gives the execution timestamp.

---

## Decision

### D1 — Detection mechanism: query-based periodic audit

Implement a new `CoherenceSensorWorker` that runs periodically (every 10 minutes). On each cycle it executes a single query against `core.proposal_consequences` and `core.blackboard_entries`:

**Incoherence condition:** a new open finding F_new exists where:
- F_new's `check_id` and `file_path` match a finding F_old that was in `findings_resolved` of a completed proposal
- F_new was created AFTER the proposal's `recorded_at`
- F_new is in a non-terminal status (`open`, `claimed`, or `deferred_to_proposal`)
- The proposal's `recorded_at` is within the lookback window (governed in `.intent/`)

The query joins `proposal_consequences` → `blackboard_entries` (old findings) → `blackboard_entries` (new findings) on `check_id + file_path` payload match.

Rationale for query-based over event-stream: the consequence chain is already materialised in DB; no new infrastructure is required. A periodic query is architecturally consistent with `CommitReachabilityAuditor` and `BlackboardShopManager`.

### D2 — "Same violation" identity: check_id + file_path

Two findings represent the same violation if they have the same `payload->>'check_id'` and `payload->>'file_path'`. This is the narrowest possible identity that avoids false positives (matching on subject alone would miss rule/file combinations that change subject format across sensor versions).

### D3 — Lookback window: governed in `.intent/`

The detection window (default: 2 hours) is read from `.intent/cim/thresholds.yaml` under a new `coherence` key. Setting it too short produces false negatives (fixer may take more than one cycle to be verified). Setting it too long produces noise from unrelated re-introductions of the same violation.

### D4 — Signal surface: Blackboard finding

On detecting incoherence, `CoherenceSensorWorker` posts a `coherence.incoherence::<rule>::<file_hash>` finding to the Blackboard with payload:
```json
{
  "check_id": "<rule>",
  "file_path": "<file>",
  "proposal_id": "<proposal that ran the fixer>",
  "original_finding_id": "<F_old id>",
  "re_posted_finding_id": "<F_new id>",
  "fixer_ran_at": "<recorded_at>"
}
```

`file_hash` is the first 8 characters of a deterministic hash of `file_path` to keep subjects short. Deduplication: do not re-post if an open `coherence.incoherence::` finding already exists for the same subject.

Rationale for Blackboard finding over log/alert: consistent with the governance pattern (findings are the canonical signal surface in CORE). The finding is observable via `core-admin workers blackboard`, actionable by humans, and potentially automatable (a future rule can route coherence findings to a human delegate or an architectural reviewer).

### D5 — No autonomous remediation for coherence findings

`auto_remediation.yaml` does NOT map `coherence.incoherence` entries. Incoherence requires human architectural judgment: either the fixer is wrong, the sensor is wrong, or the rule definition needs revision. This is a DELEGATE-class finding.

### D6 — Worker class: supervisory, audit phase

`CoherenceSensorWorker` is a supervisory worker in the `audit` phase. No LLM calls. No file writes. Reads `core.proposal_consequences` and `core.blackboard_entries`. Writes only to Blackboard. Follows the `WorkerShopManager` pattern for self-scheduling.

---

## Alternatives considered

**A1 — Real-time event hook on ProposalExecutor completion.** Would detect incoherence sooner but requires coupling ProposalExecutor to a new service and introduces ordering constraints. Rejected: query-based is simpler and sufficient given the 10-minute cycle.

**A2 — Extend AuditViolationSensor to check its own post-fix state.** Each sensor would compare its current detections against recent consequence records. Rejected: couples sensing logic (constitutional audit) with coherence meta-audit; violates single responsibility. Sensors should not reason about their own historical output.

**A3 — Match on subject rather than check_id + file_path.** Subjects include UUIDs or variable elements in some sensors. Rejected: check_id + file_path is stable and unambiguous.

---

## Consequences

- New worker: `CoherenceSensorWorker` declared at `.intent/workers/coherence_sensor.yaml`, implemented at `src/will/workers/coherence_sensor.py`.
- New `.intent/cim/thresholds.yaml` key: `coherence.lookback_seconds` (default: 7200).
- New Blackboard subject namespace: `coherence.incoherence::`.
- `auto_remediation.yaml`: no entry for `coherence.incoherence` (DELEGATE by design).
- Closes the sensor-fixer coherence gap identified as a Known Blocker in CORE-A3-plan.md Phase 3+.
