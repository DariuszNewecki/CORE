# Constitutional Coverage - Implementation Checklist

## ✅ Phase 1: Core Files (30 minutes)

### Prompt Templates
- [ ] Create `.intent/mind/prompts/coverage_strategy.prompt`
  - Copy from artifact: "Coverage Strategy Generation Prompt"
- [ ] Create `.intent/mind/prompts/test_generator.prompt`
  - Copy from artifact: "Test Generation Prompt"

### Python Modules
- [ ] Create `src/features/self_healing/coverage_analyzer.py`
  - Copy from artifact: "Coverage Analyzer Module"
- [ ] Create `src/features/self_healing/test_generator.py`
  - Copy from artifact: "Test Generator Module"
- [ ] Replace `src/features/self_healing/coverage_remediation_service.py`
  - Backup old version first
  - Copy from artifact: "Coverage Remediation Service (Refactored)"

### Verification
- [ ] Run `make dev-sync` - Should pass with no lint errors
- [ ] Test imports:
  ```bash
  python -c "from features.self_healing.coverage_analyzer import CoverageAnalyzer"
  python -c "from features.self_healing.test_generator import TestGenerator"
  ```

---

## ✅ Phase 2: Policy & Governance (20 minutes)

### Policy File
- [ ] Create `.intent/charter/policies/governance/quality_assurance_policy.yaml`
  - Copy from artifact: "Quality Assurance Policy (Constitutional)"

### Governance Check
- [ ] Create `src/features/governance/checks/coverage_check.py`
  - Copy from artifact: "Coverage Governance Check"

### Register Check
- [ ] Edit `src/features/governance/audit_runner.py`
  - Import: `from features.governance.checks.coverage_check import CoverageGovernanceCheck`
  - Register in checks list

### Verification
- [ ] Run `core-admin check audit` - Should include coverage check
- [ ] Verify policy loads: `python -c "from shared.config import settings; print(settings.load('charter.policies.governance.quality_assurance_policy')['id'])"`

---

## ✅ Phase 3: CLI & Workflows (20 minutes)

### CLI Commands
- [ ] Create `src/cli/commands/coverage.py`
  - Copy from artifact: "Coverage CLI Commands"

### Register CLI
- [ ] Edit `src/cli/admin_cli.py`
  - Import: `from cli.commands.coverage import coverage_app`
  - Register: Add `coverage_app` to command list

### Update Workflows
- [ ] Edit `.intent/charter/policies/operations/workflows_policy.yaml`
  - Copy from artifact: "Updated Workflows Policy with Coverage"
  - Or manually add the two new steps (test_suite and coverage_check)

### Verification
- [ ] Test CLI: `core-admin coverage --help`
- [ ] Test check: `core-admin coverage check`
- [ ] Test report: `core-admin coverage report`

---

## ✅ Phase 4: Watcher & Automation (15 minutes)

### Watcher Service
- [ ] Create `src/features/self_healing/coverage_watcher.py`
  - Copy from artifact: "Coverage Watcher Service"

### Register Capability
- [ ] Edit `.intent/mind/knowledge/domains/autonomy/self_healing.yaml`
  - Add capability entry for `coverage_remediation`
  - Reference implementation file

### Verification
- [ ] Test watcher imports: `python -c "from features.self_healing.coverage_watcher import watch_and_remediate"`

---

## ✅ Phase 5: Testing (30 minutes)

### Manual Tests
- [ ] Run coverage check: `core-admin coverage check`
  - Should report current coverage (likely < 75%, violations expected)

- [ ] Generate report: `core-admin coverage report --html`
  - Should create `htmlcov/index.html`

- [ ] Test integration workflow:
  ```bash
  echo "# test" > test_file.py
  git add test_file.py
  core-admin submit changes -m "Test coverage gate"
  ```
  - Should fail at coverage check if < 75%

### Optional: Test Remediation (takes 10-20 minutes)
- [ ] Run remediation: `core-admin coverage remediate`
  - Will generate tests for top 5 modules
  - May take 10-20 minutes
  - Check `work/testing/` for outputs

---

## ✅ Phase 6: Documentation (15 minutes)

### Update README
- [ ] Add coverage badge/section
- [ ] Mention 75% constitutional requirement
- [ ] Link to quick reference

