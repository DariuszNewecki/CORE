# Constitutional Coverage - Quick Reference

## 🎯 The Core Concept

**Test coverage is now a constitutional requirement, not optional.**

```yaml
Coverage < 75% = Constitutional Violation = Auto-Remediation
```

---

## 📋 Key Commands

### Check Coverage Compliance
```bash
core-admin coverage check
```
Returns exit code 0 if compliant, 1 if violations found.

### Generate Coverage Report
```bash
# Terminal report
core-admin coverage report

# HTML report (opens in browser)
core-admin coverage report --html
```

### Trigger Autonomous Remediation
```bash
core-admin coverage remediate
```
AI generates tests to restore compliance (may take 10-30 minutes).

### View Coverage History
```bash
core-admin coverage history
```

### Show Coverage Targets
```bash
core-admin coverage target
```

---

## 🔄 How It Works

### Integration Workflow (Automatic)
```
1. Developer commits code
2. Integration workflow runs
3. Tests execute
4. Coverage measured
5. If < 75%: HALT ❌
6. Developer must fix or remediate
7. Once compliant: commit proceeds ✅
```

### Background Watcher (Automatic)
```
1. Scheduled check runs (e.g., nightly)
2. Coverage violation detected
3. Auto-triggers remediation
4. Tests generated and validated
5. Coverage restored
6. Team notified
```

---

## 📊 Coverage Thresholds

| Type | Threshold | Enforcement |
|------|-----------|-------------|
| Overall | 75% | ERROR (blocks) |
| Target | 80% | WARN (aspirational) |
| Core modules | 85% | ERROR (critical paths) |
| Features | 80% | WARN |
| New code | 80% | WARN |

---

## 🚨 What Happens on Violation?

### During Integration
```
❌ Coverage check failed: 68% < 75%

Your options:
1. Run: core-admin coverage remediate
   (AI generates tests automatically)

2. Write tests manually
   (Traditional approach)

3. Request exception
   (Requires justification + approval)
```

### After Hours (Automatic)
```
[Background watcher detects violation]
→ Auto-triggers remediation
→ Generates 5 test files
→ Validates and commits
→ Coverage restored to 77%
→ Notification sent
```

---

## 🤖 Autonomous Remediation Process

```
Phase 1: Strategic Analysis (1-2 min)
├─ Measure coverage gaps
├─ Analyze module dependencies
├─ Prioritize by criticality
└─ Generate testing strategy

Phase 2: Goal Generation (30 sec)
├─ Convert strategy to tasks
├─ Create prioritized queue
└─ Save to work/testing/goals/

Phase 3: Test Generation (5-20 min)
├─ Generate test code with AI
├─ Validate syntax and style
├─ Execute tests
└─ Measure coverage improvement

Phase 4: Integration (30 sec)
├─ Re-measure final coverage
├─ Generate report
└─ Update ledger
```

---

## 📁 File Locations

### Work Directory
```
work/testing/
├── strategy/
│   └── test_plan.md          # AI-generated strategy
├── goals/
│   └── test_goals.json       # Prioritized test queue
├── logs/
│   └── remediation_*.json    # Execution logs
└── coverage_history.json     # Historical tracking
```

### Generated Tests
```
tests/
├── unit/
│   ├── test_prompt_pipeline.py    # Generated
│   ├── test_validation_pipeline.py
│   └── ...
└── integration/
    └── ...
```

---

## 🔧 Configuration

### Policy File
`.intent/charter/policies/governance/quality_assurance_policy.yaml`

Key settings:
```yaml
coverage_config:
  minimum_threshold: 75
  target_threshold: 80

  remediation_config:
    max_iterations: 10
    batch_size: 5
    cooldown_seconds: 10
    cooldown_hours: 24
```

### Exclusions
Add paths to exclude from coverage:
```yaml
exclusions:
  - "src/**/__init__.py"
  - "src/**/models.py"
  - "scripts/**/*.py"
```

---

## 🐛 Troubleshooting

### Coverage Check Fails
```bash
# Get detailed report
core-admin coverage report --show-missing

# Check which modules need tests
core-admin coverage check

# Manually add tests or trigger remediation
core-admin coverage remediate
```

### Remediation Produces Invalid Tests
```bash
# Check logs
cat work/testing/logs/remediation_*.json

# Review generated test files
ls tests/unit/test_*.py

# Manually fix and re-run
pytest tests/unit/test_problem.py
```

