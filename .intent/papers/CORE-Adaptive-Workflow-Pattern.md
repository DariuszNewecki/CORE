<!-- path: .intent/papers/CORE-V2-Adaptive-Workflow-Pattern.md -->

# CORE: V2 Adaptive Workflow Pattern

**Status:** Draft (Greenfield)

**Depends on:**

* `papers/CORE-Constitutional-Foundations.md`
* `papers/CORE-Phases-as-Governance-Boundaries.md`
* `papers/CORE-Authority-Without-Registries.md`

**Audience:** CORE developers, autonomous system architects, AI governance engineers

---

## Abstract

This paper defines the V2 Adaptive Workflow Pattern—a constitutional architecture for self-correcting autonomous operations within CORE. V2 establishes a component-based framework where all autonomous actions flow through a universal sequence: Interpret → Analyze → Strategize → Generate → Evaluate → Decide. The pattern enforces Mind-Body-Will separation, enables pattern-based adaptation, and maintains constitutional governance throughout generation cycles. Unlike procedural V1 approaches, V2 treats every operation as a composition of evaluable, traceable components that adapt to failure patterns while respecting phase boundaries.

---

## 1. Motivation

Autonomous systems that generate code, refactor implementations, or modify their own artifacts face a fundamental challenge: how to self-correct without self-undermining. Early CORE workflows (V1) used procedural approaches with fixed strategies and ad-hoc error handling. This resulted in:

* brittle failure modes (one error pattern → full stop),
* scattered decision logic (strategy selection mixed with execution),
* untraceable adaptations (no record of why pivots occurred),
* constitutional violations (evaluations performed outside proper phases).

V2 emerged from observed patterns in `coverage generate-adaptive` and `fix clarity` commands, where component-based adaptive loops achieved 70-80% autonomous success rates while maintaining constitutional compliance.

This paper formalizes that pattern as constitutional doctrine.

---

## 2. Constitutional Context

V2 Adaptive Workflow Pattern derives authority from:

* **CORE Constitution Article IV** (Phase boundaries must be enforced)
* **Mind-Body-Will Separation** (.intent/ governance, src/ execution, Will/ orchestration)
* **Component Evaluability** (All operations must return structured, evaluable results)
* **Decision Traceability** (Strategic decisions must be recorded for learning)

The pattern is not optional for autonomous operations. It is the constitutional form of self-correction.

---

## 3. Design Principles

### 3.1 Universal Flow Model

ALL autonomous commands follow the same high-level flow:

```
INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE
```

Commands differ only in **which specific components** plug into each phase.

### 3.2 Conceptual Decision Points

The workflow uses **conceptual questions**, not implementation details:

* "Did result improved?" (relative quality assessment)
* "SOLVED?" (multi-dimensional quality gate)
* "Continue trying?" (holistic termination evaluation)

NOT magic numbers like `attempts >= max_attempts` or `pattern_count >= 2`.

### 3.3 TERMINATE Boundary

**TERMINATE marks the end of the generation loop**, not the end of the command.

```
[Setup] → [V2 Generation Loop] → TERMINATE → [Finalization]
```

Post-TERMINATE actions (constitutional audit, file writes, reporting) are command-specific.

### 3.4 Component Architecture

Every step is a Component implementing:

```python
@property
def phase(self) -> ComponentPhase:
    """INTERPRET | PARSE | LOAD | AUDIT | RUNTIME | EXECUTION"""

async def execute(self, **inputs) -> ComponentResult:
    """Returns evaluable, structured result"""
```

---

## 4. Constitutional Phases

V2 introduces **INTERPRET** and formalizes existing phases:

| Phase | Purpose | Component Types |
|-------|---------|-----------------|
| **INTERPRET** | Parse user intent → task structure | RequestInterpreter, CommandParser |
| **PARSE** | Extract facts from code/files | FileAnalyzer, SymbolExtractor |
| **LOAD** | Retrieve data from storage | RepositoryLoader, ConfigLoader |
| **AUDIT** | Evaluate quality, identify patterns | FailureEvaluator, ClarityEvaluator |
| **RUNTIME** | Make deterministic decisions | TestStrategist, ClarityStrategist |
| **EXECUTION** | Mutate state | ActionExecutor, FileHandler |

Phase boundaries are enforced: components cannot evaluate rules outside their declared phase.

---

## 5. Component Types

### 5.1 Interpreters (Will/INTERPRET)

**Purpose:** Convert natural language or structured input → canonical task definition

**Characteristics:**
* Deterministic mapping (same input → same task structure)
* No LLM calls (pure parsing/routing logic)
* Output: `{task_type, targets, constraints}`

