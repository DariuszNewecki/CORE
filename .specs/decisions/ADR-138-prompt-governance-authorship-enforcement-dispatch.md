---
kind: adr
id: ADR-138
title: "ADR-138 — Prompt Governance and Authorship Integrity Enforcement Dispatch"
status: accepted
---

<!-- path: .specs/decisions/ADR-138-prompt-governance-authorship-enforcement-dispatch.md -->

# ADR-138 — Prompt Governance and Authorship Integrity Enforcement Dispatch

**Date:** 2026-07-02
**Governing paper:** `.specs/papers/CORE-PromptGovernancePipeline.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-07-02)
**Band:** B — Governance Infrastructure
**Grounding papers:** ADR-066 (unmapped-rules invariant); ADR-129 (authorship integrity);
ADR-134 (prompt content governance)
**Related:** Issues #745, #746, #747 (three inert rules); ADR-136 (dispatch-parity)

---

## Context

Three rule namespaces were constitutionally declared but had no dispatch engine mapping,
making them structurally inert. The ADR-066 invariant (`governance.remediation.all_rules_mapped`)
requires every active reporting rule to have an `auto_remediation.yaml` stub — all three had
stubs — but the orthogonal requirement is an enforcement mapping entry that tells the audit
engine *how* to evaluate the rule. Without a mapping entry, the audit-cycle never fires the
rule and the finding type is permanently dead.

The affected rules were:

| Rule ID | Enforcement | Detector |
|---------|-------------|----------|
| `governance.commit_authorship_integrity` | reporting | CommitAuthorshipAuditWorker (ADR-129 D5) |
| `ai.prompt.governed_change_requires_review` | reporting | PromptDriftSensor (ADR-134 D6) |
| `ai.prompt.constitutional_grounding_section` | reporting | none yet |
| `ai.prompt.governed_prompt_must_have_anchor` | **blocking** | none yet — needs static check |

The first two rules are runtime-detected: their findings are posted to the blackboard by
workers/sensors that run continuously. Duplicating the detection in the static audit engine
would produce false double-counts and add brittle maintenance overhead. The third rule has
no runtime detector today; the governed_grounding_section check requires semantic judgment
(which ADR clauses apply to a given prompt) and is intentionally non-automatable.

The fourth rule is blocking: it must fire at IntentGuard pre-commit. Blocking rules are
statically evaluated and cannot rely on a runtime sensor. A real engine check is required.

### The passive_gate contract

`passive_gate.verify()` always returns `ok=True`; `passive_gate.verify_context()` always
returns `[]`. This is the correct engine for rules whose detection is entirely worker- or
sensor-driven. The mapping entry satisfies the engine-dispatch requirement (a mapping must
exist) while correctly communicating "the audit engine does not re-implement what the
runtime detector already does."

`passive_gate` is *not* a workaround for blocked implementation; it is the semantically
correct dispatch for sensor-driven rules. The distinction matters for future auditors: a
`passive_gate` mapping on a REPORTING rule signals "worker detects, engine yields." Using
it on a BLOCKING rule would be wrong — blocking rules fire at static audit time when no
worker is running.

---

## Decisions

### D1 — passive_gate is canonical for sensor/worker-driven REPORTING rules

When a REPORTING rule's detection is owned exclusively by a running worker or sensor (which
posts findings to the blackboard), the enforcement mapping MUST use `passive_gate`. This
avoids double-counting findings, avoids brittle engine re-implementation of runtime logic,
and communicates the correct intent to future maintainers.

This does NOT apply to BLOCKING rules. Blocking rules fire at static audit time (IntentGuard)
and MUST have a real engine check. A `passive_gate` mapping on a blocking rule would mean
the rule never fires at pre-commit, defeating the blocking classification.

### D2 — governance.commit_authorship_integrity maps to passive_gate

`CommitAuthorshipAuditWorker` (ADR-129 D5) is the authoritative detector. The worker
compares actual git diffs against `proposal_consequences.declared_production` and posts
`governance.commit_authorship_integrity::{proposal_id}` findings to the blackboard. The
static audit engine has no access to git-diff content at check time and cannot reproduce
this verification.

Mapping file: `.intent/enforcement/mappings/governance/authorship_integrity.yaml`

### D3 — ai.prompt.governed_change_requires_review maps to passive_gate

`PromptDriftSensor` (ADR-134 D6) is the authoritative detector. The sensor compares
SHA-256 hashes of governed prompt files against a baseline, posting
`ai.prompt.governed_change_requires_review` findings to the blackboard on content change.
The static audit engine sees only the current file state — it has no baseline hash to
compare against.

Mapping file: `.intent/enforcement/mappings/ai/prompt_governance.yaml`

### D4 — ai.prompt.constitutional_grounding_section maps to passive_gate

No runtime detector and no static check for CONSTITUTIONAL-section presence exists today.
The check requires semantic judgment: which ADR clauses apply to a given prompt's governance
contract is a governor determination, not an automatable pattern match.

`passive_gate` declares the mapping to satisfy the engine-dispatch requirement. The rule
remains constitutionally declared and will fire real findings when a real detector is wired
in a future delivery. Until then the finding type is known-declared-unimplemented, which is
the correct state to surface rather than deleting the rule or silently omitting the mapping.

Mapping file: `.intent/enforcement/mappings/ai/prompt_governance.yaml`

### D5 — ai.prompt.governed_prompt_must_have_anchor maps to artifact_gate with a new check_type

This rule is BLOCKING; `passive_gate` would make it permanently inert. A new per-file
check_type `governed_prompt_has_anchor` is added to `ArtifactGateEngine.verify()`. The
check applies to all `var/prompts/**/model.yaml` files and cross-references
`.intent/enforcement/config/governed_prompts.yaml` at check time to determine which prompts
are governed. Only governed prompts are required to carry `adr_anchor`; ungoverned prompts
pass silently.

Mapping file: `.intent/enforcement/mappings/ai/prompt_artifact_structure.yaml`

### D6 — governed_prompt_has_anchor resolves the governed list from the repo root

The check locates `.intent/enforcement/config/governed_prompts.yaml` by walking parent
directories from the `file_path` argument until a directory containing both `.intent/` and
`.specs/` is found (using the existing `_find_repo_root` helper). This makes the check
portable across different absolute mount paths (container vs. host) and requires no
hardcoded path constant in the engine.

The check is PROVEN evidence class (deterministic, file-based) — it reads only static files
and compares field presence. All 21 currently governed prompts already carry `adr_anchor`,
so the check fires no violations in the current corpus.

---

## Constraints and invariants

- A `passive_gate` mapping on a BLOCKING rule is constitutionally invalid. Future additions
  of engine mappings for BLOCKING rules MUST use a real engine (artifact_gate, ast_gate,
  glob_gate, or equivalent). This constraint is not currently enforced mechanically; it is
  an architectural invariant to uphold at code-review time.

- `governed_prompts.yaml` is the authoritative source for which prompts require `adr_anchor`.
  When a new governed prompt is added to that file, the `governed_prompt_has_anchor` check
  will enforce the anchor requirement at the next IntentGuard run automatically — no engine
  change is required.

- The three `passive_gate` mappings created here satisfy ADR-066 (all_rules_mapped) by
  providing an engine-dispatch entry. The auto_remediation stubs for all four rules already
  existed before this ADR; this ADR provides only the dispatch-side mapping.

---

## Files changed

| File | Change |
|------|--------|
| `.intent/enforcement/mappings/governance/authorship_integrity.yaml` | Created (D2) |
| `.intent/enforcement/mappings/ai/prompt_governance.yaml` | Added D3 + D4 entries |
| `.intent/enforcement/mappings/ai/prompt_artifact_structure.yaml` | Added D5 entry |
| `src/mind/logic/engines/artifact_gate.py` | Added `_check_governed_prompt_has_anchor` method + dispatch (D5/D6) |
| `tests/mind/logic/engines/test_artifact_gate__governed_prompt_has_anchor.py` | New — 5 tests |
