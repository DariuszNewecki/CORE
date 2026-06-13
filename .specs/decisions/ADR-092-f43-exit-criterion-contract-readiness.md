---
kind: adr
id: ADR-092
title: 'ADR-092 — F-43 exit criterion: contract-readiness replaces invented-proof'
status: accepted
---

<!-- path: .specs/decisions/ADR-092-f43-exit-criterion-contract-readiness.md -->

# ADR-092 — F-43 exit criterion: contract-readiness replaces invented-proof

**Date:** 2026-06-06
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-06 — drafted under Path A execute-verb authorization, "draft ADR-092 under Path 1", after the governor interrogated whether F-43's exit criterion required inventing its own proof when every other gate item ratified a pre-existing live capability)
**Grounding decisions:** ADR-085 §Context (the 5+3 table whose F-41/F-42/F-43 row this ADR amends) + §D5 (the mechanical-check clause that makes amendment-by-ADR necessary) + §D7 (the on-equal-footing-amendment clause). ADR-089 (precedent — the same surface-and-shape amendment for F-27's exit criterion). ADR-090 D5 (the `supported_actions: []` empty list in artifact_type schema was authored as forward placeholder for F-43; this ADR governs what populating it does or doesn't require). ADR-091 D6 (the F-42→F-43 forward contract — the four items this ADR ratifies and parks selectively).
**Related:** ADR-074 D13 + ADR-080 §D5 — append-only ADR-amendment precedent. ADR-084 D7 §1 — completeness as constitutional commitment; this ADR clarifies that completeness for F-43 is *contract* completeness, not *invented-instance* completeness.

---

## Context

### The criterion being amended

ADR-085's §Context table line 35 reads, for the row that bundles F-41 + F-42 + F-43:

> | | Extension interfaces F-41 + F-42 + F-43 | registry | all three `status: shipping`; one first-party non-code instantiation exists as proof of the plugin-interface contract |

The first half ("all three `status: shipping`") is structural — every feature in the 5+3 table requires its registry row to flip to `shipping`. This ADR does not amend that half.

The second half ("one first-party non-code instantiation exists as proof of the plugin-interface contract") is grammatically a trio-level claim — *one* instantiation total, not one per feature. F-41 and F-42 are now closed against that claim by their own implementations. This ADR amends what the F-43 portion specifically must show to close.

The row in ADR-085 stays verbatim — closure markers and amendments are additive per the same append-only discipline ADR-085 §Context already applies to its own Verification log, and per the ADR-089 precedent that established amendment-of-5+3-rows as an ADR-shaped act on equal footing with the original.

### Why the original criterion does not earn its keep for F-43

F-43 is the only item in the 5+3 list whose exit criterion, as currently written, requires *inventing its own proof* rather than ratifying a pre-existing live capability. The asymmetry across the gate items:

| Item | Pre-existing live target ratified | Invented proof required |
|---|---|---|
| F-10 | Existing audit pipeline | — |
| F-27 | Existing routing infrastructure (after ADR-089 amendment) | — |
| F-40 | Existing API surface | — |
| F-41 | Three pre-existing pipelines (Python AST + intent YAML + spec markdown) | — |
| F-42 | Eleven pre-existing sensors | — |
| F-48 | Existing CLI + packaging | — |
| **F-43** | Nothing — no non-Python action exists in `src/body/atomic/` | The non-Python action would have to be authored to satisfy the gate |

Three problems follow from this asymmetry.

**First, the "one first-party non-code instantiation" criterion is already substantively satisfied by F-41 + F-42.** F-41 declared three artifact_type instances in `.intent/artifact_types/`; two are non-code (`intent_yaml`, `spec_markdown`). F-42 declared eleven sensors carrying `mandate.scope.artifact_type`; several target the non-code artifact_types (`coherence_sensor` → `spec_markdown`; `meta_validator` → `intent_yaml`). The plugin-interface contract is *already proven instantiable* by live work on the sensing-side. Requiring a third instantiation on the action-side, where no consumer exists, is contract-completeness theatre.

