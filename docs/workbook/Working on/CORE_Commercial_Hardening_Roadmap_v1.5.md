# CORE Hardening Plan

**Created:** 2026-02-17
**Updated:** 2026-02-23 (v1.5 – The "Shadow Sensation" Update)
**North Star:** Truthfulness · Non-bypass · Determinism
**Current Status:** ~92% of P0–P2 Complete

---

## Recent Wins (Feb 18–23)

* **Shadow Sensation:** Resolved the "Two Brains" bug by localizing `ContextService` to `LimbWorkspace`. Agents now see their own uncommitted changes.
* **Anti-Lobotomy Guard:** Implemented `LogicConservationCheck` to prevent AI from deleting production code during refactoring.
* **Bypass Hardening:** Governance Token ("ID Badge") now required for all `@atomic_action` calls.
* **Kernel Security:** Hardcoded `KERNEL_SERVICES` in `ServiceRegistry` to prevent RCE via database edits.

---

# P0 — Audit Truthfulness: COMPLETE ✅

## Rule Crash → Enforcement Failure Finding

* Rule crashes produce `ENFORCEMENT_FAILURE` findings (no silent failures).
* Audit verdict becomes `DEGRADED` if rule engines fail.

## Truthful Statistics

* Coverage stats use total declared rules as denominator.
* Reports list unmapped rule IDs explicitly.

---

# P1 — Close Bypass Surfaces + Determinism: 95% COMPLETE 🟢

## Atomic Actions: Executor-Only Enforcement

* `ContextVar` governance token carrying executor trace ID.
* `@atomic_action` validates token presence.
* Raises `GovernanceBypassError` if missing.

**Verification:** Actions cannot be called directly from agents without `ActionExecutor`.

---

## Planning Must Be Pure

* Removed non-deterministic random cleanup from planning.
* Memory cleanup moved to explicit CLI command (database cleanup).

---

## LLM Gate Cannot Be Blocking Authority

* Downgraded all 7 `llm_gate` rules to reporting.
* LLM failure yields `ENFORCEMENT_UNAVAILABLE` finding.

**OPEN:** Define graduation criteria — when does an LLM rule become "trusted" enough to block?

---

## ServiceRegistry Hardening

* Moved `cognitive_service` initialization inside async lock.
* Added `ServiceRegistry.reset()` for test isolation.

---

# P2 — Boundaries Without Breakage: 85% COMPLETE 🟡

## Layer Boundary AST Gates (Reporting-First)

* Created `mind.no_body_imports` / `mind.no_will_imports` mappings.
* Created `shared.no_upward_imports` mapping.

**Focus:** Establish baseline violation counts for new gates.

---

## Purge Mind's Upward Dependencies (High Success)

* Decoupled `llm_gate.py` via `LLMClientProtocol`.
* Decoupled `assumption_extractor.py` via `CognitiveProtocol`.

**Target:** Mind depends only on `mind`, `shared`, and stdlib.

---

## Purge Shared's Upward Dependencies

* Moved `shared/infrastructure/lifespan.py` → `body/infrastructure/lifespan.py`.
* `shared/models/constitutional_validation.py` now uses protocols (`ViolationLike`).

---

## CLI Extraction (Final P2 Hurdle)

* Move `src/body/cli/` → `src/cli/` as independent composition layer.

**Verification Target:** Body file count drops from ~360 to ~150.

---

# P3 — Structural Consolidation: 40% COMPLETE 🟠

## Consolidate Test Generation

* Merge `will/self_healing/test_generation/` → `will/test_generation/`.
* Delete obsolete v1 services (`clarity_service.py`, `complexity_service.py`).

**Ownership Established:**

* Body = analysis (`FileAnalyzer`)
* Will = reasoning (`CoderAgent`)

---

## Consolidate Governance Location

* Move `src/body/governance/intent_guard.py` → `src/mind/enforcement/intent_guard.py`.
* Body retains only execution capability (`EngineDispatcher`), no "Law" logic.

---

## Exception Hierarchy

* Define `CoreError` tree in `shared/exceptions.py`.
* Replaced silent `except Exception → return None` with structured logging.

---

## Eliminate Passive Engine Rules

* Implemented `passive_gate` engine to acknowledge substrate-enforced rules.

**OPEN:** Map or remove remaining 13 unmapped constitutional rules.

---

# Operational Discipline

No large relocations or architectural cleanups unless they directly reduce:

* Audit untruthfulness
* Bypassability
* Nondeterminism

---

# Next Major Action

**Move `src/body/cli` → `src/cli`.**

---

# Progress Log

| Date       | Item                                                         | Status | Notes                                   |
| ---------- | ------------------------------------------------------------ | ------ | --------------------------------------- |
| 2026-02-18 | Commit 3f05c71a: audit crash handling, token enforcement     | Done   | ~75–90% overall hardening               |
| 2026-02-23 | Shadow Sensation + Anti-Lobotomy + Localized Context Service | Done   | ~92% complete. Split-brain bug resolved |
