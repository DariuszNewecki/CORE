# CORE A2 Autonomy Roadmap
## From Self-Healing to Autonomous Code Generation

**Version**: 1.0
**Created**: 2024-11-25
**Status**: ACTIVE PLAN

---

## Executive Summary

This roadmap advances CORE from A1 (self-healing) to A2 (autonomous code generation) through a **validation-first approach**. Rather than building infrastructure speculatively, we prove the core capability first, then optimize it through semantic enhancements.

**Key Principle**: "You can't automate anything if you don't have all the tools to do it manually" - extended to "You can't optimize a capability you haven't validated."

---

## Current State Assessment

### ✅ Operational Capabilities
- **A1 Loop**: 90-95% success rate on self-healing tasks
- **Test Coverage**: 821 passing tests, 51% coverage (exceeds 50% constitutional requirement)
- **Vectorization**: 233/233 symbols vectorized, semantic search operational
- **Knowledge Graph**: ReconnaissanceAgent provides symbol/file context
- **Constitutional Compliance**: 0 audit errors/warnings

### ❌ A2 Blockers Identified
1. **Unvalidated Core Capability**: No proof LLMs can generate constitutionally-compliant code
2. **Static Action Registry**: yaml-sync problem between policy and implementation
3. **No Semantic Governance**: Can't detect architecturally misplaced code
4. **Monolithic ExecutionAgent**: Code generation not separated from execution

### 🎯 Success Criteria for A2
1. Generate new production code (not just fix existing)
2. 70%+ constitutional compliance rate without human intervention
3. Semantic understanding of architectural placement
4. Measurable metrics for academic publication

---

## Phase 0: A2 Capability Validation (Week 1)
**Goal**: Prove LLMs can generate constitutionally-compliant code at all

### Critical Question
Can a CoderAgent, with existing context infrastructure, generate code that passes constitutional audit?

### Implementation

#### 1. Minimal CoderAgent (3 days)
```python
# src/will/agents/coder_agent_v0.py
class CoderAgentV0:
    """Minimal code generation agent for capability validation."""

    async def generate_code(self, goal: str, context: ContextPackage) -> str:
        """Generate code using current context system."""
        # Uses existing ContextService
        # No semantic enhancements yet
        # Returns: Generated code as string
```

**Integration Points**:
- Uses existing `ContextService` for symbol/file context
- Uses existing `ReconnaissanceAgent` for related code
- Uses existing `CognitiveService` for LLM orchestration

#### 2. Test Harness (2 days)
Create 10 representative A2 tasks:
```yaml
# tests/fixtures/a2_validation_tasks.yaml
tasks:
  - id: "util_markdown_parser"
    goal: "Create utility function to extract markdown headers"
    expected_location: "src/shared/utils/markdown.py"
    difficulty: "simple"

  - id: "domain_validator"
    goal: "Create email validator in domain layer"
    expected_location: "src/domain/validators/email.py"
    difficulty: "medium"

  - id: "action_handler"
    goal: "Create new self-healing action for fixing imports"
    expected_location: "src/core/actions/healing_actions_extended.py"
    difficulty: "complex"
```

#### 3. Validation Metrics (2 days)
```python
# tests/validation/a2_smoke_test.py
class A2ValidationMetrics:
    """Track CoderAgent success metrics."""

    def measure(self, task_id: str, generated_code: str) -> dict:
        return {
            "constitutional_compliance": bool,  # Passes audit?
            "semantic_placement": float,        # Correct module? (0-1)
            "test_coverage": float,             # Has tests? (0-1)
            "execution_success": bool,          # Code runs?
            "time_to_generate": float,          # Seconds
        }
```

### Success Threshold
**Proceed to Phase 1 IF**:
- ≥70% constitutional compliance rate
- ≥80% semantic placement accuracy (human judgment)
- ≥50% execution success (code runs without errors)

**Pivot IF**:
- <50% constitutional compliance → Research problem, not engineering
- <60% semantic placement → Need semantic infrastructure first
- <30% execution success → LLM quality issue, not context issue

### Deliverables
- [ ] `CoderAgentV0` implementation
- [ ] 10-task validation suite
- [ ] Metrics report with decision recommendation
- [ ] `docs/validation/A2_SMOKE_TEST_RESULTS.md`

