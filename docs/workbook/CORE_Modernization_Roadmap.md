What You Need (Not Tasks, Just Focus)

Pattern compliance - Everything uses the workflow
Component clarity - Know what exists, what's missing
Autonomous loops - Self-correction everywhere
Conversational routing - Intent → Workflow mapping


# CORE Development Roadmap

**Last Updated:** 2026-01-10

## Current State (A2 Autonomy - 70-80% success rate)

### Foundation Health ✅ COMPLETED
**Priority 1: Delete Legacy Code**
- ✅ Deleted `src/body/cli/logic/atomic_actions_checker.py` - Replaced by AtomicActionsEvaluator
- ✅ Deleted `src/body/cli/logic/pattern_checker.py` - Replaced by PatternEvaluator
- ✅ All evaluators now self-contained Component implementations
- ✅ No external checker dependencies
- ✅ Format functions moved into evaluators for backward compatibility

**Priority 2: Test Coverage (ACTIVE)**
- Current: 45-51% coverage
- Constitutional requirement: 75% minimum
- Gap: ~24-30 percentage points
- Autonomous test generation capability exists but needs activation
- Coverage watcher implemented with auto-remediation

**Priority 3: Observability**
- DecisionTracer exists but lacks CLI viewer
- Need: `core-admin inspect decisions` command for trace analysis
- Pattern classification insights needed for debugging

### Technical Infrastructure
**Database (PostgreSQL)**
- ✅ Single source of truth for runtime state
- ✅ 1436 symbols indexed
- ✅ Knowledge graph fully populated
- ✅ Sync operations working (0 changes on last sync = stable)

**Vector Databases (Qdrant)**
- ✅ Code capabilities: 513+ symbols with semantic search
- ✅ Constitutional patterns: 48+ policy chunks, 13+ pattern chunks
- ✅ Smart deduplication working (skips unchanged items)
- ✅ Module anchors: 66+ anchors for code navigation

**Constitutional Governance**
- ✅ 213+ executable rules with 100% coverage
- ✅ Zero constitutional violations after autonomous fixes
- ✅ Strict Mind/Body/Will separation enforced
- ✅ Cryptographic governance ready (quorum-based amendments)

**CLI Infrastructure**
- ✅ All fix actions working (format, ids, headers, docstrings, logging)
- ✅ Atomic actions pattern compliance checking
- ✅ Pattern compliance checking
- ✅ Comprehensive `core-admin` tooling

### Component Architecture (V2.2)
**Evaluators (AUDIT Phase)**
- ✅ AtomicActionsEvaluator - Self-contained pattern validation
- ✅ PatternEvaluator - Self-contained design pattern checking
- ✅ ClarityEvaluator - Code complexity analysis
- ✅ ConstitutionalEvaluator - Constitutional compliance
- ✅ FailureEvaluator - Test failure pattern recognition
- ✅ PerformanceEvaluator - Performance metrics
- ✅ SecurityEvaluator - Security vulnerability detection

All evaluators follow Component primitive with ComponentPhase.AUDIT.

### Autonomy Capabilities
**Current Level: A2 (Code Generation)**
- ✅ 70-80% success rate in autonomous code generation
- ✅ Self-healing loops operational
- ✅ Constitutional auditing with auto-fix
- ✅ Autonomous test generation (needs coverage boost activation)
- ✅ Context-aware code generation infrastructure exists (underutilized)

**Path to A3 (Strategic Refactoring)**
- Better ContextPackage utilization → 90%+ success rates
- Background monitoring agents ("Sentinels")
- Expanded autonomous action handler scope
- Pattern-based refactoring suggestions

## Active Development Focus

### 1. Test Coverage Improvement (PRIORITY)
**Goal:** Reach 75% constitutional requirement

**Approach:**
```bash
# Activate autonomous test generation
poetry run core-admin test generate --write
```

**Strategy:**
- Use existing autonomous test generation capability
- Target critical paths first (Mind governance, Body actions, Will orchestration)
- Leverage coverage watcher for continuous improvement
- Aim for incremental 5-10% gains per session

### 2. Context Awareness Enhancement
**Problem:** Autonomous agents underutilize rich context infrastructure

**Solution:**
- Enhance ContextPackage integration in code generation
- Improve semantic search relevance scoring
- Better module anchor utilization
- Expected outcome: 70% → 90%+ autonomous success rate

### 3. Observability Tools
**Need:** `core-admin inspect decisions` command

**Features:**
- View recent decision traces
- Pattern classification analysis
- Success/failure rate tracking
- Common error pattern identification

## Deferred / Lower Priority

### Pattern Consolidation
- Some duplicate code patterns exist
- Can be addressed after test coverage reaches 75%
- Low risk, medium effort

### CORE.NG (Future Vision)
- Next-generation system written BY CORE
- Based on CORE's own functionality, not its code
- Requires A3+ autonomy level
- Timeline: After achieving stable A3

### Academic Engagement
- Presentations to CS departments
- AI safety lab engagement
- Community building (HN, Reddit, technical blogs)
- Documentation for external researchers

## Success Metrics

### Short-term (1-2 weeks)
- [ ] Test coverage: 45% → 60%
- [ ] `inspect decisions` CLI command implemented
- [ ] Context awareness improvements deployed

### Medium-term (1 month)
- [ ] Test coverage: 75% (constitutional requirement)
- [ ] Autonomous success rate: 90%+
- [ ] A3 capabilities demonstrated

### Long-term (3 months)
- [ ] Full strategic refactoring autonomy (A3)
- [ ] Academic paper draft
- [ ] Community engagement initiated
- [ ] Demonstration of constitutional governance at scale

## Recent Achievements

**2026-01-10:**
- ✅ Deleted legacy AtomicActionsChecker, replaced with self-contained AtomicActionsEvaluator
- ✅ Deleted legacy PatternChecker, replaced with self-contained PatternEvaluator
- ✅ All evaluators now pure Component implementations
- ✅ Foundation hardening complete - ready for test coverage push

**2026-01-09:**
- ✅ Fixed all broken atomic fix actions (format, ids, headers, docstrings, logging)
- ✅ Achieved 100% success in dev sync workflow
- ✅ Constitutional compliance fully operational

## Key Learnings Applied

1. **Constitution → CORE:** If Constitution conflicts with reality, fix Constitution
2. **Quality over Speed:** Long-term architectural health over quick fixes
3. **Files <300-400 lines:** Atomic action principle for maintainability
4. **Complete files, not diffs:** Architect specifies intent, AI handles implementation
5. **Git checkpoints:** Before major changes, systematic verification at each step
6. **Self-awareness:** Rich context enables autonomous validation and self-improvement
