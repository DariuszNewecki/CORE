---
kind: adr
id: ADR-029
title: ADR-029 — Explicitly map non-automatable rules in RemediationMap
status: accepted
---

# ADR-029 — Explicitly map non-automatable rules in RemediationMap

**Status:** Accepted
**Date:** 2026-05-08
**Governing paper:** `.specs/papers/CORE-Enforcement-Completeness.md`
**Authors:** Darek (Dariusz Newecki)

---

## Context

ADR-007 introduced `modularity.class_too_large` as a non-automatable
rule — class-level refactoring requires human architectural judgment
and cannot be safely delegated to the autonomous remediation loop.
ADR-007's implicit assumption was: absence from `auto_remediation.yaml`
means human-only routing. The rule was declared, the finding was
expected to surface on the Blackboard, and the human would act.

That assumption is broken by `ViolationExecutorWorker`.

The two-path remediation architecture is:

- **Proposal Path** — `ViolationRemediatorWorker` claims findings that
  ARE mapped in `auto_remediation.yaml`, creates Proposals, executes
  via `ProposalConsumerWorker`.
- **ViolationExecutor Path** — `ViolationExecutorWorker` claims
  findings that are NOT mapped — the "discovery fallback" for rules
  with no known remediation. It uses LLM to construct a fix candidate.

A rule absent from the map is claimed by `ViolationExecutorWorker`,
not left for the human. ADR-007 declared `modularity.class_too_large`
non-automatable but left it unmapped, which routes it directly into
the LLM-driven fallback — the opposite of the intended behavior.

## Decision

Non-automatable rules MUST be explicitly mapped in
`auto_remediation.yaml` with `confidence < 0.50` (PENDING threshold).
This excludes them from the `ViolationExecutorWorker` fallback while
keeping the finding visible on the Blackboard for human action.

An absent rule and a PENDING-mapped rule have identical human-visible
outcomes (finding stays open, no autonomous fix attempted) but
opposite autonomous-loop outcomes. Explicit PENDING mapping is the
constitutional form — it records the deliberate decision that this
rule requires human judgment.

**First application:** `modularity.class_too_large` — added to
`auto_remediation.yaml` with `confidence: 0.0` and a rationale note.

**General principle:** any rule declared non-automatable in its ADR
or rule document MUST have a corresponding PENDING entry in
`auto_remediation.yaml`. Absence is not a valid signal for
human-only routing.

## Consequences

**Positive:**
- `modularity.class_too_large` findings are no longer claimed by
  `ViolationExecutorWorker` and fed into LLM-driven fix attempts that
  cannot succeed.
- The RemediationMap becomes a complete picture of every rule's
  remediation posture — mapped (automatable) or PENDING (human-only).
  Absence from the map becomes a genuine gap rather than a policy.
- The 1-rule-to-1-method pattern from ADR-007 is preserved; the
  enforcement boundary is now also preserved in the map.

**Negative:**
- Every future non-automatable rule requires an explicit PENDING entry
  at declaration time. This is a small authoring overhead but
  eliminates a silent routing failure.

**Neutral:**
- Existing findings for `modularity.class_too_large` already on the
  Blackboard are unaffected. The change prevents future mis-routing;
  it does not retroactively resolve open findings.

## References

- ADR-007 — `modularity.class_too_large` rule declaration
- `.intent/enforcement/remediation/auto_remediation.yaml`
- `ViolationExecutorWorker` — unmapped-claim path
- `ViolationRemediatorWorker` — mapped-claim path