---

## Phase 1: Semantic Foundation (Week 2-3)
**Prerequisite**: Phase 0 success rate ≥70%

**Goal**: Enhance context quality through semantic infrastructure

### 1.1: Constitution Vectorization
**What**: Transform policy documents into searchable vectors

```python
# src/features/introspection/policy_vectorizer.py
class PolicyVectorizer:
    """Vectorize constitutional policies for semantic search."""

    async def vectorize_policies(self) -> int:
        """
        Scans .intent/charter/policies/*.yaml
        Creates POLICY vectors in Qdrant
        Returns: Number of policies vectorized
        """
```

**Target Files**:
- `agent_governance.yaml` → Agent behavior rules
- `code_standards.yaml` → Code style/structure requirements
- `operations.yaml` → Risk gates and validation rules
- `data_governance.yaml` → Data handling policies

**Usage**:
```python
# CoderAgent queries before generating
relevant_policies = await cognitive_service.search_policies(
    query="rules for creating new action handlers"
)
```

**Constitutional Compliance**:
- Policies remain in `.intent/` (Mind)
- Vectors stored in Qdrant (Body)
- Agents query via CognitiveService (Will)

### 1.2: Module-Level Context
**What**: Extract and vectorize module docstrings

```python
# Enhancement to existing vectorization_service.py
async def vectorize_modules(self) -> int:
    """
    For each src/**/__init__.py:
      - Extract module-level docstring
      - Create MODULE vector
      - Link to contained symbols
    """
```

**Example**:
```python
# src/core/actions/__init__.py docstring becomes:
{
    "type": "MODULE",
    "path": "src/core/actions",
    "intent": "Action handlers for autonomous self-healing operations",
    "contained_symbols": ["fix_docstrings", "format_code", ...]
}
```

**Usage**: Agents understand "forest, not just trees"

### 1.3: Architectural Anchors
**What**: Vectorize project structure definitions

```python
# src/features/introspection/anchor_vectorizer.py
class AnchorVectorizer:
    """Create semantic anchors for architectural zones."""

    async def vectorize_structure(self) -> int:
        """
        Parse project_structure.yaml
        Create ANCHOR vectors for:
          - "Infrastructure" (system/, services/)
          - "Domain Logic" (features/, domain/)
          - "Shared Utilities" (shared/)
        """
```

**Result**: Mathematical reference points for semantic placement

### Deliverables
- [ ] `core-admin vectorize --policies` command
- [ ] `core-admin vectorize --modules` command
- [ ] `core-admin vectorize --anchors` command
- [ ] Updated `CoderAgentV1` using enhanced context
- [ ] Re-run Phase 0 validation suite → measure improvement

**Target Improvement**: 70% → 85% constitutional compliance

---

## Phase 2: Living Action Registry (Week 4)
**Goal**: Eliminate yaml-sync problem, enable dynamic tool discovery

### 2.1: Database Schema
```sql
-- Migration: 00X_create_system_actions.sql
CREATE TABLE system_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,  -- "self_healing", "introspection", etc.
    parameters_schema JSONB NOT NULL,
    risk_level TEXT NOT NULL,  -- "low", "medium", "high"
    vector_id TEXT,  -- Link to Qdrant vector
    registered_at TIMESTAMP DEFAULT NOW(),
    last_verified TIMESTAMP,

    CONSTRAINT valid_risk_level CHECK (risk_level IN ('low', 'medium', 'high'))
);

CREATE INDEX idx_actions_category ON system_actions(category);
CREATE INDEX idx_actions_risk ON system_actions(risk_level);
```

### 2.2: Action Introspection Service
```python
# src/services/action_registry_sync.py
class ActionRegistrySync:
    """Synchronize ActionRegistry code with database."""

    async def sync_actions(self) -> dict:
        """
        1. Introspect ActionRegistry class
        2. Extract: name, docstring, parameters, risk_level
        3. Upsert to system_actions table
        4. Vectorize descriptions
        5. Return sync report
        """
```

**Key Features**:
- **Idempotent**: Safe to run multiple times
- **Auditable**: Logs all changes
- **Validated**: Must pass schema checks