### Create Developer Guide
- [ ] Add `docs/coverage.md` (use Quick Reference artifact)
- [ ] Or update existing quality docs

### Verification
- [ ] Documentation is clear and accurate
- [ ] Examples work as shown

---

## 🚀 Quick Start (Minimum Viable)

If you want to get something working FAST, do these in order:

1. **Create prompt templates** (5 min)
2. **Create analyzer & generator modules** (5 min)
3. **Replace remediation service** (5 min)
4. **Create policy file** (5 min)
5. **Create coverage check** (5 min)
6. **Run `make dev-sync`** (2 min)
7. **Test `core-admin coverage check`** (1 min)

**Total: ~30 minutes to working system**

---

## 🐛 Troubleshooting

### Lint Errors
```bash
# Run linting
make dev-sync

# If errors, check:
# - Variable names (no single letters like 'l')
# - Import order
# - Line length < 88 chars
```

### Import Errors
```bash
# Test each module independently
python -c "from features.self_healing.coverage_analyzer import CoverageAnalyzer"
python -c "from features.self_healing.test_generator import TestGenerator"

# If fails, check:
# - File exists
# - __init__.py in directory
# - No syntax errors
```

### Policy Not Loading
```bash
# Test policy loading
python -c "from shared.config import settings; print(settings.load('charter.policies.governance.quality_assurance_policy'))"

# If fails, check:
# - File path correct
# - YAML syntax valid
# - policy_id field exists
```

### CLI Command Not Found
```bash
# Check registration
core-admin --help | grep coverage

# If missing, verify:
# - Import in admin_cli.py
# - coverage_app registered
# - No syntax errors in coverage.py
```

---

## 📊 Success Criteria

### Phase 1 Complete When:
- ✅ `make dev-sync` passes
- ✅ All imports work
- ✅ No lint errors

### Phase 2 Complete When:
- ✅ Policy loads without errors
- ✅ Coverage check runs
- ✅ Violations reported correctly

### Phase 3 Complete When:
- ✅ CLI commands work
- ✅ Integration workflow includes coverage gate
- ✅ Gate blocks low coverage

### Phase 4 Complete When:
- ✅ Watcher service imports
- ✅ Can trigger remediation
- ✅ Cooldown works

### Phase 5 Complete When:
- ✅ All manual tests pass
- ✅ Coverage check reliable
- ✅ Remediation generates valid tests

### Phase 6 Complete When:
- ✅ Documentation complete
- ✅ Examples work
- ✅ Ready for demo

---

## 🎯 Priority Order

### Must Have (P0)
1. Coverage check working
2. Integration gate blocking
3. CLI commands functional

### Should Have (P1)
4. Remediation service working
5. Watcher service setup
6. Documentation complete

### Nice to Have (P2)
7. CI integration
8. Background automation
9. Historical tracking

---

## ⏱️ Time Estimates

| Phase | Time | Cumulative |
|-------|------|------------|
| Phase 1 | 30 min | 30 min |
| Phase 2 | 20 min | 50 min |
| Phase 3 | 20 min | 70 min |
| Phase 4 | 15 min | 85 min |
| Phase 5 | 30 min | 115 min |
| Phase 6 | 15 min | 130 min |

**Total: ~2 hours for full implementation**

**Minimum viable: ~30 minutes**

---

## 📞 Need Help?

### Common Issues

**Q: Lint fails with E741?**
A: Change single-letter variables (`l` → `line`, `i` → `index`)

**Q: Import errors?**
A: Check file paths and `__init__.py` files exist

**Q: Policy doesn't load?**
A: Verify YAML syntax and file path

**Q: CLI command not found?**
A: Check registration in `admin_cli.py`

**Q: Coverage check fails?**
A: This is expected if coverage < 75%, it's working correctly!

---

## ✨ You're Done When...

- [ ] `make dev-sync` passes ✅
- [ ] `core-admin coverage check` works ✅
- [ ] Integration blocks on low coverage ✅
- [ ] Can generate coverage reports ✅
- [ ] Can trigger remediation ✅
- [ ] Documentation exists ✅

**Congratulations! You've made test coverage constitutional!** 🎉

---

*Remember: Start with the minimum viable (30 min) and iterate from there. Don't try to do everything at once!*
