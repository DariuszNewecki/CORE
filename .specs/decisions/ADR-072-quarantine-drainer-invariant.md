---
kind: adr
id: ADR-072
title: 'ADR-072: Quarantine-Drainer Invariant — Every `awaiting_reaudit` Subject Namespace
  Must Have a Registered Drainer'
status: accepted
---

# ADR-072: Quarantine-Drainer Invariant — Every `awaiting_reaudit` Subject Namespace Must Have a Registered Drainer

**Status:** Accepted
**Date:** 2026-05-25
**Authority:** policy
**Closes:** TBD (issue to be filed once accepted)
**Band:** F (post-ADR-069)
**Extends:** ADR-045

---

## Context

### The asymmetric quarantine

ADR-045 introduced `awaiting_reaudit` as a quarantine state for findings whose
proposal was rejected or failed. The state has two lifecycle ends:

- **Entry** is subject-agnostic. `BlackboardProposalService.revive_for_failed_proposal`
  transitions any `deferred_to_proposal` finding to `awaiting_reaudit` based on
  `payload.proposal_id`, with no filter on the finding's subject namespace.
- **Exit** is subject-namespace-scoped. `BlackboardService.adjudicate_awaiting_reaudit_findings`
  accepts a `rule_namespace` parameter and only touches rows whose subject
  begins with that prefix.

