---
kind: adr
id: ADR-127
title: ADR-127 — Indeterminate clean-pass drain via AuditViolationSensor
status: accepted
---

<!-- path: .specs/decisions/ADR-127-indeterminate-clean-pass-drain.md -->

# ADR-127 — Indeterminate clean-pass drain via AuditViolationSensor

**Date:** 2026-06-27
**Governing paper:** `.specs/papers/CORE-Blackboard-State-Machine.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-27 — drafted under governor direction)
**Relates to:** ADR-045 (awaiting_reaudit drain — symmetric predecessor),
ADR-082 (blackboard retention policy — established the principle that findings
must not accumulate without a resolution path), ADR-091 (status vocab and
resolution_mechanism), ADR-082 D7 (new retention behaviours require ADR text)

---

## Context

### The gap

ADR-045 established that `AuditViolationSensor` is the truth-keeper for its
rule namespace across the full finding lifecycle: it posts violations and it
closes `awaiting_reaudit` quarantined findings when re-audit shows them clean.
ADR-082 established that `open` DELEGATE findings are closed by TTL sweep in
`BlackboardShopManager`. Together they cover:

- `open` → `resolved` via TTL (ADR-082 D3)
- `awaiting_reaudit` → `open` or `resolved` via re-audit (ADR-045)

`indeterminate` has no equivalent automatic resolution path.

### What `indeterminate` means — and what it does not mean

A finding enters `indeterminate` when `ViolationRemediatorWorker` or the
`LLM gate` determines that autonomous remediation cannot proceed: the rule
requires human judgment to select a remediation path, or the autonomous fix
attempt failed in a non-retriable way.

Critically, `indeterminate` encodes **remediation uncertainty**, not
**violation uncertainty**. The human judgment call is: "how should this be
fixed?" — not "does this violation still exist?" If the underlying violation
has self-resolved (the file was refactored externally, a threshold was raised,
or another commit brought the file into compliance), the `indeterminate`
finding no longer represents real work. The governance judgment that was
missing has become moot.

Under the current design, the finding stays `indeterminate` indefinitely.
Neither `BlackboardShopManager` (which lacks the audit engine context to
re-evaluate rules) nor `AuditViolationSensor` (which only drains
`awaiting_reaudit`) touches it. The governor inbox accumulates findings whose
underlying violations have cleared, masking genuinely indeterminate work behind
resolved noise.

### Observed instance — 2026-06-27

Three `style.formatter_required` findings remained `indeterminate` for 1–2
weeks:

- `python::style.formatter_required::src/body/atomic/assisted_actions.py` —
  created 2026-06-15, no `fix.format` proposal ever generated.
- `python::style.formatter_required::src/cli/resources/lane/next.py` —
  created 2026-06-16 07:23 (immediately after a prior `resolved` entry at
  07:03); a manual verify proposal completed 2026-06-16 10:01.
- `python::style.formatter_required::src/mind/logic/grc_applicability.py` —
  created 2026-06-20 (preceded by an `abandoned` entry from 2026-06-20 11:55).

`ruff format --check` on all three on 2026-06-27 returned **3 files already
formatted**. The findings were stale. They were closed manually via SQL this
session. A structural fix is warranted so this manual step is never needed
again.

### Why `BlackboardShopManager` cannot host this mechanism

ADR-082 hosts TTL-based sweeps in `BlackboardShopManager` because TTL requires
only a timestamp comparison — no rule evaluation, no engine context. The
`indeterminate` clean-pass requires re-running the rule against the current
file state to determine if the violation still holds. `BlackboardShopManager`
has no access to the audit engine; adding it would violate the worker's
scope (blackboard hygiene only) and duplicate the engine's call path.

### Why a new worker is not warranted

`AuditViolationSensor` is already the constitutional truth-keeper for its rule
namespace. It already performs the symmetric operation for `awaiting_reaudit`.
Introducing a second worker that performs rule-level re-evaluation would create
a second truth source for the same namespace — a coherence risk without any
compensating benefit.

---

## Decision

### D1 — AuditViolationSensor drains `indeterminate` findings on each cycle

`AuditViolationSensor.run()` gains a second drain pass, executed immediately
after the existing `awaiting_reaudit` drain (ADR-045) and before the
new-violations pass:

1. Fetch all findings with `status = 'indeterminate'` whose subject begins
   with `<artifact_type_id>::<rule_namespace>`.
2. For each finding, re-evaluate the rule against the current file state using
   the same engine path used for the `awaiting_reaudit` drain.
3. If the violation **still holds**: leave the finding in `indeterminate` — the
   remediation-uncertainty judgment is still valid, the governor must act.
4. If the violation **no longer holds**: transition to `resolved` with
   `resolution_mechanism = 'system.audit'` and a `payload.resolution` block:

```json
{
  "reason": "ADR-127 clean-pass: violation no longer present on re-audit",
  "resolved_by": "audit_violation_sensor",
  "resolution_authority": "system.audit"
}
```

This is the same resolution authority shape used by the `awaiting_reaudit`
drain (ADR-045), which also re-evaluates and closes via `system.audit`.

### D2 — Implementation via extended `adjudicate_awaiting_reaudit_findings`

Rather than adding a new `BlackboardService` method, extend
`adjudicate_awaiting_reaudit_findings` (or add a parallel
`adjudicate_indeterminate_findings` method) to accept an explicit `status`
parameter. The resolution logic is identical: fetch by subject prefix + status,
compare subject set against current violations, resolve those absent from the
current set.

Preferred: a separate `adjudicate_indeterminate_findings` method that mirrors
the `awaiting_reaudit` counterpart. This preserves method-name clarity and
avoids a parameter that changes the SQL predicate — a hidden-behaviour pattern
that the codebase has flagged in prior feedback.

### D3 — Only violations-gone findings are closed; still-real findings are untouched

The drain pass MUST NOT close `indeterminate` findings whose violation still
holds. The `indeterminate` state for those findings correctly reflects that the
governor has an unresolved decision to make. This drain is specifically for the
case where the decision has become moot because the code is now compliant.

This is the distinguishing constraint from ADR-082 D3's TTL sweep, which
resolves regardless of whether the violation is still real (treating the
TTL as a proxy for "governor chose not to act"). For `indeterminate` findings,
that heuristic is too aggressive: the governor may be planning remediation.
The clean-pass drain is conservative — it only closes what the audit engine
certifies is no longer a violation.

### D4 — Dedup interaction is unchanged

`BlackboardService.fetch_active_finding_subjects_by_prefix` already includes
`indeterminate` in its active-subject set (the `IN ('open', 'claimed',
'indeterminate', 'awaiting_reaudit')` predicate). An `indeterminate` finding
for a still-real violation is already in the dedup set; the sensor's
new-violations pass will not re-post it. When the drain resolves an
`indeterminate` finding (violation gone), the active-subject set shrinks and
the next new-violations pass will not re-post either (because the rule doesn't
fire on the now-compliant file). No change to the dedup query is needed.

### D5 — Drain runs after `awaiting_reaudit` drain, before new-violations pass

Ordering within `AuditViolationSensor.run()`:

1. Heartbeat + intent reload (existing)
2. `awaiting_reaudit` drain (ADR-045, existing)
3. **`indeterminate` clean-pass drain (this ADR, new)**
4. New-violations pass (existing)

This ordering means: findings closed in step 3 are already `resolved` when
step 4 computes active subjects; no ghost re-post is possible.

### D6 — Observability: existing `audit.reaudit.complete` report extended

The `audit.reaudit.complete` blackboard report posted at the end of the drain
passes gains two additional fields:

```json
{
  "indeterminate_drained": 2,
  "indeterminate_drain_subjects": ["python::style...::src/foo.py", "..."]
}
```

No new report subject needed; the existing subject carries the extended payload.
Operators who want to observe the drain frequency query
`audit.reaudit.complete` blackboard entries for the relevant namespace.

---

## Consequences

**Positive:**

- `indeterminate` findings for self-resolved violations drain within one audit
  cycle (~10 minutes under current cadence) without governor intervention. The
  governor inbox reflects genuinely open decisions, not resolved noise.
- The AuditViolationSensor becomes the full lifecycle owner for its namespace:
  posts violations, quarantines revived findings (ADR-045), and now also closes
  stale `indeterminate` entries when the code becomes compliant.
- The observed 1–2 week staleness window (2026-06-27 instance) shrinks to one
  audit cycle.
- No new worker, no new table, no schema migration. The only change is one new
  `BlackboardService` method and a new pass in `AuditViolationSensor.run()`.

**Negative:**

- `AuditViolationSensor.run()` becomes slightly longer per cycle (one
  additional DB query for `indeterminate` findings per namespace). In steady
  state on a stable codebase this query returns zero rows and is negligible.
- The `indeterminate` state's semantics shift marginally: it now means "needs
  human judgment AND violation still confirmed real." Prior semantics (needs
  human judgment, violation status unconfirmed) were implicit; this ADR makes
  the confirmation aspect explicit.

**Neutral:**

- The existing manual escape hatch (`core-admin workers resolve` or direct SQL)
  remains available for cases where the governor wants to close an
  `indeterminate` finding before the next audit cycle.
- `BlackboardShopManager`'s role is unchanged. It continues to handle TTL
  sweeps and SLA-tier stale alerts; rule-level adjudication stays in the sensor.

---

## Implementation guidance

Three sites, in order:

1. **`BlackboardService` (`src/body/services/blackboard_service/blackboard_service.py`)**:
   Add `adjudicate_indeterminate_findings(subject_prefix, current_violation_subjects,
   resolved_by)` method. Implementation mirrors `adjudicate_awaiting_reaudit_findings`
   exactly, with `status = 'indeterminate'` substituted in the predicate and
   `resolution_mechanism = 'system.audit'` in the resolution payload.

2. **`AuditViolationSensor.run()` (`src/will/workers/audit_violation_sensor.py`)**:
   After the `awaiting_reaudit` drain block (current lines ~212–250), add the
   `indeterminate` drain pass: call `bb_svc.adjudicate_indeterminate_findings()`
   with the same `subject_prefix` and `current_subjects` set already computed
   for the `awaiting_reaudit` drain. Extend the `audit.reaudit.complete` report
   payload with D6's new fields.

3. **Tests (`tests/will/workers/test_audit_violation_sensor*.py` or equivalent)**:
   - `indeterminate` finding whose violation is gone → `resolved` after drain.
   - `indeterminate` finding whose violation still holds → remains `indeterminate`.
   - Both drain passes run in the correct order (step 2 before step 3 before step 4).

**Acceptance conditions:**

- A file with an `indeterminate` finding that `ruff format --check` (or the
  relevant rule's engine) certifies as clean transitions to `resolved` within
  one `AuditViolationSensor` cycle.
- A file with an `indeterminate` finding that still violates its rule is
  untouched by the drain pass.
- The `audit.reaudit.complete` report for the affected namespace includes the
  `indeterminate_drained` field.
- The governor inbox count (`SELECT COUNT(DISTINCT subject) FROM blackboard_entries
  WHERE status = 'indeterminate'`) does not include self-resolved files after
  one sensor cycle.

---

## References

- ADR-045 — `awaiting_reaudit` quarantine and AuditViolationSensor drain
  (symmetric predecessor; this ADR extends the same pattern to `indeterminate`)
- ADR-082 — Blackboard retention policy (established the principle; D7 requires
  ADR text for new retention behaviours)
- ADR-082 D3 — DELEGATE OPEN finding TTL sweep (the existing mechanism for
  `open` findings; this ADR deliberately avoids extending it to `indeterminate`
  per D3 of this ADR)
- ADR-091 — Status vocab and `resolution_mechanism` closed set
  (`system.audit` is the correct authority for sensor-adjudicated closure)
- 2026-06-27 observed instance: three `style.formatter_required` `indeterminate`
  findings persisting 1–2 weeks after files reached compliance; closed manually
  via SQL as a one-time recovery; this ADR prevents recurrence.
