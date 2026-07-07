---
kind: adr
id: ADR-064
title: ADR-064 — fix_actions.py capability_tagging body→will closure
status: accepted
---

<!-- path: .specs/decisions/ADR-064-fix-actions-capability-tagging-body-will-closure.md -->

# ADR-064 — fix_actions.py capability_tagging body→will closure

**Status:** Accepted
**Date:** 2026-05-19
**Governing paper:** `.specs/papers/CORE-Mind-Body-Will-Separation.md`
**Authors:** Darek (Dariusz Newecki)
**Deadline:** 2026-09-16 (120 days)
**Closes:** Fix-actions bullet of #313 (fix_actions.py exclude added in `5201b3b6`)
**Relates to:** ADR-049 D3 (closure ADR + deadline requirement),
CORE-Mind-Body-Will-Separation.md §5.4 Body→Will prohibition

---

## Context

`src/body/atomic/fix_actions.py:666` contains a lazy
(function-scoped) import inside the body of
`action_fix_capability_tagging`:

```python
from will.self_healing.capability_tagging_service import main_async as tag
```

This violates `architecture.layers.no_body_to_will`
(`layer_separation.yaml` RULE 12) under the expanded bare-prefix
`forbidden:` list (ADR-049 D1). The exclude entry for this file was
added in commit `5201b3b6` (`feat(intent): no_body_to_will — exempt
fix_actions.py (ADR-049 D3)`) to keep the audit clean while a closure
ADR was authored. This is that ADR.

The import is required because:

- `fix.capability_tagging` is an `@atomic_action`-registered Body
  action that the proposal-driven remediation path dispatches via
  the `POST /v1/fix/run/{fix_id}` route.
- The actual capability-tagging logic — `CapabilityTaggerAgent` and
  its main-async entrypoint — lives in
  `src/will/self_healing/capability_tagging_service.py` because it
  uses `will/orchestration` services (the cognitive service for LLM
  capability-name suggestions, the knowledge service for symbol
  context retrieval).
- The body atomic action is a thin dispatch wrapper: it opens a DB
  session, hands `cognitive_service` and `knowledge_service` to the
  Will-layer function, and reports an `ActionResult`. It contains no
  capability-tagging logic of its own.

The docstring at `fix_actions.py:658–663` correctly identifies the
pattern: capability tagging is a Will responsibility because it
involves LLM reasoning over architectural context, but the dispatch
surface must live in Body to participate in the atomic-action
registry.

---

## Why this is structurally harder than a one-line move

The closure path is named in the existing YAML comment at
`layer_separation.yaml:277–280`: "Structural fix requires extracting
a Body-layer service facade that capability_tagging delegates
through."

This requires:

- Defining a Body-layer service facade (e.g.
  `body.services.capability_tagging_dispatch.CapabilityTaggingService`)
  that owns the public interface Body uses.
- Inverting the dependency: the Will-layer `CapabilityTaggerAgent`
  registers itself or is constructed at composition time and the Body
  service holds a reference, not the other way around.
- Either keeping `main_async` in Will and making the Body facade call
  it via a constructor-injected callable, or moving `main_async` into
  the Body facade and demoting `CapabilityTaggerAgent` to a
  Will-internal helper.

The work touches the Will-layer service file, the new Body service,
the lifespan composition (to wire the dependency), and the
`fix_actions.py` call site. This is a multi-file refactor — out of
scope for the #313 doctrine-rule parity closure.

---

## Closure path

**Option A — Body-layer dispatch facade with injected callable.**

Add `CapabilityTaggingService` in `src/body/services/` accepting a
`main_async`-shaped callable in its constructor. The lifespan
composition wires the Will-layer `main_async` into the service at
startup. `fix_actions.py:action_fix_capability_tagging` calls
`core_context.capability_tagging_service.run(...)`. The Body file no
longer imports from Will; the wiring is constructor-time in the
composition root, which is the architecturally clean location for
cross-layer references.

**Option B — Move `main_async` to Body, keep agent in Will.**

`main_async` becomes a Body function that constructs the
`CapabilityTaggerAgent` (Will) from injected services. The Body
action calls the Body function; the agent stays in Will but is
treated as a Will-internal helper, not a public entrypoint.

Option A is preferred on first reading because it preserves the
agent's identity as the entrypoint and adds only a thin facade —
Body's surface grows by one service, Will keeps its main_async
function. Option B inverts the natural ownership (agent in Will,
public main_async in Body) which would be confusing for readers.

---

## Deadline

**2026-09-16** (120 days from acceptance). Matches ADR-051 / ADR-062 /
ADR-063.

- Warning state: audit emits a warning when this date passes if the
  exclude entry is still present.
- Blocking state: 30 days past deadline (2026-10-16), the entry is
  treated as a rule violation; `fix_actions.py` fails audit until
  refactored or until this ADR is amended.

---

## Consequences

**Positive:**

- The body→will exclude in `fix_actions.py` has a named refactor path
  and a deadline. The "TBD" deadline marker in
  `layer_separation.yaml` can be replaced with `2026-09-16` and a
  back-reference to this ADR.
- The closure path here (Body-layer facade) is the same shape used
  to close `context/service.py`'s body import in #315 Tier B/2
  (`BrainServicesProvider` protocol, commit `c9332d73`). The pattern
  is precedented; only the specific service identity differs.

**Negative:**

- The refactor adds one Body service and one wiring point at the
  lifespan composition root. Each consumer of `fix.capability_tagging`
  continues to carry the Will dependency until the refactor lands.

**Neutral:**

- The lazy-import form is honest about what it is: a deferred
  cross-layer reference to keep cold-path cost bounded. The closure
  path eliminates the cross-layer reference entirely; cold-path cost
  becomes constructor-time cost paid at startup, which is the right
  trade.

---

## Verification

This ADR is verified when, on or before 2026-09-16:

1. Either `src/body/atomic/fix_actions.py` no longer imports from
   `will.*` (eagerly or lazily), or this ADR has been amended with a
   new deadline and named blocker.
2. The `src/body/atomic/fix_actions.py` entry in
   `architecture.layers.no_body_to_will` `excludes:` is removed (if
   refactored) or its comment is updated to reference this ADR's new
   deadline.

---

## References

- ADR-049 — Doctrine-rule parity; D3 sets the closure ADR + deadline
  requirement that this document satisfies.
- ADR-051 — file_handler.py closure (precedent for this ADR's shape).
- `src/body/atomic/fix_actions.py:644–689` — `action_fix_capability_tagging`
  atomic action and the lazy `will.self_healing` import.
- `src/will/self_healing/capability_tagging_service.py` — Will-layer
  `main_async` and `CapabilityTaggerAgent`.
- `.intent/enforcement/mappings/architecture/layer_separation.yaml`
  RULE 12 `excludes:` block (and the structural-fix note at
  `layer_separation.yaml:277–280`) — the entry this ADR closes.
- Commit `5201b3b6` — `feat(intent): no_body_to_will — exempt
  fix_actions.py (ADR-049 D3)` (added the exclude in anticipation of
  this ADR).
- Commit `c9332d73` — `BrainServicesProvider` protocol injection
  (precedent for the Body-facade Option A pattern).