**Second, no consumer is waiting for a non-Python action.** Open-issue search (2026-06-06) returns zero open requests for non-Python remediation. Every `fix.*` action in `src/body/atomic/fix_actions.py` operates on Python source (`fix.docstrings`, `fix.format`, `fix.imports`). Inventing a non-Python action to satisfy a posture criterion — without a downstream consumer that would route to it — is precisely the abstraction-without-conviction pattern memory `feedback_protocols_reflex_check` flags.

**Third, the *real* F-43 capability claim is structural, not instantiation-counted.** Per ADR-091 D6 item 3, the load-bearing F-43 commitment is: "actions declaring an unregistered artifact_type fail registration, exactly as sensors do." That is the action-layer registry-coupling enforcement — a single mechanism, verifiable by one test, that closes the F-41 ↔ F-43 boundary the same way ADR-091 D5 Phase 3 closed the F-41 ↔ F-42 boundary for sensors. The presence-or-absence of a non-Python action ships orthogonally to whether the coupling enforcement exists.

### What "contract-readiness" looks like operationally

The new criterion below requires one mechanism with two observable properties, **both observable on the negative path** (the load-bearing claim is refusal, not happy-path dispatch):

1. **Registry-coupling enforcement at the action layer, demonstrated by refusal.** `ActionExecutor.execute()` refuses to dispatch an action whose declared `artifact_type` is not present in the F-41 `IntentRepository.list_artifact_types()` set. The closing test MUST exercise the rejection path — an action declaring an unregistered artifact_type calls `ActionExecutor.execute()` and the call returns a refusal (e.g., `RefusalResult` per the boundary-violation factory, or a documented exception class) rather than dispatching. A happy-path test that dispatches a Python action against the registered `python` type is not sufficient; it satisfies neither D1's wording nor its intent. This is the F-43 analogue of ADR-091 D2's canonical subject format enforcement on the sensor side — a single chokepoint that makes the contract live, not aspirational.
2. **Action-side artifact_type declaration site exists.** At least one atomic action in `src/body/atomic/` declares its target `artifact_type`. The declaration site (decorator field, capability-yaml field, or new YAML surface) is an implementation decision left to the follow-on session (see D4); ADR-092 does not pre-judge it.

The demonstration is a one-shot verification, not an authored second proof. The negative-path rejection test plus the declared action record as a §Verification entry on ADR-085's append-only log.

### Why this is an amendment and not a reframing of ADR-085's intent

Same shape as ADR-089: ADR-085 D5's mechanical-check rule and D7's on-equal-footing-amendment clause together make this ADR the only legitimate surface for changing a 5+3 row's criterion text. The intent of ADR-085 — engineering capacity concentrates on open-operational-completeness until exit — is unchanged. The shape of the F-43 portion of one row changes from "invent a proof" to "ratify the contract enforcement."

---

## Decisions

### D1 — F-43 exit criterion is amended to a contract-readiness demonstration

The F-43 portion of ADR-085 §Context table line 35 is amended from:

> all three `status: shipping`; one first-party non-code instantiation exists as proof of the plugin-interface contract

to (F-43 portion only; F-41 and F-42 portions stay structurally unchanged, both already shipped):

> all three `status: shipping`; F-41 and F-42's non-code instantiations (`intent_yaml` + `spec_markdown` artifact_types, plus the sensors observing them) ratify the trio-level "one first-party non-code instantiation" criterion; F-43 specifically ships when `ActionExecutor.execute()` refuses to dispatch actions whose declared artifact_type is not registered in the F-41 registry (the action-layer registry-coupling enforcement of ADR-091 D6 item 3), and at least one atomic action in `src/body/atomic/` declares its target artifact_type

The original row in ADR-085 stays verbatim; this ADR is the controlling statement of the F-43 exit criterion from the date of acceptance forward. When F-43 is closed, ADR-085's §Context Verification log entry cites this ADR as the criterion source.

