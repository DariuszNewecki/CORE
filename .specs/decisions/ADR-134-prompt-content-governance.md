---
kind: adr
id: ADR-134
title: "ADR-134 — Prompt Content Governance: Traceability and Drift Review Gate"
status: accepted
---

# ADR-134 — Prompt Content Governance: Traceability and Drift Review Gate

**Date:** 2026-06-29
**Governing paper:** `.specs/papers/CORE-PromptGovernancePipeline.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Band:** E — Constitutional Completeness
**Grounding papers:** ADR-090 (PromptModel as governed surface, `var/prompts/` crawl
scope); ADR-049 (privilege-boundary imports); rules.ai.prompt_governance;
rules.ai.prompt_artifact_structure
**Related:** ADR-132 (governor authentication boundary); ADR-133 (test gap evaluator,
`build.test_for_symbol`); CLAUDE.md §"Constitutional rules"

---

## Context

CORE's constitutional governance model enforces correctness at the code layer through
69 rules (34 blocking, 27 reporting, 8 advisory). The AI invocation surface is partially
governed: `rules.ai.prompt_governance` and `rules.ai.prompt_artifact_structure` enforce
**structural** properties — every `PromptModel` must have a `model.yaml` with required
fields, a non-empty `system.txt`, a declared `role`, and output validation. These rules
ensure that every AI call is channelled through a named, versioned artifact.

What they do not govern is **semantic content**. A `system.txt` or `user.txt` can be
modified in ways that silently alter AI behaviour — removing a constitutional constraint,
weakening a validation criterion, changing the task framing — without triggering any
existing audit rule. No rule checks whether prompt content still reflects the ADR decision
that authorised the prompt's behavioural contract. No gate surfaces governed-prompt changes
for governor review.

This is the **prompt drift gap**: prompt content is CORE's instruction set to the AI, but
that instruction set is unversioned relative to the decisions that mandated it.

The gap is especially consequential for prompts that implement ADR-governed behaviour:
code generation (ADR-003), test generation (ADR-133), assumption extraction, coherence
checking. A drift in `system.txt` for any of these can degrade the quality gate that
the governing ADR was written to enforce, and the degradation is invisible to the audit
engine.

**Scope.** This ADR does not attempt to semantically validate prompt content — that is
outside deterministic audit scope. The goal is narrower: (1) make the relationship between
a prompt and its authorising ADR explicit and machine-readable; (2) enforce that governed
prompts carry visible constitutional grounding; (3) surface changes to governed prompts for
governor review rather than letting them land silently.

**Existing structural rules are not changed.** D1–D3 below add to `rules.ai.*`; they do
not modify or relax existing blocking rules.

---

## Decisions

### D1 — `adr_anchor` field added to `model.yaml` manifest schema

A new optional field `adr_anchor` is added to `PromptModelManifest`:

```yaml
# model.yaml — example for a governed prompt
id: context_aware_test_gen
version: "2.1"
role: coder
adr_anchor: "ADR-133:D6"          # <-- new field
input:
  required: [source_file, symbol_name, symbol_kind, signature]
output:
  format: python
