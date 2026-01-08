What You Need (Not Tasks, Just Focus)

Pattern compliance - Everything uses the workflow
Component clarity - Know what exists, what's missing
Autonomous loops - Self-correction everywhere
Conversational routing - Intent → Workflow mapping


# CORE Modernization Roadmap

**Purpose**: Track migration to Adaptive Workflow Pattern across all sessions.
**Status**: ACTIVE - Update this file as work progresses.
**Last Updated**: 2026-01-08

---

## Vision

**Every autonomous operation in CORE follows the universal pattern:**
```
INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE → TERMINATE → FINALIZE
```

**Success Criteria**: No ad-hoc workflows. No procedural code. All operations are component compositions.

---

## Phase 1: Foundation (CRITICAL PATH)

### 1.1 Document the Pattern ✅
- [x] Create CORE-Adaptive-Workflow-Pattern.md paper
- [x] Create Component Inventory
- [x] Create Modernization Roadmap (this document)
- [ ] Add examples to paper (one per command type)
- [ ] Review with team/stakeholders

### 1.2 Fill Critical Gaps
**Priority: HIGH - Blocks everything else**

#### RequestInterpreter (INTERPRET Phase)
- [ ] Create `src/will/interpreters/` directory
- [ ] Implement `RequestInterpreter` base class
- [ ] Implement `CLIRequestInterpreter` (parse typer args → task structure)
- [ ] Implement `NaturalLanguageInterpreter` (for conversational interface)
- [ ] Add tests for interpreters
- [ ] Document interpreter contract

**Deliverable**: Every command starts with INTERPRET phase

#### Missing Strategists
- [ ] Create `ValidationStrategist` (choose validation approach)
- [ ] Create `SyncStrategist` (decide sync order)
- [ ] Create `FixStrategist` (select fix priority)
- [ ] Add tests for new strategists
- [ ] Document strategist patterns

**Deliverable**: Complete decision coverage for common operations

#### Missing Evaluators
- [ ] Create `ConstitutionalEvaluator` (assess policy compliance)
- [ ] Create `PerformanceEvaluator` (measure speed/memory)
- [ ] Create `SecurityEvaluator` (identify risks)
- [ ] Add tests for new evaluators
- [ ] Document evaluator patterns

**Deliverable**: Comprehensive quality gates

### 1.3 Refactor Existing Components
**Priority: MEDIUM - Improves consistency**

#### Checkers → Evaluators
- [ ] Refactor `AtomicActionsChecker` → `AtomicActionsEvaluator`
  - [ ] Change to Component base class
  - [ ] Return ComponentResult
  - [ ] Add phase = AUDIT
  - [ ] Update callers
- [ ] Refactor `PatternChecker` → `PatternEvaluator`
  - [ ] Change to Component base class
  - [ ] Return ComponentResult
  - [ ] Add phase = AUDIT
  - [ ] Update callers
- [ ] Move to `src/body/evaluators/`
- [ ] Update tests

**Deliverable**: All quality checks use Evaluator interface

#### Builders → Analyzers
- [ ] Refactor `KnowledgeGraphBuilder` → `KnowledgeGraphAnalyzer`
  - [ ] Separate analysis from persistence
  - [ ] Return ComponentResult
  - [ ] Add phase = PARSE
  - [ ] Move persistence to separate component
- [ ] Refactor `PromptBuilder` → `PromptAnalyzer`
  - [ ] Template analysis phase
  - [ ] Template assembly phase
  - [ ] Clear separation
- [ ] Move to `src/body/analyzers/`
- [ ] Update tests

**Deliverable**: Clear phase boundaries, no mixed concerns

---

## Phase 2: Migrate Commands (INCREMENTAL)

**Strategy**: Migrate commands one at a time, validate, then move to next.

### 2.1 Simple Commands (Good Starting Points)
**Priority: HIGH - Build confidence with easy wins**

#### `core-admin fix clarity` ✅
- [x] Uses V2 pattern (clarity_service_v2.py)
- [x] Has FileAnalyzer, ClarityStrategist, ClarityEvaluator
- [ ] Add RequestInterpreter
- [ ] Add explicit TERMINATE boundary documentation
- [ ] Verify full workflow compliance

