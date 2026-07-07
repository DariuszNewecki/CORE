---
kind: adr
id: ADR-038
title: ADR-038 — Circuit-breaker on repeated proposal failures
status: accepted
---

<!-- path: .specs/decisions/ADR-038-circuit-breaker-on-repeated-proposal-failures.md -->

# ADR-038 — Circuit-breaker on repeated proposal failures

**Date:** 2026-05-11
**Status:** Accepted — Implemented
**Author:** Darek (Dariusz Newecki)
**Closes:** #281
**Implementation:** `src/will/workers/circuit_breaker.py` · `src/will/workers/violation_remediator_proposal.py` · `.intent/enforcement/config/circuit_breaker.yaml` (commit `bd998c24`)
**Governing paper:** `.specs/papers/CORE-Workers-and-Governance-Model.md`
**Relates:** ADR-010 (finding-proposal contract — §7/§7a revival), ADR-015 (consequence chain attribution), ADR-035 (one finding, one proposal), ADR-031 / #282 (no hardcoded governance values in `src/`)

---

## Context

The autonomous remediation loop has no upper bound on how many times the
same systematic failure can repeat. Today's flow:

1. `AuditViolationSensor` posts an open finding for a violation on
   `(rule, file)`.
2. `ViolationRemediatorWorker._create_proposal` mints a proposal for
   `(action, file)` and defers the finding to it.
3. `ProposalConsumerWorker` executes; the action fails (LLM gate refusal,
   validator rejection, infra error).
4. `ProposalStateManager.mark_failed`
   (`src/will/autonomy/proposal_state_manager.py:91`) writes
   `status='failed'`, `failure_reason`, `execution_results`.
5. `revive_and_report`
   (`src/will/workers/proposal_consumer_revival.py:43`) flips the
   deferred finding back to `open`. ADR-010 §7a contract honored.
6. Next remediator cycle re-claims the finding, runs the dedup at
   `_get_active_proposal_id_by_action_file`
   (`src/will/workers/violation_remediator.py:475`), finds **no active
   proposal** (the failed one is terminal), and mints proposal #N+1 with
   byte-identical contents.

Nothing reads the historical failure tail. Confirmed instance: a
`purity.no_todo_placeholders` finding on
`src/will/workers/violation_remediator.py` produced **128 failed
`fix.placeholders` proposals**, all rejected by the same IntentGuard
gate error in 0.17s each. Per the Convergence Principle, a loop that
amplifies failures rather than resolving them cannot converge.

The companion IntentGuard scope-leak issue addresses the root cause of
*that specific* failure family. This ADR addresses the architectural gap
that allows *any* systematic failure — present or future, known or
unknown — to amplify unbounded.

The signals needed to gate the loop already live on the
`autonomous_proposals` row: `actions` JSONB carries `ref_id` and
`parameters.file_path`; `status='failed'` is indexed; `failure_reason`
is the canonical error text. No schema change required.

---

## Why the gate must sit at proposal **creation**

Two viable insertion points were considered:

- **A. `ViolationRemediatorWorker.run()`, between dedup and
  `_create_proposal`.**
- **B. Inside `revive_and_report`** — refuse to revive findings whose
  parent proposal has failed N times.

**B alone is insufficient.** Not reviving leaves the finding parked at
`deferred_to_proposal`, but `AuditViolationSensor` re-senses the
underlying violation in the next cycle and emits a fresh finding with a
new entry_id. That fresh finding is then claimed by
ViolationRemediatorWorker, which has no reason to refuse it, and proposal
#N+1 is minted anyway. The gate is bypassed by the sensor.

A is the choke point: every new proposal for an `(action, file)` pair
flows through `_create_proposal`, regardless of whether the originating
finding was revived from a deferred state or freshly emitted by the
sensor. The historical failure tail is queried *before* the new proposal
is built.

---

## Decision

### D1 — Failure identity is `(ref_id, file_path, error_signature)`

Counting `(ref_id, file_path)` alone over-trips on flaky infrastructure
(LLM timeouts, transient DB errors, rate-limit blips) where the
underlying action would succeed on the next attempt.