success_criteria: "Single valid Python test function"
```

Semantics:

- `adr_anchor` is a string of the form `"ADR-NNN"` or `"ADR-NNN:DN"` where `:DN` pins
  to a specific decision clause. A prompt may anchor to more than one clause by providing
  a list.
- **Required** for prompts whose behavioural contract is defined by an ADR decision.
  Governed prompts include, at minimum: all prompts under `var/prompts/` that implement
  code generation, test generation, assumption extraction, repair, coherence checking, or
  any other action whose output feeds an `@atomic_action`.
- **Optional** for purely operational prompts (docstring writer, format fixer, enrichment
  helpers) whose behaviour is not mandated by a specific ADR clause.

`PromptModelManifest` adds `adr_anchor: str | list[str] | None = None`.
`PromptModel.load()` logs the anchor at `DEBUG` level at load time, creating an audit
trail that correlates prompt loads to ADR decisions in the application log.

The set of prompts that require `adr_anchor` is initially enumerated in a companion
`.intent/enforcement/config/governed_prompts.yaml` (D4 below).

### D2 — New blocking rule: `ai.prompt.governed_prompt_must_have_anchor`

Added to `rules.ai.prompt_artifact_structure`:

```json
{
  "id": "ai.prompt.governed_prompt_must_have_anchor",
  "statement": "Any PromptModel listed in governed_prompts.yaml MUST declare an adr_anchor in its model.yaml. A governed prompt without a traceable ADR anchor has no constitutional standing.",
  "enforcement": "blocking",
  "rationale": "Governed prompts implement ADR-mandated behaviour. Without an anchor, there is no machine-readable link between the prompt's contract and the decision that defined it. The anchor is the traceability record; its absence is equivalent to an ungoverned invocation."
}
```

The check reads `governed_prompts.yaml` (D4) and verifies that each listed prompt name
has `adr_anchor` set in its `model.yaml`. A missing or null value is a blocking violation.

### D3 — New reporting rule: `ai.prompt.constitutional_grounding_section`

Added to `rules.ai.prompt_governance`:

```json
{
  "id": "ai.prompt.constitutional_grounding_section",
  "statement": "The system.txt of any governed prompt (one with adr_anchor declared) MUST contain a section beginning with '# CONSTITUTIONAL' that names the policies or ADR clauses being enforced. An empty or generic system prompt provides no constitutional grounding.",
  "enforcement": "reporting",
  "rationale": "The system prompt is the channel through which CORE communicates constitutional law to the AI. For governed prompts, that communication must be explicit. A system.txt that does not name what it enforces cannot be audited for drift. The section heading makes the grounding machine-detectable."
}
```

Enforcement is `reporting` (not blocking) at introduction. The ramp pattern from ADR-059
applies: once the existing governed prompts are updated to comply, promote to `blocking`.

The `# CONSTITUTIONAL` section may be named `# CONSTITUTIONAL PRINCIPLE`,
`# CONSTITUTIONAL GROUNDING`, or `# CONSTITUTIONAL CONSTRAINTS` — the prefix `# CONSTITUTIONAL`
is the detectable token. The `assumption_extractor` system prompt already uses this pattern;
this rule makes it normative.

### D4 — `governed_prompts.yaml` registry in `.intent/enforcement/config/`

A new file `.intent/enforcement/config/governed_prompts.yaml` enumerates every prompt
whose behavioural contract is ADR-governed:

```yaml
# .intent/enforcement/config/governed_prompts.yaml
# Prompts whose behavioural contract is defined by an ADR clause.
# Changes to any listed prompt's content require governor review (D5).
# Each entry must have adr_anchor in its model.yaml (D1/D2).

governed_prompts:
  - name: code_generation_task_step_prompt
    anchors: ["ADR-003"]
    rationale: Routes ExecutionTask.task_type to correct generation phase.

  - name: context_aware_test_gen
    anchors: ["ADR-133:D6"]
    rationale: Symbol-scoped test generation; single-function output contract.

  - name: assumption_extractor
    anchors: ["ADR-???"]         # governor fills in at ratification
    rationale: Constitutional assumption synthesis from policy corpus.

  - name: coder_repair
    anchors: ["ADR-???"]
    rationale: Repair strategy constrained by constitutional envelope.

  - name: constitutional_coherence_analyst
    anchors: ["ADR-027"]
    rationale: CCC coherence checking; must reflect live coherence ruleset.
```

The governor populates missing `ADR-???` anchors at ratification by checking git history
for the commit that introduced each prompt. The registry is author-controlled; new governed
prompts are added when the ADR that mandates them is accepted.

### D5 — Reporting rule: `ai.prompt.governed_change_requires_review`

Added to `rules.ai.prompt_governance`:

```json
{
  "id": "ai.prompt.governed_change_requires_review",
  "statement": "Any modification to the system.txt or user.txt of a governed prompt (listed in governed_prompts.yaml) MUST be surfaced as a blackboard finding for governor review before the change is considered ratified. Governed prompt changes that are not reviewed are constitutional debt.",
  "enforcement": "reporting",
  "rationale": "Governed prompts implement ADR-mandated behaviour. A silent change to system.txt can degrade a quality gate that an ADR was written to enforce. The review gate is the semantic equivalent of the .intent/ confirmation gate for source changes: it surfaces the change without blocking, preserving velocity while creating an explicit review obligation."
}
```

