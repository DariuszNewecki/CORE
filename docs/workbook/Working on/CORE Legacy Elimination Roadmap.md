# CORE Legacy Elimination Roadmap → Pure V2 Alignment

**Date**: January 12, 2026
**Status**: Strategic Planning
**Goal**: Eliminate ALL legacy V1 patterns and achieve 100% V2 compliance

---

## 1. Current State Assessment

### ✅ What's Already V2-Aligned (Keep/Maintain)
- **AutonomousWorkflowOrchestrator**: Implements full A3 loop correctly
- **Component Architecture**: Analyzers, Evaluators, Strategists, Interpreters working
- **Adaptive Loops**: `fix clarity v2.3`, `fix complexity v2.3` achieving 57-70% success
- **V2 Command Pattern**: Documented and implemented in reference commands
- **Constitutional Governance**: Decision tracers, audit context, governance decider
- **UNIX Philosophy**: Single responsibility, clear interfaces, minimal coupling
- **Atomic Actions**: ActionExecutor, atomic_action decorator system

### ⚠️ What's Broken/Incomplete (Must Fix)
1. **ExecutionAgent file return issue**: Doesn't return `files_written` in ExecutionResults
2. **Crate extraction logic**: References `step.params["code"]` that doesn't exist
3. **Modularity remediation**: Broken because of crate issue + logic conservation gate
4. **develop_from_goal output_mode="crate"**: Returns empty dict

### ❌ What's Legacy V1 (Remove)
1. **AccumulativeTestService** (`src/features/self_healing/accumulative_test_service.py`)
   - Commands: `coverage accumulate`, `coverage accumulate-batch`
   - Strategy: Symbol-by-symbol generation (no adaptation, ~0% success)
   - Replacement: Use `coverage generate-adaptive` (V2)

2. **Legacy test generation infrastructure**
   - `SingleFileRemediationService` (old version)
   - `FullProjectRemediationService` (monolithic, non-adaptive)
   - Replacement: `EnhancedSingleFileRemediationService` + adaptive loop

3. **CrateCreationService + CrateProcessingService** (deprecated)
   - Status: The service exists but isn't properly integrated
   - Issue: ExecutionAgent writes files directly, skipping the crate packaging
   - Decision: Either integrate properly OR deprecate entirely
   - Recommendation: **Integrate properly** (Option B from investigation)

4. **Deprecated CLI commands**
   - `core-admin fix line-lengths` (no strategic value)
   - `core-admin coverage accumulate` (V1 pattern)
   - `core-admin coverage accumulate-batch` (V1 pattern)
   - `core-admin develop feature/fix/test` (should only use `develop refactor`)

5. **Mixed settings.load() calls**
   - Throughout codebase
   - Replacement: `settings.get_path()` + structured config loading

---

## 2. Phase 1: Fix Critical Infrastructure (Week 1)

### A. ExecutionAgent Enhancement
**Goal**: Make ExecutionAgent return what it writes

```python
# In ExecutionResults dataclass
@dataclass
class ExecutionResults:
    steps: list[ActionResult]
    files_written: dict[str, str] = field(default_factory=dict)  # <-- ADD THIS
    # ... other fields
```

**In ExecutionAgent.execute_plan()**:
```python
files_written = {}

for step in detailed_plan.steps:
    result = await self.executor.execute(
        action_id=step.action,
        file_path=step.params.get("file_path"),
        code=step.params.get("code"),
        write=self.write
    )

    # Capture writes
    if step.action in ("file.create", "file.edit") and result.ok:
        file_path = step.params.get("file_path")
        code = step.params.get("code")
        if file_path and code:
            files_written[file_path] = code

return ExecutionResults(
    ...,
    files_written=files_written  # <-- RETURN IT
)
```

**Impact**:
- ✅ Modularity remediation starts working
- ✅ Crate extraction gets actual content
- ✅ All output_mode variations work

### B. Fix develop_from_goal Crate Extraction
**In develop_from_goal()**:
```python
if output_mode == "crate":
    # Use files_written from execution, not step.params
    generated_files = execution_results.files_written or {}

    return (True, {
        "files": generated_files,
        "context_tokens": 0,
        "plan": [...],
        "validation_passed": True,
    })
```