**Example:**
```python
class RequestInterpreter(Component):
    phase = ComponentPhase.INTERPRET

    async def execute(self, user_request: str) -> ComponentResult:
        return ComponentResult(
            ok=True,
            data={
                "task_type": "test_generation",
                "targets": ["src/models/user.py"],
                "constraints": {"write": False, "max_attempts": 3}
            },
            next_suggested="file_analyzer"
        )
```

### 5.2 Analyzers (Body/PARSE)

**Purpose:** Extract structural facts without making decisions

**Characteristics:**
* Pure functions (same input → same output)
* No mutations
* Output: Observable facts (`file_type`, `complexity`, `symbols`)

**Example:**
```python
class FileAnalyzer(Component):
    phase = ComponentPhase.PARSE

    async def execute(self, file_path: str) -> ComponentResult:
        tree = ast.parse(code)
        return ComponentResult(
            ok=True,
            data={
                "file_type": "sqlalchemy_model",
                "complexity": 15,
                "line_count": 200
            }
        )
```

### 5.3 Strategists (Will/RUNTIME)

**Purpose:** Make deterministic decisions based on facts

**Characteristics:**
* Rule-based logic (no LLM calls)
* Stateless (no memory between calls)
* Adaptive (consider failure patterns)
* Traceable (use DecisionTracer)

**Example:**
```python
class TestStrategist(Component):
    phase = ComponentPhase.RUNTIME

    async def execute(self, file_type: str, failure_pattern: str = None) -> ComponentResult:
        if failure_pattern == "type_introspection":
            strategy = "integration_tests_no_introspection"
        elif file_type == "sqlalchemy_model":
            strategy = "integration_tests"
        else:
            strategy = "unit_tests"

        self.tracer.record(
            agent="TestStrategist",
            decision_type="strategy_selection",
            rationale=f"Selected {strategy} for {file_type}",
            chosen_action=strategy
        )

        return ComponentResult(
            ok=True,
            data={"strategy": strategy, "approach": "...", "constraints": [...]}
        )
```

### 5.4 Evaluators (Body/AUDIT)

**Purpose:** Assess quality and identify patterns

**Characteristics:**
* Read-only evaluation
* No execution
* Return recommendations (not commands)

**Example:**
```python
class FailureEvaluator(Component):
    phase = ComponentPhase.AUDIT

    async def execute(self, error: str, pattern_history: list) -> ComponentResult:
        pattern = self._classify_error(error)
        occurrences = pattern_history.count(pattern)

        should_switch = occurrences >= 2

        return ComponentResult(
            ok=True,
            data={
                "pattern": pattern,
                "occurrences": occurrences,
                "should_switch": should_switch,
                "recommendation": "switch_strategy" if should_switch else "retry"
            }
        )
```

### 5.5 Orchestrators (Will/RUNTIME)

**Purpose:** Compose components into adaptive workflows

**Characteristics:**
* Follow `next_suggested` hints
* Handle retry logic
* Enforce termination conditions

**Example:**
```python
class ProcessOrchestrator:
    async def run_adaptive(self, initial_component: Component, max_steps: int) -> ComponentResult:
        """Follow next_suggested hints until done"""
        current = initial_component
        for step in range(max_steps):
            result = await current.execute(**accumulated_data)
            if not result.ok or not result.next_suggested:
                return result
            current = self._resolve_component(result.next_suggested)
        return result
```

---

## 6. The Adaptive Loop

### 6.1 Flow Diagram

```
┌─────────────────────────────────────────┐
│ 0. INTERPRET: RequestInterpreter        │
│    → task_type, parameters, constraints │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ 1. ANALYZE: FileAnalyzer                │
│    → file_type, complexity, line_count  │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ 2. STRATEGIZE: TestStrategist           │
│    → strategy, approach, constraints    │
└────────────────┬────────────────────────┘
                 ↓
         ┌──────────────────┐
         │ Did result       │
         │ improved?        │
         └────┬─────────────┘
              │
       ┌──────┴──────┐
       │ NO          │ YES
       ↓             ↓
┌─────────────────────────────────────────┐
│ 3. GENERATE: CognitiveService           │
│    → proposed_code                      │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ 4. EVALUATE: FailureEvaluator/Sandbox   │
│    → pattern, should_switch, confidence │
└────────────────┬────────────────────────┘
                 ↓
          ┌──────────────┐
          │   SOLVED?    │
          └──────┬───────┘
                 │
        ┌────────┴────────┐
        │ YES             │ NO
        ↓                 ↓
    TERMINATE      ┌──────────────────┐
                   │ Continue trying? │
                   └────┬─────────────┘
                        │
                 ┌──────┴──────┐
                 │ NO          │ YES
                 ↓             ↓
            TERMINATE   (back to "Did result improved?")
```