#### `core-admin coverage generate-adaptive` ✅
- [x] Uses V2 pattern (test_generation_v2/)
- [x] Has FileAnalyzer, SymbolExtractor, TestStrategist, FailureEvaluator
- [ ] Add RequestInterpreter
- [ ] Add explicit TERMINATE boundary documentation
- [ ] Verify full workflow compliance

#### `core-admin fix complexity`
- [ ] Extract FileAnalyzer usage
- [ ] Create ComplexityStrategist
- [ ] Create ComplexityEvaluator
- [ ] Build adaptive loop
- [ ] Add tests
- [ ] Deprecate old implementation

#### `core-admin fix constitutional`
- [ ] Add ConstitutionalAnalyzer (analyze violations)
- [ ] Create ConstitutionalStrategist (select remediation)
- [ ] Use existing ConstitutionalEvaluator
- [ ] Build adaptive loop
- [ ] Add tests
- [ ] Deprecate old implementation

### 2.2 Medium Commands (Multi-Action Workflows)
**Priority: MEDIUM - Demonstrate composition**

#### `core-admin dev-sync`
- [ ] Already uses DevSyncWorkflow
- [ ] Add INTERPRET phase (which fixes to run?)
- [ ] Add ANALYZE phase (current state)
- [ ] Add STRATEGIZE phase (execution order)
- [ ] Add EVALUATE phase (success criteria)
- [ ] Refactor to orchestrator pattern
- [ ] Add tests

#### `core-admin develop`
- [ ] Currently uses AutonomousWorkflowOrchestrator
- [ ] Add explicit INTERPRET phase
- [ ] Document generation loop boundaries
- [ ] Document TERMINATE → finalization
- [ ] Verify component composition
- [ ] Add tests

### 2.3 Complex Commands (Full Autonomy)
**Priority: LOW - After foundation is solid**

#### `core-admin coverage accumulate` (V1 Legacy)
- [ ] Mark as deprecated
- [ ] Point to `generate-adaptive` in help text
- [ ] Eventually remove

#### `core-admin coverage accumulate-batch` (V1 Legacy)
- [ ] Mark as deprecated
- [ ] Point to `generate-adaptive` in help text
- [ ] Eventually remove

---

## Phase 3: Infrastructure Modernization

### 3.1 Component Discovery
**Priority: MEDIUM - Improves developer experience**

- [ ] Implement dynamic component discovery
- [ ] Create component registry
- [ ] Add `core-admin components list` command
- [ ] Add `core-admin components info <component_id>` command
- [ ] Document discovery patterns

**Deliverable**: Developers can see all available components

### 3.2 Orchestrator Framework
**Priority: MEDIUM - Reduces boilerplate**

- [ ] Extract common orchestration patterns
- [ ] Create reusable orchestrator base classes
- [ ] Add orchestrator builders (fluent API)
- [ ] Document orchestration patterns
- [ ] Add examples

**Deliverable**: Building new workflows is trivial

### 3.3 Decision Tracing
**Priority: LOW - Nice to have**

- [ ] Enhance DecisionTracer
- [ ] Add trace visualization
- [ ] Add trace analysis tools
- [ ] Add `core-admin traces` command group
- [ ] Document tracing patterns

**Deliverable**: Full audit trail of autonomous decisions

---

## Phase 4: Documentation & Testing

### 4.1 Component Documentation
**Priority: HIGH - Parallel to development**

- [ ] Document each Analyzer
- [ ] Document each Evaluator
- [ ] Document each Strategist
- [ ] Document each Orchestrator
- [ ] Create component API reference
- [ ] Add usage examples

**Deliverable**: Clear contracts for all components

### 4.2 Pattern Examples
**Priority: MEDIUM - Helps adoption**

- [ ] Create example: Simple file operation
- [ ] Create example: Multi-step workflow
- [ ] Create example: Adaptive retry loop
- [ ] Create example: Custom strategist
- [ ] Create example: Custom evaluator
- [ ] Document in pattern paper

**Deliverable**: Developers know how to create components

### 4.3 Testing Framework
**Priority: HIGH - Ensure quality**

