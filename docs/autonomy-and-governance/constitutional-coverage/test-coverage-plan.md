# Constitutional Test Coverage - Implementation Plan

## 🎯 Vision

Transform CORE from a system with **22% test coverage** (toy project status) to **75%+ coverage** (production-grade) by making quality assurance a **constitutional requirement** with **autonomous self-healing**.

## 📋 What We're Building

### The Constitutional Approach

Instead of a bash script, we're integrating coverage requirements into CORE's governance DNA:

```
Code Change → Coverage Drops → Constitutional Violation → Auto-Remediation → Coverage Restored
```

This isn't a feature—it's a **constitutional mandate** that CORE must maintain.

---

## 📁 Files to Create/Modify

### 1. New Policy File
**File:** `.intent/charter/policies/governance/quality_assurance_policy.yaml`
- Establishes 75% minimum coverage as constitutional requirement
- Defines autonomous remediation process
- Specifies critical paths requiring higher coverage (85%+)
- Configures exclusions, reporting, and enforcement

### 2. Governance Check
**File:** `src/features/governance/checks/coverage_check.py`
- Implements `CoverageGovernanceCheck` class
- Measures current coverage using pytest
- Compares against constitutional thresholds
- Returns `AuditFinding` objects for violations
- Tracks coverage history for regression detection

### 3. Remediation Service
**File:** `src/features/self_healing/coverage_remediation_service.py`
- Implements `CoverageRemediationService` class
- **Phase 1:** Strategic analysis of coverage gaps
- **Phase 2:** Goal generation (prioritized test queue)
- **Phase 3:** Autonomous test generation using AI
- **Phase 4:** Validation and integration proposals

### 4. Coverage Watcher
**File:** `src/features/self_healing/coverage_watcher.py`
- Monitors for coverage violations
- Triggers autonomous remediation
- Implements cooldown to prevent excessive runs
- Maintains audit trail of remediation history

### 5. CLI Commands
**File:** `src/cli/commands/coverage.py`
- `core-admin coverage check` - Check compliance
- `core-admin coverage report` - Generate reports
- `core-admin coverage remediate` - Trigger remediation
- `core-admin coverage history` - View trends
- `core-admin coverage target` - Show requirements

### 6. Update Workflows
**File:** `.intent/charter/policies/operations/workflows_policy.yaml` (modify)
- Add `quality.test_suite` step to integration workflow
- Add `quality.coverage_check` step (blocking gate)
- Add `quality.generate_tests` to self-healing routines
- Version bump to 2.0.0

### 7. Register CLI Command
**File:** `src/cli/admin_cli.py` (modify)
- Import and register `coverage_app`
- Add to command registry

### 8. Register Capability
**File:** `.intent/mind/knowledge/domains/autonomy/self_healing.yaml` (modify)
- Add `coverage_remediation` capability
- Link to implementation in `coverage_remediation_service.py`

### 9. Register Governance Check
**File:** `src/features/governance/audit_runner.py` (modify)
- Import and register `CoverageGovernanceCheck`
- Add to list of constitutional checks

---

## 🚀 Implementation Phases

### Phase 1: Foundation (Day 1)
1. Create `quality_assurance_policy.yaml`
2. Implement `CoverageGovernanceCheck`
3. Update `workflows_policy.yaml` with coverage gate
4. Test that coverage check runs and reports violations

**Deliverable:** Integration workflow blocks on low coverage

### Phase 2: CLI Interface (Day 1-2)
1. Create `coverage.py` CLI commands
2. Register in `admin_cli.py`
3. Test all commands work correctly
4. Generate initial coverage reports

**Deliverable:** Developers can check coverage via CLI

### Phase 3: Autonomous Remediation (Day 2-3)
1. Implement `CoverageRemediationService`
2. Create strategy generation prompt template
3. Build test generation pipeline
4. Test on 1-2 modules manually

**Deliverable:** System can autonomously generate tests

### Phase 4: Watcher & Automation (Day 3-4)
1. Implement `CoverageWatcher`
2. Integrate with workflows
3. Add to CI pipeline
4. Test full autonomous loop

**Deliverable:** Full self-healing coverage enforcement

### Phase 5: Documentation & Polish (Day 4-5)
1. Update README with coverage info
2. Create demo video/screenshots
3. Write capability documentation
4. Add usage examples

