<!-- path: .specs/papers/CORE-V2-Command-Pattern-Reference.md -->

# V2 Command Pattern Reference

**Status**: PRODUCTION READY
**Reference Implementation**: `core-admin fix clarity`
**Location**: `src/body/cli/commands/fix/clarity.py` + `src/features/self_healing/clarity_service_v2.py`
**Compliance**: 95% V2 Architecture

---

## Relationship to CORE-V2-Adaptive-Workflow-Pattern.md

This paper and `CORE-V2-Adaptive-Workflow-Pattern.md` describe the same
architectural approach at different levels of abstraction. They are
compatible and complementary, not competing.

**`CORE-V2-Adaptive-Workflow-Pattern.md`** is the constitutional paper.
It defines the abstract loop model, the Component contract, ComponentResult,
and the governance principles that apply to all autonomous operations.
It is authoritative. In case of conflict between the two papers,
`CORE-V2-Adaptive-Workflow-Pattern.md` takes precedence.

**This paper** is the concrete implementation guide for CLI commands.
It translates the abstract loop into the 7-phase sequence a command
developer follows in practice.

**Reconciling the phase counts:**

The Adaptive Workflow paper defines a 6-stage loop:
`INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE`

This paper defines a 7-phase sequence:
`INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE → EXECUTE`

These are the same model. The difference is that the Adaptive Workflow
paper's loop terminates at DECIDE (TERMINATE boundary), and EXECUTE
is what the Adaptive Workflow paper calls "Post-TERMINATE Finalization."
This paper makes EXECUTE explicit as Phase 7 because CLI command
developers need to see it as a distinct step with its own rules
(ActionExecutor, write flag, governance token). Neither paper is wrong;
they describe the same structure at different granularity.

**The DECIDE phase** in this paper corresponds to the GovernanceDecider
gate — the constitutional authorization check before mutation. The
Adaptive Workflow paper's "Continue trying?" and "SOLVED?" decision
points correspond to the adaptive loop logic *within* the Generate →
Evaluate cycle, not to the GovernanceDecider gate. They are different
decisions that both use the word "decide."

---

## Purpose

This document defines the canonical V2 command pattern for CORE. All autonomous operations must follow this structure **when LLM reasoning is required**.

**Success Metric**: An AI agent can read this document and generate a compliant command without human guidance.

---

## When to Use V2 Pattern vs. Direct Tooling

### ✅ Use V2 Pattern (Full 7-Phase Flow) When:
- **LLM judgment required**: Code refactoring, complexity reduction, architectural changes
- **Reasoning needed**: Test generation, documentation writing, design decisions
- **Quality evaluation**: Changes need mathematical validation (complexity, coverage)
- **Adaptive feedback**: Multiple attempts with learning from failures
- **Examples**: `fix clarity`, `fix complexity`, `coverage generate-adaptive`, `develop`

### ❌ Use Direct Tooling (Simple Command) When:
- **Deterministic operations**: Import sorting, code formatting, linting
- **Tool-based fixes**: Black, Ruff, mypy, isort already solve it
- **No judgment needed**: The operation has one correct answer
- **No adaptation needed**: Either works or fails, no iteration
- **Examples**: `fix imports`, `fix code-style`, `check lint`

**Rule**: Don't force V2 pattern where simple tooling suffices. Reserve it for operations requiring intelligence.

---

## The Universal Flow (For AI-Powered Operations)

```
INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE → EXECUTE
```

Every V2 command follows this exact sequence. No exceptions.

---

## Phase-by-Phase Implementation

### Phase 1: INTERPRET (Will Layer)
**Purpose**: Parse user intent into canonical task structure

```python
from will.interpreters.cli_args_interpreter import CLIArgsInterpreter

interpreter = CLIArgsInterpreter()
task_result = await interpreter.execute(
    command="fix",
    subcommand="clarity",
    targets=[str(file_path)],
    write=write
)
task = task_result.data["task"]
```

