# CORE Enforcement Roadmap - Risk-Tier Prioritization

## The Problem

Current state: 40.5% enforcement coverage, only 3 policies at 100%
- This is a **credibility issue** for "constitutional governance"
- Shows governance is aspirational, not operational

## The Vision

**"CORE is the last programmer you'll ever need"**
- CORE doesn't need simple tools
- CORE needs REAL constraints that prevent unsafe autonomy
- Enforcement coverage = safety guarantee

## The Solution: Risk-Tier-First Enforcement

Prioritize by **impact**, not **ease**. Get critical safety rules to 100% FIRST.

---

## Priority 1: CRITICAL RISK (Target: 100% by Week 2)

**Goal:** Prevent catastrophic failures that compromise system integrity

### Rules to Enforce (13 rules)

**From safety.yaml:**
- ✅ `safety.change_must_be_logged` - Every file change logged with IntentBundle
- ✅ `safety.deny_core_loop_edit` - Cannot modify orchestration/governance without human
- ✅ `safety.immutable_constitution` - Constitution immutable without human
- ✅ `safety.no_dangerous_execution` - No dangerous execution primitives

**From agent_governance.yaml:**
- ✅ `agent.compliance.no_write_intent` - Agents cannot write to .intent/charter/**
- ✅ `agent.compliance.respect_cli_registry` - All tools route through CLI
- ✅ `agent.execution.no_unverified_code` - Cannot execute/commit without validation
- ✅ `agent.execution.require_runtime_validation` - Generated code must pass tests

**From code_execution.yaml:**
- ✅ `agent.execution.no_unverified_code` - Dangerous functions require multi-layer protection
- ✅ `agent.execution.require_runtime_validation` - Dynamic code must validate inputs

**From boundaries.yaml (if has rules):**
- 🎯 `boundaries.database_ssot` - Database is single source of truth
- 🎯 `boundaries.mind_immutability` - Mind layer cannot be modified by Body/Will
- 🎯 `boundaries.layer_separation` - Strict Mind/Body/Will separation

**Status:**
- Currently: 10/13 enforced (77%)
- Target: 13/13 enforced (100%)
- Effort: 2-3 days

**Deliverables:**
1. Implement 3 missing critical checkers
2. All critical violations = blocking errors
3. CI fails on any critical violation

---

## Priority 2: ELEVATED RISK (Target: 75% by Week 4)

**Goal:** Prevent operations with significant system impact

### Categories

**Architectural Boundaries:**
- `di.*` - Dependency injection requirements (already 100%!)
- `layer.*` - Layer separation contracts
- `boundary.*` - Cross-layer communication rules

**Data Integrity:**
- `db.*` - Database usage patterns
- `state.*` - State management rules
- `storage.*` - Data persistence policies

**Security:**
- `secrets.*` - Secret handling
- `auth.*` - Authentication/authorization
- `permissions.*` - Access control

**Target:**
- Currently: ~30-40% of elevated rules enforced
- Target: 75% enforced
- Effort: 2 weeks

---

## Priority 3: STANDARD RISK (Target: 50% by Month 2)

**Goal:** Enforce best practices that prevent technical debt

### Categories

**Code Quality:**
- `code.max_file_lines` - File size limits
- `code.max_function_lines` - Function size limits
- `code.complexity_limits` - Cyclomatic complexity

**Style (Automated):**
- ✅ `style.linter_required` - Ruff linting (already enforced!)
- ✅ `style.formatter_required` - Black formatting (already enforced!)
- `style.import_order` - Import ordering

**Documentation:**
- ✅ `style.docstrings_public_apis` - Public APIs have docstrings (already enforced!)
- `header_compliance` - File headers present

**Target:**
- Currently: ~40% of standard rules enforced
- Target: 50% enforced
- Effort: 1 month

---

## Priority 4: ROUTINE RISK (Target: Eventually)

**Goal:** Nice-to-haves that improve consistency

### Categories

**Naming Conventions:**
- `naming.code.python_module_naming` - snake_case modules
- `naming.intent.policy_file_naming` - Policy naming conventions
- `naming.code.test_module_naming` - test_ prefix

**Capabilities:**
- ✅ `caps.id_format` - ID format (already enforced!)
- ✅ `caps.meaningful_description` - No placeholder text (already enforced!)

**Target:**
- Currently: ~20% of routine rules enforced
- Target: 30%+ eventually
- Effort: Ongoing, low priority

---

## Implementation Strategy

### Week 1: Quick Wins
```bash
# 1. Identify missing critical checkers
core-admin governance coverage --format json | \
  jq '.entries[] | select(.rule.severity=="error" and .coverage_status=="declared_only")'

# 2. Focus on boundaries.yaml and safety.yaml
# Create checkers for 3 missing critical rules

# 3. Deploy and verify
core-admin check audit
```

### Week 2-4: Elevated Risk
- Batch-create checkers for elevated risk categories
- Focus on architectural boundaries (biggest ROI)
- Use CORE to generate the checkers! (A2 capability)

### Month 2: Standard Risk
- Automate what can be automated (style, imports)
- Use CORE to self-improve enforcement

---

## Success Metrics

### Current State
```
Total Enforcement: 40.5%
├─ Critical:  77% (10/13) ⚠️ BLOCKING
├─ Elevated:  35% (est)
├─ Standard:  40% (est)
└─ Routine:   20% (est)
```

### Target State (Month 2)
```
Total Enforcement: 65%+
├─ Critical:  100% (13/13) ✅ SAFE
├─ Elevated:   75%
├─ Standard:   50%
└─ Routine:    30%
```

### Ultimate Goal (Month 6)
```
Total Enforcement: 75%+ (Constitutional Requirement)
├─ Critical:  100% ✅
├─ Elevated:   90%
├─ Standard:   70%
└─ Routine:    40%
```

---

## Why This Matters

**For Academic Credibility:**
- "100% critical enforcement" = real safety guarantees
- "Risk-tier prioritization" = intelligent governance
- "Measurable progress" = scientific validation

**For AI Safety:**
- Critical rules = bounded autonomy proof
- Elevated rules = operational safety
- Coverage growth = continuous improvement

**For The Vision:**
- Safe autonomy enables A3/A4
- Constitutional compliance enables trust
- Risk-based gating enables "last programmer you'll ever need"

---

## Action Items (This Week)

**Day 1-2:** Implement 3 missing critical checkers
- [ ] `boundaries.database_ssot` checker
- [ ] `boundaries.mind_immutability` checker
- [ ] `boundaries.layer_separation` checker

**Day 3:** Deploy and validate
- [ ] Run full audit
- [ ] Verify 100% critical enforcement
- [ ] Update coverage report

**Day 4-5:** Document and communicate
- [ ] Update README with "100% critical enforcement"
- [ ] Blog post: "How CORE Achieves Safe Autonomy"
- [ ] Prepare academic presentation

---

## The Pragmatic Approach

**Don't:**
- ❌ Try to enforce everything at once
- ❌ Build complex DSLs for rule logic
- ❌ Over-engineer the checker system

**Do:**
- ✅ Focus on critical safety first
- ✅ Use simple Python checkers (works fine!)
- ✅ Let CORE generate its own checkers (dogfooding!)
- ✅ Measure and communicate progress

**Remember:**
- 100% critical = credible safety claim
- 75% overall = constitutional requirement met
- Risk-first = intelligent prioritization

**This is how CORE becomes "the last programmer you'll ever need" - through REAL, MEASURABLE governance.** 🚀
