# Phase 1 Implementation Plan: Semantic Infrastructure

**Start Date**: 2024-11-25
**Duration**: 2-3 weeks
**Goal**: Improve semantic placement from 45% to 90%+

---

## Overview

Phase 1 builds semantic infrastructure that gives CoderAgent "architectural intuition"
through three key components:

1. **Policy Vectorization** - Constitutional rules as searchable vectors
2. **Module Anchors** - Mathematical reference points for each layer/module
3. **Enhanced Context** - Rich architectural guidance in prompts

---

## Week 1: Foundation (Days 1-5)

### Day 1: Policy Vectorization ✅ STARTED

**Files to create**:
- ✅ `src/features/introspection/policy_vectorizer.py` (DONE)
- `tests/features/test_policy_vectorizer.py`

**Tasks**:
1. ✅ Create PolicyVectorizer class skeleton (DONE)
2. Parse policy YAML files into semantic chunks
3. Generate embeddings for each chunk
4. Store in Qdrant with metadata (type, policy_id, rule_id)
5. Create search interface

**Acceptance Criteria**:
- All policies in `.intent/charter/policies/` vectorized
- Can search "rules for action handlers" and get relevant chunks
- Metadata preserved (policy version, enforcement level)

---

### Day 2: Module Anchor Generation

**Files to create**:
- `src/features/introspection/module_anchor_generator.py`
- `tests/features/test_module_anchor_generator.py`

**Concept**: Each module gets a semantic "anchor" vector representing its purpose.

**Tasks**:
1. Extract module-level docstrings from all Python files
2. Parse module structure (shared, domain, features, will, core)
3. Generate embedding for each module's purpose
4. Calculate layer-level anchor (aggregate of modules in that layer)
5. Store anchors in Qdrant with metadata

**Example Anchors**:
```python
{
    "shared/utils/": {
        "purpose": "Pure utility functions with no business logic",
        "vector": [0.1, 0.3, ...],  # 768-dim embedding
        "examples": ["json_utils.py", "path_utils.py"],
    },
    "domain/validators/": {
        "purpose": "Business rule validation with ValidationResult pattern",
        "vector": [0.2, 0.5, ...],
        "examples": ["email_validator.py", "semver_validator.py"],
    },
    "features/introspection/": {
        "purpose": "System introspection and analysis capabilities",
        "vector": [0.4, 0.1, ...],
        "examples": ["diff_service.py", "formatter_service.py"],
    },
}
```

**Acceptance Criteria**:
- Anchors generated for all major modules
- Can calculate semantic distance between code and modules
- Closest module = best placement

---

### Day 3: Architectural Context Builder

**Files to create**:
- `src/will/agents/architectural_context.py`
- `tests/will/agents/test_architectural_context.py`

**Purpose**: Build rich context for code generation prompts.

**Tasks**:
1. Create ArchitecturalContextBuilder class
2. Query module anchors for target location
3. Find similar code examples in same module
4. Extract layer-specific patterns
5. Build structured context package

**Context Package Structure**:
```python
{
    "target_module": "src/domain/validators/",
    "layer": "domain",
    "layer_purpose": "Business logic and domain rules",
    "layer_patterns": [
        "Return ValidationResult dataclasses",
        "No external dependencies except shared",
        "Pure domain logic, no I/O",
    ],
    "similar_files": [
        {
            "path": "domain/validators/email_validator.py",
            "purpose": "Email validation with regex",
            "distance": 0.15,
        },
    ],
    "relevant_policies": [
        "ValidationResult must have is_valid and error_message fields",
        "Domain layer must not import from features or will",
    ],
}
```

**Acceptance Criteria**:
- Context builder produces rich, structured context
- Includes layer patterns, similar examples, relevant policies
- Context is concise (under 2000 tokens)

---

### Day 4-5: Integrate with CoderAgentV0

**Files to modify**:
- `src/will/agents/coder_agent_v0.py` → Create `coder_agent_v1.py`

**Tasks**:
1. Create CoderAgentV1 (copy from V0)
2. Integrate ArchitecturalContextBuilder
3. Query policy vectorization for relevant rules
4. Calculate semantic distance to module anchors
5. Use closest anchor for file placement
6. Enhanced prompt with architectural context

**New Generation Flow**:
```
User Goal → CoderAgentV1
  ↓
1. Generate embedding for goal
2. Query module anchors (find 3 closest)
3. Query policy vectors (find 5 relevant rules)
4. Build architectural context
  ↓
5. Enhanced prompt:
   - Goal
   - Target layer (from closest anchor)
   - Layer patterns
   - Similar code examples
   - Relevant constitutional rules
  ↓
6. LLM generates code
7. Place in closest anchor's module
```

**Acceptance Criteria**:
- CoderAgentV1 uses all Phase 1 components
- Placement based on semantic distance
- Prompt includes architectural context

---

## Week 2: Validation & Refinement (Days 6-10)

### Day 6: Re-run Phase 0 Validation

**Tasks**:
1. Update `run_phase0_validation.py` to use CoderAgentV1
2. Run all 10 validation tasks
3. Collect metrics (constitutional, placement, execution)
4. Compare to Phase 0 baseline

**Expected Results**:
- Constitutional compliance: 90% → 95%
- Semantic placement: 45% → 90%+
- Execution success: 80% → 85%