**Impact**:
- ✅ All autonomous development output modes functional
- ✅ Crate mode actually returns files

### C. Decision: Crate System (Keep or Remove?)
**Current state**:
- CrateCreationService: Exists but unused
- CrateProcessingService: Exists but skipped
- Papers: Documented the intent (staging + canary)

**Options**:
1. **Remove entirely** (simplification): Delete crate services, use ExecutionAgent.files_written directly
2. **Restore properly** (full A3 pattern): Integrate CrateProcessingService back into AutonomousWorkflowOrchestrator

**Recommendation**: **RESTORE PROPERLY** because:
- It's documented in papers as part of A3 loop
- Canary validation is a safety feature
- Non-trivial for academic demonstration
- Aligns with "trial-and-error" pattern

**Timeline**: Phase 2 (after Phase 1 quick wins)

---

## 3. Phase 2: Eliminate V1 Commands & Services (Week 2)

### Step 1: Deprecate AccumulativeTestService
```bash
# These commands will be REMOVED:
- core-admin coverage accumulate <file>
- core-admin coverage accumulate-batch --count 5

# Users must use instead:
- core-admin coverage generate-adaptive <file>     # V2: 57% success, adapts
- core-admin coverage check gaps                   # See what's missing first
```

**Action Items**:
- [ ] Remove `AccumulativeTestService` class
- [ ] Remove commands from CLI registration
- [ ] Update help text to direct users to `generate-adaptive`
- [ ] Remove test fixtures that test accumulative service

### Step 2: Remove Legacy Test Generation Services
```python
# REMOVE:
- src/features/self_healing/accumulative_test_service.py
- src/features/self_healing/single_file_remediation.py (old version)
- src/features/self_healing/full_project_remediation.py (old version)

# KEEP:
- EnhancedSingleFileRemediationService (uses V2 adaptive loop)
- Coverage remediation infrastructure that routes to enhanced version
```

### Step 3: Clean Up Deprecated CLI Commands
```python
# REMOVE from core-admin:
- fix line-lengths                    # No strategic value
- develop feature/fix/test            # Confusing, use "develop refactor"
- coverage accumulate*                # V1 pattern

# KEEP:
- coverage generate-adaptive          # V2, ~57% success
- coverage check                      # Diagnostics
- fix clarity                         # V2.3, 70% success
- fix complexity                      # V2.3, 70% success
- develop refactor                    # Generic autonomous refactoring
```

### Step 4: Modernize Settings Usage
**Replace all `settings.load()` with structured access**:
```python
# OLD (deprecated):
policy = settings.load("charter.policies.governance.quality_assurance_policy")

# NEW:
qa_policy_path = settings.paths.policy("quality_assurance")
qa_policy = yaml.safe_load(qa_policy_path.read_text())
```

**Files to update**:
- [ ] `coverage_watcher.py`
- [ ] All service classes with `settings.load()`
- [ ] Configuration bootstrap code

---

## 4. Phase 3: Restore Crate System (Week 3)

### Step 1: Reintegrate CrateProcessingService
Put this back into `AutonomousWorkflowOrchestrator.execute_autonomous_goal()`:

```python
# In the A3 loop (after SpecificationAgent, before ExecutionAgent):

# 3. STAGE IN CRATE (new location)
crate_id = await self._stage_in_crate(goal, detailed_plan)

# 4. RUN CANARY TRIAL
success, feedback = await self._run_canary_trial(crate_id)

if not success:
    # Feedback loop: engineer tries again with canary insights
    # (existing retry logic with crate_id from feedback)
    pass

# 5. EXECUTE APPROVED CRATE
execution_results = await self.exec_agent.execute_plan(detailed_plan)
```

### Step 2: Connect ExecutionAgent to Crate Results
```python
# ExecutionAgent knows what was written
# Return that in execution_results.files_written

# Then update task tracking:
# - crate_id (staging ID for audit trail)
# - files_written (content returned)
```

**Impact**:
- Full A3 loop operational: Plan → Spec → Crate → Canary → Execute
- Canary validates before production write
- Audit trail intact (crate_id)
- Self-healing through trial-and-error

---

## 5. Phase 4: Test & Consolidate (Week 4)

