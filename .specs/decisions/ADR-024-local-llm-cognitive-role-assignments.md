<!-- path: .specs/decisions/ADR-024-local-llm-cognitive-role-assignments.md -->

# ADR-024: Local LLM cognitive role assignments — governed evaluation over assumption

**Status:** Accepted
**Date:** 2026-05-05
**Depends on:**
- `.specs/papers/CORE-Constitutional-Foundations.md`
- `.intent/ai/cognitive_roles.yaml`
- `scripts/eval_ollama.py` (evaluation harness, version pass 3)

**Related:** ADR-018 (vector_sync_worker retirement), ADR-001 (AI trust posture)

---

## Context

CORE uses LLMs as cognitive roles — named capability contracts that map to
PromptModel artifacts in `var/prompts/`. Each cognitive role is backed by a
configured provider and model. Prior to this ADR, role-to-model assignments
for local (Ollama) models were untested assumptions. CORE's production path
uses `anthropic_claude_sonnet` for all cognitive roles; local models existed
on the development machine (`aaiMac`, M1 16GB) as unqualified fallbacks.

The available local models were:

| Handle | Model | Size |
|---|---|---|
| `qwen2.5-coder:14b` | coder, 14B params | 9.0 GB |
| `qwen2.5-coder:3b` | coder, 3B params | 1.9 GB |
| `qwen2.5:7b` | general, 7B params | 4.7 GB |
| `phi4:14b` | general reasoning, 14B params | 9.1 GB |
| `nomic-embed-text-8k` | embeddings only | 274 MB |

Three evaluation passes were conducted using a purpose-built harness
(`scripts/eval_ollama.py`) that:

- Reads actual PromptModel artifacts from `var/prompts/` (system.txt,
  user.txt, model.yaml) — not synthetic proxies.
- Injects CORE-domain fixtures into each prompt template.
- Calls each model via the same HTTP API CORE's OllamaProvider uses.
- Scores each response on eight binary dimensions: `non_empty`, `json_valid`,
  `schema_fields`, `ast_valid`, `no_prose_leak`, `has_code_field`,
  `imports_clean`, `instruction_follow`.
- Runs three repetitions per (model, prompt) pair and reports pass rates and
  latency.

Pass 1 covered 4 prompts (initial fixture set). Pass 2 extended to 21 prompts
after fixture expansion covering all role-mapped artifacts. Pass 3 corrected
two harness scoring bugs, added `phi4:14b`, and produced the definitive
qualification matrix.

**Harness bugs corrected before final scoring (pass 3):**

- `has_code_field` was incorrectly applied to analysis/reasoning JSON prompts
  (`llm_gate`, `assumption_extractor`, `plan_goal`, `modularity_analyze`,
  `llm_gate_audit_prompt`) whose schemas declare no `code` property. These
  prompts now correctly score `has_code_field = N/A`.
- `imports_clean` rejected `from src.body.workers...` imports in generated
  test files. `src` added to `CORE_INTERNAL_PREFIXES`.

**Prompt not fully testable with current fixtures:**

`clarity_v2_refactor` — its `model.yaml` declares only `improvement_ratio`
as a required input, providing no source code context. All models responded
with generic refactoring tutorials rather than Python output. This prompt is
documented as undertested; its role assignment is based on the remaining
LocalCoder evidence, not this prompt's score.

---

## Evaluation results (pass 3 — definitive)

### Per-prompt scores