### In Cooldown Period
```bash
# Check watcher state
cat work/testing/watcher_state.json

# Wait for cooldown or manually bypass
# (Edit policy to reduce cooldown_hours)
```

### Emergency Bypass
If coverage gate blocks critical hotfix:

1. Add to exclusions temporarily
2. Or: Use `--no-verify` (NOT RECOMMENDED)
3. Or: Request emergency exception
4. Then: File issue to add tests later

---

## 📈 Best Practices

### For Developers

**Before Committing:**
```bash
# Check coverage
core-admin coverage check

# If low, remediate
core-admin coverage remediate

# Or add tests manually
```

**Writing New Code:**
- Write tests alongside new features
- Aim for 80%+ on new modules
- Don't rely solely on auto-generation

**Code Review:**
- Check coverage in PR
- Verify tests are meaningful
- Not just hitting lines, but testing behavior

### For AI-Generated Tests

**Review Before Accepting:**
- Tests actually test something
- Edge cases covered
- Error conditions handled
- Mocks used appropriately

**When to Regenerate:**
- Test is trivial (just imports)
- Coverage didn't improve
- Tests don't match module purpose

---

## 🎓 Examples

### Example 1: New Feature
```bash
# 1. Write feature code
vim src/features/new_feature.py

# 2. Check coverage impact
core-admin coverage check
# Output: 72% < 75% ❌

# 3. Generate tests
core-admin coverage remediate
# Output: Generated tests for 3 modules
#         Final coverage: 76% ✅

# 4. Commit
git add .
core-admin submit changes -m "Add new feature with tests"
```

### Example 2: Coverage Regression
```bash
# Integration workflow detects drop
> coverage.coverage_check FAILED
> Coverage dropped from 77% to 71%
> Significant regression: 6% drop

# Developer options:
Option 1: Auto-fix
$ core-admin coverage remediate

Option 2: Manual fix
$ # Write tests for affected modules
$ git add tests/
$ git commit --amend
```

### Example 3: CI Integration
```yaml
# .github/workflows/ci.yml
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Check Coverage
        run: |
          poetry install
          core-admin coverage check

      - name: Auto-Remediate if Needed
        if: failure()
        run: |
          core-admin coverage remediate
          core-admin coverage check
```

---

## 📞 Getting Help

### Documentation
- Implementation Plan: See `implementation_plan.md`
- Policy: `.intent/charter/policies/governance/quality_assurance_policy.yaml`
- Code: `src/features/governance/checks/coverage_check.py`

### Commands
```bash
# Help text
core-admin coverage --help
core-admin coverage check --help
core-admin coverage remediate --help

# View targets and config
core-admin coverage target

# Check history
core-admin coverage history
```

### Logs
```bash
# Remediation logs
ls work/testing/logs/

# Watcher state
cat work/testing/watcher_state.json

# Coverage history
cat work/testing/coverage_history.json
```

---

## 🎯 Quick Wins

### Increase Coverage Fast
1. Run remediation: `core-admin coverage remediate`
2. Let it generate 5 test files
3. Review and refine generated tests
4. Repeat for next 5 modules
5. Reach 75% in 2-3 cycles

### Maintain Coverage
1. Enable background watcher
2. Set up CI integration
3. Write tests with new code
4. Review coverage in PRs
5. Let system self-heal

### Demonstrate Quality
```bash
# Show current status
core-admin coverage report

# Show constitutional compliance
core-admin coverage check
# Output: ✅ Coverage meets requirements

# Show it's enforced
git commit
# Output: ✅ All checks passed
```

---

## 🚀 Pro Tips

1. **Run remediation overnight** - It takes time, let it work while you sleep

2. **Review generated tests** - AI is good but not perfect, refine for quality

3. **Start with core modules** - Get foundations solid first

4. **Use HTML reports** - Much easier to see what's missing
   ```bash
   core-admin coverage report --html
   ```

5. **Track trends** - Coverage should trend up over time
   ```bash
   core-admin coverage history
   ```

6. **Don't game the system** - Coverage is means to quality, not end goal

7. **Test behavior, not lines** - Focus on meaningful tests

8. **Keep exclusions minimal** - Most code should be tested

---

*Remember: This isn't about hitting a number. It's about building professional, maintainable, trustworthy software.* ✨
