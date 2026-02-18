# CORE Hardening Plan

**Created:** 2026-02-17
**North Star:** Truthfulness · Non-bypass · Determinism
**Rule:** If a change doesn't strengthen one of those three, it's not priority work.

---

## P0 — Today: Audit Truthfulness (15–60 min)

### P0.1 Rule crash → enforcement-failure finding
- [ ] Replace `except Exception: continue` in `constitutional_auditor_dynamic.py` with catch → finding
- [ ] Crashing rule produces finding with severity `ERROR` and type `ENFORCEMENT_FAILURE`
- [ ] Audit verdict becomes `DEGRADED` (not `PASS`) if any blocking rule crashed
- [ ] Audit summary includes: executed / crashed / skipped / unmapped counts

### P0.2 Unmapped/skipped rules visible in denominator
- [ ] Coverage stats use total declared rules as denominator (not just mapped)
- [ ] Report lists unmapped rule IDs explicitly
- [ ] Skipped-due-to-exclusion rules enumerated by rule + scope

---

## P1 — Week 1–2: Close Bypass Surfaces + Determinism

### P1.1 Atomic actions: executor-only enforcement (ContextVar token)
- [ ] Create `ContextVar` governance token carrying executor trace ID (not just boolean)
- [ ] `ActionExecutor.execute()` sets token before calling action
- [ ] `@atomic_action` wrapper validates token presence; raises `BypassError` if missing
- [ ] Direct calls fail loudly with structured log event
- [ ] Tests: direct-call failure + executor-call success

### P1.2 Planning must be pure
- [ ] Remove `random.random() < 0.1` cleanup from `PlannerAgent.create_execution_plan()`
- [ ] Move memory cleanup to explicit CLI command / scheduled maintenance
- [ ] Verify: zero `random.*` calls in planning, policy evaluation, or routing paths
- [ ] Audit trace distinguishes planning from maintenance

### P1.3 LLM gate cannot be blocking authority
- [ ] Audit all 7 `llm_gate` rules — downgrade any that are `blocking` to `reporting`
- [ ] LLM failure yields `ENFORCEMENT_UNAVAILABLE` finding (not code violation)
- [ ] Implement content-hash persistence for verdicts (same hash → same stored result)
- [ ] Define graduation criteria: when can an LLM rule become blocking?

### P1.4 ServiceRegistry race condition
- [ ] Move `cognitive_service` initialization fully inside the async lock
- [ ] Audit all `get_*` methods on ServiceRegistry for the same pattern
- [ ] Add explicit `reset()` method for test isolation
- [ ] Verify: no double-init under concurrent access

---

## P2 — Weeks 2–6: Boundaries Without Breakage

### P2.1 Layer boundary AST gates (reporting-first)
- [ ] Create `mind.no_body_imports` enforcement mapping (reporting-only)
- [ ] Create `mind.no_will_imports` enforcement mapping (reporting-only)
- [ ] Create `shared.no_upward_imports` enforcement mapping (reporting-only)
- [ ] Establish baseline violation count
- [ ] Promotion threshold: 0 violations for 2 consecutive weeks → blocking

### P2.2 Purge Mind's upward dependencies (incremental)
- [ ] Write "degraded Body" test: mock Body to throw on every call, run auditor
- [ ] Fix `mind/governance/enforcement/async_units.py` (imports service_registry)
- [ ] Fix `mind/logic/engines/llm_gate.py` (imports LLMClient) — inject via Protocol
- [ ] Fix `mind/governance/assumption_extractor.py` (imports CognitiveService)
- [ ] Fix remaining Mind → Body imports (12 more)
- [ ] Fix Mind → Will imports (5 total)
- [ ] Target: Mind depends only on mind, shared, stdlib, third-party

### P2.3 Purge Shared's upward dependencies
- [ ] Move `shared/infrastructure/lifespan.py` → `body/infrastructure/lifespan.py`
- [ ] Inject Body dependency in `shared/infrastructure/context/builder.py` via Protocol
- [ ] Move Mind types from `shared/models/constitutional_validation.py` to shared
- [ ] Remove remaining 6 upward imports
- [ ] Target: shared imports only from stdlib + third-party

### P2.4 CLI extraction (end of P2)
- [ ] Move `body/cli/` → `src/cli/` as independent composition layer
- [ ] CLI imports from Body/Will/Mind through stable interfaces only
- [ ] Verify: Body file count drops from 364 to ~143

---

## P3 — Weeks 6–10: Structural Consolidation (defer until P0–P2 done)

### P3.1 Consolidate test generation
- [ ] Merge `will/self_healing/test_generation/` into `will/test_generation/`
- [ ] Delete v1 services (clarity_service.py, complexity_service.py)
- [ ] Clear ownership: Body = analysis, Will = LLM generation

### P3.2 Consolidate governance location
- [ ] Move `body/governance/intent_guard.py` → `mind/enforcement/intent_guard.py`
- [ ] Move `body/services/constitutional_validator.py` → `mind/governance/`
- [ ] Body retains zero governance decision code

### P3.3 Exception hierarchy
- [ ] Define `CoreError` tree in `shared/exceptions.py`
- [ ] Systematic replacement of 102 silent `except Exception → return None`
- [ ] AST gate check: bare `except Exception` requires `# INTENTIONAL-CATCH: <reason>`

### P3.4 Eliminate passive engine rules
- [ ] Audit 9 passive-engine rules: enforce, reclassify, or delete
- [ ] Map or remove 13 unmapped constitutional rules
- [ ] Target: every rule either has enforcement or doesn't exist

---

## Operational Discipline

> No large relocations, merges, or "architecture cleanups" unless they directly reduce
> audit untruthfulness, bypassability, or nondeterminism.

---

## Progress Log

| Date | Item | Status | Notes |
|------|------|--------|-------|
| | | | |