### Comprehensive Testing
```bash
# Test each V2 command works end-to-end:

1. core-admin fix clarity <file> --write
   - Should use V2.3 pattern
   - Run adaptive loop up to 3x
   - Show strategy selection

2. core-admin fix modularity --limit 1 --write
   - Should use develop_from_goal with crate mode
   - Modularity checker validates improvement
   - Files actually written

3. core-admin coverage generate-adaptive <file> --write
   - Should use adaptive test generator
   - Pattern recognition switches strategies
   - Tests end up in /tests

4. core-admin develop refactor "split this service"
   - Full workflow: Plan → Spec → Crate → Canary → Execute
   - Output shows A3 loop phases
```

### Update Documentation
- [ ] Remove V1 references from papers/
- [ ] Update V2 Command Pattern Reference with crate integration
- [ ] Add decision trace examples
- [ ] Document when to use which V2 command

---

## 6. What You'll Have at the End

| Aspect | V1 Legacy | V2 Future |
|--------|-----------|-----------|
| **Test Gen** | Accumulative (0% success) | Adaptive (57% success) |
| **Refactoring** | Procedural | Component-based with phases |
| **Feedback** | None (one-shot) | Adaptive loop + decision tracing |
| **Validation** | Post-execution | Canary pre-execution (when crate enabled) |
| **Architecture** | Scattered decision logic | Unified orchestrator |
| **Governance** | Implicit | Explicit (GovernanceDecider) |
| **Traceability** | Logs | Decision traces + audit log |
| **Success Rate** | ~10% | ~60-70% |
| **Code Complexity** | High (lots of special cases) | Low (universal pattern) |

---

## 7. Implementation Checklist

### Phase 1: Quick Wins (Days 1-3)
- [ ] ExecutionAgent: Add `files_written` to ExecutionResults
- [ ] ExecutionAgent.execute_plan(): Capture writes
- [ ] develop_from_goal(): Use `execution_results.files_written` for crate mode
- [ ] Test: `core-admin fix modularity --limit 1` works
- [ ] Test: `core-admin develop refactor "test goal"` returns files

### Phase 2: Deprecation (Days 4-7)
- [ ] Remove AccumulativeTestService
- [ ] Remove legacy test generation CLI commands
- [ ] Remove deprecated commands (line-lengths, develop feature/fix/test)
- [ ] Update all settings.load() → settings.paths.policy()
- [ ] Run full test suite

### Phase 3: Crate Restoration (Days 8-14)
- [ ] Restore CrateProcessingService integration
- [ ] Wire crate_id through workflow
- [ ] Enable canary trials
- [ ] Test full A3 loop

### Phase 4: Consolidation (Days 15-21)
- [ ] Comprehensive testing of all V2 commands
- [ ] Update all documentation
- [ ] Remove this roadmap (it becomes obsolete)
- [ ] Prepare for academic presentation

---

## 8. Success Metrics

After this roadmap:

✅ **Zero legacy code**: No V1 patterns in src/
✅ **100% V2 commands**: All autonomous operations follow INTERPRET→EXECUTE
✅ **Crate system working**: Staging + canary trials fully operational
✅ **Adaptive loops everywhere**: All test/fix commands use pattern recognition
✅ **Decision tracing**: Can audit "why did CORE choose X?"
✅ **70%+ autonomous success**: Measurable improvement over current
✅ **Academic ready**: Architecture clear enough to publish

---

## 9. Contingencies

**If crate restoration proves complex**:
- Keep it simple: Just return `files_written` dict
- Skip canary trials for now (Phase 4 future work)
- Document as "staged for Phase 2"

**If settings modernization takes longer**:
- Gradual migration (one service at a time)
- Parallel old+new for transition period

**If V2 pattern doesn't work for some command**:
- Document exception + rationale
- Update "When to Use V2" guide
- Consider if it should be a simple tool instead

---

## Next Action

**Start with Phase 1, Day 1**: ExecutionAgent enhancement.
This unblocks everything else and is the lowest-risk change.

Once that works, modularity remediation will work, and you'll see immediate value.

Then proceed through phases sequentially.

**Total timeline**: 3 weeks to pure V2 alignment.

---

**Version**: 1.0
**Author**: Code Review
**Status**: Ready for execution
