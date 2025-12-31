# LLM Gate Rule Optimization Analysis

## Current State
- **Total llm_gate rules**: 140 (stubbed, auto-passing)
- **Real enforcement**: 73 rules (ast/workflow/glob/regex/knowledge gates)
- **Actual coverage**: ~34% (73/213)

## Conversion Opportunity Breakdown

### Category 1: AST_GATE Convertible (32 rules - 23%)
**High confidence conversion - structural code patterns**

#### Return Type Enforcement
- `atomic.action_must_return_result` → ast_gate check for `-> ActionResult`
- `body.atomic_actions_use_actionresult` → already exists in ast_gate!
- `standard_architecture_body_contracts.action_results.0` → duplicate check

#### Print/IO Detection
- `atomic.action_must_be_headless` → ast_gate forbidden calls: print, Rich, Console
- `body.no_print_or_input_in_body` → duplicate of above
- `standard_architecture_body_contracts.headless_rules.1` → duplicate again

#### Environment Variable Access
- `body.no_envvar_access_in_body` → ast_gate forbidden: os.environ, os.getenv
- `operations.runtime.env_vars_defined` → WAIT - this is different (checks vars exist)

#### Import/Decorator Analysis
- All `*_rules.auto_rule_*` → check for specific decorators/imports
- `body.dependency_injection_preferred` → detect import-time instantiation

**Estimated Reduction**: 32 → ~15 unique checks (many duplicates)

---

### Category 2: REGEX_GATE Convertible (30 rules - 21%)
**Pattern matching on text content**

#### Pattern Conformance
- All `*.pattern.*_pattern` rules (cognitive_agent, orchestrator_agent, etc.)
- These check for docstring patterns like "Pattern: cognitive_agent"
- Simple regex: `Pattern:\s*(cognitive_agent|orchestrator_agent|...)`

#### Naming Conventions
- `intent.artifact_schema_naming` → filename patterns
- `intent.policy_file_naming` → filename patterns
- Already handled by existing checks?

**Estimated Reduction**: 30 → ~5 unique regex patterns

---

### Category 3: GLOB_GATE Convertible (11 rules - 8%)
**File path restrictions**

#### Path-Based Rules
- `safety.charter_immutable` → no writes to `.intent/charter/**`
- `agent.compliance.no_write_intent` → same as above
- Schema location rules → already covered by glob_gate

**Estimated Reduction**: 11 → ~3 unique path checks

---

### Category 4: KNOWLEDGE_GATE Opportunities (20 rules - 14%)
**Database/knowledge graph queries**

#### Database SSOT Rules
- `db.cli_registry_in_db` → query DB: "does CLI command exist?"
- `db.domains_in_db` → query DB: "are domains in DB not hardcoded?"
- `db.cognitive_roles_in_db` → query DB table
- `knowledge.database_ssot` → check for code duplication vs DB

#### Symbol/Capability Checks
- `symbols.public_capability_id_and_docstring` → query knowledge graph
- `caps.owner_required` → query DB: capability.owner IS NOT NULL
- `code_index.meta_aggregator` → knowledge graph integrity

**Estimated Reduction**: Create 8-10 new knowledge_gate checks

---

### Category 5: WORKFLOW_GATE Opportunities (15 rules - 11%)
**Build/test/integration checks**

#### QA Rules
- `qa.coverage.minimum_threshold` → already in workflow_gate!
- `qa.audit.quality_verified` → audit must pass
- `refactor.audit_after` → run audit after refactor
- `integration.tests_must_pass` → test execution check

#### Change Management
- `qa.change.evaluation_required` → run evaluation workflow
- `qa.change.evaluation_threshold_pass` → check evaluation score
- `safety.change_must_be_logged` → check git log/changelog

**Estimated Reduction**: Most already exist, ~3 new checks

---

### Category 6: TRUE LLM-ONLY (32 rules - 23%)
**Semantic understanding genuinely required**

#### Semantic Quality Checks
- `caps.meaningful_description` → "is description meaningful?" (not just non-empty)
- `style.docstrings_public_apis` → "is docstring adequate?"
- `observability.metrics_actionable` → "are metrics useful?"
- `qa.audit.explanation_required` → "is explanation clear?"

#### Architectural Reasoning
- `atomic.actions_compose_transitively` → "can A→B→C compose?"
- `atomic.governance_never_bypassed` → "is validation skipped?"
- `body.dependency_injection_preferred` → "should this use DI?" (judgment call)
- `workflow_composition.idempotent` → "is workflow re-runnable?"

#### Complex Policy Interpretation
- `purity.framework_binding_limits` → "is framework coupling excessive?"
- `irritation.placeholder` → catch-all for AI irritation patterns
- `layers.placeholder` → layer violation detection
- `ui.placeholder` → UI/headless boundary violations

**Cannot be reduced**: These need genuine LLM reasoning

