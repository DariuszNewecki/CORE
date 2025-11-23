# Technical Debt & Architectural Health (Governed Log)

This document provides the **canonical, governed overview** of technical debt inside CORE.
It consolidates all real architectural signals that emerged from:

* the `DuplicationCheck` audit,
* introspection reports,
* architectural validator findings,
* Phase 4 hardening work,
* and long-term governance expectations.

It replaces old notes with a single, authoritative document.

---

# 1. Purpose

Technical debt in CORE is not merely “messy code.” In a governed system, debt is:

* **misalignment with constitutional principles**,
* **friction between Mind, Body, and Will**,
* **ambiguity in intent or structure**,
* **drift between knowledge and source**,
* **duplication that erodes clarity**,
* **architecture violations**,
* **unruled exceptions**,
* **or inconsistent patterns**.

This log exists to ensure debt is:

* **transparent**,
* **classifiable**,
* **prioritized**,
* **tractable**,
* **and auditable**.

---

# 2. Sources of Technical Debt in CORE

CORE’s architecture produces *three* classes of debt:

## 2.1. **Code-Level Debt** (Body)

Issues in the runtime codebase, including:

* duplicate logic,
* unclear boundaries,
* mis-scoped helpers,
* complexity hotspots,
* missing tests.

## 2.2. **Knowledge Debt** (Mind)

When the internal knowledge model becomes stale:

* drift between symbols in the DB and real code,
* outdated capability metadata,
* missing domain boundaries,
* legacy tags,
* old patterns that are no longer accurate.

## 2.3. **Intent Debt** (Will → Mind alignment)

When capabilities or agents operate under outdated assumptions:

* prompts outdated vs system expectations,
* missing policy coverage,
* unclear example sets,
* ambiguity in context providers.

---

# 3. Classification of Debt (Derived from Real Findings)

Debt uncovered through audits falls into **three categories**.

## 3.1. Category 1 — False Positives (High Cohesion)

These are **non-problems**.

Examples:

* A class flagged as similar to its own methods.
* Thin service wrappers that mirror internal structure.

**Interpretation:** High cohesion, not duplication.

**Action:** Tune `DuplicationCheck` sensitivity.

---

## 3.2. Category 2 — Intentional Architectural Patterns

This duplication is *deliberate*.

Examples:

* CLI wrappers in `/cli/commands/` matching service-layer logic.
* Mirrored structure in Mind vs Body checks.

**Interpretation:** Intentional DDD replication.

**Action:** Document via:

* `audit_ignore_policy.yaml` → `symbol_ignores`
* In-code Justification comments

---

## 3.3. Category 3 — Legitimate Duplication (Actionable Debt)

This is real technical debt.

Examples:

* Duplicate AST extraction logic across `knowledge_helpers.py` and vectorizer services.
* YAML-loading utility duplicated in two different modules.

**Interpretation:** Violates `dry_by_design`.

**Action:**

* Consolidate into shared utilities.
* Update call sites.
* Remove outdated helpers.

---

# 4. Architecture Debt (Cross-Cutting)

Beyond duplication, architectural health checks revealed:

## 4.1. Capability Model Drift

* Some capabilities lack owners.
* Some symbols assigned incorrectly.
* Some domains missing rules.

**Action:** Regenerate capability docs, re-run indexing.

## 4.2. Import Boundary Violations

* `shared.*` depends on `features.*` (illegal direction).

**Action:** Move modules or break dependency chain.

## 4.3. Context Providers Out of Sync

* Missing examples/test patterns.
* Inconsistent context enrichment.

**Action:** Phase 4/5 consolidation.

## 4.4. Overlapping Logic in Self-Healing

Multiple services handle:

* complexity detection,
* refactoring suggestions,
* duplication checks,
* vectorization.

**Action:** Merge under a unified self-healing architecture.

---

# 5. Phase 4 Roadmap: Hardening & Debt Repayment

Mapped against constitutional principles.

| Priority | Task                                                    | Principle                | Status  |
| -------: | ------------------------------------------------------- | ------------------------ | ------- |
|    **1** | Consolidate duplicated helpers                          | `dry_by_design`          | Pending |
|    **2** | Tune `DuplicationCheck` (reduce false positives)        | `clarity_first`          | Pending |
|    **3** | Add justified `symbol_ignores` for intentional patterns | `separation_of_concerns` | Pending |
|    **4** | Remove global ignores once above resolved               | `safe_by_default`        | Pending |

---

# 6. Technical Debt Scanner (Planned Component)

The upcoming **develop scan** command integrates:

* complexity metrics,
* architecture violations,
* similarity detection,
* refactoring suggestions,
* estimated effort ratings.

Its output guides human developers and agents.

This will add:

* `ComplexityAnalyzer` (extended),
* `ArchitectureCheck`,
* `RefactoringSuggester`,
* optional `AutoRefactorer`.

These are governed extensions, not replacements.

---

# 7. Governance Principles for Debt

Technical debt must always be evaluated through CORE’s constitutional lens.

## 7.1. `clarity_first`

Prefer clarity over sophistication.
If fixing debt reduces cognitive load, it is **mandatory**.

## 7.2. `dry_by_design`

No duplicated logic across modules.
If duplication emerges, consolidate.

## 7.3. `evolvable_structure`

Debt resolution must improve long-term maintainability.

## 7.4. `safe_by_default`

Debt resolutions must:

* maintain audit compliance,
* avoid direct mutation without crates,
* use safe refactoring paths.

## 7.5. `separation_of_concerns`

Architectural boundaries should be clear and enforced.

---

# 8. Recommended Workflow for Addressing Debt

When a new debt signal appears:

1. **Reproduce audit findings**

```bash
poetry run core-admin check audit
```

2. **Classify** (Category 1, 2, or 3)
3. **Decide on remedy**
4. Apply safe fixes:

```bash
poetry run core-admin fix ids --write
poetry run core-admin fix headers --write
```

5. Sync knowledge:

```bash
poetry run core-admin manage database sync-knowledge
```

6. Run constitutional audit again:

```bash
poetry run core-admin check audit
```

---

# 9. Long-Term Expectations

CORE aims for:

* **zero net debt**,
* **continuous architectural clarity**,
* **automatic detection**,
* **governed remediation**,
* **and safe evolution**.

This log should be revisited **after every major enhancement**.

---

# 10. Closing Principle

> Technical debt in CORE is not a flaw.
> It is a **signal** — an opportunity to strengthen the system’s clarity, correctness, and constitutional alignment.