**Output**: Normalized task with validated targets and constraints

---

### Phase 2: ANALYZE (Body Layer)
**Purpose**: Extract facts from the target without making decisions

```python
from body.analyzers.file_analyzer import FileAnalyzer

analyzer = FileAnalyzer(context)
analysis = await analyzer.execute(file_path=target_path)

if not analysis.ok:
    logger.error("Analysis failed: %s", analysis.data.get("error"))
    return
```

**Output**: Observable facts (line_count, complexity, symbols, dependencies)
**Critical**: No mutations, no decisions - pure observation

---

### Phase 3: STRATEGIZE (Will Layer)
**Purpose**: Make deterministic decision about approach

```python
from will.strategists.clarity_strategist import ClarityStrategist

strategist = ClarityStrategist()
strategy = await strategist.execute(
    complexity_score=analysis.metadata["total_definitions"],
    line_count=analysis.metadata["line_count"]
)

logger.info("Selected Strategy: %s", strategy.data["strategy"])
```

**Output**: Concrete strategy with actionable instruction
**Rule**: Strategy selection is deterministic - same inputs → same strategy

---

### Phase 4: GENERATE (Will Layer)
**Purpose**: Create new artifact using LLM

```python
prompt = (
    f"Task: Refactor for {strategy.data['strategy']}.\n"
    f"Instruction: {strategy.data['instruction']}\n\n"
    f"SOURCE CODE:\n{original_code}"
)

coder = await context.cognitive_service.aget_client_for_role(
    "Coder",
    high_reasoning=use_expert_tier
)

response = await coder.make_request_async(prompt, user_id="command_id")
new_code = extract_python_code_from_response(response)
```

**Output**: Generated artifact (code, config, documentation)

---

### Phase 5: EVALUATE (Body Layer)
**Purpose**: Assess quality against objective criteria

```python
from body.evaluators.clarity_evaluator import ClarityEvaluator

evaluator = ClarityEvaluator()
verdict = await evaluator.execute(
    original_code=original_code,
    new_code=new_code
)

if verdict.ok and verdict.data.get("is_better"):
    logger.info("✅ Improvement: %.1f%%", verdict.data["improvement_ratio"] * 100)
    final_artifact = new_code
else:
    logger.warning("❌ Quality check failed")
```

**Output**: Binary verdict (ok/not ok) + metrics
**Critical**: Evaluator never accepts worse quality

---

### Phase 6: DECIDE (Mind Layer)
**Purpose**: Constitutional authorization gate — GovernanceDecider only

```python
from will.deciders.governance_decider import GovernanceDecider

decider = GovernanceDecider()
authorization = await decider.execute(
    evaluation_results=[verdict],
    risk_tier="ELEVATED" if write else "ROUTINE"
)

if not authorization.data["can_proceed"]:
    blockers = authorization.data.get("blockers", [])
    logger.error("EXECUTION HALTED: %s", ", ".join(blockers))
    return
```

**Output**: Authorization decision + blockers if denied
**Rule**: DECIDE phase can veto execution. No bypass allowed.

---

### Phase 7: EXECUTE (Body Layer)
**Purpose**: Apply approved changes under governance

```python
from body.atomic.executor import ActionExecutor

if authorization.data["can_proceed"] and final_artifact:
    if write:
        executor = ActionExecutor(context)
        await executor.execute(
            "file.edit",
            write=True,
            file_path=target_path,
            code=final_artifact
        )
        logger.info("✅ Changes applied")
    else:
        logger.info("💡 DRY RUN: Changes validated but not applied")
```

**Output**: Mutation applied OR dry-run confirmation
**Critical**: All mutations go through ActionExecutor

---

## The Adaptive Loop Pattern

For operations requiring multiple attempts:

```python
max_attempts = 3
attempt = 0
final_artifact = None

while attempt < max_attempts:
    attempt += 1

    # GENERATE
    artifact = await generate_with_prompt(current_prompt)

    # EVALUATE
    verdict = await evaluator.execute(original=original, new=artifact)

    if verdict.ok and verdict.data["is_better"]:
        final_artifact = artifact
        break  # SUCCESS
    else:
        current_prompt = build_feedback_prompt(verdict, original)
```

**Rules**:
- Maximum 3 attempts (constitutional limit)
- Each failure provides specific feedback
- Loop terminates on first success OR max attempts
- Final attempt uses high-reasoning tier

---

## Simple Command Pattern (Non-AI Operations)

For deterministic operations, use this simpler pattern:

```python
@fix_app.command("imports")
@core_command(dangerous=False)
async def fix_imports_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write")
):
    """Sort imports using ruff."""
    try:
        cmd = ["ruff", "check", "src/", "--select", "I"]
        if write:
            cmd.append("--fix")

        run_poetry_command("Sorting imports", cmd)
        console.print("[green]✅ Import sorting completed[/green]")
    except Exception as e:
        console.print(f"[red]❌ Failed: {e}[/red]")
        raise typer.Exit(1)

@atomic_action(
    action_id="fix.imports",
    intent="Sort imports according to PEP 8",
    impact=ActionImpact.WRITE_METADATA,
    policies=["import_organization"],
    category="fixers",
)
async def fix_imports_internal(write: bool = False) -> ActionResult:
    """Internal atomic action for import sorting."""
    pass
```

---

## Component Selection Guide

| Phase | Component Type | Examples | When to Use |
|-------|---------------|----------|-------------|
| INTERPRET | RequestInterpreter | CLIArgsInterpreter | Always |
| ANALYZE | Analyzer | FileAnalyzer, SymbolExtractor | When facts needed |
| STRATEGIZE | Strategist | ClarityStrategist, TestStrategist | When decision needed |
| GENERATE | CognitiveService | Coder role, Architect role | AI operations only |
| EVALUATE | Evaluator | ClarityEvaluator, ConstitutionalEvaluator | When quality measurement needed |
| DECIDE | Decider | GovernanceDecider (only one exists) | Always for write operations |
| EXECUTE | ActionExecutor | ActionExecutor.execute(action_id, ...) | Always for mutations |

---

## Anti-Patterns

❌ Use V2 for deterministic operations
❌ Skip phases in V2
❌ Direct file writes (always use ActionExecutor)
❌ Bypass DECIDE (GovernanceDecider is not optional for mutations)
❌ Mutate in ANALYZE (analyzers are read-only)
❌ Decision in EVALUATE (evaluators measure, don't decide)
❌ Accept worse quality
❌ Unbounded loops (max 3 attempts is constitutional limit)
❌ Mix patterns

---

## File Organization Pattern

### V2 Commands (AI-powered)
```
src/body/cli/commands/[category]/[command].py     # CLI entry point (thin)
src/features/[domain]/[command]_service_v2.py     # Orchestration logic (thick)
src/body/analyzers/                               # ANALYZE components
src/will/strategists/                             # STRATEGIZE components
src/body/evaluators/                              # EVALUATE components
src/will/deciders/                                # DECIDE components
src/body/atomic/                                  # EXECUTE actions
```

### Simple Commands (Tool-based)
```
src/body/cli/commands/[category]/[command].py     # CLI + atomic action (all-in-one)
```

---

## Constitutional Alignment

This pattern enforces:
- **Article IV**: Phase separation maintained
- **Mind-Body-Will**: Clear layer boundaries
- **Component Evaluability**: All operations return ComponentResult or ActionResult
- **Constitutional Governance**: GovernanceDecider is mandatory gate for mutations
- **Atomic Actions**: All mutations are auditable

---

**VERSION**: 1.2
**CHANGELOG**:
- v1.2: Added reconciliation section for CORE-V2-Adaptive-Workflow-Pattern.md (Finding 41)
- v1.1: Added guidance on when to use V2 vs Simple pattern
- v1.0: Initial V2 pattern documentation