ADR-045 explicitly contemplated multiple sensors as drainers ("Fetch all
findings in `awaiting_reaudit` for the sensor's rule namespace") and promised
that on a stable codebase "the quarantine drains to zero within one cycle after
the rejection burst ends."

In the current implementation, **only one drainer exists**:
`AuditViolationSensor.run()` (`src/will/workers/audit_violation_sensor.py:183`)
calls `adjudicate_awaiting_reaudit_findings` once per cycle, scoped to the
`audit.violation::<rule_namespace>::*` prefix.

A `grep` across `src/` for callers of `adjudicate_awaiting_reaudit_findings`
returns exactly one site. Findings posted in any subject namespace other than
`audit.violation::*` can enter quarantine but cannot leave.

### Peak evidence

As of 2026-05-25, 19 findings sit in `awaiting_reaudit`, all from
`TestRunnerSensor` (worker_uuid `4cd25142-3953-458f-8d0f-6cbe674e02f0`):

| Subject namespace | Stuck rows | Oldest | Newest |
|---|---|---|---|
| `test.missing::*` | 18 | 2026-05-16 | 2026-05-25 |
| `test.failure::*` | 1 | 2026-05-16 | 2026-05-16 |
| **Total** | **19** | — | — |

`TestRunnerSensor` posts findings in these namespaces (`src/will/workers/test_runner_sensor.py:166, 204, 217`)
but has zero calls to `adjudicate_awaiting_reaudit_findings`. Once a
`build_tests` proposal fails for a `test.missing` finding, the finding enters
quarantine and remains there until the next governor SQL purge.

Of the 19 stuck rows, 2 reference files that have since been deleted
(`src/will/cli_logic/reviewer.py`, `src/cli/resources/admin/legacy.py`). These
would not converge even if a drainer existed without a "file no longer present"
branch.

### Why silence is not a valid default

This is the same structural shape as ADR-066: a governance mechanism was
introduced (the state); one wiring path was implemented (the audit sensor's
drain); other paths were assumed to follow but never did. Findings posted in
unwired namespaces fall into a quiet hole — no alert, no convergence signal,
no governor inbox routing. The quarantine "drains to zero within one cycle"
promise from ADR-045 holds only for the `audit.violation::*` subset of
findings, contrary to its design intent.

A subject namespace that can place findings into `awaiting_reaudit` without a
corresponding drainer is a constitutional gap, not an implementation oversight.

---

## Decision

**Every subject namespace that can place findings into `awaiting_reaudit` MUST
have a registered drainer worker in `.intent/enforcement/quarantine/drainer_registry.yaml`.**

A subject namespace is "quarantine-capable" if any code path posts a finding
under that namespace prefix AND that finding can transition to `deferred_to_proposal`
via the proposal-creation flow (the upstream of `revive_for_failed_proposal`).

Silence — the absence of a drainer entry — is not permitted for an active
quarantine-capable namespace.

### Minimum valid entry

A drainer registry entry maps a subject-prefix glob to the worker class that
periodically calls `adjudicate_awaiting_reaudit_findings` for that prefix:

```yaml
namespaces:
  - prefix: "audit.violation::"
    drainer_worker: "AuditViolationSensor"
    drain_method: "adjudicate_awaiting_reaudit_findings"
    cycle_source: "AuditViolationSensor.run"
    description: >
      Drains audit violations against the current file state per ADR-045.
      Released if the rule still fires; resolved otherwise.
  - prefix: "test.missing::"
    drainer_worker: "TestRunnerSensor"
    drain_method: "adjudicate_awaiting_reaudit_findings"
    cycle_source: "TestRunnerSensor.run"
    description: >
      Drains missing-test findings by re-scanning the source tree. Released
      if the source file still has no corresponding test; resolved otherwise
      (or if the source file no longer exists).
  - prefix: "test.failure::"
    drainer_worker: "TestRunnerSensor"
    drain_method: "adjudicate_awaiting_reaudit_findings"
    cycle_source: "TestRunnerSensor.run"
    description: >
      Drains test-failure findings by re-running pytest on the referenced
      test file. Released if the failure still occurs; resolved otherwise.
```

Registry entries are governor-authored. They serve two purposes:
1. **Declarative ownership** — a single grep answers "what drains namespace X?"
2. **Audit anchor** — the new governance rule below validates against this
   registry.

### Deleted-source handling

Drainers MUST treat "current state cannot be evaluated" as a resolution
condition, not a release condition. Specifically, when the file referenced by
a finding's subject no longer exists in the working tree, the drainer resolves
the finding with attribution `system.audit::source_removed`. This prevents the
infinite-loop pattern where a deleted file's quarantined finding never finds
its way to either branch.

---

## Mechanism

### New blocking audit rule: `governance.quarantine.namespace_has_drainer`

A new audit rule enforces the invariant at each audit cycle.

**Behaviour:**

1. Query `blackboard_entries WHERE status = 'awaiting_reaudit' AND resolved_at IS NULL`.
2. Group by `SPLIT_PART(subject, '::', 1)` — the namespace prefix.
3. Load registered prefixes from `.intent/enforcement/quarantine/drainer_registry.yaml`.
4. For each namespace present in quarantine but absent from the registry: emit
   a `FAIL` finding with severity `HIGH`. Include the namespace, the oldest
   stuck row's `created_at`, and the row count.
5. If any such finding is emitted: audit verdict is `FAIL`.

**Rule declaration (`.intent/rules/governance/quarantine.json`):**

```json
{
  "id": "governance.quarantine.namespace_has_drainer",
  "statement": "Every subject namespace with rows in awaiting_reaudit must have a registered drainer in drainer_registry.yaml.",
  "enforcement": "blocking",
  "authority": "constitution",
  "phase": "audit",
  "status": "active",
  "rationale": "ADR-072. Without a registered drainer, findings entering awaiting_reaudit cannot exit. ADR-045's drain-to-zero promise holds only for namespaces with a registered drainer; silent accumulation otherwise."
}
```

**Position in rule hierarchy:** Meta-governance, alongside
`governance.remediation.all_rules_mapped` (ADR-066). Both rules guard a
state-machine invariant where silence is the failure mode.

**Scope:** Active drainers only. A namespace registered with
`status: deprecated` and no live rows is excluded.

### `auto_remediation.yaml` self-entry

Per ADR-066, the new rule must itself have a remediation map entry:

```yaml
governance.quarantine.namespace_has_drainer:
  action: fix.modularity
  confidence: 0.40
  risk: high
  description: >
    A subject namespace has rows in awaiting_reaudit but no drainer is
    registered in .intent/enforcement/quarantine/drainer_registry.yaml.
    The structural invariant established by ADR-072 is violated. Resolution:
    either implement a drainer worker for the namespace and register it,
    or determine that emission into the namespace should be removed.
    Non-automatable; requires governor architectural decision. Routed to
    governor inbox as DELEGATE.
  status: DELEGATE
```

---

## Consequences of violation

When a quarantine-capable namespace has no registered drainer:

1. `revive_for_failed_proposal` transitions findings into `awaiting_reaudit`
   subject-agnostically.
2. No drainer processes the namespace.
3. The finding remains in `awaiting_reaudit` indefinitely. Status is non-terminal,
   so `BlackboardShopManager` emits a `blackboard.entry_stale` meta-finding once
   the row exceeds the stale-alert SLA (default 3600s).
4. Each subsequent failed-proposal revival adds another row.
5. The `BlackboardShopManager` stale-alert pile grows in parallel.
6. ADR-045's "drain to zero on a stable codebase within one cycle" promise is
   violated silently — no audit verdict flips, no convergence signal degrades
   in a way that fires an alert.

At the rate observed (19 rows over 9 days for a single sensor's namespaces;
ratio is bounded by proposal-failure rate, not detection rate), an unregistered
quarantine-capable namespace is a slow but unbounded leak. The leak is
invisible to ADR-038 (no proposals are being created downstream) and to
ADR-066 (the rule is mapped — the problem is in the state machine, not the
remediation map).

---

## Relation to existing decisions

| ADR | Relationship |
|---|---|
| ADR-045 | Established `awaiting_reaudit` and the drain mechanism. ADR-072 closes the implementation gap that ADR-045 contemplated but did not enforce: drain must be wired for every quarantine-capable namespace, not just `audit.violation::*`. |
| ADR-066 | Direct structural analog: a governance state where silence-is-failure-mode is enforced by a meta-rule + self-referential map entry. ADR-072 applies the same pattern to a different state-machine invariant. |
| ADR-038 | Circuit-breaker on proposal failures. Operates downstream of revival; cannot detect the upstream lifecycle break. ADR-072 is required because ADR-038 does not fire on this class. |
| ADR-069 | Claim-lifecycle lease semantics. Both ADRs target gaps in the blackboard-entry lifecycle. ADR-069 covers held-claim release on shutdown; ADR-072 covers quarantine-exit on next audit cycle. Complementary, not overlapping. |

---

## Implementation note

This ADR establishes the constitutional decision and the invariant. The
implementation change-set is out of scope for the ADR itself:

- **D1.** `.intent/enforcement/quarantine/drainer_registry.yaml` — governor-authored;
  initial population covers the three known namespaces above.
- **D2.** `.intent/rules/governance/quarantine.json` — governor-authored rule
  declaration.
- **D3.** `auto_remediation.yaml` self-entry — governor-authored mapping.
- **D4.** Audit-engine check implementing the rule (queries blackboard +
  registry diff). Claude Code implements per governor instruction; lives in
  the audit-engine source path.
- **D5.** `TestRunnerSensor.run` drain wiring — mirror of
  `AuditViolationSensor:172-205`. Computes `current_subjects` from the live
  pytest scan; handles deleted-source case per the registry's `source_removed`
  resolution.
- **D6.** One-time governor SQL purge of the 19 currently-stuck rows, after
  D5 lands and is observed draining new arrivals correctly (so the purge
  reflects a working steady state, not a recurring workaround).

Implementation tracking: TBD issue.

---

## Appendix: lifecycle table

State-machine summary post-ADR-072. Asterisks mark transitions whose
implementation must be registered.

| From | To | Trigger | Subject-scoped? |
|---|---|---|---|
| `open` | `claimed` | Worker claim | No |
| `claimed` | `resolved` | Worker reports success | No |
| `claimed` | `abandoned` | TTL exceeded | No |
| `open` | `deferred_to_proposal` | Remediator creates proposal | No |
| `deferred_to_proposal` | `awaiting_reaudit` | Proposal failure/rejection | No (revive_for_failed_proposal) |
| `awaiting_reaudit` | `open` | Drain releases (violation still fires) | **Yes — drainer required\*** |
| `awaiting_reaudit` | `resolved` | Drain releases (violation cleared OR source removed) | **Yes — drainer required\*** |

Pre-ADR-072, the two starred transitions had a registered drainer for one
namespace prefix (`audit.violation::*`) and no drainer for others
(`test.missing::*`, `test.failure::*`). ADR-072 makes "drainer registered" a
structural prerequisite for any namespace whose findings can reach
`awaiting_reaudit`.
