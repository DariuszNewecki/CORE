---
kind: adr
id: ADR-135
title: "ADR-135 — Dual-Mode Generation: Single-Shot and Iterative Execution Primitives"
status: accepted
---

<!-- path: .specs/decisions/ADR-135-dual-mode-generation-primitives.md -->

# ADR-135 — Dual-Mode Generation: Single-Shot and Iterative Execution Primitives

**Date:** 2026-07-01
**Status:** Draft
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-07-01)
**Band:** C — Autonomy Loop
**Grounding papers:** ADR-003 (task_type routing through CoderAgent); ADR-106
(hermetic worktree per flow execution); ADR-133 (symbol-granular test generation,
`build.test_for_symbol`); ADR-109 (assisted remediation lane)
**Related:** Issue #563 (F-19 convergence); `spikes/loop_vs_singleshot/` (measurement
harness, 2026-06-30); `src/will/agents/coder_agent.py`; `src/will/self_healing/`

---

## Context

### The current generation primitive

`CoderAgent.generate_or_repair` is the single LLM generation primitive available to all
governed flows. Its contract is fixed:

1. **Generate** — one LLM call produces a candidate artifact.
2. **Repair (optional)** — if the caller supplies a `pain_signal`, one repair call is made
   with the failure detail threaded into the prompt.

The "repair" step is not a loop — it is a single follow-up call. The primitive returns after
at most two LLM invocations regardless of whether the output is accepted. Acceptance
evaluation, sandboxing, and any further retry happen at the proposal level, not inside the
primitive.

### What happens when a generation step fails

When `flow.build_test_for_symbol` runs and the generated test file violates a constitutional
rule (`code.imports.generated_must_resolve`, `valid_python_syntax`, etc.), `FlowExecutor`
records the failure and `ProposalConsumerWorker` marks the proposal `failed`. The violation
detail is stored in `execution_results` but is never fed back to the LLM for a second
generation attempt. The circuit breaker (ADR-038) eventually suspends the source file from
further proposals.

This is correct behaviour for a single-shot primitive: the primitive returned its best
attempt; the governed pipeline evaluated it and recorded the outcome. The gap is not a bug
in the current primitive — it is the *absence of an iterative primitive* that could use the
violation output as a feedback signal.

### An iterative primitive already exists, but ungoverned

`src/will/self_healing/test_generation/` contains `EnhancedTestGenerator`, which implements
a repair loop (`max_fix_attempts=3`). It is not connected to the governed proposal pipeline:
`ProposalConsumerWorker` and `FlowExecutor` do not use it, and it has no `.intent/flows/`
declaration. It exists as a standalone, ungoverned path that predates the flow-based
pipeline. Its iteration budget, acceptance condition, and feedback format are hardcoded.

### Spike evidence

A controlled spike (`spikes/loop_vs_singleshot/`, 2026-06-30) measured the loop hypothesis
against the governed acceptance conditions (pytest green + CORE audit pass) on
previously-failed proposals:

```
Spike baseline SHA:    34cec8347c842a45df61a4e3503ed296ca62644d
Corpus:                failed autonomous_proposals, failure_reason = 'Actions failed: flow.build_tests:0'
Tasks measured:        10 (sample from 30 distinct candidates)
Isolation:             one hermetic git worktree per task, removed after
Single-shot baseline:  0/10 (historical; all proposals already exhausted)
Loop pytest green:     10/10
Loop CORE-audit pass:  10/10
Oracle-gaming signal:  0/10 (green-but-audit-failed)

Wall-clock per task:
  min:    74s
  max:    186s
  mean:   123.5s
  median: 122s
```

The validated claim:

> On 10 previously failed `flow.build_tests` tasks, the iterative governed loop converted
> 10/10 into pytest-green, CORE-audit-passing test diffs, without modifying source files.

The claim this ADR does **not** extend to:

> The iterative primitive is superior to single-shot for all generation tasks.

The sample is small, the corpus is scoped to failed test-generation proposals, and the
single-shot baseline is historical (same-prompt same-model re-run was not performed). This
ADR is grounded in the test-generation recovery evidence. Generalisation to source-file
modification or other task types requires its own measurement.

### The design opportunity

The spike established that two execution strategies are useful for different task profiles:

- **Single-shot** — one (optionally two with repair) LLM invocations. Appropriate for
  well-defined, low-ambiguity tasks where first-attempt success is expected. Low token cost,
  low latency.
- **Iterative** — repeated (generate → evaluate acceptance → feed back violations → repeat)
  up to a governed cap. Appropriate for tasks where the acceptance condition is
  deterministic and computable, and where violation detail is rich enough to guide repair.
  Higher token cost; recovery rate justifies the spend for high-failure-rate tasks.