**Detection mechanism:** `PromptDriftSensor` (D6) detects when a governed prompt's
content changes between cycles and posts a `prompt.drift_detected` finding to the
blackboard. The finding payload includes: `prompt_name`, `adr_anchor`, `changed_files`
(which of `system.txt` / `user.txt` / `model.yaml` changed), and `git_commit` that
introduced the change.

The governor reviews the finding and resolves it as `ratified` (intentional, consistent
with ADR) or `revert_required` (drift identified). Resolution is manual; no automated
remediation is defined for this rule.

### D6 — `PromptDriftSensor` worker

A new sensor `PromptDriftSensor` is introduced in `src/will/workers/` (or
`src/body/services/` pending layer assignment — see note).

**Layer note.** A sensor that reads `var/prompts/` file content and posts blackboard
findings is a read + blackboard-post operation. Reading files is Body-sanctioned. Posting
findings routes through the Worker base class. The component should extend `Worker` and
live in `src/will/workers/` as a lightweight sensor alongside `TestCoverageSensor`.

**Behaviour:**

1. On each cycle, load `governed_prompts.yaml` via `IntentRepository`.
2. For each governed prompt, compute a SHA-256 hash of `system.txt` + `user.txt` +
   `model.yaml` concatenated.
3. Compare to the hash stored in the previous cycle's blackboard entry
   (`prompt.drift_baseline`).
4. If changed: post a `prompt.drift_detected` finding with the payload described in D5.
5. If unchanged: post a `prompt.drift_clean` heartbeat.

The baseline hash is persisted via a blackboard `post_report("prompt.drift_baseline", ...)`
entry rather than in-memory state, so restarts do not lose the comparison point.

Cadence: `max_interval: 300` (5-minute cycle; prompt files change rarely, so a tight
cadence is not needed).

### D8 — Self-healing write-feeder prompts governed under ADR-134

**Scope correction.** D1 listed "docstring writer, format fixer, enrichment helpers" as
"purely operational" with `adr_anchor` optional. On full-surface audit of `var/prompts/`
(2026-07-02), eleven prompts were found to produce source or test artifacts written to disk
via `ActionExecutor` or `FileHandler.write_runtime_text` but were absent from
`governed_prompts.yaml`. These constitute the **self-healing write-feeder group** and are
brought into scope under the same governance framework as D1–D6.

| Prompt | Write surface |
|---|---|
| `violation_remediator` | ViolationRemediatorWorker → ActionExecutor / FileHandler |
| `call_site_rewriter` | CallSiteRewriter → ActionExecutor("crate.create") |
| `body_contracts_fixer` | BodyUiFixer → FileHandler.write_runtime_text |
| `docstring_writer` | DocstringService → FileHandler.write_runtime_text |
| `modularity_analyze` | modularity_fix atomic action (Body-layer LLM call) |
| `line_length_refactorer` | LineLengthService → ActionExecutor |
| `clarity_v2_refactor` | ClarityService → ActionExecutor |
| `logic_alignment_generic_repair` | alignment specialists → ActionExecutor |
| `complexity_reflex_refactor` | ComplexityService → ActionExecutor |
| `godd_object_modularizer` | alignment specialists → ActionExecutor |
| `single_test_fixer` | SingleTestFixer → FileHandler / ActionExecutor |

All eleven carry `adr_anchor: "ADR-134:D8"` in their `model.yaml` and are registered in
`governed_prompts.yaml` with `anchors: ["ADR-134:D8"]`.

**Explicit exclusions.** The following active prompts are **out of scope** for
`governed_prompts.yaml`:

- `pattern_correction` — intermediate correction pass inside `CorrectionEngine`; does not
  produce the write artifact; output feeds a governed prompt downstream.
- `self_correction_engine_correction_prompt` — self-correction refinement inside the
  generation loop; same reasoning.
