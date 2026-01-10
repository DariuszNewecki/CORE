# V2 Command Pattern Reference

**Status**: PRODUCTION READY
**Reference Implementation**: `core-admin fix clarity`
**Location**: `src/body/cli/commands/fix/clarity.py` + `src/features/self_healing/clarity_service_v2.py`
**Compliance**: 95% V2 Architecture

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
# Build prompt from strategy
prompt = (
    f"Task: Refactor for {strategy.data['strategy']}.\n"
    f"Instruction: {strategy.data['instruction']}\n\n"
    f"SOURCE CODE:\n{original_code}"
)

# Get appropriate cognitive client
coder = await context.cognitive_service.aget_client_for_role(
    "Coder",
    high_reasoning=use_expert_tier
)

# Generate
response = await coder.make_request_async(prompt, user_id="command_id")
new_code = extract_python_code_from_response(response)
```

**Output**: Generated artifact (code, config, documentation)
**Pattern**: Always extract clean output, never assume format

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
**Purpose**: Constitutional authorization gate

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
        # Build feedback prompt for next iteration
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
# CLI entry point
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

# Atomic action wrapper (for orchestration)
@atomic_action(
    action_id="fix.imports",
    intent="Sort imports according to PEP 8",
    impact=ActionImpact.WRITE_METADATA,
    policies=["import_organization"],
    category="fixers",
)
async def fix_imports_internal(write: bool = False) -> ActionResult:
    """Internal atomic action for import sorting."""
    # Same logic as CLI but returns ActionResult
    pass
```

**Pattern**: CLI command + atomic action wrapper. No LLM, no adaptive loop.

---

## Component Selection Guide

| Phase | Component Type | Examples | When to Use |
|-------|---------------|----------|-------------|
| INTERPRET | RequestInterpreter | CLIArgsInterpreter, NaturalLanguageInterpreter | Always (even simple commands) |
| ANALYZE | Analyzer | FileAnalyzer, SymbolExtractor, KnowledgeGraphAnalyzer | When facts needed |
| STRATEGIZE | Strategist | ClarityStrategist, TestStrategist, ValidationStrategist | When decision needed |
| GENERATE | CognitiveService | Coder role, Architect role, Reviewer role | **Only for AI operations** |
| EVALUATE | Evaluator | ClarityEvaluator, ConstitutionalEvaluator, SecurityEvaluator | When quality measurement needed |
| DECIDE | Decider | GovernanceDecider (only one exists) | Always for write operations |
| EXECUTE | ActionExecutor | ActionExecutor.execute(action_id, ...) | Always for mutations |

---

## Decision Tree: Which Pattern?

```
Does the operation require LLM judgment or reasoning?
├─ YES → Use V2 Pattern (7 phases)
│   └─ Examples: refactoring, test generation, complexity fixes
│
└─ NO → Use Simple Pattern (direct tooling)
    └─ Examples: formatting, import sorting, linting
```

---

## Anti-Patterns (DO NOT DO THIS)

❌ **Use V2 for deterministic operations**: Don't use LLM for import sorting
❌ **Skip phases in V2**: Every phase is mandatory when using V2
❌ **Direct file writes**: Always use ActionExecutor
❌ **Bypass DECIDE**: GovernanceDecider is not optional for mutations
❌ **Mutate in ANALYZE**: Analyzers are read-only
❌ **Decision in EVALUATE**: Evaluators measure, don't decide
❌ **Accept worse quality**: Evaluator must validate improvement
❌ **Unbounded loops**: Max 3 attempts is constitutional limit
❌ **Mix patterns**: Keep phase boundaries clean

---

## File Organization Pattern

### V2 Commands (AI-powered)
```
src/body/cli/commands/
  └── [category]/
      └── [command].py          # CLI entry point (thin)

src/features/[domain]/
  └── [command]_service_v2.py   # Orchestration logic (thick)

src/body/analyzers/             # ANALYZE components
src/will/strategists/           # STRATEGIZE components
src/body/evaluators/            # EVALUATE components
src/will/deciders/              # DECIDE components
src/body/atomic/                # EXECUTE actions
```

### Simple Commands (Tool-based)
```
src/body/cli/commands/
  └── [category]/
      └── [command].py          # CLI + atomic action (all-in-one)
```

**Rule**: CLI commands are thin shells. Business logic lives in service layer (V2) or stays in command file (simple).

---

## How to Create a New V2 Command (AI-Powered)

### Step 1: Verify AI is Actually Needed

Ask yourself:
- Does this need LLM reasoning? (refactoring, generation, complex decisions)
- Could ruff/black/mypy/pytest do this? → Use simple pattern instead
- Does quality need evaluation? (is "better" subjective?)

If AI is truly needed, proceed:

### Step 2: Create CLI Entry Point
```python
# src/body/cli/commands/fix/new_command.py

@fix_app.command("new-command")
@core_command(dangerous=True)
async def new_command_cmd(
    ctx: typer.Context,
    target: Path,
    write: bool = typer.Option(False, "--write")
):
    """Your command description."""
    from features.domain.new_command_service_v2 import remediate_new_v2

    core_context: CoreContext = ctx.obj
    await remediate_new_v2(
        context=core_context,
        target=target,
        write=write
    )
```