### 6.2 Decision Point Semantics

**"Did result improved?"**
* Compares current attempt to previous attempt
* Not "is it perfect?" but "is it better?"
* YES → Keep current strategy, continue generating
* NO → Consider strategy pivot

**"SOLVED?"**
* Multi-dimensional quality gate:
  - Syntax valid?
  - Tests pass?
  - Constitutional compliant?
  - Quality improved?
* ALL gates must pass
* YES → TERMINATE (success)
* NO → Continue evaluation

**"Continue trying?"**
* Holistic termination evaluation:
  - Time exceeded?
  - Attempts exhausted?
  - Confidence too low?
  - Stuck in loop?
  - No strategies left?
* ANY trigger → TERMINATE (failure)
* NONE → Continue loop

---

## 7. ComponentResult Contract

Every component returns:

```python
@dataclass
class ComponentResult:
    component_id: str          # Which component produced this
    ok: bool                   # Binary success indicator
    data: dict[str, Any]       # Component-specific output
    phase: ComponentPhase      # Constitutional phase
    confidence: float          # 0.0-1.0 for workflow routing
    next_suggested: str        # Hint for adaptive workflows
    metadata: dict[str, Any]   # Context for downstream components
    duration_sec: float        # Performance tracking
```

**Constitutional requirements:**
* `ok` is binary (not "partially succeeded")
* `confidence` is for workflow routing (not accuracy metric)
* `next_suggested` is a hint (orchestrator may ignore)
* `metadata` accumulates context across workflow

---

## 8. Decision Tracing

All strategic decisions MUST be traced:

```python
from will.orchestration.decision_tracer import DecisionTracer

tracer = DecisionTracer()
tracer.record(
    agent="TestStrategist",
    decision_type="strategy_pivot",
    rationale="Failure pattern 'type_introspection' occurred 3x",
    chosen_action="integration_tests_no_introspection",
    context={"pattern": "type_introspection", "count": 3},
    confidence=0.95
)
```

Traces are stored for:
* Post-mortem analysis
* Pattern learning
* Constitutional audit trails
* Debugging autonomous operations

---

## 9. Post-TERMINATE Finalization

TERMINATE marks the end of the generation loop, NOT the end of the command.

### 9.1 Command-Specific Finalization

**`coverage generate-adaptive`:**
```
TERMINATE → Persist tests to /tests or var/artifacts
         → Generate test report
         → Update coverage metrics
```

**`fix clarity`:**
```
TERMINATE → Constitutional audit of refactored code
         → Execute file.edit (if --write and audit passes)
         → Calculate complexity metrics
         → Report improvement ratio
```

**`develop`:**
```
TERMINATE → Create files in proper directories
         → Run test suite
         → Commit changes (if tests pass)
         → Report completion status
```

### 9.2 Finalization Rules

* Finalization MUST check `--write` flag before mutations
* Constitutional audit MUST occur before EXECUTION phase
* Failures in finalization do not invalidate generation results
* Finalization reports success/failure to user

---

## 10. V2 Compliance Checklist

For a command to be V2-compliant:

- [ ] Uses Component-based architecture (not procedural functions)
- [ ] All phases explicitly declared (Interpreter/Analyzer/Evaluator/Strategist)
- [ ] Returns ComponentResult from all components
- [ ] Implements adaptive loop with conceptual decision points:
  - [ ] "Did result improved?" (relative quality)
  - [ ] "SOLVED?" (multi-dimensional gate)
  - [ ] "Continue trying?" (holistic evaluation)
- [ ] Uses DecisionTracer for strategic decisions
- [ ] Evaluator validates quality before accepting
- [ ] Constitutional compliance checks integrated
- [ ] No global state mutations outside EXECUTION phase
- [ ] Idempotent operations (same inputs → same outputs)
- [ ] Clear separation: Generation Loop → TERMINATE → Finalization
- [ ] Finalization handles write mode, persistence, reporting

---

## 11. V2 Anti-Patterns

**Forbidden patterns that violate V2 principles:**

❌ **Bypassing Evaluators:** Accepting LLM output without validation
❌ **Direct Mutations:** Writing files without ActionExecutor
❌ **Missing Tracing:** Strategic decisions without DecisionTracer
❌ **Fixed Strategies:** No adaptation to failure patterns
❌ **Implementation-Detail Decisions:** Checking counters instead of conceptual questions
  - Bad: `if attempts >= max_attempts`
  - Good: `if should_give_up(context)`