**Deliverable:** Production-ready system

---

## 🔧 Configuration

### Coverage Thresholds
```yaml
minimum_threshold: 75      # Constitutional mandate
target_threshold: 80       # Aspirational goal
critical_paths:
  - "src/core/**/*.py: 85%"
  - "src/features/governance/**/*.py: 85%"
```

### Exclusions
```yaml
exclusions:
  - "src/**/__init__.py"
  - "src/**/models.py"      # Data classes
  - "tests/**/*.py"
  - "scripts/**/*.py"
```

### Remediation Settings
```yaml
max_iterations: 10
batch_size: 5               # Process 5 modules per run
cooldown_seconds: 10        # Between test generations
cooldown_hours: 24          # Between full remediations
```

---

## 📊 Integration Workflow (Updated)

```
1. fix ids --write
2. fix duplicate-ids --write
3. sync-knowledge --write
4. vectorize --write
5. define-symbols
6. ⭐ check tests                    [NEW]
7. ⭐ coverage check                 [NEW - BLOCKING GATE]
8. check audit
9. git commit
```

If step 7 fails (coverage < 75%):
- Integration **halts**
- Violation logged
- Developer notified
- Can manually run: `core-admin coverage remediate`
- Or: System auto-triggers in CI/background

---

## 🤖 Autonomous Remediation Process

### Trigger Conditions
- Coverage < 75% (constitutional violation)
- New uncovered modules > 3
- Coverage delta < -5% (significant drop)

### Execution Flow
```
1. STRATEGIC ANALYSIS
   ├─ Measure current coverage by module
   ├─ Analyze codebase structure (AST)
   ├─ Identify dependencies (import graph)
   ├─ Calculate priority scores
   └─ Generate test_plan.md

2. GOAL GENERATION
   ├─ Parse strategy document
   ├─ Create test goal queue (JSON)
   ├─ Prioritize by criticality
   └─ Save to test_goals.json

3. TEST GENERATION (Loop)
   ├─ Pop next goal from queue
   ├─ Generate test code via AI
   ├─ Validate (syntax, style, execution)
   ├─ Run tests and measure coverage
   ├─ If passed: commit test file
   └─ If failed: log and continue

4. INTEGRATION
   ├─ Re-measure coverage
   ├─ Generate remediation report
   ├─ Create micro-proposal (optional)
   └─ Update operational ledger
```

---

## 🎪 Demo Script

### The Problem
```bash
# Show current coverage
poetry run pytest --cov=src --cov-report=term

# Output: TOTAL ... 22%  ❌ Not professional
```

### The Solution
```bash
# Check constitutional compliance
core-admin coverage check

# Output:
# ❌ Found 1 coverage violation:
# ▸ Coverage 22% below constitutional minimum 75%
#   Current: 22%, Required: 75%, Gap: -53%
```

### Auto-Remediation
```bash
# Trigger autonomous healing
core-admin coverage remediate

# Output:
# 🤖 Constitutional Coverage Remediation Activated
# 📊 Phase 1: Strategic Analysis
# ✅ Strategy saved to work/testing/strategy/test_plan.md
# 📝 Phase 2: Goal Generation
# ✅ Generated 5 test goals
# 🔨 Phase 3: Test Generation
# ━━━ Iteration 1/5 ━━━
# 🎯 Target: src/core/prompt_pipeline.py
# ✅ Tests generated and passing
# ...
# 📊 Remediation Summary
#    Total: 5, Succeeded: 4, Failed: 1
#    Final Coverage: 78% ✅
```

### The Pitch
> "CORE doesn't just write code—it ensures quality. When coverage drops, **CORE writes its own tests**. When bugs appear, **CORE fixes itself**. This isn't just autonomous coding—**it's autonomous quality assurance**.
>
> And it's **constitutionally mandated**. Coverage below 75%? That's not just a warning—it's a **constitutional violation** that triggers automatic remediation. CORE treats quality as seriously as security."

---

## 📈 Success Metrics

### Immediate (Week 1)
- [ ] Coverage gate blocks integration when < 75%
- [ ] CLI commands operational
- [ ] Manual remediation works for 3+ modules
- [ ] Coverage increases to 40%+

### Short-term (Month 1)
- [ ] Autonomous remediation generates valid tests
- [ ] Coverage reaches 60%+
- [ ] Zero false positives in coverage gate
- [ ] Full audit trail in operational ledger