- [ ] Create component test helpers
- [ ] Create orchestrator test helpers
- [ ] Add integration test patterns
- [ ] Document testing approaches
- [ ] Achieve 80%+ coverage for V2 code

**Deliverable**: All V2 code is well-tested

---

## Phase 5: Migration Completion

### 5.1 Remove Legacy Code
**Priority: LOW - After everything else works**

- [ ] Remove `features/self_healing/accumulative_test_service.py`
- [ ] Remove other V1 implementations
- [ ] Update imports
- [ ] Update documentation
- [ ] Verify no regressions

**Deliverable**: Clean codebase

### 5.2 Constitutional Updates
**Priority: LOW - Formalize patterns**

- [ ] Add component phase rules to constitution
- [ ] Add orchestrator composition rules
- [ ] Add decision tracing requirements
- [ ] Update enforcement mappings
- [ ] Run full audit

**Deliverable**: Pattern is constitutionally enforced

---

## Progress Tracking

### Work Sessions Log

**Session 2026-01-08**:
- ✅ Created Adaptive Workflow Pattern paper
- ✅ Created Component Inventory
- ✅ Created Modernization Roadmap
- 🔄 Identified critical gaps (RequestInterpreter, Strategists, Evaluators)

**Session YYYY-MM-DD** (Template):
- [ ] Tasks completed
- [ ] Decisions made
- [ ] Blockers encountered
- [ ] Next session priorities

---

## Metrics Dashboard

### Overall Progress
- **Phase 1 (Foundation)**: 25% ✅ (3/12 tasks)
- **Phase 2 (Commands)**: 15% ✅ (2/13 commands started)
- **Phase 3 (Infrastructure)**: 0% ⚪ (0/12 tasks)
- **Phase 4 (Documentation)**: 10% ✅ (2/15 tasks)
- **Phase 5 (Cleanup)**: 0% ⚪ (0/6 tasks)

**Total Modernization**: ~12% complete

### Command Migration Status
- ✅ **Fully Migrated**: 0 commands
- 🔄 **In Progress**: 2 commands (fix clarity, coverage generate-adaptive)
- ⚪ **Not Started**: 11 commands
- ❌ **Deprecated**: 0 commands

### Component Coverage
- **Interpreters**: 0/3 needed
- **Analyzers**: 2/5 needed
- **Evaluators**: 2/5 needed
- **Strategists**: 2/5 needed
- **Orchestrators**: 5/5 (sufficient)
- **Atomic Actions**: 10/10 (sufficient)

---

## Decision Log

### Architectural Decisions

**AD-001: Universal Workflow Pattern**
- **Date**: 2026-01-08
- **Decision**: All autonomous operations MUST follow INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE pattern
- **Rationale**: Closes all loops, enables composition, maintains constitutional governance
- **Status**: APPROVED

**AD-002: TERMINATE Boundary**
- **Date**: 2026-01-08
- **Decision**: TERMINATE marks end of generation loop, NOT end of command. Finalization is command-specific.
- **Rationale**: Separates concerns, allows same generation loop for different finalization needs
- **Status**: APPROVED

**AD-003: Conceptual Decision Points**
- **Date**: 2026-01-08
- **Decision**: Use "Did result improved?", "SOLVED?", "Continue trying?" instead of counters/thresholds
- **Rationale**: High-level concepts, not implementation details. More flexible and maintainable.
- **Status**: APPROVED

**AD-004: Component Phase Enforcement**
- **Date**: 2026-01-08
- **Decision**: Every component MUST declare phase, respect boundaries
- **Rationale**: Constitutional requirement, prevents temporal leakage
- **Status**: APPROVED

---

## Risk Management

### Known Risks

**R-001: Breaking Changes**
- **Risk**: Refactoring breaks existing functionality
- **Mitigation**:
  - Migrate incrementally
  - Keep old code until new is proven
  - Comprehensive testing
  - Feature flags for new implementations
- **Status**: MONITORING

**R-002: Performance Overhead**
- **Risk**: Component abstraction adds latency
- **Mitigation**:
  - Profile component creation/execution
  - Cache component instances
  - Lazy evaluation where possible
  - Benchmark critical paths
