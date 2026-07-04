---
kind: adr
id: ADR-076
title: ADR-076 — Context-Level Dispatch as a Per-Check-Type Engine Property
status: accepted
---

# ADR-076 — Context-Level Dispatch as a Per-Check-Type Engine Property

**Date:** 2026-05-29
**Governing paper:** `.specs/papers/CORE-Gate.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Band:** E — Outward-Facing
**Closes:** #480
**Grounding paper:** `papers/CORE-Gate.md` (Gate/engine validation model)
**Related:** ADR-040 (no hardcoded values in `src/`), ADR-043 (only prior reference to `is_context_level`), ADR-066 and ADR-072 (invariants silently unenforced by this gap), ADR-075 (its D7 rule is among the inert set)

---

## Context

An audit rule is dispatched in one of two ways. A **per-file** rule iterates
the file list and the engine's `verify(file_path, params)` runs once per file.
A **context-level** rule does not iterate — the engine's
`verify_context(context, params)` runs once over the whole repository. The
dispatch decision is already per-rule: `rule_executor.py:118` branches on
`rule.is_context_level` and returns before the per-file loop at line 143.

The defect is in how `is_context_level` is *set*. It is hydrated once at
extraction time, purely from the engine name:

```
# rule_extractor.py:178-179
is_context_level = engine in CONTEXT_LEVEL_ENGINES   # frozenset({"workflow_gate", "knowledge_gate"})
```

There is no per-rule or per-check-type path to `True`. The dispatch is per-rule;
the *setting* is per-engine. That asymmetry is the bug.

`artifact_gate` is a **mixed-mode engine**. Its `verify(file_path, params)`
routes by `params.check_type` to a `_check_*` function. Six of its nine
check_types are repo-level — they walk to the repo root and ignore `file_path`
(the governance and vocabulary checks, e.g. `all_rules_mapped`,
`classification_complete`, `projection_must_match_canonical`). Three are
genuinely per-file — they parse `file_path` as YAML (the PromptModel checks).
Because context-level is an all-or-nothing per-engine property, `artifact_gate`
cannot be enrolled: adding it to `CONTEXT_LEVEL_ENGINES` would force the three
per-file PromptModel checks context-level and break them, while leaving it out
keeps the six repo-level checks dispatched per-file.

The consequence, verified empirically (#480): all nine `artifact_gate` checks
have been inert since the audit walker was authored 2026-05-16. The six
repo-level checks are dispatched per-file, but the walker is `*.py`-only
(`audit_context.py:277`) with `.intent/**` and `var/**` in `hard_excludes`
(`audit_context.py:281-290`), so `get_files()` returns empty for their scopes
and the per-file loop never iterates them. They produce no findings under any
condition. A provocation test (deliberately breaking the ADR-066 invariant)
left the audit verdict PASS — the blocking rule never fired.

The mode is therefore a property of the **check_type**, not the rule and not the
engine: a check_type is repo-level precisely when its `_check_*` function
ignores `file_path`. Today's per-rule override would be correct only by the
coincidence that rule-to-check_type is 1:1; the truth lives one level down.

There is no ADR — and no paper — governing context-level dispatch. ADR-043
references `is_context_level` only to validate that it cannot combine with
`requires_findings_from`. This ADR governs the mechanism for the first time.

---

## Decisions

### D1 — Context-level is a per-check-type property owned by the engine

Whether a rule dispatches context-level or per-file is determined by its
check_type, and the authority on that is the engine that implements the
check_type. The mode lives where the truth lives: in the engine, adjacent to
the `_check_*` function it describes. It is neither a per-engine constant nor a
governor-declared field.

### D2 — The extractor consults the engine, not a frozenset

`rule_extractor` sets `is_context_level` by asking the engine for the mode of
the rule's check_type — `engine.is_context_level_for(check_type)` — rather than
by `engine in CONTEXT_LEVEL_ENGINES`. Engines that do not implement the method
default to per-file (`False`), so `ast_gate`, `glob_gate`, and `regex_gate` are
unchanged. `CONTEXT_LEVEL_ENGINES` is retired; `workflow_gate` and
`knowledge_gate` declare their check_types context-level via the same method.
One mechanism replaces the frozenset shortcut. `PassiveGateEngine`'s existing
`verify_context` becomes formally unreachable under the new dispatch (its
default mode is per-file); it is harmless dead code and its removal is separate
scope.

### D3 — `artifact_gate` becomes explicitly mixed-mode

`artifact_gate` declares, per check_type, which of its nine checks are
context-level (the six repo-level governance/vocabulary checks) and which are
per-file (the three PromptModel checks). It gains a `verify_context(context,
params)` entry point that serves the six repo-level check_types, and keeps
`verify(file_path, params)` for the three per-file ones. The dispatcher already
routes correctly once `is_context_level` is set per D2.

### D4 — Effective mode is surfaced in audit/inspect output

Because the mode is derived in the engine rather than declared in `.intent/`,
each rule's *effective* dispatch mode is exposed in the audit/inspect output, so
the governor can read which rules are context-level without inspecting `src/`.
This recovers governance visibility under a single source of truth: the engine
owns the mode; the inspect surface projects it.

### D5 — The audit walker admits the file set per-file rules declare

The three per-file PromptModel checks require their files to be walked, and the
walker bars them two ways: it is `*.py`-only (`audit_context.py:277`) **and**
excludes `var/**` (`hard_excludes`, `:281-290`). Both must change — widening the
file-type filter without admitting the root leaves the three rules inert. The
walked set is derived from the active per-file rules' `scope` declarations: a
file is walked iff some active rule's scope matches it, after structural
excludes (`.git`, `.venv`, `__pycache__`, build artifacts). The reason for
deriving — rather than walking everything (`rglob("*")` + structural excludes)
and letting per-rule `scope` includes filter at dispatch — is consistency with
this ADR's own stance: walker scope is a projection of declared rule scopes, the
same single-source-of-truth pattern by which mode (D1) and its visibility (D4)
are projections of engine code. The alternative, no-hardcode scan-all-filter is
viable and operationally simpler; it is rejected for that coherence, not on
ADR-040 grounds. ADR-040 only forbids one *naive* form — a hardcoded extension
set such as `rglob("*.{py,yaml,json}")` — and rules out neither the derived form
nor scan-all-filter. The derived form adds no separate config artifact and
self-adjusts as per-file rules' scopes change. The repo-level checks need no
walker change; they do not iterate files. This is the per-file half of closing
#480 and the bounded form of walker-widening this ADR adopts.

### D6 — Every check_type must demonstrably fire

The risk D6 closes is a check_type that is dispatched but never produces a
finding — the #480 silent-inert class. Rather than statically inferring whether
a `_check_*` function uses `file_path` (a brittle proxy whichever way it is
implemented), the gate is a test-time coverage assertion: every `artifact_gate`
check_type, and every context-level rule, must produce a finding when run
through the real audit dispatch against a fixture carrying a known violation. A
check_type that cannot be made to fire is inert by definition and fails the
gate. This tests the property that matters — the rule enforces — not a proxy for
it. An extraction-time structural assertion that a declared mode is internally
coherent may be added as a cheap secondary, but the firing-coverage test is the
authoritative gate.

---

## State at ADR acceptance

Implementation is deferred; no code changes at acceptance. Touch sites named for
implementation: `rule_extractor.py:30-31` (`CONTEXT_LEVEL_ENGINES` retirement)
and `:178-179` (consult the engine); `executable_rule.py:67` (docstring on how
`is_context_level` is now derived); `artifact_gate.py` (per-check-type mode
declaration + `verify_context`); `workflow_gate` and `knowledge_gate` (declare
their check_types context-level); `audit_context.py:277` (rglob file-type
scope) and `:281-290` (`hard_excludes`), both driven by the D5 derivation. No
`.intent/` rule-document or mapping schema change — the mode is not a
governance-declared field.

---

## Consequences

- **Nine rules un-inert.** The six repo-level `artifact_gate` checks dispatch
  context-level and fire; the three PromptModel checks fire per-file once the
  walker admits their files. ADR-066's blocking unmapped-rules invariant, ADR-072
  cognates, and ADR-075 D7 enforce for the first time.
- **One dispatch mechanism.** `CONTEXT_LEVEL_ENGINES` is gone; mode is uniformly
  engine-declared per check_type. Mixed-mode engines are now a supported,
  first-class shape.
- **Context-level dispatch is governed.** A previously ungoverned runtime
  pattern now has a constitutional record.
- **Visibility without a second source.** The governor can audit each rule's
  effective mode via the inspect surface; the mode is not duplicated into
  `.intent/`, so there is nothing to drift.
- **`passive_gate` dead code.** Its `verify_context` becomes formally
  unreachable under D2; harmless, cleanup is separate scope.
- **A class of false-PASS is closed.** The provocation that left the verdict
  PASS now produces FAIL when the invariant is broken.

---

## Alternatives considered

- **Mapping-declared mode (Option B).** Declare `is_context_level` per rule in
  the enforcement mapping. Rejected: the mode is an implementation fact about the
  check_type, so declaring it in `.intent/` creates a second source that must be
  kept coherent with the engine. Both B and D need a guardrail — the honest
  contrast is *where* it sits. B's is **cross-surface** (mapping ↔ engine, an
  ADR-070-shaped coherence check that exists only because B introduced a second
  source). D6's is **within-engine** (mode declaration ↔ function behavior, one
  source). The choice is cross-surface vs intra-engine, not guardrail vs none;
  intra-engine is strictly smaller.
- **Engine split (Option C).** Split `artifact_gate` into a per-file engine (the
  three PromptModel checks) and a context-level engine (the six repo-level
  checks, enrolled in the frozenset). Rejected: more churn (new engine, re-mapped
  rules, moved check_types) and it preserves the per-engine setting model rather
  than resolving the per-rule/per-engine asymmetry that is the root defect.
- **Widen the walker alone (issue #480 Option 1).** Remove `.intent/**`/`var/**`
  from `hard_excludes` and broaden the glob, without the dispatch correctness of
  D1–D4. Rejected: it makes today's rules fire but leaves the failure mode intact
  — a future repo-level rule whose files the walker misses goes silently inert
  again — and dispatches repo-level checks once per matching file, risking
  duplicate findings. D5 is the bounded form of walker-widening this ADR adopts:
  scoped to what per-file rules declare, alongside correct per-rule dispatch.

---

## Verification

Closing #480 requires, after implementation:

- A dispatch trace shows the six repo-level checks invoked via `verify_context`,
  and the three PromptModel checks invoked per-file over
  `var/prompts/**/model.yaml`.
- Each of the nine rules produces a finding on a planted violation (the D6
  coverage gate).
- The ADR-066 provocation (remove a rule's `auto_remediation.yaml` entry) yields
  audit verdict FAIL, not PASS.
- The D6 coverage test fails when a check_type is wired such that it cannot fire.

---

## References

- `papers/CORE-Gate.md` — the Gate/engine validation model this dispatch
  mechanism sits within (engine-model context; the paper does not itself govern
  dispatch mode).
- ADR-040 — no hardcoded values in `src/`; forbids a naive hardcoded-extension
  walker filter, but is not the reason D5 chooses the derived form over a
  no-hardcode scan-all-filter (that reason is coherence with D1/D4).
- ADR-043 — LLM Gate Audit Throughput; the only prior reference to
  `is_context_level`, used there to validate the `requires_findings_from`
  exclusion.
- ADR-066 — Unmapped-rules invariant; its blocking rule
  `governance.remediation.all_rules_mapped` has been silently unenforced since
  landing because of this gap.
- ADR-072 — cognate meta-rules in the same inert set.
- ADR-075 — `governance.namespace.classification_complete` (D7) is among the
  nine inert checks.
- Issue #480 — audit walker-scope gap; empirical evidence of the inert dispatch.
- 2026-05-29 reconnaissance — mapped `is_context_level` hydration
  (`rule_extractor.py:178-179`), dispatch (`rule_executor.py:118-141`),
  `CONTEXT_LEVEL_ENGINES` membership (`rule_extractor.py:30-31`), and
  `artifact_gate`'s per-file-only surface (`artifact_gate.py:650`).