### Step 3: Create Service Orchestrator
```python
# src/features/domain/new_command_service_v2.py

async def remediate_new_v2(context: CoreContext, target: Path, write: bool):
    """V2 Orchestrator following canonical pattern."""

    # 1. INTERPRET
    interpreter = CLIArgsInterpreter()
    task_result = await interpreter.execute(...)

    # 2. ANALYZE
    analyzer = FileAnalyzer(context)
    analysis = await analyzer.execute(...)

    # 3. STRATEGIZE
    strategist = YourStrategist()
    strategy = await strategist.execute(...)

    # 4-5. GENERATE + EVALUATE (Adaptive Loop)
    max_attempts = 3
    for attempt in range(max_attempts):
        artifact = await generate(...)
        verdict = await evaluate(...)
        if verdict.ok:
            break

    # 6. DECIDE
    decider = GovernanceDecider()
    auth = await decider.execute(...)

    # 7. EXECUTE
    if auth.data["can_proceed"] and write:
        executor = ActionExecutor(context)
        await executor.execute(...)
```

### Step 4: Test
```bash
# Dry run (safe)
poetry run core-admin fix new-command /path/to/target

# Write mode (requires confirmation)
poetry run core-admin fix new-command /path/to/target --write
```

---

## How to Create a Simple Command (Tool-Based)

### Step 1: Verify Simplicity

Ask yourself:
- Is this deterministic? (same input → same output always)
- Does existing tooling solve it? (ruff, black, mypy, pytest)
- No quality judgment needed? (either works or doesn't)

If yes to all, use simple pattern:

### Step 2: Create Single File
```python
# src/body/cli/commands/fix/tool_command.py

@fix_app.command("tool-command")
@core_command(dangerous=False)
async def tool_command_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write")
):
    """Run tool X on codebase."""
    try:
        cmd = ["tool", "arg1", "arg2"]
        if write:
            cmd.append("--fix")

        run_poetry_command("Running tool", cmd)
        console.print("[green]✅ Completed[/green]")
    except Exception as e:
        console.print(f"[red]❌ Failed: {e}[/red]")
        raise typer.Exit(1)

@atomic_action(
    action_id="fix.tool",
    intent="Run tool X",
    impact=ActionImpact.WRITE_METADATA,
    policies=["tool_policy"],
    category="fixers",
)
async def tool_internal(write: bool = False) -> ActionResult:
    """Atomic action wrapper for orchestration."""
    # Same logic, returns ActionResult
    pass
```

### Step 3: Test
```bash
poetry run core-admin fix tool-command --write
```

---

## Decision Tracing (Future Enhancement)

Currently the `fix clarity` command does not explicitly trace decisions. When implementing decision tracing:

```python
from will.orchestration.decision_tracer import DecisionTracer

tracer = DecisionTracer()
tracer.record(
    agent="ClarityStrategist",
    decision_type="strategy_selection",
    rationale=f"Complexity={score} → Selected {strategy}",
    chosen_action=strategy.data["strategy"],
    context={"score": score, "line_count": lines},
    confidence=1.0
)
```

This will enable `core-admin traces show` functionality.

---

## Success Criteria Checklist

### V2 Command (AI-Powered)
A V2 command is complete when:

- [ ] Follows INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE → EXECUTE
- [ ] All phases use Components (not procedural functions)
- [ ] Returns ComponentResult from all components
- [ ] Adaptive loop with max 3 attempts
- [ ] Quality validated by Evaluator before acceptance
- [ ] GovernanceDecider gates execution
- [ ] All mutations through ActionExecutor
- [ ] Works in both dry-run and write modes
- [ ] Logs clearly show phase transitions
- [ ] No direct file I/O outside ActionExecutor

### Simple Command (Tool-Based)
A simple command is complete when:

- [ ] Uses existing proven tooling (ruff, black, mypy, etc.)
- [ ] Has both CLI entry point and atomic action wrapper
- [ ] Supports --write flag (dry-run by default)
- [ ] Returns ActionResult from atomic action
- [ ] Error handling with clear messages
- [ ] No unnecessary complexity
- [ ] Constitutional alignment via atomic_action decorator

---

## Constitutional Alignment

This pattern enforces:
- **Article IV**: Phase separation maintained (V2 only)
- **Mind-Body-Will**: Clear layer boundaries
- **Component Evaluability**: All operations return ComponentResult or ActionResult
- **Constitutional Governance**: GovernanceDecider is mandatory gate for mutations
- **Atomic Actions**: All mutations are auditable
- **Self-Correction**: Adaptive loops with evaluator feedback (V2 only)
- **Tool Reuse**: Prefer existing tooling over custom solutions (Simple commands)

---

**VERSION**: 1.1
**AUTHOR**: CORE Architecture Team
**DATE**: 2026-01-09
**STATUS**: PRODUCTION REFERENCE
**CHANGELOG**:
- v1.1: Added guidance on when to use V2 vs Simple pattern
- v1.0: Initial V2 pattern documentation

---

## Next Steps After Reading This

1. **First**: Determine if your operation needs AI (V2) or tooling (Simple)
2. Study the appropriate reference:
   - V2: `src/features/self_healing/clarity_service_v2.py`
   - Simple: `src/body/cli/commands/fix/imports.py`
3. Run the command to see it in action
4. Copy the appropriate pattern when creating new commands
5. Update this document when patterns evolve

**Remember**: Don't force V2 pattern where simple tooling suffices. The best code is the code you don't write.
