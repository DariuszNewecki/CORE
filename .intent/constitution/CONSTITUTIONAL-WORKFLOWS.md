# Constitutional Workflows

Workflows and phases are constitutional declarations. Their definitions live in `.intent/`. No workflow or phase definition lives in `src/`. Implementation code may consume these declarations; it may not embed them.

A workflow or phase that exists only as code, with no corresponding `.intent/` declaration, is in violation.

## Declaration Locations

- **Phases** are declared under `.intent/phases/`. Each declaration is a YAML document of `kind: phase` validated against `META/phase.schema.json`.
- **Workflows** are declared under `.intent/workflows/`. A workflow declaration composes a sequence of phase declarations.

The phase declarations and the workflow declarations are the authoritative source. Code that derives phase ordering, failure handling, or workflow composition from any other source is in violation.

## Phase Contract

Every phase declaration MUST include:

- `phase_type` — the canonical phase identifier, drawn from `enums.json#/definitions/phase`
- `description` — natural-language statement of the phase's responsibility
- `authority` — the authority class under which the phase operates, drawn from `enums.json#/definitions/authority`
- `failure_modes` — a mapping from failure-class name to response-strategy value (see below)

A phase declaration MAY also declare its `inputs`, `outputs`, `constitutional_requirements`, `permitted_actions`, `forbidden_actions`, `success_criteria`, `notes`, and an `implementation` reference. The full schema is fixed in `META/phase.schema.json`.

## Failure Modes

`failure_modes` is a **mapping** from a phase-local failure-class name to a canonical response-strategy value drawn from `enums.json#/definitions/failure_mode`. It is neither a scalar nor a list.

| Strategy | Semantic |
|---|---|
| `block` | Halt the workflow. The phase did not produce a usable result and no recovery is available without external action. |
| `clarify` | Halt the workflow pending user dialogue. The phase detected ambiguity in its input that the user must resolve before progress is possible. |

Failure-class names — the map keys — are phase-local. Each phase declares the failure classes it can detect, named in terms of its own concerns. The closed-enum discipline applies only to the strategy values; class names are governed locally by each phase declaration.

A phase declaration MUST contain at least one entry in `failure_modes`. A phase that can fail under more than one class MUST declare each class as a separate map entry bound to its corresponding strategy. Modeling distinct failure classes under a single shared value erases the distinction and is in violation.

## Workflow Lifecycle

```
1. Load workflow declaration from .intent/workflows/
2. For each phase named in the workflow:
   a. Load the phase declaration from .intent/phases/
   b. Execute the phase under its declared contract
   c. On failure, dispatch the strategy from failure_modes
      for the detected failure class
   d. Pass declared outputs to the next phase as context
3. Evaluate the workflow's declared success criteria
4. Return the workflow result
```

A phase failure dispatches the strategy bound to the detected failure class. A phase that does not declare a strategy for a detected failure class halts the workflow. There is no implicit fallthrough; an unrecognized or unbound strategy MUST NOT permit silent continuation.

## Separation of Concerns

Each workflow declaration addresses a single goal class. A workflow that mixes responsibilities — for example, code refactoring combined with test generation, or test generation combined with production-code mutation — is in violation. Code-mutating workflows do not generate tests. Test-generating workflows do not mutate production code. Goal-specific composition is the unit of workflow design.

This is the constitutional analogue of the UNIX-philosophy principle: one workflow, one well-defined transformation. A workflow whose stated goal cannot be expressed in a single sentence is suspect.

## Success Criteria

Every workflow declaration MUST include explicit `success_criteria`. The criteria define the conditions under which the workflow's result is considered successful. Workflows that declare no success criteria, or whose criteria cannot be evaluated mechanically, are in violation: such a workflow cannot be audited against its own contract.

Specific threshold values, comparison operators, and signal names are governed by the workflow declaration itself, not by this document.

## Truth Hierarchy

When generated artifacts and pre-existing artifacts disagree on whether code is correct, the pre-existing artifacts prevail. Specifically: when a canary test suite passes and newly-generated tests fail against the same code, the canary result is authoritative. Newly-generated tests are themselves candidate output and may be wrong; the canary suite is established ground.

Workflows MUST gate on the canary result when both signals are available. Workflows MUST NOT gate the commitment of production code on the agreement of newly-generated tests with newly-generated code.

This invariant does not absolve newly-generated tests of correctness; it asserts the order of evidence.

## Constitutional Position

These constraints are constitutional because workflow composition determines what CORE can do autonomously. A drifting workflow definition, a phase with under-declared failure modes, or a workflow with no auditable success criteria each erode the defensibility that the founding charter and the user requirements demand.

This document declares the invariants. Implementation conformance is verified by audit; deviation from it is enforced as governance failure, not corrected silently.
