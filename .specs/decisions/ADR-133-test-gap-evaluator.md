---
kind: adr
id: ADR-133
title: ADR-133 — Test Gap Evaluator and Symbol-Granular Test Generation
status: accepted
---

# ADR-133 — Test Gap Evaluator and Symbol-Granular Test Generation

**Date:** 2026-06-28
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Band:** C — Autonomy Loop
**Grounding papers:** ADR-104 (worker contract, circuit breaker); ADR-107 (proposal
production, files_produced); CLAUDE.md §"The autonomous test-generation loop"
**Related:** ADR-039 (derived-walk, bounded sensor scope); ADR-045 (audit findings feed
remediation loop dynamics); Issue #563 (F-19 convergence goal)

---

## Context

The autonomous test-generation loop (`TestCoverageSensor` → `TestRemediatorWorker` →
`build.tests` → `CoderAgent`) operates at **file granularity**: one proposal generates an
entire test file for one source file. This granularity has two failure modes that are
structurally embedded in the design:

**Truncation.** Complex source files (workers, services) require test files that exceed the
LLM output token ceiling. The output is cut mid-expression; IntentGuard rejects the result
with a syntax violation. Raising `max_tokens` (done as an immediate patch in the session
preceding this ADR) buys headroom but does not address the root cause.

**Import hallucination.** A full-file generation task asks the LLM to reason about every
public symbol at once, hold all context simultaneously, and produce correct import paths for
all of them. This is a wide-context task that exceeds reliable LLM accuracy. A per-symbol
task is narrower and more grounded.

**Wasted regeneration.** When a test file already exists but is partially missing coverage,
the current loop regenerates the entire file — overwriting existing passing tests to re-cover
already-tested symbols. This adds variance and burn under the circuit breaker.

Observable consequence (dashboard, 2026-06-28): 56 failures in 24h across 21 source files,
all `flow.build_tests:0`, cycling 2-3× each under the circuit breaker. Violations:
`code.imports.generated_must_resolve`, `code.imports.generated_no_relative`,
`valid_python_syntax`.

The fix is architectural: decompose the file-level generation task into two separate
concerns — **gap identification** (what is untested?) and **symbol-level generation**
(generate one test for one symbol).

---

## Decisions

### D1 — `TestGapEvaluator` is a new `BaseEvaluator` (AUDIT phase)

A new component `TestGapEvaluator` is introduced in
`src/body/evaluators/test_gap_evaluator.py`, extending `BaseEvaluator` with
`phase = ComponentPhase.AUDIT`.

Its contract:

```
input:  source_file: str   (repo-relative path, e.g. "src/body/foo.py")
output: GapReport          (structured list of SymbolGap records)
```

`GapReport` is a typed dataclass:

```python
@dataclass
class SymbolGap:
    name: str          # public symbol name (function or class)
    kind: str          # "function" | "class" | "method"
    signature: str     # full signature string for context
    tested: bool       # True if a test_<name> function already exists

@dataclass
class GapReport:
    source_file: str
    gaps: list[SymbolGap]   # only untested symbols
    already_covered: list[SymbolGap]   # already tested symbols (for logging)
    test_file: str          # governed path (source_to_test_path)
    test_file_exists: bool
```

`TestGapEvaluator` is read-only, side-effect-free, and deterministic (no LLM calls).
It must not import from Mind, Will, or the database session layer.

### D2 — Gap detection uses AST only; heuristic is `test_<name>` match

**Source pass:** Extract all top-level `def` and `class` symbols that are public (no leading
underscore). For classes, also extract public methods that are substantive (exclude
`__init__`, `__repr__`, `__eq__`, and other dunder methods from the gap list — they are
incidental to the class under test; a test targeting the class covers them).

**Test pass:** If `test_file` exists, parse its AST and collect all function names matching
`test_<name>`. A source symbol `foo` is considered "tested" if `test_foo` appears in the
test file. This is a conservative heuristic — it may mark a symbol as tested when the
existing test is insufficient, but it prevents overwriting passing tests. The inverse
(false negative: marking a symbol as untested when it is covered under a different name) is
acceptable; the circuit breaker limits re-spend.

If the test file does not exist, all extracted symbols are gaps.

### D3 — New atomic action `build.test_for_symbol`

A new atomic action `build.test_for_symbol` is introduced in
`src/body/atomic/build_test_for_symbol_action.py`.

Parameters:

```
source_file:  str   — repo-relative source path
symbol_name:  str   — name of the symbol to test
symbol_kind:  str   — "function" | "class" | "method"
signature:    str   — full signature (from GapReport)
write:        bool  — governed write flag, default False
```

It uses `context_aware_test_gen` (already exists in `var/prompts/`) to generate **one
test function** targeting exactly one symbol. Output is bounded by the single-symbol scope
— a single test function is well within the token ceiling regardless of source file size.

The action appends to the existing test file (if it exists) or creates it (if not). Append
uses `FileHandler`; it inserts the new test function after the last existing test function
in the file. If the file does not exist, it writes a fresh module with the standard header
(`from __future__ import annotations`, imports, the generated function).

`files_produced` declares the test file path per ADR-107 D2 (one entry regardless of
append vs create).

`build.tests` (file-level generation) is retained for backward compatibility and for
cases where a complete regeneration is explicitly requested. It is no longer the primary
path for autonomous test coverage.

### D4 — `TestRemediatorWorker` calls `TestGapEvaluator` before proposal creation

`TestRemediatorWorker` is updated to:

1. Receive a `source_file` claim from the blackboard (unchanged).
2. Instantiate `TestGapEvaluator` and call `evaluate(source_file)` → `GapReport`.
3. If `gap_report.gaps` is empty: post a `test.coverage.complete` finding and skip
   proposal creation. This is the no-op path when all symbols are already tested.
4. For each `SymbolGap` in `gap_report.gaps`:
   a. Apply the existing circuit breaker check per (source_file, symbol_name) pair.
   b. If not circuit-broken: create one `build.test_for_symbol` proposal for that symbol.

The per-symbol circuit breaker key is `f"{source_file}::{symbol_name}"` — distinct from
the file-level key used by the old `build.tests` path. This prevents one persistently
failing symbol from consuming the budget of all other symbols in the same file.

### D5 — `action_risk.yaml` entry for `build.test_for_symbol`

`build.test_for_symbol` is registered in `.intent/enforcement/config/action_risk.yaml`
with:

```yaml
build.test_for_symbol:
  impact_level: moderate
  reversible: true
  rationale: >
    Appends or creates a test file. Test files are not production code;
    the change is reversible via git. Impact is lower than write_code
    because the target is always a tests/ path, never a src/ path.
```

### D6 — `context_aware_test_gen` prompt is authorised for `build.test_for_symbol`

`context_aware_test_gen` already exists in `var/prompts/` with a `max_tokens` that is
appropriate for single-function output. `build.test_for_symbol` loads this prompt
directly via `PromptModel.load("context_aware_test_gen")`.

The `system.txt` for `context_aware_test_gen` is updated to add the same absolute-import
and context-grounded-import constraints introduced in the preceding `build.tests` goal
string fix, so the constraints are enforced at the prompt level rather than only in the
caller's goal string.

### D7 — IntentGuard validation applies to the appended function, not the whole file

When `build.test_for_symbol` generates a function to append, IntentGuard validation runs
on the **generated snippet** (the single function), not on the full post-append file. This
is consistent with the action's scope: it authors one function; it validates one function.
A separate `test.execute` or `sandbox_validate` step in `flow.build_tests` (or a new
`flow.build_test_for_symbol`) covers the full file post-append.

---

## Consequences

- **Truncation is structurally eliminated.** A single test function for a single symbol
  cannot exceed any reasonable token ceiling. The `max_tokens` patch on
  `code_generation_task_step_prompt` remains in place for other generation tasks but is no
  longer load-bearing for the test generation path.
- **Import hallucination surface shrinks.** `context_aware_test_gen` is scoped to one
  symbol; the LLM's import task is to import exactly one symbol from one module path
  provided in the context. Multi-symbol hallucination is eliminated.
- **Existing passing tests are preserved.** The gap evaluator's `already_covered` list
  prevents overwriting. Files with partial coverage are augmented, not replaced.
- **Circuit breaker granularity improves.** A file with 10 symbols where 1 persistently
  fails no longer blocks the other 9.
- **`build.tests` is not removed.** It remains valid for explicit full-file regeneration
  (governor-invoked), canary testing, and backward compatibility with any existing
  integrations. It is also the action underlying the `coverage_remediation` workflow
  (`EnhancedTestGenerator` → `GenerationWorkflow` → `build.tests`), which is a named
  workflow type in `AutonomousDeveloper` and `runtime_phase.py`. Both paths use
  `test_gen_prompt` (ADR-003 governed, ADR-134 registered).
- **`flow.build_tests` must be updated** to route through `build.test_for_symbol` per
  symbol rather than one `build.tests` call per file. This is a `.intent/flows/` change
  (governor-applied) and a `FlowExecutor` invocation change.

---

## Verification

This ADR is closed when:

1. `TestGapEvaluator` exists in `src/body/evaluators/test_gap_evaluator.py`, extends
   `BaseEvaluator`, returns `GapReport`, makes no LLM calls, has no write side effects.
2. `build.test_for_symbol` is registered in `@register_action` and
   `action_risk.yaml`, uses `context_aware_test_gen`, appends via `FileHandler`.
3. `TestRemediatorWorker` calls `TestGapEvaluator` before proposal creation; creates one
   proposal per gap symbol; skips circuit-broken symbols individually.
4. `flow.build_tests` (or a new `flow.build_test_for_symbol`) reflects the per-symbol
   execution path in `.intent/flows/`.
5. Dashboard `failed today` count for `flow.build_tests` returns to single digits within
   one 24h cycle after deployment.
6. A source file with 3 public symbols where 1 is already tested generates 2 proposals
   (not 1 file-level proposal); the already-tested symbol is not overwritten.

---

## References

- ADR-104 — Worker contract, ADR-104 D9 circuit breaker cap.
- ADR-107 — Proposal production set, `files_produced` declaration.
- ADR-039 — Derived-walk; bounded scope in sensor components.
- ADR-045 — Audit findings feed remediation; loop dynamics.
- CLAUDE.md §"The autonomous test-generation loop" — source→test path mapping, governed
  by `shared.infrastructure.intent.test_coverage_paths.source_to_test_path`.
- `src/body/atomic/build_tests_action.py` — file-level generation (retained, not primary).
- `var/prompts/context_aware_test_gen/` — per-symbol prompt (authorised for D3/D6).
- `src/will/workers/test_remediator/` — worker to be updated per D4.
- `.intent/enforcement/config/action_risk.yaml` — risk registry (D5).
- Issue #563 — F-19 convergence metric; reducing failure rate contributes to this goal.