- **Status**: MONITORING

**R-003: Learning Curve**
- **Risk**: Team struggles with new patterns
- **Mitigation**:
  - Comprehensive documentation
  - Pattern examples
  - Pair programming sessions
  - Office hours for questions
- **Status**: MITIGATING

**R-004: Incomplete Migration**
- **Risk**: Half-migrated codebase is confusing
- **Mitigation**:
  - Clear migration priority
  - Mark legacy code explicitly
  - Document transition state
  - Set deadline for completion
- **Status**: MITIGATING

---

## Next Session Priorities

### Immediate (Next 1-2 Sessions)

1. **Implement RequestInterpreter** - Unblocks everything
   - Start with CLIRequestInterpreter
   - Test with simple command
   - Document pattern

2. **Create Missing Strategists** - Complete decision coverage
   - ValidationStrategist (highest priority)
   - Document strategy selection patterns

3. **Refactor One Checker** - Prove refactoring pattern
   - Start with AtomicActionsChecker → AtomicActionsEvaluator
   - Update callers
   - Verify no regressions

### Short Term (Next 3-5 Sessions)

4. **Migrate 2 Simple Commands** - Build momentum
   - Fix complexity
   - Fix constitutional

5. **Create Missing Evaluators** - Complete quality gates
   - ConstitutionalEvaluator
   - PerformanceEvaluator

6. **Document Components** - Parallel work
   - API reference for analyzers
   - API reference for evaluators
   - API reference for strategists

### Medium Term (Next 10+ Sessions)

7. **Migrate Medium Commands** - Demonstrate composition
8. **Infrastructure Improvements** - DX enhancements
9. **Testing Framework** - Ensure quality
10. **Constitutional Updates** - Enforce patterns

---

## Success Criteria

### Per-Command Success
A command is "modernized" when:
- ✅ Has explicit INTERPRET phase (RequestInterpreter)
- ✅ Uses Analyzers for fact extraction
- ✅ Uses Strategists for decisions
- ✅ Uses Evaluators for quality gates
- ✅ Has adaptive loop with conceptual decision points
- ✅ Uses DecisionTracer for strategic decisions
- ✅ Has clear TERMINATE → Finalization boundary
- ✅ All mutations via ActionExecutor
- ✅ Comprehensive tests
- ✅ Documentation updated

### Overall Success
Modernization is "complete" when:
- ✅ All commands follow pattern (0 exceptions)
- ✅ All critical components implemented
- ✅ All legacy code removed
- ✅ Pattern is constitutionally enforced
- ✅ Documentation is comprehensive
- ✅ Test coverage > 80%
- ✅ Zero ad-hoc workflows
- ✅ Team is trained and confident

---

## Resources

### Key Documents
- `.intent/papers/CORE-Adaptive-Workflow-Pattern.md` - The canonical pattern
- `CORE_Component_Inventory.md` - What we have
- `CORE_Modernization_Roadmap.md` - This document

### Code Locations
- Components: `src/body/{analyzers,evaluators}/`, `src/will/{strategists,orchestration}/`
- Atomic Actions: `src/body/atomic/`
- V2 Examples: `features/test_generation_v2/`, `features/self_healing/clarity_service_v2.py`

### Communication
- **Session Notes**: Update "Work Sessions Log" each session
- **Blockers**: Add to "Risk Management" if blocked
- **Questions**: Document decisions in "Decision Log"

---

## Notes

**Why This Roadmap Matters**:
The adaptive workflow pattern is not just "nice to have" - it's the foundation for autonomous operations at scale. Without it:
- AI agents can't self-correct reliably
- Failures aren't traceable
- Constitutional governance is ad-hoc
- Code quality degrades over time

With it:
- Every operation is self-correcting
- Every decision is traceable
- Every mutation is governed
- Quality improves autonomously

**The workflow closes all loops** - that's why completing this modernization is critical.

**Approach**:
- Work incrementally (small wins build momentum)
- Document everything (future you will thank present you)
- Test rigorously (no regressions)
- Communicate clearly (team alignment is key)

---

**END OF ROADMAP - Update after each session**