### D2 — The `action_supported_by_declaration` coherence rule is parked

ADR-091 D6 item 2 declared a forward contract that F-43 would ship a new `governance.taxonomy.action_supported_by_declaration` rule completing the F-41↔F-42↔F-43 triad alongside `operational_capabilities_decorator_backing` (ADR-079 D9) and `sensor_supported_by_declaration` (ADR-091 D4). This ADR parks that rule with a triggering condition.

The rule is parked because the population it would govern is too small to earn the rule's keep, not because the asymmetry it detects is impossible. Post-D1 the populations are: authored set (every artifact_type's `supported_actions`) stays empty per D5; introspected set is the one atomic action D1 requires to declare its target. The two sets differ by one entry as a structural consequence of this ADR — that *is* the drift class the rule would detect, but with a single asymmetric edge the rule's findings carry no information beyond what D5's own bookkeeping already supplies. Compare to the two existing triad rules at ship time: `operational_capabilities_decorator_backing` caught phantom capabilities in a population of dozens; `sensor_supported_by_declaration` caught the `audit_sensor_governance` ↔ `python.yaml` asymmetry during its own promotion in a population of eleven. The action-support rule's day-one population is one, with the asymmetry pre-declared by D5; firing it would be noise, not signal.

The rule unparks when D5's trigger fires: a second non-Python action ships, raising the introspected-set cardinality and creating a population in which authored-vs-introspected drift could occur *without* being pre-declared by this ADR. At that point a successor ADR-092-A authors the rule with conviction equal to ADR-091 D4's. Until then, the trio is structurally two-of-three on the coherence-rule axis — honest visible governance debt, not regressive: the third rule exists when its drift class earns enforcement.

### D3 — F-41 and F-42's existing non-code instantiations satisfy the trio-level criterion text

The "one first-party non-code instantiation" clause in ADR-085's row was grammatically trio-level (one instantiation, not three). F-41's `intent_yaml` + `spec_markdown` artifact_types and F-42's coherence_sensor / meta_validator sensors targeting them are live first-party non-code instantiations of the artifact_type and sensor contracts; the criterion text is satisfied at the trio level by work already shipped.

This decision concerns *criterion text*, not *F-43 proof*. The sensing-side instantiations do not exercise the action interface and are not proof that F-43's contract is real — D1 alone provides that proof via the registry-coupling refusal demonstration. D3's role is narrow: it forecloses a future-reader misreading in which the trio-level "one non-code instantiation" clause is interpreted as a per-feature requirement that F-43 has not separately met. F-43 has met its specific gate (D1); the trio-level clause is met by F-41 + F-42; D3 records the bookkeeping so the two facts are not conflated.

### D4 — Action-layer declaration site is left to the implementation session

Three viable declaration sites exist for an atomic action's `artifact_type` field:

- The existing `@register_action` decorator in `src/body/atomic/*.py` (AST-walked, symmetric with how `operational_capabilities_decorator_backing` already walks the same decorator).
- The existing `.intent/taxonomies/operational_capabilities.yaml` per-capability entry (augments the live authorization surface that already names every action by capability id).
- A new `.intent/atomic_actions/<id>.yaml` declaration surface (symmetric with `.intent/workers/*.yaml`).

This ADR does not pre-judge which site. The F-43 implementation session selects one with conviction, records the choice in the implementation commit, and lands. The criterion in D1 is site-agnostic — any of the three honestly satisfies "at least one atomic action declares its target artifact_type." If the implementation session surfaces a fourth site, the same logic applies.

### D5 — Unparking trigger for the coherence rule and `supported_actions` population