### Long-term (Quarter 1)
- [ ] Coverage stabilizes at 75%+
- [ ] Auto-remediation success rate > 70%
- [ ] Coverage violations rare (< 1/month)
- [ ] System self-maintains quality

---

## 🧪 Testing Strategy

### Unit Tests Needed
1. `test_coverage_check.py` - Test governance check
2. `test_coverage_remediation.py` - Test service
3. `test_coverage_watcher.py` - Test watcher
4. `test_coverage_cli.py` - Test CLI commands

### Integration Tests
1. Full remediation loop (mock AI)
2. Workflow integration with coverage gate
3. Watcher cooldown behavior
4. History tracking and regression detection

### Manual Tests
1. Run coverage check on current codebase
2. Trigger remediation on low-coverage module
3. Verify generated tests are valid
4. Test coverage gate blocks commit
5. Verify cooldown prevents spam

---

## 🚨 Risk Mitigation

### Risk: AI Generates Invalid Tests
**Mitigation:**
- Full validation pipeline (syntax, lint, execution)
- Only commit tests that pass
- Track failure rate, improve prompts
- Human review for critical paths

### Risk: Infinite Remediation Loop
**Mitigation:**
- Max iterations limit (10)
- Cooldown period (24 hours)
- Failure tracking and circuit breaker
- Manual override available

### Risk: Coverage Gate Blocks Legitimate Work
**Mitigation:**
- Clear error messages with remediation guidance
- Emergency bypass flag (requires justification)
- Exclusions for non-critical paths
- Grace period for new features

### Risk: Performance Impact
**Mitigation:**
- Async execution
- Cooldown between generations
- Run in background/CI, not blocking dev
- Batch processing (5 modules at a time)

---

## 🎓 Developer Experience

### When Coverage Drops

**Before (without system):**
```
Developer: "I'll add tests later"
[Coverage drops to 15%]
[Project looks unmaintained]
```

**After (with system):**
```
$ git commit -m "Add new feature"
> Running integration workflow...
> ❌ Coverage check failed: 68% < 75%
>
> Action required:
> 1. Run: core-admin coverage remediate
> 2. Or: Add tests manually for new code
> 3. Or: Request exception with justification
```

### Autonomous Healing
```
[Background service detects violation]
[Auto-triggers remediation]
[Generates 5 test files]
[Coverage restored to 77%]
[Notification sent to team]
[No developer intervention needed]
```

---

## 🔮 Future Enhancements

### V2: Intelligent Test Generation
- Learn from existing test patterns
- Generate integration tests, not just unit tests
- Test edge cases and error conditions
- Property-based testing

### V3: Coverage Quality Metrics
- Not just line coverage, but branch coverage
- Mutation testing scores
- Test effectiveness metrics
- Critical path redundancy

### V4: Predictive Maintenance
- Predict modules likely to need tests
- Pre-generate tests before code changes
- Suggest test improvements
- Identify flaky tests

---

## 📚 References

### Constitutional Documents
- `.intent/charter/policies/governance/quality_assurance_policy.yaml`
- `.intent/charter/policies/operations/workflows_policy.yaml`
- `.intent/charter/policies/safety_policy.yaml`

### Implementation Files
- `src/features/governance/checks/coverage_check.py`
- `src/features/self_healing/coverage_remediation_service.py`
- `src/features/self_healing/coverage_watcher.py`
- `src/cli/commands/coverage.py`

### Related Services
- `src/core/test_runner.py` - Test execution
- `src/features/governance/audit_runner.py` - Constitutional auditor
- `src/features/self_healing/enrichment_service.py` - Similar AI service
- `src/features/project_lifecycle/integration_service.py` - Workflow runner

---

## ✅ Next Steps

1. **Review this plan** - Get team alignment
2. **Create branch** - `feature/constitutional-coverage`
3. **Phase 1 implementation** - Coverage check + gate
4. **Test and validate** - Ensure it blocks correctly
5. **Phase 2-4 implementation** - Full autonomous system
6. **Demo and document** - Show it off!
7. **Deploy to production** - Make it constitutional law

**Timeline:** 4-5 days for full implementation
**Priority:** HIGH - This is a production readiness blocker

---

*"Quality isn't a feature—it's a constitutional right."* 🏛️
