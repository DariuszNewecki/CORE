# Technical Debt & Architectural Health (Governed Log)

> **Status:** Active
> **Last Updated:** 2025-11-24
> **Recent Milestone:** Completed A2-Readiness Refactor (ServiceRegistry & DI)

This document serves as the **canonical, governed overview** of technical debt inside CORE.
It consolidates architectural signals from:

* `DuplicationCheck` audits
* Introspection reports
* Constitutional validator findings
* A2-readiness refactor results

It replaces legacy notes with a **single source of truth** that guides safe evolution.

---

# 1. Purpose

In CORE, technical debt is **not** “messy code.”
In a governed system, debt is any misalignment between **constitution, architecture, and implementation**, such as:

* misalignment with constitutional principles,
* friction between Mind, Body, and Will,
* drift between source code and knowledge graph,
* architecture or dependency violations,
* unruled exceptions,
* duplicated logic that weakens clarity.

Technical debt is tracked to ensure it is:

* **transparent**
* **classifiable**
* **prioritized**
* **tractable**
* **auditable**

---

# 2. Sources of Technical Debt

CORE produces three natural classes of debt:

## 2.1 Code-Level Debt (Body)

* Duplicate logic
* Complexity hotspots
* Mis-scoped helpers
* Missing tests
* Thin wrappers being misclassified as duplicates

## 2.2 Knowledge Debt (Mind)

* Drift between DB symbols and actual source
* Outdated capability definitions
* Missing or stale domain boundaries
* Legacy tags

## 2.3 Intent Debt (Will → Mind Alignment)

* Prompts outdated vs current expectations
* Missing policy coverage
* Incomplete or inconsistent examples in context providers

---

# 3. Current Architectural Debt (Backlog)

## 🔴 High Priority — Critical for A2

### 3.1 Test Coverage Gaps

* Current: ~51% (target: 75%)
* Impact: limits trust in autonomous refactoring
* Action: nightly coverage remediation
* Principle: `safe_by_default`

### 3.2 Semantic Duplication Warnings

* ~57 warnings flagged
* Many due to legitimate CLI→Service mirrors
* Action: Tune `DuplicationCheck` or mark intentional patterns
* Principle: `dry_by_design`

## 🟡 Medium Priority — Structural Maintenance

### 3.3 Legacy "Shared" Utilities

* Overlap between `src/shared/utils` and `src/services`
* Action: Consolidate into clear boundaries:

  * logic utilities → `shared.universal`
  * infra utilities → `services`
* Principle: `separation_of_concerns`

---

# 4. Recently Resolved Debt (Victories)

### ✅ [2025-11-24] Split-Brain Dependency Injection

* Issue: Multiple independent instantiations of `QdrantService`
* Fix: Introduced `ServiceRegistry` + strict DI
* Result: Stable service lifecycle

### ✅ [2025-11-24] Orphaned Logic in Self-Healing

* Issue: New components missing capability IDs
* Fix: Added 13 capability definitions + resynced DB
* Result: Auditor passes cleanly

### ✅ [2025-11-24] Database-as-SSOT Migration

* Issue: Mixed YAML/db source of truth
* Fix: DB is now the canonical SSOT
* Result: Docs auto-generated from knowledge graph

---

# 5. Governance Principles for Debt

Debt evaluation follows CORE’s constitutional guidelines:

1. **`clarity_first`** — clarity beats cleverness
2. **`dry_by_design`** — eliminate duplication
3. **`evolvable_structure`** — improve long-term adaptability
4. **`safe_by_default`** — never break audit compliance
5. **`separation_of_concerns`** — maintain boundary integrity

---

# 6. Recommended Workflow for Addressing Debt

1. Reproduce audit findings:

   ```bash
   poetry run core-admin check audit
   ```
2. Classify the finding: **False Positive → Intentional Pattern → Actionable Debt**
3. Apply safe fixes:

   ```bash
   poetry run core-admin fix all
   ```
4. Sync knowledge:

   ```bash
   poetry run core-admin manage database sync-knowledge
   ```
5. Re-run the constitutional audit.

---

# 7. Closing Principle

> Technical debt in CORE is not a flaw.
> It is a **signal** — an invitation to strengthen clarity, correctness, and constitutional alignment.
