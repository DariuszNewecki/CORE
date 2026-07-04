---
kind: adr
id: ADR-066
title: 'ADR-066: Unmapped-Rules Invariant — Every Active Rule Must Have an `auto_remediation.yaml`
  Entry'
status: accepted
---

# ADR-066: Unmapped-Rules Invariant — Every Active Rule Must Have an `auto_remediation.yaml` Entry

**Status:** Accepted
**Date:** 2026-05-21
**Governing paper:** `.specs/papers/CORE-Enforcement-Completeness.md`
**Authority:** policy
**Closes:** #418
**Band:** E

---

## Context

### The re-emit loop

When an active audit rule produces a finding and no entry exists for that rule's
`check_id` in `auto_remediation.yaml`, the following loop occurs:

1. Audit cycle N produces a finding for the subject file.
2. `ViolationRemediatorWorker` has no mapping entry → takes no action.
3. The finding ages past its TTL without resolution → transitions to `abandoned`.
4. `blackboard_query_service.py:103` excludes `abandoned` from the active set by
   design — the dedup guard does not fire on abandoned findings.
5. Audit cycle N+1 re-evaluates the same file → the rule fires again → a new
   finding is created.
6. The new finding has no mapping entry → loop repeats indefinitely.

Result: finding count grows without bound. The finding is never resolved, never
delegated, and never surfaced to the governor inbox. The system emits governance
debt silently.

### Peak evidence

Four rules were simultaneously unmapped during the 48-hour window ending
2026-05-21. All four produced the same loop pattern:

| Rule ID | Abandoned findings (peak) | Resolved by |
|---|---|---|
| `architecture.cli.api_only` | 4,282 | mapping added |
| `purity.no_orphan_files` | 1,691 | mapping added |
| `architecture.channels.logger_not_presentation` | 1,558 | #343/#344 (source files deleted) + mapping added |
| `architecture.layers.no_body_to_will` | 8 | mapping added |
| **Total** | **8,539** | — |

`architecture.channels.logger_not_presentation` is the sharpest case study: two
source files produced 1,558 abandoned findings across 48 hours before deletion.
Once the files were deleted (`4e8a5cdc`, `851` deletions, 2026-05-21) and a
`DELEGATE` entry was added to the map (`ce15df4b`), the loop collapsed
immediately. The entry itself — not the deletion — was the structural fix that
would have prevented the accumulation had it been in place when the rule was
activated.

### Why silence is not a valid default

The absence of a mapping entry is currently treated as a no-op signal: the
remediator sees nothing, does nothing, and no alert fires. This is incorrect.
Silence means the finding lives outside the remediation system entirely —
neither dispatched, nor delegated, nor reported. It is unreachable governance
debt that the system cannot converge away from.

A rule that produces findings and has no mapping entry is a constitutional gap,
not an implementation detail.

---

## Decision

**Every rule that is `active` in the audit rule registry and capable of
producing findings MUST have a corresponding entry in
`.intent/enforcement/remediation/auto_remediation.yaml`.**

Silence — the absence of any entry — is not permitted for active rules.

### Minimum valid entry

A `DELEGATE` entry with a description is sufficient to satisfy the invariant.
It requires no automatable fixer, no action ID, and no implementation work. Its
sole purpose is to close the loop: `ViolationRemediatorWorker` recognises the
entry, routes the finding to the governor inbox, and the finding does not
re-accumulate.

```yaml
some.rule.id:
  action: fix.some_handler        # any registered action; may be approximate
  confidence: 0.40                # below MIN_CONFIDENCE (0.80) — prevents dispatch
  risk: moderate
  description: >
    Non-automatable. <One sentence explaining why no autonomous fixer exists
    and what human action is required.> Routed to governor inbox as DELEGATE.
    Explicitly mapped to prevent abandoned-finding re-emission loop.
  status: DELEGATE
```

The `action` field must reference a registered action ID even for DELEGATE
entries, because the remediator validates the action field at load time. Use the
closest plausible action (e.g. `fix.layer_violation`, `fix.logging`) without
implying it will be dispatched.

### Authoritative precedent

`modularity.class_too_large` (`.intent/enforcement/remediation/auto_remediation.yaml`,
TIER 3a) is the reference DELEGATE entry. Its structure is the model:

```yaml
modularity.class_too_large:
  action: fix.modularity
  confidence: 0.40
  risk: high
  description: >
    Class-level refactors require human architectural decision —
    non-automatable per ADR-007. Routed to governor inbox as DELEGATE.
    Explicitly mapped to prevent ViolationExecutorWorker from claiming
    these findings as unmapped. Human review required before any action.
  status: DELEGATE
```

`architecture.channels.logger_not_presentation` (added `ce15df4b`) is the
direct application of this pattern to collapse a live loop.