**Acceptance Criteria**:
- All metrics collected
- Improvement clearly attributed to Phase 1 components
- Results saved for academic paper

---

### Day 7: Failure Analysis & Prompt Tuning

**Tasks**:
1. Analyze any remaining failures
2. Review generated code quality
3. Refine prompts based on patterns
4. Adjust module anchor calculations if needed

**Focus Areas**:
- Missing imports (should be fixed by similar examples)
- Wrong layer placement (should be fixed by anchors)
- Constitutional violations (should be fixed by policy context)

---

### Day 8: Additional Test Tasks

**Tasks**:
1. Create 5 new validation tasks (different from Phase 0)
2. Run through CoderAgentV1
3. Validate generalization (not overfitting to Phase 0 tasks)

**New Tasks** (examples):
- Create a rate limiter utility
- Create a JWT token validator
- Create a file watcher service
- Create a code complexity analyzer
- Create a git diff parser

**Acceptance Criteria**:
- 80%+ success on new tasks
- Proves Phase 1 improvements generalize

---

### Day 9: Performance Optimization

**Tasks**:
1. Profile generation time
2. Cache module anchors (don't recalculate each time)
3. Optimize policy search (limit to top 5 results)
4. Batch embedding generation where possible

**Target**:
- Mean generation time: <30s (from 49.72s)

---

### Day 10: Documentation & Metrics

**Tasks**:
1. Document Phase 1 architecture
2. Create comparison charts (Phase 0 vs Phase 1)
3. Write academic paper section on semantic infrastructure
4. Update README with Phase 1 capabilities

**Deliverables**:
- Architecture diagram (Mind-Body-Will with semantic layer)
- Metrics table (quantitative comparison)
- Paper section draft (2-3 pages)

---

## Week 3: Polish & Integration (Optional)

### Day 11-12: CLI Commands

**Tasks**:
1. Add `core-admin vectorize policies` command
2. Add `core-admin generate anchors` command
3. Add `core-admin a2 validate` command (runs Phase 0 suite)

**Usage**:
```bash
# Vectorize all policies
poetry run core-admin vectorize policies

# Generate module anchors
poetry run core-admin generate anchors

# Run A2 validation
poetry run core-admin a2 validate --agent v1
```

---

### Day 13-14: Real-World Test

**Tasks**:
1. Pick a real feature to implement (small scope)
2. Use CoderAgentV1 to generate it
3. Review code quality manually
4. Integrate into CORE (if quality is good)

**Candidate Features**:
- Add a "last modified" timestamp to action logs
- Create a simple API rate limiter
- Add a "dry run" flag to actions

**Acceptance Criteria**:
- Code passes constitutional audit
- Code works without modification
- Team approves merge

---

### Day 15: Phase 1 Completion Report

**Tasks**:
1. Generate final metrics report
2. Document lessons learned
3. Create Phase 2 recommendations
4. Present to team/advisors

**Deliverables**:
- Phase 1 completion report
- Metrics comparison (Phase 0 → Phase 1)
- Academic paper draft sections
- Recommendation for Phase 2 (or A2 production readiness)

---

## Success Criteria Summary

### Must Have (Week 1-2)
- ✅ Policy vectorization working
- ✅ Module anchors generated
- ✅ CoderAgentV1 with semantic placement
- ✅ 90%+ semantic placement on Phase 0 tasks
- ✅ Maintained or improved constitutional compliance

### Nice to Have (Week 3)
- CLI commands for Phase 1 operations
- Real-world feature generated and merged
- Performance optimization (<30s generation)

### Academic Impact
- Quantitative improvement attribution
- Novel semantic governance architecture
- Empirical validation of approach

---

## Risk Mitigation

### Risk: Module anchors don't improve placement

**Mitigation**:
- Fallback to heuristic placement (file name matching)
- Hybrid approach: anchors + rules
- Iterate on anchor calculation methodology

### Risk: Policy vectorization adds latency

**Mitigation**:
- Cache policy search results
- Limit to top 5 most relevant policies
- Pre-filter by policy type

### Risk: Prompts become too long (token overflow)

**Mitigation**:
- Prioritize: anchors > examples > policies
- Truncate similar code examples
- Summary mode for policies (key rules only)

---

## Rollback Plan

If Phase 1 doesn't improve placement:

1. Keep CoderAgentV0 as default
2. Make CoderAgentV1 opt-in flag
3. Analyze failure modes
4. Consider alternative approaches (retrieval-augmented generation, etc.)

Constitutional principle: `safe_by_default` - we can always revert.

---

## Next Immediate Steps

**TODAY (Day 1)**:
1. ✅ Create policy_vectorizer.py skeleton (DONE)
2. Implement policy chunk extraction
3. Implement embedding generation
4. Store first policy in Qdrant
5. Test search functionality

**START HERE**:
```bash
# Test policy vectorizer
cd /opt/dev/CORE
poetry run python -c "
import asyncio
from pathlib import Path
from features.introspection.policy_vectorizer import vectorize_policies_command

result = asyncio.run(vectorize_policies_command(Path.cwd()))
print(f'Vectorized {result['policies_vectorized']} policies')
"
```

Let's build the foundation that will take CORE to A2! 🚀