The `governance.taxonomy.action_supported_by_declaration` rule (D2) and the `supported_actions: []` arrays on artifact_type schemas (currently empty under ADR-090 D5's "empty list permitted until F-43 lands") unpark when **a second first-party non-Python atomic action ships**. The first non-Python action is the D1 gate; the second is the conviction trigger that makes a coherence rule earn its keep. Until then, the arrays stay empty and the rule is unfiled.

Authoring an ADR-092-A at that future point follows ADR-091 D4's shape: rule declaration + taxonomy_gate engine extension + reporting cycle + blocking promotion under live audit.

---

## Consequences

### F-43 ships in ~1–2 sessions, not ~5–8

Under the original criterion + the Option C "new YAML surface" implementation the recon surfaced as the most literal F-42-mirror, F-43 was a ~5–8-session arc (declaration surface + schema + engine extension + reporting cycle + blocking promotion + non-Python action authoring). Under D1 + D2, F-43 collapses to: one decorator field (or equivalent), one ActionExecutor-side enforcement check, one test, one declared atomic action carrying the field. The original ~5–8-session estimate was scoping the wrong thing.

### The 5+3 list closes on capability claims, not contract-surface population

Every other 5+3 item ratifies a capability that already exists. With this amendment, F-43 joins the same pattern: registry-coupling enforcement is the capability claim; whether the action layer ever grows non-Python instances is a downstream consumer question, not a gate question. The 5+3 list returns to its original load-bearing shape (capability completeness) and stops drifting into contract-completeness theatre.

### BYOR commercial story is unchanged

The "extension interfaces" arm of ADR-084's commercial-shape decomposition is the *published contract* — `META/artifact_type.schema.json` (F-41) + the sensor mandate shape (F-42) + the action declaration surface (F-43 under D1). Buyers extending CORE for their own artifact types receive: a documented artifact_type declaration schema, a documented sensor declaration shape, and a documented action-layer registry-coupling guarantee. The commercial story does not require a first-party non-Python action to exist; it requires the contract to be *stable and enforced*, which D1 delivers.

### ADR-091 D6's four-item forward contract becomes "three committed, one parked"

ADR-091 D6 declared four items F-42 committed to on F-43's behalf:

1. Artifact_type list pattern on action declarations — **shipped under D1** (declaration site per D4).
2. Cross-validation invariant via `action_supported_by_declaration` rule — **parked per D2** with D5 trigger.
3. Registry-coupling at registration time — **shipped under D1** (this is the load-bearing F-43 mechanism).
4. Canonical subject format boundary — **shipped under D1** (ActionResult dominant case = no subject format; Blackboard-emitting actions follow ADR-091 D2). F-43 implementation specifies the boundary as part of the registration enforcement.

The parking is honest: item 2 lacks a population to govern today, and ADR-091 D6 was a forward declaration, not a binding promise to land all four under F-43 specifically.

### The implementation session inherits D4's declaration-site choice

The follow-on F-43 implementation session opens with one open design decision (D4's site selection) and a closed gate definition (D1). The recon for that session is bounded — does Option A, B, or C honor `feedback_protocols_reflex_check`'s "fewest new abstraction surfaces" rule? Likely Option A (decorator field, AST-walked) or Option B (augment `operational_capabilities.yaml`); Option C (new YAML kind) earns suspicion because it adds a fourth action-metadata surface to a system that already has three (decorator + `action_risk.yaml` + `operational_capabilities.yaml`).

### Planning doc updates are operational, not constitutional

The amendment lands in three documents:

- This ADR (constitutional) — controlling.
- ADR-085 §Context Verification log, when F-43 closes — references this ADR as the criterion source.
- `planning/CORE-Operational-Completeness.md` §2.1 F-41/F-42/F-43 row "Done" cell, §3 Tier-A, §6 activity log — updated to reflect the new F-43 criterion shape.

The planning-doc updates are operational per ADR-085 D6 and do not require their own ADR amendments.

### Symmetric with ADR-089

ADR-089 amended F-27's exit criterion from a *usage* window to a *capability* demonstration when recon showed the original criterion measured the wrong thing. ADR-092 amends F-43's exit criterion from an *invented instantiation* to a *contract-coupling* demonstration when recon showed the original criterion required authoring its own proof rather than ratifying a live capability. Both follow ADR-085 D7's on-equal-footing-amendment discipline. Both convert a hypothetical-future criterion into a present-tense capability claim that matches the live system.

---

## Verification

- This ADR exists at `.specs/decisions/ADR-092-f43-exit-criterion-contract-readiness.md`.
- ADR-085 §Context table line 35 is unchanged (append-only discipline).
- `planning/CORE-Operational-Completeness.md` §2.1 F-41/F-42/F-43 row "Done looks like" cell is updated to reference this ADR's D1 criterion for the F-43 portion.
- `planning/CORE-Operational-Completeness.md` §3 Tier-A F-43 wording updates from "ready as next feature pickup" (current) to "ready as next feature pickup — registry-coupling enforcement per ADR-092 D1; declaration site per D4."
- `planning/CORE-Operational-Completeness.md` §6 activity log records this amendment with date 2026-06-06 and a one-line summary citing the ADR-089 precedent.
- F-43 GH issue #417 receives a comment recording the amendment and the ADR-092 D1 closure criterion (parallel with the ADR-091 D6 forward-contract comment already on the issue).
- When F-43 closes, the closure entry in ADR-085's §Context Verification log cites ADR-092 D1 as the criterion source and records: (a) the negative-path test result — an action declaring an unregistered artifact_type calls `ActionExecutor.execute()` and the call refuses dispatch (RefusalResult or documented exception class), and (b) the one declared atomic action carrying the artifact_type field. A happy-path-only test result is not accepted as evidence; the load-bearing F-43 mechanism is refusal.
- The `governance.taxonomy.action_supported_by_declaration` rule is *not* filed at F-43 close; it is filed when D5's trigger fires (second non-Python action ships).

---

## References

- ADR-085 §Context (the 5+3 table whose F-41/F-42/F-43 row this ADR amends) + §D5 (mechanical-check) + §D7 (on-equal-footing-amendment).
- ADR-089 — direct precedent. Same surface (a 5+3 row's exit criterion), same shape (capability-replaces-window-or-invented-proof), same drafter under same Path A authorization.
- ADR-090 D5 — the `supported_actions: []` empty-list-permitted clause that this ADR's D5 keeps in effect indefinitely (until the unparking trigger).
- ADR-091 D6 — F-42's four-item forward contract for F-43. This ADR ratifies items 1, 3, 4 and parks item 2.
- ADR-091 D4 — the cognate `sensor_supported_by_declaration` rule that the parked `action_supported_by_declaration` rule would mirror.
- ADR-079 D9 — `operational_capabilities_decorator_backing` cognate.
- ADR-084 D7 §1 — completeness as constitutional commitment. This ADR clarifies that F-43 completeness is contract completeness, not invented-proof completeness.
- `papers/CORE-Features.md` F-43 entry — the capability claim being honored.
- F-43 GH issue #417 — the operational tracking surface.
- `planning/CORE-Operational-Completeness.md` §2.1, §3, §6 — the operational surfaces this ADR triggers updates in.
- Memory `feedback_phase_goal_absorbs_design` — the original F-43 criterion was a mechanism-shaped goal that locked in early and falsified under recon. This ADR interrogates the goal, not the mechanism.
- Memory `feedback_conviction_signal` — defending a feature without conviction means the framing is suspect. F-43 lacked conviction because the criterion asked for invented proof; D1 restores conviction by tying the gate to a real enforcement mechanism.
- Memory `feedback_protocols_reflex_check` — the parked coherence rule + decorator-or-YAML site choice both honor this rule by deferring new abstraction until a population exists for it to govern.
- Memory `feedback_park_cleanup_when_boundary_works` — D2's coherence-rule parking and D5's unparking trigger are the canonical shape of this discipline.
- Memory `feedback_hardening_over_coverage` — F-43 closure under D1 is hardening (the registry-coupling enforcement is a live constraint), not coverage (authoring forward contract surface nobody consumes).
- Memory `feedback_exception_register_growth_trap` — the parked coherence rule's unparking trigger (D5) is the antidote: the rule doesn't accumulate without conviction; it ships when its drift class ships.