- `test_generation_test_executor` — validates test output before a write decision; advisory,
  not generative.

These do not require `adr_anchor` per D1's optional category. Explicit declaration here
closes the question for future audits.

### D9 — `external-review.md` prompt is explicitly out of scope

`var/prompts/external-review.md` (the template for human-initiated external LLM reviews)
is NOT listed in `governed_prompts.yaml` and is exempt from D2/D3/D5/D6. It is a human
communication artefact, not an AI invocation surface. No `PromptModel.load()` call reads
it; it is never passed to `CognitiveService`. Its governance is the same as any
`.specs/` document — governor-authored, human-reviewed.

---

## Consequences

- **Traceability.** Every governed prompt has a machine-readable link to the ADR clause
  that defines its behavioural contract. A future governor or reviewer can answer "why does
  this system.txt say what it says?" without reading git blame.
- **Drift visibility.** Silent changes to governed prompt content now surface as blackboard
  findings. The audit engine cannot prevent drift, but it can make it visible immediately.
- **Constitutional grounding is enforceable.** The `# CONSTITUTIONAL` section convention
  becomes a reportable rule rather than a style convention, creating an audit-visible signal
  of governance intent in every governed prompt.
- **No velocity impact at introduction.** All new rules are `reporting` or `blocking`
  only against the new `governed_prompts.yaml` registry, which the governor populates
  incrementally. No existing passing audit is broken by this ADR.
- **Ramp path.** Once `governed_prompts.yaml` is complete and all listed prompts carry
  `adr_anchor` and `# CONSTITUTIONAL` sections, `ai.prompt.constitutional_grounding_section`
  is promoted from `reporting` to `blocking`. This follows the ramp-arc pattern
  (ADR-059 D2).

---

## Verification

This ADR is closed when:

1. `adr_anchor` is a recognised field in `PromptModelManifest`; `PromptModel.load()`
   logs it at `DEBUG` level.
2. `governed_prompts.yaml` exists at `.intent/enforcement/config/governed_prompts.yaml`
   with all `ADR-???` placeholders resolved.
3. Every prompt listed in `governed_prompts.yaml` has `adr_anchor` in its `model.yaml`.
4. The blocking rule `ai.prompt.governed_prompt_must_have_anchor` fires on any listed
   prompt missing the field (verified by a test that temporarily removes the field from a
   fixture `model.yaml`).
5. `PromptDriftSensor` (declared at `.intent/workers/prompt_drift_sensor.yaml`) posts `prompt.drift_detected` when a governed prompt's content changes between cycles (verified by mutating a fixture prompt file mid-test and confirming the finding appears on the blackboard).
6. Every prompt listed in `governed_prompts.yaml` has a `# CONSTITUTIONAL` section in
   `system.txt`; `ai.prompt.constitutional_grounding_section` reports zero violations.
7. `external-review.md` is not flagged by any D2/D3/D5/D6 check.

---

## References

- ADR-090 — PromptModel as governed AI invocation surface; `var/prompts/` crawl scope.
- ADR-059 — Severity vocabulary governance; ramp-arc pattern (reporting → blocking).
- ADR-003 — `ExecutionTask.task_type` routing; canonical anchor for code generation prompt.
- ADR-133 — Test gap evaluator; `build.test_for_symbol`; anchor for `context_aware_test_gen`.
- ADR-027 — CCC coherence audit; anchor for `constitutional_coherence_analyst`.
- ADR-132 — Governor authentication boundary; `governed_prompts.yaml` is governor-authored.
- `src/shared/ai/prompt_model.py` — `PromptModel`, `PromptModelManifest`.
- `.intent/rules/ai/prompt_governance.json` — rules extended by D3/D5.
- `.intent/rules/ai/prompt_artifact_structure.json` — rule extended by D2.
- `.intent/artifact_types/prompt.yaml` — prompt artifact type; `vector_collection: core-prompts`.
- `var/prompts/assumption_extractor/system.txt` — existing `# CONSTITUTIONAL PRINCIPLE`
  section; the pattern this ADR makes normative.
- `var/prompts/external-review.md` — explicitly out of scope (D9).
