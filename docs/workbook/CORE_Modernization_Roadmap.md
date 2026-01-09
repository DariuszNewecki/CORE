What You Need (Not Tasks, Just Focus)

Pattern compliance - Everything uses the workflow
Component clarity - Know what exists, what's missing
Autonomous loops - Self-correction everywhere
Conversational routing - Intent → Workflow mapping


# CORE Modernization Roadmap

**Purpose**: Track migration to Universal Adaptive Workflow Pattern across all sessions.
**Status**: ACTIVE
**Current Version**: 2.2.0
**Last Updated**: 2026-01-09

---

## Vision

**Every autonomous operation in CORE follows the universal pattern:**
```
INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE → TERMINATE → FINALIZE
```

**Success Criteria**: No ad-hoc procedural workflows. All operations are component compositions returning `ComponentResult` and governed by the `ActionExecutor`.

---

## Phase 1: Foundation (REFINING)

### 1.1 Document the Pattern ✅
- [x] Create `CORE-Adaptive-Workflow-Pattern.md` paper
- [x] Define `Component` primitive and `ComponentPhase` enum
- [x] Establish `ActionResult` as the universal execution contract

### 1.2 Component Gap Closure (ALMOST COMPLETE)
**Priority: HIGH - Standardize existing thinking/checking logic**

#### RequestInterpreters (INTERPRET Phase) ✅
- [x] Implement `RequestInterpreter` base class
- [x] Implement `CLIArgsInterpreter` (Normalizes Typer input)
- [x] Implement `NaturalLanguageInterpreter` (Powers the `core` CLI)
- [x] Integrate into `ConversationalAgent`

#### Strategists (RUNTIME Phase) ✅
- [x] `TestStrategist`: Decide generation approach based on file type
- [x] `ClarityStrategist`: Decide refactoring path
- [x] `ValidationStrategist`: Choose required checks for risk tiers
- [x] `FixStrategist`: Prioritize code remediation sequence
- [x] `SyncStrategist`: Manage DB/Vector dependency order

#### Evaluators (AUDIT Phase) ✅
- [x] `FailureEvaluator`: Analyze sandbox errors for adaptation
- [x] `ClarityEvaluator`: Measure mathematical complexity reduction
- [x] `ConstitutionalEvaluator`: Assess policy compliance
- [x] `SecurityEvaluator`: Identify secrets and injection risks
- [x] `PerformanceEvaluator`: Track duration and resource overhead

### 1.3 Refactor Legacy Logic (ACTIVE)
**Priority: CRITICAL - Move logic from CLI/Logic to Body/Components**

- [ ] **Refactor Checkers → Evaluators**
  - [ ] `AtomicActionsChecker` → `AtomicActionsEvaluator`
  - [ ] `PatternChecker` → `PatternEvaluator`
  - [ ] Move to `src/body/evaluators/`
- [ ] **Refactor Builders → Analyzers**
  - [ ] `KnowledgeGraphBuilder` → `KnowledgeGraphAnalyzer` (Separate scan from write)
  - [ ] `SymbolExtractor` (Improve to match `Component` base class)
- [ ] **Implement the DECIDE Component**
  - [ ] Create `GovernanceDecider`: A formal component that evaluates if the `AUDIT` results allow the `ActionExecutor` to proceed to `EXECUTION`.

---

## Phase 2: Command Migration (INCREMENTAL)

### 2.1 V2-Hardened Commands
**Priority: HIGH - Finalize "Interpret" and "Decide" wiring**

- [ ] **`core-admin fix clarity`** (Status: 85%)
  - [x] Uses V2 Adaptive Loop
  - [ ] Wire `CLIArgsInterpreter` to the entry point
  - [ ] Use `ValidationStrategist` for pre-flight setup
- [ ] **`core-admin coverage generate-adaptive`** (Status: 75%)
  - [x] Uses V2 Component architecture
  - [ ] Standardize prompt building via `ConstitutionalTestPromptBuilder`
  - [ ] Formalize `DECIDE` phase before `PersistenceService` mutation
- [ ] **`core-admin fix complexity`** (Status: 10%)
  - [ ] Replace legacy `complexity_service.py` with V2 Orchestrator
  - [ ] Wire `FileAnalyzer` → `ComplexityStrategist` → `ClarityEvaluator`

### 2.2 Workflow Composition
**Priority: MEDIUM - Unify multi-step processes**

- [ ] **`core-admin dev-sync`**
  - [x] Uses `ActionExecutor`
  - [ ] Refactor `DevSyncPhases` into a sequence of `SyncStrategist` calls
- [ ] **`core-admin develop`**
  - [x] Uses `AutonomousWorkflowOrchestrator`
  - [ ] Map `PlannerAgent` output directly to `TaskStructure`

---

## Phase 3: Infrastructure & DX

### 3.1 Discovery & Registry
- [x] `discover_components` utility in `shared/`
- [ ] Implement `core-admin components list` for system visibility
- [ ] Auto-generate `Component API Reference` from docstrings

### 3.2 Decision Tracing
- [x] `DecisionTracer` core implementation
- [ ] Implement `core-admin traces list/show`
- [ ] Add JSONL streaming of traces to `var/logs/decisions.jsonl`

---

## Metrics Dashboard

### Overall Progress
- **Phase 1 (Foundation)**: 75% 🔄
- **Phase 2 (Commands)**: 25% 🔄
- **Phase 3 (Infrastructure)**: 15% 🔄
- **Phase 5 (Cleanup)**: 5% ⚪

**Total Modernization**: ~35% complete

### Component Coverage
- **Interpreters**: 3/3 (Base, CLI, NL) - **100%**
- **Analyzers**: 2/5 (File, Symbol) - **40%**
- **Evaluators**: 5/7 (Const, Perf, Sec, Fail, Clar) - **71%**
- **Strategists**: 5/5 (Val, Sync, Fix, Test, Clar) - **100%**
- **Orchestrators**: 2/2 (Standard, Adaptive) - **100%**

---

## Decision Log

**AD-005: Unified ContextService Usage**
- **Date**: 2026-01-09
- **Decision**: All V2 Analyzers must use `ContextService.build_for_task` instead of direct `KnowledgeGraphBuilder` calls.
- **Rationale**: Ensures graph-traversal and semantic context are available to every analysis step.

**AD-006: Sandbox as a Signal, not a Gate**
- **Date**: 2026-01-09
- **Decision**: In `generate-adaptive`, sandbox failure does not block the "Generated" status but triggers a "Quarantine" persistence instead of "Promotion".
- **Rationale**: Preserves LLM work for human review/fixing even if runtime environment is unstable.

---

## Immediate Next Session Priorities

1.  **Refactor Checkers**: Convert `AtomicActionsChecker` to `AtomicActionsEvaluator`.
2.  **Standardize `fix clarity`**: Fully wire it to use `CLIArgsInterpreter` so the input is normalized before the loop starts.
3.  **PathResolver Expansion**: Add `var/canary/` and `var/morgue/` as canonical paths to `PathResolver`.---

**END OF ROADMAP - Update after each session**