❌ **Imperative Flow:** `if/else` chains instead of component composition
❌ **Global State:** Modifying shared state outside EXECUTION phase
❌ **Missing TERMINATE Boundary:** Not separating generation from finalization
❌ **Absolute Quality Gates:** "Is it perfect?" instead of "Did it improve?"
❌ **Unbounded Loops:** No termination conditions

---

## 12. Migration Path: V1 → V2

Existing commands should migrate incrementally:

### Phase 1: Extract Components
1. **Extract Analyzers:** Convert data extraction to Analyzer components
2. **Extract Evaluators:** Convert quality checks to Evaluator components
3. **Extract Strategists:** Convert decision logic to Strategist components

### Phase 2: Compose Workflow
4. **Build Orchestrator:** Wire components into adaptive workflow
5. **Add Tracing:** Instrument with DecisionTracer
6. **Add Evaluation Gates:** Validate before accepting outputs

### Phase 3: Add Adaptation
7. **Add Retry Logic:** Implement failure recovery loops
8. **Add Pattern Detection:** Identify recurring failure modes
9. **Add Strategy Pivots:** Switch strategies on repeated patterns

### Phase 4: Finalize Boundaries
10. **Separate TERMINATE:** Decouple generation from finalization
11. **Add Conceptual Decisions:** Replace counters with holistic evaluation
12. **Constitutional Audit:** Ensure all phases respect boundaries

---

## 13. File Locations

V2 components are organized by constitutional role:

```
src/body/
  analyzers/          # PARSE phase components
    file_analyzer.py
    symbol_extractor.py
  evaluators/         # AUDIT phase components
    clarity_evaluator.py
    failure_evaluator.py
  atomic/
    executor.py       # EXECUTION phase

src/will/
  strategists/        # RUNTIME phase components
    test_strategist.py
    clarity_strategist.py
  orchestration/
    process_orchestrator.py
    decision_tracer.py
    cognitive_service.py

src/features/
  test_generation_v2/
    adaptive_test_generator.py  # Orchestrator
  self_healing/
    clarity_service_v2.py       # Orchestrator

shared/
  component_primitive.py  # Base classes and interfaces
```

---

## 14. Implementation Notes

### 14.1 Confidence Scoring

Confidence is a workflow circuit breaker, not precision metric:

* confidence < 0.3 → Stop workflow, cannot proceed safely
* confidence 0.3-0.7 → Proceed with caution, increase validation
* confidence > 0.7 → High trust, normal operation

### 14.2 Pattern Memory

Strategists should track attempted strategies to prevent loops:

```python
attempted_strategies = set()
if strategy in attempted_strategies:
    # Already tried this, pick different one
    strategy = self._next_fallback_strategy()
attempted_strategies.add(strategy)
```

### 14.3 Component Discovery

Components can be discovered dynamically:

```python
from shared.component_primitive import discover_components

analyzers = discover_components('body.analyzers')
file_analyzer = analyzers['fileanalyzer']()
result = await file_analyzer.execute(file_path="models.py")
```

---

## 15. Relationship to Other Papers

### 15.1 Constitutional Foundations
V2 pattern enforces Article IV (phase boundaries) through component-level phase declarations.

### 15.2 Authority Without Registries
Components resolve authority at runtime from declared rules, not from static registries.

### 15.3 Phases as Governance Boundaries
Each component declares its phase explicitly, preventing cross-phase evaluation.

### 15.4 Common Governance Failure Modes
V2 prevents temporal leakage (audit influencing runtime) through strict phase separation.

---

## 16. Non-Goals

V2 Adaptive Workflow Pattern explicitly does NOT:

* Define storage formats for traces
* Specify UI/UX for viewing decision history
* Mandate specific LLM providers
* Define rollback strategies
* Specify retry timing/backoff algorithms
* Define component discovery mechanisms
* Mandate specific testing frameworks

These are implementation concerns, not constitutional requirements.

---

## 17. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in accordance with the CORE amendment mechanism.

Amendments must preserve:
* Phase boundary enforcement
* Component evaluability
* Decision traceability
* Mind-Body-Will separation

---

## 18. Closing Statement

V2 Adaptive Workflow Pattern is not optional for autonomous operations.

It is the constitutional form of self-correction within CORE.

Systems that can act must adapt.
Systems that adapt must trace their decisions.
Systems that trace their decisions can be governed.

This is the foundation.

**End of Paper.**
