# ADR-003: task_type as a first-class field on ExecutionTask

**Status:** Accepted
**Date:** 2026-04-19
**Authors:** Darek (Dariusz Newecki)

## Context

The `build.tests` atomic action was producing hallucinated tests. The Gap 2 + Gap 3 change-set (landed 2026-04-19) closed the symptom: by pointing `ExecutionTask.params.file_path` at the source file being tested rather than the not-yet-existing test file, `CodeGenerator._build_context_package` now calls `ContextService.build_for_task` with a target that actually exists, so the evidence retrieved is real. First dry-run against `src/shared/time.py` confirmed the fix — generated tests reference real symbols (`now_iso`, `datetime`, `timezone`) rather than invented ones.

That fix works by redirection, not by design. The structural problem remains.

Inside `CodeGenerator._build_context_package`, the task_spec built for `ContextService.build_for_task` hardcodes:

```python
"task_type": "code_generation",
```

regardless of whether the caller is generating code, generating tests, repairing a failure, or tagging capabilities. `ContextService.build_for_task` then maps this through `_PHASE_BY_TASK_TYPE`:

```python
_PHASE_BY_TASK_TYPE = {
    "code_generation":   "execution",
    "code_modification": "execution",
    "test_generation":   "audit",
    "test.generate":     "audit",
    "conversational":    "runtime",
}
```

The mapping already anticipates test generation as a distinct task type routed to the `audit` phase. The mechanism exists. The signal to reach it does not — every caller is labelled as `code_generation`, regardless of intent.

The consequences of mislabelling are not yet visible. They are latent.

- The `ContextBuildRequest.phase` field feeds rule selection, prompt template selection, and any future phase-conditioned behaviour. Downstream consumers that branch on phase currently see `execution` for test generation, which is wrong.
- The constitutional envelope injection logic is phase-aware. A rule scoped to `audit` phase is not currently being injected into test-generation prompts, even though test generation is constitutionally an audit-phase activity.
- Any prompt template that branches on `task_type` (none do today, but the Prompt Canon anticipates this) cannot be authored safely.
- The fix in ADR-003's predecessor change-set made test generation *work*. It did not make the system *honest about what it was doing*.

Nothing downstream is checking hard enough today for the mislabelling to produce a user-visible regression. That is exactly the condition under which governance debt accumulates silently. Correcting the signal now, before consumers are written against the incorrect default, is cheaper than correcting it after.

## Decision

`task_type` becomes a first-class field on `ExecutionTask`.

- `ExecutionTask` gains a `task_type: str` field with a default of `"code_generation"` for backward compatibility with existing construction sites.
- `CoderAgent.generate_or_repair` passes `task.task_type` through to `CodeGenerator`.
- `CodeGenerator._build_context_package` uses `task.task_type` instead of the hardcoded `"code_generation"` string when constructing the task_spec for `ContextService.build_for_task`.
- `build_tests_action` sets `task_type="test_generation"` when constructing the `ExecutionTask` it hands to `CoderAgent`.
- The set of permitted `task_type` values is constrained to the keys of `ContextService._PHASE_BY_TASK_TYPE`. A value outside that set is a construction error, not a runtime error.

The admission test for this change is: *every call to `ContextService.build_for_task` made via `CoderAgent` must carry the task_type the caller actually intended, not the default.*

## Alternatives Considered

**Make `task_type` a required parameter on `CoderAgent.generate_or_repair`.** Rejected. Every existing caller of `generate_or_repair` would need to be migrated in the same change-set, and the migration surface is large — `build_tests_action`, the `interactive_test` workflow, the self-healing remediation paths, and any future caller. A required parameter also forecloses the possibility of new callers legitimately wanting the default. The optional-with-default pattern preserves backward compatibility without compromising correctness for callers that opt in.

**Add `task_type` to `TaskParams` instead of `ExecutionTask`.** Rejected. `TaskParams` is concerned with *what* the task operates on (file path, symbol name) — not *what kind* of task it is. Task kind is a property of the task itself. Placing it in `TaskParams` would be a category error and would force every `TaskParams` construction site to make a decision about task kind that belongs one level up.

**Leave `task_type` inside `_build_context_package` and pass it as a kwarg to `generate_or_repair`.** Rejected. This treats task_type as a cross-cutting concern threaded through argument lists rather than as a property of the task. It also splits the source of truth: the `ExecutionTask` describes the task, but a second, disconnected parameter describes what kind of task it is. The two can fall out of sync.

**Move `_PHASE_BY_TASK_TYPE` to `.intent/`.** Deferred, not rejected. The phase-to-task-type mapping is a policy decision that belongs in `.intent/`, consistent with the principle established in ADR-002 ("Policy decisions in `.intent/`, mechanisms in `src/`"). However, moving it requires a separate ADR and touches `ContextService` rather than `CoderAgent`. Out of scope for this decision. A follow-up ADR should address it; tracked as a known gap.

**Do nothing and rely on the `target_file` redirection.** Rejected. This is the duct-tape. It works today because no downstream consumer branches on phase strongly enough to produce a user-visible bug. That condition is not stable. The first prompt template or rule that correctly conditions on `audit` phase will produce a silent regression for test generation. Governance debt that compounds silently is worse than governance debt that breaks loudly.

## Consequences

**Positive:**

- `ContextService.build_for_task` receives the true task type, which flows through to the phase label, which is what rule selection and constitutional envelope injection already branch on. Test generation will correctly run through the `audit` phase rather than the `execution` phase.
- Future prompt templates, rule scopes, and phase-conditioned behaviours can be authored against accurate phase labels without first having to untangle a lie.
- The default value (`"code_generation"`) preserves behaviour for all existing construction sites that are not updated, so migration can be incremental.
- `build_tests_action` becomes structurally correct rather than coincidentally correct. The same pattern applies to any future atomic action that generates a non-code artifact through `CoderAgent`.

**Negative:**

- `ExecutionTask` is a widely-used model. Adding a field, even with a default, requires the model definition to change and may touch any serializer, validator, or consumer that enumerates fields. Expected blast radius is small but not zero.
- The `task_type` values are now a small closed vocabulary (`code_generation`, `code_modification`, `test_generation`, `test.generate`, `conversational`). Expanding this vocabulary requires a coordinated change across `ContextService._PHASE_BY_TASK_TYPE` and any new caller. This is the right constraint, but it is a constraint.
- The inconsistency between `"test_generation"` and `"test.generate"` in the existing phase map is inherited by this decision. A tidy-up is warranted but deferred.

**Neutral:**

- No runtime behaviour changes for any existing caller unless that caller is explicitly updated to pass a non-default `task_type`. The change is opt-in.
- The validation that `task_type` is a member of `_PHASE_BY_TASK_TYPE.keys()` is a small amount of new enforcement logic, living near the model definition.

## References

- Gap 2 + Gap 3 change-set, 2026-04-19 — first dry-run verification of `build.tests` against `src/shared/time.py`
- `src/shared/infrastructure/context/service.py` — `ContextService.build_for_task` and `_PHASE_BY_TASK_TYPE`
- `src/will/agents/code_generation/*` — `CodeGenerator._build_context_package`
- `src/will/agents/coder_agent.py` — `CoderAgent.generate_or_repair`
- `src/body/atomic/build_tests_action.py` — primary beneficiary of this change
- `src/shared/models/execution_models.py` — `ExecutionTask`, `TaskParams`
- ADR-002 — established the "Policy in `.intent/`, mechanism in `src/`" principle this ADR defers
- Related follow-up: move `_PHASE_BY_TASK_TYPE` into `.intent/` (not yet authored)
