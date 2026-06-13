---
kind: adr
id: ADR-074
title: 'ADR-074 — INTERPRET Phase: Contradiction and Ambiguity as Orthogonal Failure
  Modes'
status: accepted
---

# ADR-074 — INTERPRET Phase: Contradiction and Ambiguity as Orthogonal Failure Modes

**Status:** Accepted
**Date:** 2026-05-27
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (interpret-phase failure-mode session 2026-05-27)
**Governing paper:** `.specs/papers/CORE-Phases-as-Governance-Boundaries.md`
**Grounding requirement:** `.specs/northstar/CORE-USER-REQUIREMENTS.md` §3 UR-03 (Gap and Contradiction Reporting)
**Supersedes (partial):** none
**Amends:** ADR-073 D7 (condition 4 wording: list → mapping; corrigendum text in D13)
**Closes:** #459

---

## Context

**Grounding chain:** UR-03 declares two orthogonal non-proceed outcomes for the INTERPRET phase:

> For gaps and ambiguities: CORE asks. CORE does not guess.
> For contradictions: CORE stops until the contradiction is resolved.

(`CORE-USER-REQUIREMENTS.md` §3 UR-03.)

The downstream operationalizing artifact is `.intent/phases/interpret.yaml`, which today declares a single scalar:

```yaml
failure_mode: clarify
```

with a `notes:` field that justifies the value as follows:

> Failure mode is 'clarify' rather than 'block' because ambiguous input should
> result in dialogue, not rejection.