### 2.3: Agent Tool Discovery
```python
# Enhancement to will/agents/planner_agent.py
class PlannerAgent:
    async def find_tools(self, intent: str) -> list[Action]:
        """
        Find actions by semantic intent, not hardcoded names.

        Query: "I need to fix syntax errors"
        Returns: [fix_syntax_error, run_formatter, ...]
        """
        # Vector search against action descriptions
        results = await self.cognitive_service.search_actions(intent)
        return [self._hydrate_action(r) for r in results]
```

### 2.4: Constitutional Integration
Remove static policy file:
```yaml
# DELETE: .intent/charter/policies/available_actions_policy.yaml
# REASON: Replaced by living database registry
# MIGRATION: Data migrated in sync operation
```

Update governance to reference DB:
```yaml
# agent_governance.yaml
agent_rules:
  - id: agent.compliance.respect_action_registry
    statement: "All tool invocations MUST route through system_actions table."
    enforcement: error
    validation: "ConstitutionalAuditor checks action exists in DB"
```

### Deliverables
- [ ] `system_actions` table migration
- [ ] `core-admin actions sync` command
- [ ] `core-admin actions list [--category]` command
- [ ] Updated PlannerAgent with semantic tool discovery
- [ ] Constitutional audit check for action validation
- [ ] Migration guide for removing static YAML

**Success Metric**: 0 yaml-sync bugs in CI for 1 week

---

## Phase 3: Semantic Governance (Week 5)
**Goal**: Prevent architectural drift through mathematical validation

### 3.1: Semantic Cohesion Check
```python
# src/system/governance/checks/semantic_cohesion_check.py
class SemanticCohesionCheck(Check):
    """Validates code placement using vector distance."""

    async def validate_symbol(
        self,
        symbol: Symbol,
        module: Module
    ) -> CheckResult:
        """
        1. Get symbol's vector (from code + docstring)
        2. Get module's anchor vector
        3. Calculate cosine distance
        4. Fail if distance > threshold
        """

        symbol_vector = await self.get_symbol_vector(symbol)
        module_anchor = await self.get_module_anchor(module)

        distance = cosine_distance(symbol_vector, module_anchor)
        threshold = 0.7  # From operations.yaml

        if distance > threshold:
            return CheckResult(
                passed=False,
                severity="error",
                message=f"Symbol semantically misplaced (distance: {distance:.2f})",
                suggestion=f"Consider moving to module with anchor closer to symbol intent"
            )
```

### 3.2: Integration with Constitutional Auditor
```python
# Enhancement to system/governance/constitutional_auditor.py
class ConstitutionalAuditor:
    def _get_all_checks(self) -> list[Check]:
        return [
            # ... existing checks
            SemanticCohesionCheck(),  # NEW
        ]
```

### 3.3: Threshold Calibration
```yaml
# .intent/charter/policies/operations.yaml
semantic_governance:
  cohesion_thresholds:
    infrastructure: 0.65  # System code is specialized
    domain_logic: 0.70    # Business logic is specific
    shared_utils: 0.75    # Utilities are generic

  enforcement:
    level: "error"
    auto_fix: false  # Human judgment required for moves
```

### 3.4: CoderAgent Integration
```python
# Enhancement to CoderAgentV1
class CoderAgentV2:
    async def generate_code(self, goal: str, context: ContextPackage) -> GeneratedCode:
        code = await self._generate_impl(goal, context)

        # Pre-validate semantic placement BEFORE returning
        placement_check = await self._validate_semantic_placement(
            code=code,
            target_module=context.target_module
        )

        if not placement_check.passed:
            # Retry with different target module suggestion
            return await self._generate_with_alternate_placement(
                goal, context, placement_check.suggestion
            )
```

### Deliverables
- [ ] `SemanticCohesionCheck` implementation
- [ ] Integration with constitutional auditor
- [ ] Threshold configuration in operations.yaml
- [ ] `core-admin check semantic` command for standalone testing
- [ ] CoderAgentV2 with pre-validation
- [ ] Test suite proving misplaced code is rejected

**Success Metric**: Detects 100% of intentionally misplaced test cases

---

## Phase 4: Agent Separation (Week 6)
**Goal**: Clean architectural boundaries for code generation