| Prompt | Role | 14b-coder | 3b-coder | 7b-general | phi4-14b |
|---|---|---|---|---|---|
| architect_threats_analysis_prompt | Architect | 0.00 (timeout) | **1.00** (29.6s) | **1.00** (72.2s) | 0.00 (timeout) |
| assumption_extractor | LocalReasoner | 1.00 | 1.00 | 1.00 | 1.00 |
| clarity_v2_refactor | LocalCoder | 0.33 | 0.83 | 0.67 | 0.50 |
| coder_repair | LocalCoder | 1.00 | 1.00 | 1.00 | 1.00 |
| complexity_reflex_refactor | LocalCoder | 1.00 | 1.00 | 1.00 | 1.00 |
| context_aware_test_gen | LocalCoder | 1.00 | 1.00 | 1.00 | 1.00 |
| docstring_writer | DocstringWriter | 1.00 (13.8s) | 0.50 | **1.00 (5.1s)** | 1.00 (22.0s) |
| intent_inspector_alignment | Architect | 1.00 | 1.00 | 1.00 | 1.00 |
| intent_inspector_coherence | Architect | 1.00 | 1.00 | 1.00 | 1.00 |
| line_length_refactorer | LocalCoder | 1.00 | 1.00 | 1.00 | 1.00 |
| llm_correction_structural | LocalCoder | 1.00 | 1.00 | 1.00 | 1.00 |
| llm_correction_syntax | LocalCoder | 1.00 | 1.00 | 1.00 | 1.00 |
| llm_gate | LocalReasoner | 1.00 | 1.00 | 1.00 | 1.00 |
| llm_gate_audit_prompt | LocalReasoner | 1.00 | 1.00 | 1.00 | 1.00 |
| micro_planner_create_micro_plan | Planner | 1.00 (79.8s) | 1.00 (34.5s) | 1.00 (30.7s) | 1.00 (100.8s) |
| modularity_analyze | Architect | 1.00 | 1.00 | 1.00 | 1.00 |
| pattern_correction | LocalCoder | 1.00 | 1.00 | 1.00 | 1.00 |
| plan_goal | Planner | 1.00 | 1.00 | 1.00 | 1.00 |
| simple_test_generator_prompt | LocalCoder | 1.00 (60.6s) | 1.00 (19.8s) | 1.00 (20.8s) | 1.00 (52.1s) |
| single_test_fixer | LocalCoder | 1.00 | 1.00 | 1.00 | 1.00 |
| violation_remediator | LocalCoder | 0.80 (36.3s) | **1.00 (9.0s)** | 0.40 | 0.40 |

### Role qualification matrix

| Role | 14b-coder | 3b-coder | 7b-general | phi4-14b |
|---|---|---|---|---|
| LocalCoder | DISQUALIFIED (min=0.33) | **QUALIFIED** (min=0.80) | DISQUALIFIED (min=0.40) | DISQUALIFIED (min=0.40) |
| DocstringWriter | QUALIFIED | DISQUALIFIED (min=0.50) | **QUALIFIED** | QUALIFIED |
| Architect | DISQUALIFIED (min=0.00) | **QUALIFIED** (min=1.00) | QUALIFIED (min=1.00) | DISQUALIFIED (min=0.00) |
| LocalReasoner | QUALIFIED | **QUALIFIED** | QUALIFIED | QUALIFIED |
| Planner | QUALIFIED | **QUALIFIED** | QUALIFIED | QUALIFIED |

---

## Key findings

**F1. Model size does not predict qualification for CORE's prompt patterns.**
`qwen2.5-coder:3b` (1.9 GB) outperforms `qwen2.5-coder:14b` (9.0 GB) and
`phi4:14b` (9.1 GB) on the roles that matter most. CORE's PromptModel
artifacts are focused, structured, and short-to-medium output. This
systematically favours models that are fast and instruction-obedient over
models that are large and verbose.

**F2. The timeout boundary is the real discriminator for large models.**
At ~3 tokens/second on M1 16GB, a 120-second timeout caps output at ~360
tokens. `architect_threats_analysis_prompt` and
`micro_planner_create_micro_plan` require longer outputs. Both 14b-coder and
phi4 time out on `architect_threats_analysis_prompt` consistently (0.00).
3b-coder completes it in 29.6s avg.

**F3. `violation_remediator` is the discriminator prompt for LocalCoder.**
It requires a raw-text response containing valid JSON with a `code` field
holding parseable Python. Only 3b-coder achieves 1.00 here. 14b-coder scores
0.80 (one hallucinated syntax token across 3 runs). phi4 and 7b-general score
0.40 — they embed Python triple-quotes inside JSON strings, producing invalid
JSON on extraction.

**F4. phi4:14b earns no role not already covered.**
phi4 was evaluated as a candidate for LocalReasoner and Architect based on
its reputation for structured JSON and reasoning discipline. It qualifies for
LocalReasoner and Planner (all models do), and is competitive on DocstringWriter.
However it times out on the Architect discriminator prompt and fails
violation_remediator — the LocalCoder discriminator. It does not displace any
current assignment.

**F5. Role names must not encode model identity or provider.**
During evaluation, a naming scheme of `Coder-local-qwen2.5-coder:14b` was
considered and rejected. The constitutional rule
`ai.prompt.artifact.role_abstraction` explicitly forbids model and provider
names in role declarations. Role names encode capability and locality tier
only. Model identity is an implementation detail residing in the
`core.cognitive_roles` database table, not in PromptModel artifacts.

