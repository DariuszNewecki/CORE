# ADR-004: Govern task_type → phase mapping in `.intent/` and retire the vestigial context CLI

**Status:** Accepted
**Date:** 2026-04-19
**Authors:** Darek (Dariusz Newecki)

## Context

ADR-003 introduced `task_type` as a first-class field on `ExecutionTask` and made `CoderAgent` pass it through to `ContextService.build_for_task`. In doing so, it deliberately deferred two loose ends:

1. The task_type → phase map (`_PHASE_BY_TASK_TYPE`) lives inside the body of `ContextService.build_for_task` at `src/shared/infrastructure/context/service.py`. The map is policy — it decides which governance phase each task type routes to — but it is encoded as mechanism, hard-coded in `src/`. This violates the principle established by ADR-002 ("Policy in `.intent/`, mechanism in `src/`").
2. ADR-003 introduced `_ALLOWED_TASK_TYPES` in `src/shared/models/execution_models.py` as a closed-vocabulary validator for the new field. Its comment explicitly notes the duplication with the phase map and defers the collapse to a follow-up decision.

Reconnaissance for this ADR uncovered a third site that the ADR-003 reconnaissance did not surface: `src/cli/resources/context/build.py` carries its own copy of the same vocabulary, with a different unknown-task default (`"runtime"` versus the service map's `"execution"`). This copy is the one actually reached by `core-admin context build` — the user-facing CLI. So the drift is not two-way but three-way: the service map, the live CLI map, and a fourth vocabulary (unrelated to this ADR but worth naming) inside a fourth file that is no longer reachable.

That fourth file is `src/shared/infrastructure/context/cli.py`. It contains its own `_PHASE_BY_TASK` helper with an entirely disjoint vocabulary (`code_review`, `code_analysis`, `investigation`, `workflow_execution`, `workflow_design`) and was the previous home of `context build`, `context validate`, and `context show` Typer commands. The Resource-First CLI v2.0 commit (`b9ca5b57`, 2026-02-03) superseded it by introducing `src/cli/resources/context/` — the directory that `core-admin context` now dispatches to. Since that supersession, `src/shared/infrastructure/context/cli.py` has had no functional edits, only housekeeping. Reconnaissance confirmed:

- No Python module in `src/` imports from it.
- No `.intent/` YAML references it.
- No `.specs/` paper references it.
- No `pyproject.toml` console-script entry exposes it.
- No `README` or Markdown file mentions it.
- Git log shows no commit ever made a deliberate decision to keep it.

The file is dead code. Its vocabulary exists nowhere else as task_type strings. It is retired in this ADR alongside the map migration because the two questions share a subject — "what does the governed task_type vocabulary look like?" — and answering one without the other leaves the other open.

The consequence of leaving the current state in place is not hypothetical. Three copies of a policy vocabulary with two different unknown-task defaults means any code path that calls `ContextService` directly gets one behaviour, any code path that goes through the CLI gets another, and no caller or reviewer has a single place to consult to answer "what phase does a `test_generation` task route to?". The answer today is `"audit"` in all three live copies only by coincidence, not by governance. The first time a caller changes one copy without the others, the coincidence ends, and the resulting drift will be silent.

## Decision

The task_type → phase mapping moves to `.intent/enforcement/config/task_type_phases.yaml`, loaded via `IntentRepository`. Both live call sites (`ContextService.build_for_task` and `src/cli/resources/context/build.py`) read from the same governed source through a single new helper. The `_ALLOWED_TASK_TYPES` frozenset in `execution_models.py` is collapsed — its content comes from the same YAML, loaded at import time. The vestigial `src/shared/infrastructure/context/cli.py` is retired in the same change-set.

**Concretely:**

- A new file `.intent/enforcement/config/task_type_phases.yaml` holds the canonical mapping, with a single top-level `mapping` key and a single `default_phase` key. The vocabulary is the one shared today between the service and the live CLI: `code_generation`, `code_modification`, `test_generation`, `test.generate`, `conversational`. Each maps to one of the five `PhaseType` values: `parse`, `load`, `audit`, `runtime`, `execution`. The default_phase is `execution` — see Alternatives.
- A new helper `src/shared/infrastructure/intent/task_type_phases.py` exposes:
  - `load_task_type_phases() -> dict[str, Any]` — reads the YAML via `IntentRepository`, with a last-resort fallback to the current vocabulary if the file cannot be loaded. Mirrors the pattern established by `test_coverage_paths.py` (ADR-003's change-set).
  - `resolve_phase(task_type: str, config: dict[str, Any] | None = None) -> str` — returns the phase for a task_type, falling back to the configured `default_phase`.
  - `allowed_task_types(config: dict[str, Any] | None = None) -> frozenset[str]` — returns the vocabulary keys. Used by `execution_models.py` at import time.
- The loader validates every emitted phase value against the `PhaseType` `Literal` set at load time. A YAML that maps a task type to a phase outside `{parse, load, audit, runtime, execution}` raises `ValueError` at load, not at the call site.
- `ContextService.build_for_task` removes its method-local `_PHASE_BY_TASK_TYPE` and calls `resolve_phase(task_type)` instead.
- `src/cli/resources/context/build.py` removes its module-level `_PHASE_BY_TASK` and calls `resolve_phase(task)` instead. The file's `TASK_TYPES` list also retires in favour of `allowed_task_types()`.
- `src/shared/models/execution_models.py` replaces the hardcoded `_ALLOWED_TASK_TYPES` frozenset with a module-level value obtained from `allowed_task_types()` at import time. The `field_validator` on `task_type` remains unchanged in behaviour.
- `src/shared/infrastructure/context/cli.py` is deleted in its entirety. With the file gone, the stale `_PHASE_BY_TASK` vocabulary it contained (the disjoint one — `code_review`, `code_analysis`, `investigation`, `workflow_execution`, `workflow_design`) disappears with it. None of those keys migrate to `.intent/`; governing a vocabulary no caller uses is worse than deleting it.
- The `# type: ignore[arg-type]` comments on the `phase=phase` arguments at both call sites are removed — `resolve_phase` returns `PhaseType` by type annotation, so the ignore is no longer necessary.

The admission test: after this change, the question "what phase does task_type X route to?" has exactly one answer in the repository, and that answer lives in `.intent/`.

## Alternatives Considered

**Move only the service map; leave the CLI copy and the vestigial file alone.** Rejected. The CLI copy is the one a user reaches via `core-admin context build`; leaving it unmigrated means the user-facing surface is still mechanism, and a second ADR would be needed to finish the job. The vestigial file would then need a third ADR. One coherent decision is honest; three sequential half-decisions dilute the discipline the ADR process exists to enforce.

**Move the map and the CLI copy to `.intent/`, retire the vestigial file in a separate follow-up change-set.** Considered. The case for separation is that retiring a whole file has a different blast radius than moving a map — if a grep-missed reference turns up, the two changes would be easier to disentangle if they were separate change-sets. The case against is that the retirement check for this file was exhaustive: five independent evidence sources (`.intent/`, `.specs/`, `pyproject.toml`, Markdown, git log), all zero hits, and the file's history confirms no deliberate intent to preserve. Under verified ground truth, the separation serves no purpose. One change-set, same ADR.

**Preserve the vestigial vocabulary in the new `task_type_phases.yaml` for completeness.** Rejected. The keys (`code_review`, `code_analysis`, `investigation`, `workflow_execution`, `workflow_design`) are not used as task_type strings anywhere in the repository — reconnaissance confirmed. The unrelated hits for some of those tokens (`CodeAnalysisPhase` class name, `code_review` function name in `reviewer.py`) belong to a different conceptual surface. Enshrining an unused vocabulary in `.intent/` is not neutrality — it is obligation for every future maintainer to reason about whether those keys are live or dead. Delete now.

**Keep the unknown-task default at whichever value `build.py` currently emits (`"runtime"`).** Rejected. The live CLI and the live service today default to different phases — `"runtime"` and `"execution"` respectively. One of them is wrong; both cannot be correct for the same policy question. `"execution"` is chosen as the canonical default on the following reasoning: an unknown task_type is most safely assumed to be a write-intent task under ordinary governance, which is what the `execution` phase supplies. Routing unknown task types to `audit` or `runtime` would silently bypass execution-phase rules; routing them to `execution` is the failure mode a reviewer is most likely to notice. The default is stated in the YAML, not inferred in code, so a future revision is a one-line edit to `.intent/` rather than a code change.

**Unify the vocabularies into a single map.** Already rejected during the reconnaissance phase of this ADR — the reasoning was that the two vocabularies describe different conceptual surfaces (task submitted to the agent vs task submitted through the CLI). Reconnaissance then established that the second vocabulary has no live consumer. The question is moot; there is only one vocabulary worth governing.

## Consequences

**Positive:**

- One source of truth for the task_type → phase mapping: `.intent/enforcement/config/task_type_phases.yaml`. The question "what phase does test_generation route to?" has one answer, auditable from `.intent/` without reading `src/`.
- The discipline from ADR-002 ("policy in `.intent/`, mechanism in `src/`") is applied to a policy decision that had drifted into three Python files. The drift is paid down, not papered over.
- ADR-003's deliberate duplication (`_ALLOWED_TASK_TYPES`) collapses in the same ADR that created the new governed file — a loose end from one ADR closed by the next, within one session of architectural work.
- Runtime validation of phase values is added at load time, closing the gap between `PhaseType`'s static guarantee and the YAML's runtime looseness. The `# type: ignore[arg-type]` annotations at the call sites can be removed.
- A fossil file is retired. Fossil files accumulate cognitive load on every reader; retiring them is cheap maintenance with compounding returns.

**Negative:**

- Two call sites depend on a YAML file being readable at runtime. The helper's fallback to the current vocabulary limits the blast radius if `.intent/` is unreachable, but the fallback vocabulary is a second place the keys live. Acceptable because the fallback is last-resort-only and logged as a warning; not acceptable if it becomes a silent alternative code path.
- Deleting `src/shared/infrastructure/context/cli.py` is irreversible in a way that moving a map is not. The retirement check was thorough, but a grep-missed reference — a dynamic `importlib` call, a stringly-typed plugin registry, an external tool outside this repo — would surface only when something breaks. Risk is low based on the evidence; not zero.
- `execution_models.py` now imports from `shared.infrastructure.intent.task_type_phases` at module import time. Any import-order subtlety in this path (e.g., `IntentRepository` bootstrap ordering) will surface during the change-set, not after.

**Neutral:**

- No user-visible behaviour change is intended. The same task_types map to the same phases as before. The default for unknown task_types changes in the CLI from `"runtime"` to `"execution"`, but the service path (the one anything real uses) was already `"execution"` — the change harmonizes an inconsistency that no caller was relying on.
- The `core-admin context build` CLI command continues to work unchanged from the user's perspective.
- Future additions to the task_type vocabulary become a single `.intent/` edit plus a migration of callers, not a change to three Python files.

## References

- ADR-002 — established "policy in `.intent/`, mechanism in `src/`"
- ADR-003 — introduced `task_type` on `ExecutionTask`; explicitly deferred this decision
- `src/shared/infrastructure/context/service.py` — `ContextService.build_for_task` (primary call site)
- `src/cli/resources/context/build.py` — second live call site
- `src/shared/infrastructure/context/cli.py` — retired in this change-set
- `src/shared/models/execution_models.py` — `_ALLOWED_TASK_TYPES` collapses in this change-set
- `src/shared/infrastructure/intent/test_coverage_paths.py` — pattern reference for the new helper
- `src/shared/infrastructure/context/models.py` — `PhaseType` Literal, used for load-time validation