---

## Optimization Strategy

### Phase 1: Eliminate Duplicates (Immediate)
**Target: 140 → 110 rules**

Many llm_gate rules duplicate existing ast_gate/workflow_gate checks:
- `body.no_ui_imports_in_body` exists as ast_gate ✓
- `body.atomic_actions_use_actionresult` exists as ast_gate ✓
- `workflow.coverage_minimum` exists as workflow_gate ✓

**Action**: Delete duplicate llm_gate rules, mark as "enforced by [engine]"

---

### Phase 2: AST Conversion (High Priority)
**Target: 110 → 80 rules**

Convert structural checks to ast_gate:
1. **Print/IO detection** → extend existing forbidden_calls check
2. **Return type enforcement** → type_checker integration
3. **Decorator detection** → extend decorator checks
4. **Environment access** → forbidden_primitives pattern

**Benefit**: Deterministic, fast, no API cost

---

### Phase 3: Pattern Recognition (Medium Priority)
**Target: 80 → 60 rules**

Convert pattern checks to regex_gate:
1. **Command pattern conformance** → docstring regex
2. **Agent pattern conformance** → docstring regex
3. **Workflow pattern conformance** → docstring regex

**Benefit**: Fast, cacheable, no API cost

---

### Phase 4: Knowledge Graph Integration (Medium Priority)
**Target: 60 → 50 rules**

Convert database/knowledge checks:
1. **SSOT validation** → query DB vs code
2. **Ownership validation** → query capability.owner
3. **Registry validation** → query CLI registry
4. **Symbol validation** → query knowledge graph

**Benefit**: Authoritative SSOT, no interpretation needed

---

### Phase 5: Accept True Semantic Rules (Final State)
**Target: 50 → 32 rules**

Keep genuine semantic checks that require LLM:
- Quality judgment ("is this description meaningful?")
- Architectural reasoning ("does this violate layer boundaries?")
- Policy interpretation ("is this coupling excessive?")

**Cost Model**:
- 32 rules × 50 files = 1,600 LLM calls per audit
- With caching: ~200-400 calls (files change infrequently)
- At $0.01/call: $2-4 per audit

---

## Implementation Priority

### Week 1: Duplicate Elimination
1. Audit all 140 llm_gate rules
2. Identify exact duplicates with existing engines
3. Remove duplicates, update policy docs
4. **Expected outcome**: 140 → 110 rules

### Week 2: AST Conversions
1. Extend ast_gate with missing check_types
2. Convert 15-20 structural rules
3. Test against existing violations
4. **Expected outcome**: 110 → 80 rules

### Week 3: Regex/Glob/Knowledge Conversions
1. Add pattern checks to regex_gate
2. Add DB query checks to knowledge_gate
3. Test conversion accuracy
4. **Expected outcome**: 80 → 50 rules

### Week 4: LLM Gate Activation
1. Configure LLM API (DeepSeek/local)
2. Enable real LLM checks for remaining 32 rules
3. Establish caching strategy
4. Monitor cost/quality
5. **Expected outcome**: 50 → 32 real LLM checks active

---

## Success Metrics

### Coverage
- **Before**: 34% real enforcement (73/213)
- **After**: 85% deterministic + 15% LLM (181 deterministic + 32 LLM)

### Cost
- **Before**: $0/audit (all stubbed)
- **After**: $2-4/audit with caching

### Quality
- **Before**: Auto-pass on 140 rules (blind spot)
- **After**: Real enforcement on all rules

### Speed
- **Before**: Fast but meaningless
- **After**: Deterministic checks instant, LLM checks ~30s with caching

---

## Recommendations

### Immediate Actions
1. **Run duplicate analysis** - many llm_gate rules already enforced
2. **Prioritize AST conversions** - biggest bang for buck
3. **Defer complex semantic rules** - keep as llm_gate for now

### Strategic Decisions
1. **LLM provider choice**:
   - DeepSeek for cost ($0.001/call)
   - Claude for quality ($0.01/call)
   - Local Llama for zero cost (slower)

2. **Caching strategy**:
   - Hash (file_content + rule_instruction) → cache result
   - Clear cache on file modification
   - Expected cache hit rate: 70-80%

3. **Incremental rollout**:
   - Phase 1-3: Zero cost (deterministic only)
   - Phase 4: Enable LLM for critical rules only
   - Phase 5: Full LLM activation when budget allows

---

## Bottom Line

**You can reduce 140 llm_gate rules to ~32 genuine semantic checks** through systematic conversion to deterministic engines. This achieves:

- **77% cost reduction** (140 → 32 LLM calls)
- **85% deterministic coverage** (fast, free, reliable)
- **Real enforcement** on previously auto-passing rules
- **~$2-4/audit** operating cost with caching

The remaining 32 LLM rules genuinely need semantic understanding and are worth the cost.