---

## Decision

### D1. Cognitive role assignments for local development (aaiMac)

| Cognitive role | Assigned model | Rationale |
|---|---|---|
| `LocalCoder` | `qwen2.5-coder:3b` | Only model to achieve 1.00 on `violation_remediator`; fastest on all code tasks |
| `DocstringWriter` | `qwen2.5:7b` | 1.00 quality, 5.1s avg — 2.7× faster than 14b alternatives |
| `Architect` | `qwen2.5-coder:3b` | Only coder-class model to handle large-output JSON prompts within timeout |
| `LocalReasoner` | `qwen2.5-coder:3b` | All models qualify; 3b is 5× faster than 14b at identical quality |
| `Planner` | `qwen2.5-coder:3b` | All models qualify; 3b is fastest |

### D2. Production on-prem role assignments are deferred

Production on-prem hardware has not been specified. Role assignments for
production must be re-derived using the same harness against the production
hardware profile and model set. The evaluation harness (`scripts/eval_ollama.py`)
is the instrument for this; it is not a one-time script but a repeatable
qualification tool. Adding a new model to the harness requires only adding its
handle to the `MODELS` dict and pulling it via Ollama.

Cloud models (e.g. `kimi-k2.6:cloud`) may be evaluated as a proxy for
production-class hardware using the same harness with the `:cloud` Ollama tag.
This is explicitly in scope for a future evaluation pass.

### D3. `phi4:14b` is retained on aaiMac as a spare

`phi4:14b` does not earn a primary role assignment. It is retained on the Mac
for ad-hoc experimentation and future evaluation passes. It must not be
configured as the backing model for any cognitive role without passing the
harness at the QUALIFIED threshold (overall_score ≥ 0.80 across all
role-mapped prompts, minimum score ≥ 0.80).

### D4. `clarity_v2_refactor` fixture gap is a tracked debt item

`clarity_v2_refactor/model.yaml` declares only `improvement_ratio` as a
required input. This is insufficient context for any model to produce CORE
Python output. The fixture gap must be resolved by either:
- Adding `source_code` as a declared optional input in `model.yaml` and
  providing a corresponding fixture, or
- Determining the prompt is superseded and retiring it.

This is not blocking for role assignments but must be resolved before
LocalCoder qualification can be considered complete (coverage is currently
11/12).

### D5. The evaluation harness is a governed artifact

`scripts/eval_ollama.py` is the qualification instrument for local LLM role
assignment. It must not be modified in ways that relax scoring criteria
without a corresponding ADR update. Fixture additions (new variable values)
are permitted without ADR amendment. Scorer logic changes require amendment.

---

## Consequences

**Immediate:**
- `core.cognitive_roles` table entries for LocalCoder, DocstringWriter,
  Architect, LocalReasoner, and Planner on the development environment are
  updated to reflect D1 assignments.
- `phi4:14b` is not configured as a backing model for any role.

**Forward:**
- When production on-prem hardware is specified, pass 4 of the harness is
  run against the production model set before any deployment.
- `clarity_v2_refactor` fixture gap is tracked as a GitHub issue.
- The Convergence Principle applies to the eval harness itself: if a model
  consistently fails a prompt it previously passed, that is a regression signal
  requiring investigation before the role assignment is trusted.

---

## Alternatives considered

**A1. Assign 14b-coder to LocalCoder based on parameter count assumption.**
Rejected. Empirical evidence shows 3b-coder achieves higher scores on the
LocalCoder discriminator prompt (`violation_remediator`) and handles all other
LocalCoder prompts at equivalent or superior quality with 4× lower latency.

**A2. Assign phi4:14b to Architect based on reasoning reputation.**
Rejected. phi4 times out on `architect_threats_analysis_prompt` — the
heaviest Architect prompt — identically to 14b-coder. Reputation is not a
substitute for measured qualification on actual PromptModel artifacts.

**A3. Add mistral-nemo:12b as a LocalReasoner candidate.**
Deferred. All four evaluated models qualify for LocalReasoner. Adding a fifth
model for a role with no incumbent gap produces no actionable change. Remains
available as a future evaluation candidate if 3b-coder regresses on reasoning
prompts.

**A4. Embed model names in cognitive role names.**
Rejected on constitutional grounds. See Finding F5 and rule
`ai.prompt.artifact.role_abstraction`.