`error_signature` is `failure_reason` truncated to the first
`signature_window_chars` (default 200) characters after a canonicalizer
strips volatile substrings:

- ISO-8601 timestamps
- UUIDs (8-4-4-4-12 hex form)
- Floating-point durations matching `\d+\.\d+s`
- Process IDs and other `pid=\d+` patterns

The volatile-pattern set is governed in
`.intent/enforcement/config/circuit_breaker.yaml` (D5) so the governor
can extend it as new noise sources appear without a code change.

### D2 — Threshold is consecutive identical signatures, default N=5

The circuit trips when the **most recent N** failed proposals for the
same `(ref_id, file_path)` carry the same `error_signature`. Counting
*consecutive* identical signatures rather than *any N within a window*
means a single successful run between failures resets the count
naturally — no separate reset bookkeeping required.

Default N=5 balances "fool me twice" caution against transient-noise
tolerance. Tunable via `.intent/enforcement/config/circuit_breaker.yaml`
(D5).

### D3 — Tripping the circuit: DELEGATE the findings, post a hazard

When the circuit trips for `(ref_id, file_path)`:

1. **All findings in the current cycle's group for that key are marked
   DELEGATE** via the existing `_mark_delegated` path
   (`violation_remediator.py:791`). The loop stops auto-claiming them.
2. **A `governance.circuit_breaker_tripped` finding is posted** to the
   blackboard with payload:

   ```json
   {
     "ref_id": "...",
     "file_path": "...",
     "failure_count": 5,
     "error_signature": "...",
     "last_proposal_id": "...",
     "last_failure_reason": "..."
   }
   ```

   This mirrors the `governance.instrument_degraded` pattern at
   `violation_remediator.py:186-194` — a single triage queue for the
   governor.

3. **No new proposal is created** for that `(ref_id, file_path)` this
   cycle. The dedup `continue` is reused.

### D4 — Reset path

The circuit re-opens automatically on the next *successful* proposal for
the same `(ref_id, file_path)` — by D2's "consecutive" semantics, a
success between failures already resets the count. Since DELEGATE'd
findings stop minting proposals, the only way back to "success" is
governor intervention (manual remediation, finding re-opened, or the
underlying rule retired).

For explicit override, a CLI surface is added:

```
core-admin proposals reset-circuit <ref_id> <file_path>
```

This re-opens the DELEGATE'd findings (status: `open`) and posts a
`governance.circuit_breaker_reset` report so the action is auditable.
Implementation is a thin wrapper over existing finding-status helpers;
no new infrastructure.

### D5 — Governance values live in `.intent/`, not in `src/`

Per ADR-031 / #282, the threshold and signature configuration are
governance, not code. New file:

```yaml
# .intent/enforcement/config/circuit_breaker.yaml
threshold_n: 5
signature_window_chars: 200
volatile_patterns:
  - name: iso_timestamp
    regex: '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?'
  - name: uuid
    regex: '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
  - name: duration_seconds
    regex: '\d+\.\d+s'
  - name: pid
    regex: 'pid=\d+'
```

Loaded once at worker initialization through the existing intent-config
loader (no direct `Path` access from `src/`).

### D6 — Failure-counting query scope: all-time, ordered by completion

The query that drives D2 reads the **most recent N** rows from
`autonomous_proposals` matching the `(ref_id, file_path)` key, ordered
by `execution_completed_at DESC`, all-time (no rolling window). A flaky
period in the distant past does not affect today's count because (a) the
most-recent-N filter naturally bounds it and (b) the consecutive-identical
rule means an intervening success resets attribution.

### D7 — Out of scope for this ADR

- **Per-rule thresholds.** A single global N is correct as a starting
  point. Future per-rule overrides can be added under
  `circuit_breaker.yaml` without changing this ADR's contract.
- **Time-based decay.** Considered and rejected: introduces a "the
  circuit will magically reset in T hours" surprise that obscures the
  governor's mental model. Reset is explicit (D4) or success-driven
  (D2).
- **Cross-file circuit-tripping.** A `fix.modularity` failure pattern
  that affects 50 files is 50 separate circuits, each independently
  counted. Bundling across files would conflate distinct file contexts
  and create false positives.

---

## Implementation

### Files