The justification is sound *for ambiguity* and silent on *contradiction*. UR-03 names two failure classes; the YAML exposes one response strategy. This is conflation, not just under-specification: a singular scalar field cannot, by shape, carry two distinct response strategies for two distinct failure classes. Any value the field holds either misrepresents one class (today, `clarify` cannot represent UR-03's "CORE stops") or fails to represent the other.

**Empirical evidence the conflation matters.** ADR-073 D7's SPECGAP check at `src/mind/coherence/checks/specgap.py` actively flags UR-03 candidates against the INTERPRET phase because `clarify` does not match any of the halt-class action verbs in the `.intent/enforcement/config/normative_markers.yaml` register (`fail`, `stop`, `block`, `reject`, `abort`, `halt`, `refuse`, `prevent`). Two such candidates (`252f6707`, `f6206305`) currently sit dismissed-in-DB pending this ADR per the 2026-05-26 / 2026-05-27 CCC clearance arc. The fix to the phase YAML is the constitutional resolution; the candidates and their entire class then stop emitting on subsequent runs.

**Three drifting vocabularies were observed during recon.** The conflation has spread beyond the YAML:

| Surface | Vocabulary | Source |
|---|---|---|
| `.intent/phases/*.yaml` | `block`, `clarify` | interpret-phase notes + sibling phases |
| `src/will/orchestration/workflow_orchestrator.py:192` | `block`, `warn` (`clarify` silently falls through) | code |
| `.intent/constitution/CONSTITUTIONAL-WORKFLOWS.md:102,115` | `block`, `warn`, `continue` | constitution doc |

No two surfaces agree. There is no canonical `failure_mode` enum in `.intent/META/enums.json`. This ADR is also the constitutional moment to bring the vocabulary under closed-enum discipline (per [[feedback_enum_subset_canonicalize_and_fail_closed]] / ADR-073 D9 precedent / issue #460 runtime pattern).

**Scope question (other phases).** A phase-by-phase audit during recon found that today only INTERPRET has demonstrated conflation. The other five phases (`parse`, `load`, `audit`, `runtime`, `execution`) declare `failure_mode: block` and have a single demonstrated failure class apiece (illegibility, inconsistency, rule-violation, action-deny, mutation-failure respectively). Candidate distinct classes exist for each (e.g., `audit` advisory-vs-blocking, `execution` partial-commit-rollback) but are not currently confused in the YAML — the singular `block` is accurate for what those phases do today. The schema change in this ADR applies to all six for shape consistency; the **vocabulary expansion** is INTERPRET-only in v1, with candidate expansions for sibling phases left as governor-reviewable TBD per the [[feedback_governance_vocab_too_much_with_tbd]] discipline.

---

## Decision

### D1 — Failure-class taxonomy for INTERPRET

INTERPRET has exactly two constitutional failure classes, derived from UR-03:

| Failure class | Trigger | UR-03 directive | Response strategy |
|---|---|---|---|
| `ambiguity` | Input is unclear, under-specified, or has gaps | "CORE asks. CORE does not guess." | `clarify` — dialogue with user |
| `contradiction` | Input is internally inconsistent | "CORE stops until the contradiction is resolved." | `block` — halt; do not proceed |

These classes are **orthogonal**: a single user input may be ambiguous, contradictory, both, or neither. The phase implementation MUST distinguish the two at detection time and dispatch the corresponding response.

### D2 — Schema migration: `failure_mode:` (scalar) → `failure_modes:` (map)

`.intent/phases/*.yaml` migrates from a singular scalar field to a map of failure-class → response-strategy:

```yaml
# BEFORE (interpret.yaml)
failure_mode: clarify

# AFTER (interpret.yaml)
failure_modes:
  ambiguity: clarify
  contradiction: block
```

```yaml
# BEFORE (sibling phase, e.g. parse.yaml)
failure_mode: block

# AFTER (sibling phase, e.g. parse.yaml)
failure_modes:
  illegibility: block
```

(Per-phase failure-class names for sibling phases are governor-authored per D8.)

The map form is canonical (not a list) because it is declarative about which class triggers which response. A list form would leave the class-to-response binding implicit and reintroduce conflation as soon as a second response strategy is added to any phase.

ADR-073 D7 condition 4 reads `failure_modes:` as a list. ADR-074 D2 delivers it as a mapping. The two shapes are not interchangeable: a JSON Schema validator declaring `"type": "array"` rejects a mapping, and SPECGAP's coverage check at `src/mind/coherence/checks/specgap.py` cannot iterate "list elements" of a YAML map. D13 issues a wording corrigendum amending D7's "list" to "mapping" so ADR-073 and ADR-074 are formally coherent. D7's underlying logic (action-verb coverage of the response-strategy surface) is preserved unchanged: a map's `.values()` collection is iterable identically to a list's elements. The consumer is updated to read map values in the same change-set (per D9).

### D3 — Canonical `failure_mode` enum in `.intent/META/enums.json`

A new closed enum `failure_mode` is added to `.intent/META/enums.json` declaring the response-strategy vocabulary:

```json
"failure_mode": {
  "description": "Response strategy a phase invokes when a constitutional failure of a specific class occurs. ...",
  "type": "string",
  "enum": [
    "block",
    "clarify"
  ]
}
```

**v1 vocabulary is restricted to the two strategies INTERPRET demonstrably requires** (`block`, `clarify`). Tokens that appear in adjacent surfaces but are not yet operationalized are intentionally not included as enum members; they are documented in this ADR for governor review:

- `warn` — appears in `workflow_orchestrator.py:197` and CONSTITUTIONAL-WORKFLOWS.md. Used today by no phase YAML. Candidate semantic: "log and continue." **Status:** TBD / governor review. Include only if a concrete phase failure class motivates it.
- `continue` — appears in CONSTITUTIONAL-WORKFLOWS.md. No code consumer. Candidate semantic: "noop on failure." **Status:** TBD / governor review.
- `defer` — not in any surface today. Candidate for INTERPRET's third class if "input depends on context not yet available" becomes a distinguished class. **Status:** TBD / governor review.
- `escalate` — not in any surface today. Candidate for a "raise to human governor" strategy distinct from `block`. **Status:** TBD / governor review.

Per the [[feedback_governance_vocab_too_much_with_tbd]] discipline, these are listed here so the governor decides inclusion/exclusion rather than the vocabulary growing implicitly through future PRs.

### D4 — Closed-enum subset for phase YAMLs

A subset enum is **not** required for v1 because all six phase YAMLs operate over the same `failure_mode` vocabulary. (The `worker_phase` / `component_phase` subset pattern from issue #460 applies when only some consumers may use some values; here every phase may use every value.) If a future strategy is restricted to specific phases, a subset is declared at that point per the issue #460 precedent.

### D5 — Failure-class vocabulary discipline

Failure-class names (`ambiguity`, `contradiction`, `illegibility`, …) are **per-phase YAML keys**, not a global closed enum, in v1. A global `failure_class` enum could be introduced in a follow-up ADR if cross-phase use proves real, but in v1 each phase declares its own failure classes locally. Rationale:

- Failure classes are tightly coupled to a single phase's domain (`illegibility` is meaningless in `interpret`; `contradiction` is meaningless in `parse` — parse already operates on syntactically-validated input).
- Premature global enumeration would force conceptual fitness across phases that share no failure semantics.
- The map-form schema (D2) makes drift detectable per-phase even without a global enum.

Governor reviews D5 against personal preference; if a global enum is desired, the change-set adds it and constrains the keys of the `failure_modes:` map via JSON Schema `propertyNames` with `$ref` to `enums.json#/definitions/failure_class`.

### D6 — Phase YAML schema

A new `.intent/META/phase.schema.json` is registered, validating the shape of `.intent/phases/*.yaml`. The schema $refs `enums.json#/definitions/failure_mode` for the values of `failure_modes:`. `phases` is added to `validated_directories` in `.intent/META/intent_tree.yaml`.

Drafted schema body (governor reviewable):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CORE Phase Definition",
  "type": "object",
  "required": ["phase_type", "description", "failure_modes", "authority"],
  "properties": {
    "phase_type": { "$ref": "enums.json#/definitions/phase" },
    "authority": { "$ref": "enums.json#/definitions/authority" },
    "failure_modes": {
      "type": "object",
      "minProperties": 1,
      "additionalProperties": { "$ref": "enums.json#/definitions/failure_mode" }
    }
    // … (description, inputs, outputs, constitutional_requirements,
    //     permitted_actions, forbidden_actions, success_criteria,
    //     notes, implementation, max_retries, agent_role, llm_tier)
  }
}
```

The cross-META `$ref` to `enums.json` requires the loader pattern established in [[feedback_meta_cross_ref_needs_bootstrap_resolver]] — `src/shared/infrastructure/intent/intent_validator.py` must continue to use a `RefResolver` pre-loaded with every META schema URI. No new bootstrap is required if the loader already iterates `.intent/META/*.schema.json`.

### D7 — Consumer-code update: workflow orchestrator

`src/will/orchestration/workflow_orchestrator.py:192` migrates from scalar-string to map-of-class-to-strategy. The decision rule is updated per D2's semantics:

```python
# OLD
failure_mode = phase_def.get("failure_mode", "block")
if failure_mode == "block":
    break
if failure_mode == "warn":
    continue

# NEW
failure_modes = phase_def.get("failure_modes", {})
strategies = set(failure_modes.values())
if "block" in strategies:
    break
if "clarify" in strategies:
    # v1: surface the clarification requirement and halt pending dialogue.
    # A future ADR specifies the dialogue surface; until then, conservative halt.
    logger.warning("⚠️  Phase requires clarification; halting workflow")
    break
```

The current silent fall-through behaviour for `clarify` (neither `block` nor `warn` matches, loop body falls through to the next phase without break or continue) is a latent governance bug — it allows INTERPRET to "succeed-by-doing-nothing" when ambiguity is detected. This ADR makes the behaviour explicit: clarification halts the workflow conservatively in v1 until a clarification-dialogue surface is specified.

The `warn` token's code path is retained as dead code for back-compat *only if* the governor wants to preserve it for a future TBD vocabulary expansion; per D3 the v1 enum excludes `warn`, so the cleanest move is to delete the dead branch entirely.

### D8 — Sibling-phase YAML migration

The following five YAMLs migrate to the map form with their existing single failure class made explicit. Class names are governor-reviewable; drafted values per the recon reading:

```yaml
# parse.yaml
failure_modes:
  illegibility: block

# load.yaml
failure_modes:
  inconsistency: block

# audit.yaml
failure_modes:
  rule_violation: block

# runtime.yaml
failure_modes:
  action_denied: block

# execution.yaml
failure_modes:
  mutation_failure: block
```

These class names are **drafts** for governor amendment before the change-set lands. They preserve the v1 vocabulary at one strategy per sibling phase (`block`) and surface the *named* class so future expansion does not have to fight the schema.

### D9 — SPECGAP consumer migration

`src/mind/coherence/checks/specgap.py`'s `_load_phase_failure_modes` (line 117) and `_verbs_covered_by` (line 182) migrate to read the map form:

- `_load_phase_failure_modes` returns `dict[str, dict[str, str]]` keyed by phase, value is the failure-class → strategy map.
- The coverage check iterates the map values: if ANY response-strategy value (e.g., `block`) literal-matches an action verb in the normative-marker register, the phase is considered to address the UR's halt-class signal. Failure-class keys (e.g., `contradiction`) are also string-matched against the action-verb register as an additional signal — a phase that names `contradiction` as a class is operationalizing UR-03's contradiction directive regardless of which strategy it pairs with.

Result: INTERPRET's new `failure_modes: { ambiguity: clarify, contradiction: block }` matches under TWO independent signals: `contradiction` (key) and `block` (value). UR-03 SPECGAP candidates against INTERPRET stop emitting.

### D10 — Drift-guard test

A test mirroring `tests/intent/test_phase_enum_canonical_alignment.py` is added to assert:

1. `failure_mode` enum members in `enums.json` are exhaustive against the union of values used in `.intent/phases/*.yaml`.
2. The set of strategies recognized in `workflow_orchestrator.py` is exactly the `enums.json#/definitions/failure_mode` set (no silent fall-through for unrecognized values).
3. SPECGAP coverage check recognizes every value in the enum.

Drift in any direction fails the test, per the [[feedback_enum_subset_canonicalize_and_fail_closed]] runtime pattern.

### D11 — Notes-field rewrite for `interpret.yaml`

The existing `notes:` field justifies a singular value the new schema no longer holds. It is replaced with a passage grounded in UR-03:

```yaml
notes: >
  INTERPRET is the first constitutional phase. It does NOT have authority to
  execute - only to propose task structures that will be validated in subsequent
  phases.

  Per UR-03 (CORE-USER-REQUIREMENTS §3), INTERPRET has two orthogonal failure
  classes: ambiguity (input unclear → CORE asks via the `clarify` strategy) and
  contradiction (input internally inconsistent → CORE stops via the `block`
  strategy). These are not substitutable: ambiguity is missing-input that the
  user can supply; contradiction is malformed-input that the user must resolve.
  Modeling them as a single failure_mode value erases UR-03's distinction.

  This phase completes the Mind-Body-Will architecture by giving the Will layer
  a constitutional entry point with clear boundaries.
```

### D12 — Migration posture

Implementation lands as a single change-set per the [[feedback_intent_specs_draft_default]] discipline (ADR acceptance precedes code):

1. `.intent/META/enums.json` — add `failure_mode` enum (D3).
2. `.intent/META/phase.schema.json` — new file (D6).
3. `.intent/META/intent_tree.yaml` — add `phases` to `validated_directories` (D6).
4. `.intent/phases/*.yaml` — six files migrated to map form (D2, D8, D11).
5. `src/will/orchestration/workflow_orchestrator.py` — consumer update (D7).
6. `src/mind/coherence/checks/specgap.py` — consumer update (D9).
7. `tests/intent/test_phase_failure_mode_canonical_alignment.py` — new drift-guard test (D10).

The change-set is purely additive on the META side (new enum, new schema, new validated directory) and a shape-migration on the data side (scalar → map). It does not change runtime semantics for sibling phases (their single `block` strategy still produces the same orchestrator behaviour); it only changes runtime semantics for INTERPRET, which today silently falls through on `clarify` and after this ADR halts on either failure class.

### D13 — ADR-073 D7 corrigendum: list → mapping

ADR-073 D7 condition 4 reads:

> The phase YAML exists with a non-empty `failure_modes:` list.

ADR-074 D2 delivers `failure_modes:` as a mapping (failure-class → response-strategy), not a list. The two schemas are not interchangeable: a JSON Schema validator using `"type": "array"` rejects a mapping, and SPECGAP's consumer code at `src/mind/coherence/checks/specgap.py` cannot iterate "list elements" of a YAML mapping.

D7's underlying logic is shape-agnostic: the action-verb coverage check (D9, and ADR-073 D7 condition 5) iterates the response-strategy surface — a map's `.values()` collection is iterable identically to a list's elements. D7 was written assuming list because list was the obvious plural shape at the time; ADR-074 D2 selects mapping for the declarative class-to-strategy binding it carries.

The corrigendum is therefore a wording amendment, not a logic supersession. Applied via the append-only Note pattern per [[feedback_append_only_adr_closure_marker]] (precedent: 2026-05-26 R3b sweep, three applications). The marker text the governor appends to the end of `.specs/decisions/ADR-073-ccc-scanner-redesign.md`:

```markdown
---

## Note — 2026-05-27 (per ADR-074 D13 corrigendum)

D7 condition 4 reads:

> The phase YAML exists with a non-empty `failure_modes:` list.

Per ADR-074 D2, `failure_modes:` is declared as a mapping (failure-class → response-strategy), not a list. The condition reads:

> The phase YAML exists with a non-empty `failure_modes:` mapping.

D7's logic is unchanged: condition 5's action-verb coverage check iterates the response-strategy surface, which is identically iterable from a map's `.values()` collection as from a list's elements.

Authoritative artifact: ADR-074 §D2, §D13.
```

**Mutation posture:** governor-applied per [[feedback_intent_specs_draft_default]]. Claude Code drafts the marker text in this ADR; appending it under `.specs/decisions/ADR-073-…` is governor action.

---

## Alternatives Considered

**A1 — Keep `failure_mode: clarify` and extend the SPECGAP synonym register so `clarify` is treated as containing a halt verb.**
Rejected. This is the smallest-diff reflex called out in [[feedback_model_gaps_need_model_fixes]]. The conflation IS the defect; teaching SPECGAP to mask it preserves the wrong model. UR-03 names two failure classes; one scalar cannot carry both. A synonym map also breaks the moment a fourth response strategy joins the vocabulary.

**A2 — List form: `failure_modes: [clarify, block]`.**
Considered as the simpler schema. Rejected as primary because the list form leaves the failure-class → strategy binding implicit (the implementor must externally know that ambiguity maps to `clarify` and contradiction maps to `block`). This re-creates the conflation at the implementation layer instead of in the YAML. Map form (D2) closes it constitutionally. Governor MAY downgrade D2 to the list form if the per-phase class-naming overhead in D5/D8 is judged unnecessary; doing so re-opens a subtle ambiguity that future ADR work would need to close.

**A3 — Model ambiguity as a phase *success outcome* (`clarification_needed: true` in `outputs:`) and reserve `failure_mode` for contradiction only.**
Considered. INTERPRET's existing YAML *already* lists `clarification_needed` in `outputs:` and `request_clarification` in `permitted_actions:`, lending surface plausibility to this framing. Rejected because it underplays UR-03's symmetry. Both gaps-and-ambiguities and contradictions are non-proceed outcomes in UR-03's text: "CORE asks" and "CORE stops" are different responses to *different conditions*, not different outcome categories. Modeling one as success and the other as failure is structurally asymmetric in a way UR-03 does not authorize. The constitutional reading is that both are interpret-phase failures with different recovery paths.

**A4 — Rename the field from `failure_mode` to `failure_response` or `failure_strategy`.**
Considered. The current name is ambiguous (could mean "mode in which failure manifests" = class, or "mode of responding to failure" = strategy). The values today (`block`, `clarify`, `warn`, `continue`) are clearly strategies, so a rename to `failure_strategy` would be more accurate. Rejected as out-of-scope: the rename is churn that touches every phase YAML, the schema, and every doc that mentions the field, in exchange for clarity that the schema migration in D2 (map of class to strategy) already supplies via shape. Reconsider in a future ADR if the term `failure_mode` causes ongoing confusion.

**A5 — Defer the schema change; introduce a parallel scalar `halt_on_contradiction: bool` alongside `failure_mode`.**
Rejected as the [[feedback_half_built_schema_pattern]] anti-pattern: adding a YAML field without integrating it into a coherent model leaves the next maintainer with two surfaces to reconcile. A boolean co-axis is also unable to scale to a third class (e.g., `defer_on_missing_context: bool`); each new class demands a new boolean. The map form generalizes; bool flags do not.

**A6 — Treat this ADR as constitutional-text-only; defer all code changes (D7, D9, D10) to follow-up issues.**
Considered. ADR-073 took the opposite posture (single change-set including code), so precedent favours co-shipping. Rejected here on grounds of: (a) the YAML migration is a breaking schema change that the consumers must follow immediately or audit fails; (b) splitting risks the same half-built-schema pattern A5 was rejected for. The change-set in D12 is bounded and small enough to land atomically.

---

## Consequences

**Positive:**

- INTERPRET's UR-03 obligation is operationalized in the phase YAML rather than dispersed across English prose, code branches, and an absent third value.
- The closed-enum discipline is extended to `failure_mode`; the three drifting vocabularies (YAML, code, constitution doc) collapse to one canonical source in `enums.json`.
- The latent governance bug in `workflow_orchestrator.py` (silent fall-through on `clarify`) is closed. INTERPRET ambiguity now halts the workflow explicitly until a clarification surface is built.
- ADR-073 and ADR-074 are formally coherent after the D13 corrigendum; D7's action-verb coverage logic is preserved unchanged and operates on map `.values()` rather than list elements.
- SPECGAP false-positives against INTERPRET stop. The two dismissed candidates (`252f6707`, `f6206305`) and their class clear on the next scan.
- The schema (D6) makes phase YAMLs validated for the first time. `phases/` joins `META/`, `flows/`, `rules/`, `workers/`, `workflows/definitions/`, `workflows/stages/` in the `validated_directories` set.

**Negative:**

- The sibling-phase YAMLs migrate to map form (D8) even though they have only one strategy today. This is migration cost paid for schema consistency. Mitigation: the class names are governor-authored once; future changes are local.
- D7 conservatively halts on `clarify` until a dialogue surface exists, which means INTERPRET ambiguity becomes a workflow-stopping outcome where today it was a silent fall-through. This is a *correction* of a latent bug, but it may surface workflow halts that previously slipped through. Mitigation: workflow logs make the new behaviour explicit; a follow-up ADR specifies the dialogue surface.
- Per-phase failure-class names (D5) are not centrally enumerated, so cross-phase drift in class naming is detectable only via the per-phase schema, not via a global enum. Mitigation: explicit non-goal in v1; revisit if drift is observed.
- The vocabulary registered in `enums.json` (`block`, `clarify`) excludes tokens that appear in adjacent surfaces (`warn`, `continue`). Code paths referencing them in `src/will/orchestration/workflow_orchestrator.py` become dead and are deleted in D7.
- `.intent/constitution/CONSTITUTIONAL-WORKFLOWS.md:102,115` continues to reference `block/warn/continue` after this ADR lands. The constitution doc's vocabulary diverges from `enums.json#/definitions/failure_mode` until the governor-authored amendment lands. Residual drift is tracked by issue #476 (filed concurrent with ADR-074 acceptance per [[feedback_file_followups_before_restart]]).

---

## Non-Goals

- This ADR does not author a clarification-dialogue surface. INTERPRET's `clarify` strategy halts the workflow in v1; the user-dialogue mechanism that resolves the halt is a separate concern.
- This ADR does not specify a global `failure_class` enum (D5). Per-phase class names are local.
- This ADR does not expand the vocabulary beyond `block` and `clarify`. `warn`, `continue`, `defer`, `escalate` are governor-reviewable TBD candidates; inclusion is a future ADR.
- This ADR does not amend `.intent/constitution/CONSTITUTIONAL-WORKFLOWS.md` text. That document carries a stale vocabulary reference (`block/warn/continue`); the amendment is governor-authored, not Claude-authored. Residual drift is tracked by issue #476 (filed concurrent with ADR-074 acceptance).
- This ADR does not amend `.specs/papers/CORE-Phases-as-Governance-Boundaries.md`. The paper does not currently discuss failure modes in detail; whether to add a §8.1 covering the failure-mode discipline is a paper-amendment decision for the governor.
- This ADR does not retire the `failure_mode` (singular) name in favour of `failure_modes` (plural). They are different fields: singular is removed entirely; plural is the new shape.
- This ADR does not change SPECGAP's detection rule (ADR-073 D7) — only the consumer code that implements it (D9).

---

## Verification

ADR is considered Implemented when ALL of the following hold:

1. `.intent/META/enums.json` declares a `failure_mode` enum with members `["block", "clarify"]` (or as amended by governor per D3 TBD list).
2. `.intent/META/phase.schema.json` exists and validates against all six `.intent/phases/*.yaml` files.
3. `.intent/META/intent_tree.yaml` lists `phases` in `validated_directories`.
4. All six `.intent/phases/*.yaml` declare `failure_modes:` (map form) and no longer declare `failure_mode:` (scalar).
5. `.intent/phases/interpret.yaml` declares both `ambiguity: clarify` and `contradiction: block` in its `failure_modes` map.
6. `src/will/orchestration/workflow_orchestrator.py` reads `failure_modes` as a map; `clarify` halts the workflow with an explicit log line; no silent fall-through on unrecognized strategies.
7. `src/mind/coherence/checks/specgap.py` reads `failure_modes` as a map; `_verbs_covered_by` matches against both keys and values.
8. SPECGAP run against the current normative-marker register emits **zero** UR-03 candidates against the INTERPRET phase. The two existing dismissed-in-DB candidates (`252f6707`, `f6206305`) auto-close on next scan.
9. Drift-guard test `tests/intent/test_phase_failure_mode_canonical_alignment.py` exists and passes; mutation of any of the three surfaces (`enums.json`, phase YAMLs, orchestrator/SPECGAP code) without the others fails it.
10. `core-admin code audit` passes with no new findings introduced by the change-set.
11. `.specs/decisions/ADR-073-ccc-scanner-redesign.md` carries the D13 corrigendum Note (governor-applied per [[feedback_intent_specs_draft_default]]).

---

## Revisit Triggers

- A third interpret-phase failure class is identified (e.g., "input depends on context not yet available" → `defer`): governor-reviewable TBD per D3.
- A sibling phase introduces a second failure class (e.g., `audit` distinguishing blocking-rule-violation from advisory-rule-violation): governor extends that phase's `failure_modes` map.
- Cross-phase drift in failure-class naming becomes observable (e.g., two phases name semantically-distinct classes with the same key): introduce a global `failure_class` enum via follow-up ADR.
- The conservative `clarify`-halts-workflow behaviour in D7 causes friction: follow-up ADR specifies the dialogue surface and changes D7's behaviour to dialogue-dispatch.
- Telemetry on the SPECGAP register shows the regex-friendly action-verb set is over- or under-matching against the new vocabulary: tune `normative_markers.yaml` per its existing governor-review mutation posture.

---

## References

- Governing paper: `.specs/papers/CORE-Phases-as-Governance-Boundaries.md`
- Grounding requirement: `.specs/northstar/CORE-USER-REQUIREMENTS.md` §3 UR-03
- ADR-073 — CCC scanner redesign; D7 SPECGAP detection rule presupposes the schema migration this ADR delivers; D11 phase-responsibility mapping declares interpret responsible for UR-03
- ADR-073 D9 — closed-enum schema migration precedent (R1_SCOPED, SAMECONCERN, …); precedent for D3's vocabulary registration
- ADR-049 D2 — Paper→Rule constitutional direction; UR-03 is the upstream paragraph this ADR's downstream artifact operationalizes
- Issue #460 — canonical phase enum subsets + cross-META `$ref` bootstrap; precedent for D3 and D6's loader pattern
- Issue #459 — interpret-phase contradiction-vs-ambiguity failure-mode distinction (this ADR closes)
- `.intent/enforcement/config/normative_markers.yaml` — action-verb register against which D9's coverage check matches
- `.intent/enforcement/config/phase_responsibility.yaml` — D11 SPECGAP bridge; INTERPRET is registered as responsible for UR-03

---

**End of ADR.**
