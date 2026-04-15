<!-- path: .intent/CORE-CHARTER.md -->

# CORE Charter

**Status:** Founding Charter

**Scope:** Entire CORE system

**Location of Authority:** `.intent/`

---

## 1. Purpose

This Charter declares the founding intent of CORE and its governance structure.

It exists to orient contributors, tools, and future maintainers by making explicit:

* what CORE is,
* what CORE is not,
* where authority resides,
* and how governance is structured.

This Charter is not a specification.
It is a declaration of standing.

---

## 2. Constitutional Architecture

CORE implements a two-tier governance model:

**Tier 1: Constitutional Foundation**
* `.intent/constitution/` - Foundational constitutional documents
* `.intent/papers/` - Constitutional philosophy and principles

These documents establish **why** and **what** CORE must be.
They are vectorized for semantic understanding but not directly enforced.

**Tier 2: Operational Law**
* `.intent/META/` - Schema contracts defining authority/phase/enforcement
* `.intent/rules/` - Enforced constitutional rules (indexed and executed)
* `.intent/enforcement/mappings/` - Rule-to-engine bindings
* `.intent/phases/` - Workflow phase definitions

These documents define **how** CORE enforces its constitution.
They are the operational law that Mind reads, Body enforces, and Will respects.

---

## 3. Authority Statement

Constitutional authority operates at two levels:

**Foundation (Philosophy):**
* `.intent/constitution/` and `.intent/papers/` establish principles
* These documents inform all other governance
* Changes require constitutional replacement, not amendment

**Operation (Enforcement):**
* `.intent/META/` defines the contract for all intent artifacts
* `.intent/rules/` contains executable constitutional law
* `.intent/enforcement/` binds rules to enforcement engines
* Changes follow governance workflows with audit trails

The operational tier derives legitimacy from the foundational tier.
No operational rule may contradict constitutional principles.

---

## 4. Reading Order

To understand CORE's governance:

1. `.intent/constitution/CORE-CONSTITUTION-v0.md` - Foundation document
2. `.intent/papers/` - Constitutional philosophy:
   * `CORE-Constitutional-Foundations.md`
   * `CORE-Mind-Body-Will-Separation.md`
   * `CORE-Infrastructure-Definition.md` **(← ADDED: Infrastructure boundaries)**
   * `CORE-Common-Governance-Failure-Modes.md`
   * Additional constitutional papers
3. `.intent/META/` - Schema contracts
4. `.intent/rules/` - Operational rules
5. This Charter

Any contradiction must be resolved in favor of: Constitution → Papers → META → Rules → Charter.

---

## 5. Governance Model

**Mind Layer (.intent/):**
* Human-authored only
* Immutable at runtime
* Single source of truth for governance

**Body Layer (src/body/):**
* Reads Mind via IntentRepository
* Enforces rules through execution
* Never modifies Mind

**Will Layer (src/will/):**
* Reads Mind to understand constraints
* Makes decisions within constitutional bounds
* Delegates execution to Body

**Infrastructure (src/shared/infrastructure/):** **(← ADDED: Infrastructure category)**
* Provides mechanical coordination without strategic decisions
* Bounded by explicit authority limits defined in constitutional papers
* Subject to infrastructure-specific governance rules
* See: `.intent/papers/CORE-Infrastructure-Definition.md`

---

## 6. Intentional Incompleteness

CORE is intentionally incomplete.

Missing elements are not defects.
They are evidence that law precedes machinery.

No schema, engine, or tool may be introduced to compensate for incomplete law.
Law must be written first, then enforcement follows.

---

## 7. Change Discipline

**Constitutional Changes (Tier 1):**
1. Replace entire constitutional documents
2. Update operational rules to align
3. Verify enforcement reflects new principles

**Operational Changes (Tier 2):**
1. Propose rule changes through governance workflows
2. Validate against constitutional principles
3. Update enforcement mappings
4. Audit compliance

Skipping steps constitutes a governance violation.

---

## 8. Database as Single Source of Truth

All runtime state resides in PostgreSQL.
`.intent/` contains only human-authored governance.

The database is the operational memory.
`.intent/` is the constitutional memory.

These are separate by design and must remain so.

---

## 9. Duration

This Charter remains in force until explicitly retired or superseded by constitutional amendment.

Silence does not revoke it.

---

## 10. Closing Statement

CORE is not being refactored.
CORE is being founded on constitutional principles.

This Charter exists to make that structure unambiguous.