### 4.1: CoderAgent Finalization
```python
# src/will/agents/coder_agent.py (final version)
class CoderAgent:
    """
    Autonomous code generation agent with semantic awareness.

    Responsibilities:
      - Generate new code from high-level goals
      - Query semantic context (policies, modules, anchors)
      - Pre-validate semantic placement
      - Produce constitutionally-compliant output

    Does NOT:
      - Execute plans (that's ExecutionAgent)
      - Make autonomous decisions (that's PlannerAgent)
      - Validate constitutionality (that's ConstitutionalAuditor)
    """

    async def generate(
        self,
        goal: str,
        constraints: GenerationConstraints
    ) -> GeneratedArtifact:
        """
        Full generation pipeline:
        1. Semantic reconnaissance (policies + modules + anchors)
        2. Context assembly (related symbols + files)
        3. Code generation (LLM invocation)
        4. Semantic validation (cohesion check)
        5. Return artifact with metadata
        """
```

### 4.2: ExecutionAgent Refactoring
```python
# Refactor: src/will/agents/execution_agent.py
class ExecutionAgent:
    """Orchestrates plan execution, delegates generation to CoderAgent."""

    async def execute_plan(self, plan: Plan) -> ExecutionResult:
        for task in plan.tasks:
            if task.requires_code_generation:
                # DELEGATE to CoderAgent
                artifact = await self.coder_agent.generate(
                    goal=task.goal,
                    constraints=task.constraints
                )
                result = await self._apply_artifact(artifact)
            else:
                # Direct action execution
                result = await self._execute_action(task.action)
```

**Key Change**: ExecutionAgent becomes orchestrator, not generator

### 4.3: Constitutional Separation Validation
```yaml
# agent_governance.yaml
agent_rules:
  - id: agent.separation.coder_only_generates
    statement: "CoderAgent MUST NOT execute plans or actions directly."
    enforcement: error

  - id: agent.separation.execution_delegates_generation
    statement: "ExecutionAgent MUST delegate all code generation to CoderAgent."
    enforcement: error
```

### Deliverables
- [ ] Final `CoderAgent` implementation
- [ ] Refactored `ExecutionAgent` with delegation
- [ ] Constitutional checks for separation of concerns
- [ ] Integration tests proving end-to-end A2 flow
- [ ] Documentation: "CoderAgent Architecture Guide"

---

## Phase 5: A2 Validation & Metrics (Week 7)
**Goal**: Prove A2 works, gather academic metrics

### 5.1: Comprehensive Test Suite
Expand Phase 0's 10 tasks to 30:
- 10 simple (utility functions)
- 10 medium (domain validators, action handlers)
- 10 complex (new features with tests)

### 5.2: Demonstration Scenarios
```bash
# Scenario 1: Utility Generation
core-admin run develop --goal "create markdown table parser in shared utils"

# Scenario 2: Domain Logic
core-admin run develop --goal "add email validation to user domain model"

# Scenario 3: Self-Expansion
core-admin run develop --goal "create action handler for fixing type hints"
```

Record full execution traces for each.

### 5.3: Academic Metrics Collection
```python
# scripts/validation/a2_metrics.py
class A2AcademicMetrics:
    """Collect publishable metrics for A2 capability."""

    metrics = {
        "constitutional_compliance_rate": float,      # % passing audit
        "semantic_placement_accuracy": float,         # % in correct module
        "generation_time_mean": float,                # Seconds
        "generation_time_std": float,
        "context_size_mean": int,                     # Tokens
        "success_by_complexity": dict[str, float],    # simple/medium/complex
        "failure_modes": dict[str, int],              # Categories of failures
        "comparison_to_baseline": dict,               # vs. Phase 0 results
    }
```

### 5.4: Academic Paper Updates
Update academic materials with:
- Quantitative results from 30-task validation
- Comparison: Phase 0 vs. Phase 5 success rates
- Novel contributions: Semantic governance, living registry
- Failure analysis: What A2 still can't do
- Future work: Path to A3

### Deliverables
- [ ] 30-task comprehensive validation suite
- [ ] 3 recorded demonstration scenarios
- [ ] Academic metrics report
- [ ] Updated paper draft with empirical results
- [ ] `docs/academic/A2_VALIDATION_REPORT.md`