---

## Mechanism

### New blocking audit rule: `governance.remediation.all_rules_mapped`

A new audit rule is introduced to enforce this invariant at each audit cycle.

**Behaviour:**

1. Load the active rule registry (all rules with `status: active`).
2. Load the remediation map keys from `auto_remediation.yaml`.
3. Compute the difference: active rule IDs present in the registry but absent
   from the map.
4. For each unmapped active rule: emit a `FAIL` finding with severity `HIGH`.
5. If any such finding is emitted: audit verdict is `FAIL`.

**Rule declaration (`.intent/rules/`):**

```yaml
governance.remediation.all_rules_mapped:
  description: >
    Every active rule in the audit rule registry must have a corresponding
    entry in auto_remediation.yaml. Absence is not a valid signal — it
    produces a silent abandoned-finding re-emission loop (ADR-066).
  check_type: all_rules_mapped
  severity: HIGH
  blocking: true
  status: active
```

**Position in rule hierarchy:** `governance.*` rules are meta-rules that audit
the governance system itself. This rule belongs alongside
`governance.remediation.*` peers. It runs after the rule registry is fully
loaded, before any finding is dispatched.

**Scope:** Active rules only. Rules with `status: inactive`, `status: draft`,
or `status: deprecated` are excluded. A rule that cannot produce findings cannot
produce the loop; it need not be mapped.

### `auto_remediation.yaml` self-entry

The new rule `governance.remediation.all_rules_mapped` must itself be mapped in
`auto_remediation.yaml`. The correct entry is `DELEGATE` — a meta-governance
violation requires human review of the rule registry, not an automated fixer:

```yaml
governance.remediation.all_rules_mapped:
  action: fix.modularity
  confidence: 0.40
  risk: high
  description: >
    An active rule has no auto_remediation.yaml entry — the structural
    invariant established by ADR-066 is violated. Resolution: add a
    DELEGATE entry for the unmapped rule. Non-automatable; requires governor
    review of the rule registry. Routed to governor inbox as DELEGATE.
  status: DELEGATE
```

This is a self-referential invariant application: the enforcement rule for the
invariant is itself subject to the invariant.

---

## Consequences of violation

When an active rule has no `auto_remediation.yaml` entry:

1. `ViolationRemediatorWorker` silently skips the finding.
2. The finding is never dispatched, never delegated, never surfaced.
3. The finding ages to `abandoned` within one TTL cycle.
4. `blackboard_query_service.py:103` excludes `abandoned` from the active set;
   the dedup guard does not fire.
5. The next audit cycle re-emits the finding as if it were new.
6. The loop repeats every audit cycle indefinitely.
7. Abandoned finding count grows; convergence signal becomes unreliable;
   governance debt accrues silently.

At the rates observed (4,282 abandoned findings for a single rule over 48 hours),
an unmapped rule is a convergence-blocking defect, not a minor oversight.

---

## Relation to existing decisions

| ADR | Relationship |
|---|---|
| ADR-029 | Established that `ViolationExecutorWorker` must not claim unmapped findings as unresolvable. ADR-066 extends the obligation upstream: the mapping must exist before the executor is consulted. |
| ADR-007 | Introduced `modularity.class_too_large` without an `auto_remediation.yaml` entry (per original decision text). ADR-066 supersedes that omission; any rule introduced without a map entry is a constitutional gap from the moment the rule becomes `active`. |
| ADR-038 | Circuit-breaker on repeated proposal failures. ADR-066 addresses a distinct failure mode: no proposal is ever created, so the circuit-breaker never fires. The loop is invisible to ADR-038. |
| ADR-031 | Introduced `architecture.path_access.no_hardcoded_runtime_dirs` with an `ACTIVE` entry already in place. That sequencing — rule + map entry authored together — is the correct pattern ADR-066 mandates. |

---

## Implementation note

The `governance.remediation.all_rules_mapped` rule implementation and its
`auto_remediation.yaml` self-entry are out of scope for this ADR. This ADR
establishes the constitutional decision and the invariant. Implementation
tracking: #418.

The `auto_remediation.yaml` self-entry (shown above under "Mechanism") is a
`.intent/` file change and must be applied by the governor, not by Claude Code.

---

## Appendix: four-rule post-mortem summary

All four rules that produced abandoned-finding loops during the 2026-05-21 audit
period share one structural cause: the rule was activated before its
`auto_remediation.yaml` entry existed. In each case the loop ran undetected
until convergence monitoring surfaced the diverging signal. The ADR-038
circuit-breaker did not fire because no proposals were created. The loop was
invisible to all existing governance instruments except the raw finding count.

`governance.remediation.all_rules_mapped` would have caught each of these at
the audit cycle immediately following rule activation — before any abandoned
finding was created.