1. **`.intent/enforcement/config/circuit_breaker.yaml`** — D5.
2. **`src/will/workers/circuit_breaker.py`** — three pure functions:
   - `canonical_signature(failure_reason: str, *, window_chars: int, volatile_patterns: list[Pattern]) -> str`
   - `recent_consecutive_identical_count(session, ref_id, file_path, *, max_lookback: int) -> tuple[int, str | None]`
     — returns `(count, signature)` for the streak of the most-recent
     identical-signature failures.
   - `trip(worker, ref_id, file_path, findings, *, count, signature, last_proposal_id, last_failure_reason) -> None`
     — DELEGATE the findings + post the hazard finding.
3. **`src/will/workers/violation_remediator.py`** — patch `run()` to call
   the helper between the dedup `continue` and `_create_proposal`. ~10
   lines.
4. **`src/cli/resources/proposals/reset_circuit.py`** (new) — CLI surface
   for D4 manual reset. Thin wrapper.
5. **`tests/will/workers/test_circuit_breaker.py`** — unit on the
   canonicalizer and the count query; integration test that injects 5
   failed proposal rows for a `(ref_id, file_path)` and asserts the next
   `ViolationRemediatorWorker.run()` cycle skips creation, marks
   DELEGATE, and posts the hazard finding.

### Worker patch shape (illustrative)

```python
# In ViolationRemediatorWorker.run(), inside the action_groups loop:
for (ref_id, file_path), findings in action_groups.items():
    ...
    # Existing dedup
    if subsuming_proposal_id:
        ...
        continue

    # NEW: circuit-breaker check
    cb_count, cb_signature = await recent_consecutive_identical_count(
        session, ref_id, file_path, max_lookback=cb_config.threshold_n
    )
    if cb_count >= cb_config.threshold_n:
        await trip(
            worker=self,
            ref_id=ref_id,
            file_path=file_path,
            findings=findings,
            count=cb_count,
            signature=cb_signature,
            ...
        )
        continue

    proposal_id = await self._create_proposal(ref_id, ref_kind, findings)
```

---

## Consequences

- **Bounded failure amplification.** No `(ref_id, file_path)` pair can
  produce more than `threshold_n + 1` failed proposals before the
  circuit trips. The 128-failure pattern observed 2026-05-10 cannot
  recur for any action.
- **Governance visibility.** Every trip surfaces as a
  `governance.circuit_breaker_tripped` blackboard finding. The governor
  has a single triage queue.
- **DELEGATE is silent rejection of work.** This is the load-bearing
  hazard of the proposal: if the dashboard does not surface
  `circuit_breaker_tripped` prominently, a tripped circuit just looks
  like the loop went quiet. Acceptance criterion: dashboard surfaces
  this finding category at the same prominence as `instrument_degraded`.
- **Resource cost.** One extra DB query per `(ref_id, file_path)` group
  per remediator cycle. Bounded by `LIMIT N` (default 5). Negligible
  next to LLM call cost.
- **No schema change.** All counting is over existing
  `autonomous_proposals` columns.
- **Compatibility with ADR-035.** Circuit-breaker key matches ADR-035's
  proposal-creation key exactly. No conflict.
- **Compatibility with ADR-010 §7a.** Revival semantics unchanged. The
  circuit gates *new proposal creation*, not *finding revival*; revived
  findings still flow back to `open` and are re-claimed normally — they
  just hit the gate the next time a proposal would be minted.

---

## References

- Issue **#281** — closes
- Issue **#282** — informs D5 (no hardcoded governance in `src/`)
- ADR-010 — finding-proposal contract, §7/§7a revival
- ADR-015 — consequence chain attribution
- ADR-031 — no hardcoded runtime paths (precedent for D5 governance
  externalization)
- ADR-035 — one finding, one proposal (defines the
  `(ref_id, file_path)` key reused here)
- Code: `src/will/workers/violation_remediator.py`,
  `src/will/autonomy/proposal_state_manager.py`,
  `src/will/workers/proposal_consumer_revival.py`,
  `src/shared/infrastructure/database/models/autonomous_proposals.py`
- Dashboard observation: 2026-05-10, 128 identical failures confirmed