**Target Metrics**:
- Constitutional compliance: 85%+
- Semantic placement: 90%+
- Complex task success: 70%+

---

## Rollback & Risk Management

### Per-Phase Rollback Strategy
Each phase has a clean rollback:

**Phase 0**: Delete experimental agent, no DB changes
**Phase 1**: Vectors are additive, disable queries in agents
**Phase 2**: Keep old YAML, mark DB columns as experimental
**Phase 3**: Disable semantic check in auditor config
**Phase 4**: ExecutionAgent can handle both modes

### Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Phase 0 fails (<50% success) | Medium | High | Pivot to hybrid human-review mode |
| Semantic infrastructure doesn't improve results | Low | Medium | Use for governance only, not generation |
| LLM costs explode | Medium | Medium | Implement caching, use cheaper models for validation |
| Constitutional auditor false positives | Low | High | Calibrate thresholds in Phase 3 |
| Academic reviewers reject novelty claims | Low | Critical | Emphasize governance, not generation |

---

## Success Criteria Summary

### Technical Success
- [ ] Phase 0: ≥70% baseline success rate
- [ ] Phase 1: ≥85% with semantic context
- [ ] Phase 2: 0 yaml-sync bugs for 1 week
- [ ] Phase 3: 100% detection of misplaced code
- [ ] Phase 4: Clean agent separation maintained
- [ ] Phase 5: ≥85% constitutional compliance on 30 tasks

### Academic Success
- [ ] Quantitative metrics for 30 diverse tasks
- [ ] Novel contributions clearly articulated
- [ ] Comparison to baseline (Phase 0)
- [ ] Failure modes documented and explained
- [ ] Reproducible demonstration scenarios

### Constitutional Success
- [ ] 0 constitutional violations throughout
- [ ] All changes pass `core-admin check ci audit`
- [ ] Mind-Body-Will separation maintained
- [ ] Rollback available at every phase

---

## Timeline Summary

| Week | Phase | Key Deliverable | Go/No-Go Decision |
|------|-------|-----------------|-------------------|
| 1 | Phase 0 | A2 smoke test results | Proceed if ≥70% success |
| 2-3 | Phase 1 | Semantic infrastructure | Measure improvement vs baseline |
| 4 | Phase 2 | Living action registry | Verify yaml-sync elimination |
| 5 | Phase 3 | Semantic governance | Validate cohesion detection |
| 6 | Phase 4 | Agent separation | Prove clean architecture |
| 7 | Phase 5 | Academic validation | Publishable metrics |

**Total Duration**: 7 weeks
**Critical Decision Point**: End of Week 1 (Phase 0 results)

---

## Next Steps

1. **Immediate (This Week)**:
   - [ ] Review and approve this roadmap
   - [ ] Create Phase 0 implementation plan
   - [ ] Set up metrics collection infrastructure
   - [ ] Define 10 validation tasks

2. **Week 1 Execution**:
   - [ ] Implement CoderAgentV0
   - [ ] Build validation test harness
   - [ ] Run smoke tests and collect metrics
   - [ ] Make go/no-go decision for Phase 1

3. **If Phase 0 Succeeds**:
   - [ ] Proceed with Phase 1 implementation
   - [ ] Begin academic paper updates
   - [ ] Schedule progress reviews

4. **If Phase 0 Fails**:
   - [ ] Document failure modes
   - [ ] Pivot to hybrid approach or narrower scope
   - [ ] Re-evaluate A2 feasibility

---

## Appendix: Constitutional Alignment

This roadmap serves the following constitutional principles:

- **safe_by_default**: Phase 0 validates before building
- **reason_with_purpose**: Each phase has clear success criteria
- **evolvable_structure**: Incremental, rollback-friendly progression
- **separation_of_concerns**: Agent responsibilities clearly defined
- **single_source_of_truth**: Living registry eliminates dual truth
- **clarity_first**: Semantic understanding enables better decisions

**Constitutional Compliance**: This roadmap itself follows the amendment process by being subject to review and requiring approval before execution.

---

**Document Status**: DRAFT - PENDING APPROVAL
**Next Review**: After Phase 0 completion
**Owner**: CORE Development Team
