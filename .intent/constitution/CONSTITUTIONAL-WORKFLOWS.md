# Constitutional Workflow System

## Overview

CORE now uses **dynamic, constitutional workflow orchestration** instead of hardcoded A3 loops.

Workflows are defined in `.intent/workflows/` and composed from reusable phases defined in `.intent/phases/`.

## Architecture

```
.intent/
├── phases/              # Reusable building blocks
│   ├── planning.yaml
│   ├── code_generation.yaml
│   ├── test_generation.yaml
│   ├── canary_validation.yaml
│   ├── sandbox_validation.yaml
│   ├── style_check.yaml
│   └── execution.yaml
│
└── workflows/           # Goal-specific compositions
    ├── refactor_modularity.yaml
    ├── coverage_remediation.yaml
    └── full_feature_development.yaml
```

## Key Principle: Separation of Concerns

**Refactoring ≠ Testing**

Different goals require different phase pipelines:

### Refactor Modularity Workflow
```yaml
phases:
  - planning          # Analyze & propose split
  - code_generation   # Generate refactored code
  - canary_validation # Run EXISTING tests
  - style_check       # ruff, black, constitutional
  - execution         # Apply changes
```

**Does NOT generate tests.** New code starts with 0% coverage.

### Coverage Remediation Workflow
```yaml
phases:
  - planning          # Identify uncovered symbols
  - test_generation   # Generate tests
  - sandbox_validation # Validate in isolation
  - execution         # Promote passing tests
```

**Does NOT modify production code.** Only writes tests.

## Usage

### Explicit Workflow Type (Recommended)

```python
from features.autonomy.autonomous_developer_v2 import develop_from_goal_v2

# Refactor for modularity
await develop_from_goal_v2(
    context=core_context,
    goal="Improve modularity of user_service.py",
    workflow_type="refactor_modularity",
    write=True
)

# Generate missing tests
await develop_from_goal_v2(
    context=core_context,
    goal="Generate tests for payment_processor.py",
    workflow_type="coverage_remediation",
    write=True
)
```

### Legacy Interface (Auto-infers workflow)

```python
from features.autonomy.autonomous_developer import develop_from_goal

# Automatically infers workflow_type from goal text
await develop_from_goal(
    session=session,
    context=core_context,
    goal="Refactor user_service.py",
    write=True
)
```

## Workflow Lifecycle

```
1. Load workflow definition from .intent/workflows/{type}.yaml
2. For each phase in workflow.phases:
   a. Load phase definition from .intent/phases/{phase}.yaml
   b. Execute phase.execute(context)
   c. Check phase.failure_mode (block/warn/continue)
   d. Store outputs in context for next phase
3. Evaluate workflow.success_criteria
4. Return WorkflowResult
```

## Phase Contracts

Each phase has a clear contract:

- **Inputs**: What it needs from context
- **Outputs**: What it produces for next phase
- **Constitutional Requirements**: Rules it must enforce
- **Failure Mode**: What happens if it fails (block/warn/continue)

## Success Criteria

Workflows define explicit success criteria:

```yaml
# refactor_modularity.yaml
success_criteria:
  canary_passes: true              # Existing tests pass
  style_violations: 0              # No style errors
  modularity_score_improvement: "> 10"  # Score improved

# coverage_remediation.yaml
success_criteria:
  at_least_one_test_passing: true  # At least one test works
  coverage_improvement: "> 0"      # Coverage increased
```

## The UNIX Philosophy

Each workflow does **one thing well**:

- `refactor_modularity`: Code structure → Better structure
- `coverage_remediation`: Missing tests → Tests exist
- `full_feature_development`: Nothing → Complete feature

**No workflow tries to do everything.**

## Migration Path

1. **Phase 1**: New services use V2 interface with explicit workflow_type
2. **Phase 2**: Legacy services use backward-compatible wrapper (auto-infers)
3. **Phase 3**: Remove old AutonomousWorkflowOrchestrator
4. **Phase 4**: All code uses explicit workflow types

## Benefits

✅ **Constitutional**: Workflows defined in .intent/, not code
✅ **Composable**: Mix/match phases based on goal
✅ **Traceable**: Each phase logs decisions
✅ **Testable**: Each phase is independent unit
✅ **Evolvable**: Add workflows without touching orchestrator
✅ **Clear**: Different goals = different pipelines

## Example: Modularity Fix Flow

```bash
# User runs
core-admin fix modularity --limit 1 --write

# System executes
ModularityRemediationServiceV2
  ↓
develop_from_goal_v2(workflow_type="refactor_modularity")
  ↓
WorkflowOrchestrator.execute_goal()
  ↓
[Planning → Code Gen → Canary → Style → Execute]
  ↓
Result: Code refactored, tests pass, NO new tests generated
  ↓
(Later) Coverage scanner finds new files with 0% coverage
  ↓
core-admin fix coverage
  ↓
develop_from_goal_v2(workflow_type="coverage_remediation")
  ↓
Result: Tests generated for new modules
```

## The Truth Hierarchy

When code works but tests fail:

```
1. Canary passes = CODE WORKS ✓ (source of truth)
2. New tests fail = TESTS ARE WRONG (fix later)
```

Workflows respect this hierarchy:
- `refactor_modularity` gates on canary, not new tests
- `coverage_remediation` handles test fixing separately

**Working code > Perfect tests**