Making both available as explicit, reusable primitives — accessible to any flow via a
`.intent/` declaration — is the architectural decision this ADR records.

---

## Decisions

### D1 — Two named generation modes are defined as CORE primitives

`GenerationMode` is a closed vocabulary with two values:

| Value | Meaning |
|---|---|
| `single_shot` | Delegate to `CoderAgent.generate_or_repair`. At most one generate call and one repair call. This is the current behaviour; naming it makes the choice explicit. |
| `iterative` | Delegate to `IterativeCoderAgent`. Loops over (generate → accept → feedback) up to the governed iteration cap. Each failed iteration's violation output becomes the `pain_signal` for the next call. |

Both modes are Will-tier primitives. Both delegate LLM invocation to `CoderAgent`
internally — `IterativeCoderAgent` is not a replacement for `CoderAgent`, it is an
orchestration wrapper that calls it repeatedly with progressively richer context.

`GenerationMode` is declared in `shared.models.generation_mode` (a simple `StrEnum`). It
is imported by Will; it is not imported by Body or Mind.

### D2 — `IterativeCoderAgent` is a new Will-tier component

A new component `IterativeCoderAgent` is introduced in
`src/will/agents/iterative_coder_agent.py`.

**Contract:**

```python
@dataclass
class IterationResult:
    code: str
    iterations_used: int
    final_violations: list[str]   # empty on success
    accepted: bool

class IterativeCoderAgent:
    async def generate_until_accepted(
        self,
        task: ExecutionTask,
        goal: str,
        acceptance: AcceptanceCondition,
        iteration_cap: int,
    ) -> IterationResult: ...
```

**Loop behaviour:**

```
attempt = 0
pain_signal = None
previous_code = None
while attempt < iteration_cap:
    code = await coder_agent.generate_or_repair(task, goal, pain_signal, previous_code)
    result = await acceptance.evaluate(code, task)
    if result.accepted:
        return IterationResult(code, attempt+1, [], accepted=True)
    pain_signal = result.violation_summary
    previous_code = code
    attempt += 1
return IterationResult(previous_code, attempt, result.violations, accepted=False)
```

On exhausting `iteration_cap` without acceptance, `IterativeCoderAgent` returns an
`IterationResult` with `accepted=False`. The caller (`FlowExecutor`) treats this the same
as a single-shot failure — the proposal is marked `failed`, violation detail is recorded
in `execution_results`. No silent success is possible.

`IterativeCoderAgent` does not write files, execute tests, or evaluate audit rules itself.
It orchestrates calls to `CoderAgent` and delegates acceptance evaluation to the injected
`AcceptanceCondition`. It is a pure Will-tier orchestrator.

### D3 — `AcceptanceCondition` is an injectable protocol

```python
@dataclass
class AcceptanceResult:
    accepted: bool
    violation_summary: str    # fed as pain_signal to next iteration
    violations: list[str]     # detailed list for execution_results

class AcceptanceCondition(Protocol):
    async def evaluate(self, code: str, task: ExecutionTask) -> AcceptanceResult: ...
```

Three concrete implementations are introduced:

| Class | Location | Behaviour |
|---|---|---|
| `PytestAcceptanceCondition` | `src/will/agents/acceptance/pytest_condition.py` | Writes code to the sandboxed path, runs `pytest <test_file> -x --tb=short -q`, parses stdout for pass/fail and failure detail. |
| `AuditAcceptanceCondition` | `src/will/agents/acceptance/audit_condition.py` | Calls `core-admin code audit --offline --target <worktree> --files <path>` (same invocation as the spike harness). Returns the audit violations as the feedback signal. |
| `CompositeAcceptanceCondition` | `src/will/agents/acceptance/composite_condition.py` | Evaluates a list of conditions in order; accepted only when all pass. Returns the first failing condition's `violation_summary` as the feedback signal. |

The `AcceptanceCondition` protocol lives in `src/will/agents/acceptance/`. Body does not
import it; Mind does not import it. The implementations that shell out to pytest or
`core-admin` are Will-tier — they invoke Body services, not raw subprocesses — except where
a body service does not yet expose the required interface, in which case the implementation
may shell out and the debt is noted in `.specs/decisions/`.

### D4 — Iteration budget is governed in `.intent/`

A new file `.intent/enforcement/config/generation_budget.yaml` declares the iteration cap
per `task_type`:

```yaml
# generation_budget.yaml
# Governs IterativeCoderAgent iteration caps by task_type.
# single_shot tasks are not subject to this file.
budgets:
  test_generation:
    max_iterations: 5
    wall_clock_cap_secs: 600
  code_modification:
    max_iterations: 3
    wall_clock_cap_secs: 600
  default:
    max_iterations: 3
    wall_clock_cap_secs: 600
```

`IterativeCoderAgent` reads this file via `IntentRepository` at construction time. It does
not accept a caller-supplied `iteration_cap` that exceeds the governed value — if the
caller passes a higher value, the governed cap wins and a warning is logged.

The wall-clock cap is enforced by wrapping each `coder_agent.generate_or_repair` call with
`asyncio.wait_for`. If the wall-clock cap is reached mid-iteration, the iteration is
abandoned and the loop terminates with `accepted=False`.

### D5 — Flow manifests declare `generation_mode`

`.intent/flows/*.yaml` gains an optional top-level field `generation_mode`:

```yaml
# .intent/flows/build_test_for_symbol.yaml  (illustrative excerpt)
flow_id: flow.build_test_for_symbol
generation_mode: iterative      # new field; default: single_shot
steps:
  - ...
```

`FlowExecutor` reads `generation_mode` from the flow manifest and routes the generation
step accordingly:

- `single_shot` (default): call `CoderAgent.generate_or_repair` directly (existing path,
  unchanged).
- `iterative`: construct `IterativeCoderAgent` with the flow's declared acceptance
  conditions and the governed cap for the task's `task_type`; call
  `generate_until_accepted`.

This keeps the routing decision in `.intent/` and out of Python. A flow author cannot
select iterative mode without it being visible to the governor in the manifest diff.

The `generation_mode` field is optional. Flows that omit it behave exactly as they do
today — no migration required for existing flow manifests.

### D6 — `flow.build_test_for_symbol` is the first consumer of `iterative` mode

`flow.build_test_for_symbol` (ADR-133) is the first governed flow to declare
`generation_mode: iterative`.

Its acceptance condition is `CompositeAcceptanceCondition([PytestAcceptanceCondition,
AuditAcceptanceCondition])`, mirroring the spike harness's exit gate exactly. This is the
condition whose 10/10 recovery rate the spike evidence supports.

The 119 failed `flow.build_tests` proposals (older generation path) are separately
addressed: after this ADR is implemented, `TestRemediatorWorker` re-queues them as
`flow.build_test_for_symbol` proposals (per ADR-133 D4), which then benefit from iterative
mode automatically.

### D7 — `EnhancedTestGenerator` is deprecated as a generation path

`src/will/self_healing/test_generation/EnhancedTestGenerator` is deprecated. It is not
deleted immediately (dependent code may exist), but:

- No new flows or workers may invoke it.
- `TestRemediatorWorker` must not call it.
- Its `max_fix_attempts`, `max_complexity`, and acceptance logic are not the governed
  contract; `generation_budget.yaml` and `AcceptanceCondition` are.

A follow-on issue will track the removal once no callers remain.

---

## What this ADR does not decide

- **Quality gate beyond pytest + audit.** Assertion density, mutation testing, and
  behavioural coverage gates are not addressed here. The spike noted this gap; closing it
  is a separate ADR. The current gate (`pytest green AND CORE audit pass`) is used as-is.
- **Iterative mode for source-file modification.** The spike evidence is scoped to test
  generation. Extending `iterative` mode to `code_modification` or `code_generation`
  task types requires its own measurement and ADR decision.
- **Parallelism within a single iterative run.** Each iteration is sequential by design —
  the output of one attempt feeds the next. Parallel exploration of multiple generation
  strategies is a separate capability.
- **Harvesting the 10 spike diffs.** The patch files in `spikes/loop_vs_singleshot/results/`
  are forensic artifacts from the spike. They are not applied by this ADR; once
  `flow.build_test_for_symbol` operates in iterative mode on the live proposal pipeline,
  those proposals will be regenerated through the governed path.

---

## Implementation sequence

1. `GenerationMode` enum in `shared.models.generation_mode`
2. `AcceptanceCondition` protocol + three implementations (`pytest`, `audit`, `composite`)
3. `IterativeCoderAgent` with governed budget loading
4. `generation_budget.yaml` in `.intent/enforcement/config/`
5. `FlowExecutor` routing on `generation_mode`
6. `flow.build_test_for_symbol.yaml` updated to declare `generation_mode: iterative`
7. `EnhancedTestGenerator` deprecation notice in docstring + CHANGELOG entry

Each step is an independent, reviewable change. Steps 1–4 introduce no behavioural change
to the live pipeline; step 5 is the activation gate.
