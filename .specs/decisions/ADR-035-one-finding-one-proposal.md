---
kind: adr
id: ADR-035
title: ADR-035 — One Finding, One Proposal
status: accepted
---

<!-- path: .specs/decisions/ADR-035-one-finding-one-proposal.md -->

# ADR-035 — One Finding, One Proposal

**Date:** 2026-05-11
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Closes:** #284

---

## Context

`ViolationRemediatorWorker` groups open findings by `action_id` and
creates one proposal per action group. This means all findings that map
to the same action — regardless of which file they concern — are bundled
into a single proposal.

Observed instance: proposal `946be9e0` bundled 8 `modularity.needs_split`
findings across 8 unrelated files into one `fix.modularity` proposal.
The proposal was rejected because one suspicious file in the batch was
sufficient to block approval of the other seven.

The batching behaviour reflects an execution optimisation: fewer proposals,
fewer DB writes, fewer approval interactions. It was an acceptable posture
during loop liveness work (ADR-014: liveness before quality). At A3, where
the governor's role is reviewing what the system cannot decide alone, it
becomes a governance defect.

---

## Why batching violates the governance model

Every finding is a detected violation of a specific rule in a specific
file. That is the atomic unit of governance concern. The governor's
approval decision over file A is independent of their decision over file
B — even when both map to the same remediation action. Batching forces
an all-or-nothing decision across independent findings.

This violates three properties the governance model requires:

1. **Approval granularity.** The governor approves or rejects a unit of
   work. Under batching, the unit is an action group, not a finding. The
   governor cannot approve the fix for file A while rejecting the fix for
   file B — they must reject the whole batch or accept the risk of the
   whole batch.

2. **Consequence chain resolution.** The chain requires Finding → Proposal
   → Execution → File change as a 1:1:1:1 path. A batch proposal breaks
   this: N findings → 1 proposal → N file changes. Failures at execution
   cannot be attributed to a specific finding. Revival under §7a is
   coarse — all findings in the batch revive together.

3. **UNIX composition.** A proposal is a unit of work with one input
   (one finding), one transformation (one fix), and one verifiable output
   (finding resolved or revived). Batching is a script, not a primitive.
   Failure modes are hidden; the chain loses resolution.

The question of *who* approves a proposal — the governor or the system
via auto-approval — is governed separately in `action_risk.yaml` and is
unchanged by this ADR. The auto-approval delegation the governor has
pre-granted to safe actions (e.g. `fix.format`) remains valid per-finding
as it was per-batch.

---

## Decision

### D1 — One finding, one proposal

`ViolationRemediatorWorker` must create one proposal per finding, not one
proposal per action group. The grouping key changes from `action_id` to
`(action_id, file_path)`. Each proposal's `scope.files` contains exactly
one file.

### D2 — Deduplication preserved

The existing deduplication contract is preserved at the per-finding level:
if an active proposal already exists for the same `(action_id, file_path)`
pair, the finding is subsumed under that proposal. No duplicate proposals
are created for the same (action, file) unit.

### D3 — Batch-safe classification deferred

Certain actions (e.g. `fix.format`, `fix.imports`) apply a mechanical
transformation with no architectural judgment required. A future ADR may
introduce a `proposal_scope: per_file | batch` flag in `action_risk.yaml`
to allow governed batch proposals for those actions. Until that ADR lands,
all actions use per-finding scoping. No batch exemptions are in effect.

### D4 — Consequence chain integrity

With per-finding proposals, the consequence chain recovers full resolution:
each Finding links to exactly one Proposal, which links to exactly one
execution, which changes exactly one file, which produces exactly one
re-audit finding. The chain is unambiguous end-to-end.

---

## Implementation

The change is localised to `ViolationRemediatorWorker._process_findings()`
(or equivalent grouping site). The action group accumulator changes from:

```
action_groups: dict[action_id, list[finding]]
```

to:

```
action_groups: dict[(action_id, file_path), finding]
```

Each entry in the new structure produces one proposal. The rest of the
proposal creation, deduplication, and deferred-to-proposal transition
logic is unchanged.

---

## Consequences

- Governor inbox entries increase in count but decrease in decision
  complexity. Each entry is a single, attributable, reversible change.
- Execution failures are isolated. A failed `fix.modularity` on one file
  revives only that file's finding — not the findings for seven other files.
- The consequence chain is queryable at single-finding resolution.
- Proposal volume increases proportionally to finding count for
  moderate-impact actions. This is the correct trade-off at A3.

## References

- `ViolationRemediatorWorker` — `src/will/workers/violation_remediator.py`
- `action_risk.yaml` — `.intent/enforcement/config/action_risk.yaml`
- ADR-014 — development-phase priority (liveness before quality; this ADR
  reverses the first application of that principle as it applied to
  proposal scoping)
- ADR-015 — consequence chain attribution (D4 of this ADR completes the
  chain integrity ADR-015 established)
- Issue #284 — observed instance (proposal 946be9e0, 8-file batch)


## Amendment — 2026-06-15 — Assisted-lane multi-file exception (ADR-109 D3)

**This ADR's one-finding-one-proposal scoping remains the rule for the
*autonomous* loop. ADR-109 (Assisted Remediation Lane) D3 adds a narrow,
human-gated exception for the *assisted* lane.**

ADR-035's per-file scoping exists for **approval granularity under autonomous
trust** — the governor could not be asked to approve a bundle the daemon
assembled (the §"Why batching violates the governance model" argument). That
concern is dissolved when a human reviews the actual multi-file diff: the unit
of approval becomes the coherent change the human inspected, not a
machine-assembled batch.

Therefore, in the assisted remediation lane only (ADR-109), a single proposal
MAY span N interdependent files and be approved as one unit, on these
conditions:

- `approval_required = true` is **mandatory** — the human diff-review is the
  precondition that licenses the multi-file scope.
- The diff must clear the in-sandbox validation gate (ADR-109 §Mechanism 4)
  before it is approvable.
- The commit set derives from sandbox production with joint authorship
  (ADR-101 D1/D5).

The autonomous remediator (`ViolationRemediatorWorker`) is **unchanged**: it
still emits one proposal per `(action, file)`. The exception is unreachable
without a human at the gate. See ADR-109 D3 for the full decision; tracked in
issue #655.
