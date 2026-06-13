---
kind: adr
id: ADR-008
title: ADR-008 — Constitutionalize `impact_level`
status: accepted
---

# ADR-008 — Constitutionalize `impact_level`

**Status:** Accepted
**Date:** 2026-04-22
**Closed:** 2026-05-08
**Commit:** ae07f839

---

## Context

`impact_level` — the field that determines whether a Proposal requires
human approval or auto-approves — was declared in Python code, inside
`@register_action(...)` decorators across 22 action registrations in
`src/body/atomic/*.py`.

This is a governance decision — "which actions execute autonomously
versus which require human oversight" — carried in source code, not in
`.intent/` constitutional law. Per the established principle: **no
governance in `src/`**.

The miscategorization of `fix.placeholders` as `moderate` (surfaced
2026-04-22, Decision 1 of Option C) demonstrated the fragility: the
error went unnoticed and produced DRAFT-proposal accumulation every
sensor cycle. Under a constitutional model, the classification is
subject to `.intent/` review and audit, not buried in a decorator
literal.

## Why it was parked

ADR-008 was originally parked on a stated dependency: "the risk model
should coordinate with the second-axis question (confidence,
reversibility, scope size — Decision 3 from the 2026-04-21 handoff)
before externalization."

Investigation in the 2026-05-08 session established that this was a
conflation. Decision 3 was a policy question about whether to
auto-approve `fix.modularity` and `fix.placeholders` — not a schema
prerequisite for externalization. That question was subsequently
resolved by direct reclassification (ADR-014) without a second axis.
The parking rationale was baseless; no blocker remained.

## Decision

Externalize `impact_level` to `.intent/enforcement/config/action_risk.yaml`,
keyed by `action_id`. A loader at `shared.infrastructure.intent.action_risk`
reads the mapping at `ActionExecutor` init time and overlays it onto
registered `ActionDefinition` instances via
`ActionRegistry.apply_risk_config()`. `register_action` no longer
accepts an `impact_level` parameter. Any `action_id` absent from the
mapping raises `ConstitutionalError` at startup.

One-axis schema (safe | moderate | dangerous). A second axis is a
separate ADR if a forcing function ever surfaces.

## What shipped

- `.intent/enforcement/config/action_risk.yaml` — 22 entries
- `src/shared/infrastructure/intent/action_risk.py` — loader, mirrors
  `task_type_phases.py` pattern
- `src/body/atomic/registry.py` — `impact_level` stripped from
  `register_action()`; `apply_risk_config()` added to `ActionRegistry`
- `src/body/atomic/executor.py` — loader + overlay called at init
- 10 action files, 22 sites — `impact_level=` removed from all
  `@register_action` decorators

Audit post-change: PASS, no regressions.

## Consequences

Policy changes to action impact classification are now `.intent/` edits,
not code changes. They are auditable, reviewable, and governed by the
same path as all other constitutional law. G4 gate closed.

## References

- `.intent/enforcement/config/action_risk.yaml`
- `shared.infrastructure.intent.action_risk`
- ADR-014 — development-phase priority; first application was the
  `fix.placeholders` reclassification that exposed the original parking
  conflation
- Commit ae07f839
