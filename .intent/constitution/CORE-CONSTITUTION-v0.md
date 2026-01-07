<!-- path: .intent/constitution/CORE-CONSTITUTION-v0.md -->

# CORE Constitution — v0

**Status:** Foundational

**Scope:** Entire CORE system

---

## Preamble

CORE exists to govern systems that can act.

Governance is only meaningful when:

* authority is explicit,
* enforcement is predictable,
* and interpretation is minimized.

This Constitution defines the **irreducible primitives** of CORE.
Anything not defined here does not exist constitutionally.

This document is intentionally boring.

---

## Article I — Primitives

CORE recognizes **exactly four constitutional primitives**.

No other concept may be treated as fundamental.

### 1. Document

A **Document** is a persisted artifact that CORE may load.

A Document:

* exists at a stable path,
* declares its kind,
* is validated before use,
* has no implicit meaning.

Documents do not execute.
Documents do not infer.
Documents do not decide.

They are read or rejected.

---

### 2. Rule

A **Rule** is an atomic normative statement.

A Rule:

* expresses a single requirement,
* is evaluated as true or false,
* does not depend on interpretation,
* does not aggregate other rules.

A Rule MUST be expressible as:

> “This condition MUST / SHOULD / MAY hold.”

Rules do not explain themselves.
Rules do not justify themselves.
Rules do not modify other rules.

---

### 3. Phase

A **Phase** defines *when* a Rule is evaluated.

Every Rule belongs to **exactly one Phase**.

CORE defines only the following Phases:

1. **Parse**
   Validation of document structure and shape.

2. **Load**
   Validation of cross-document consistency.

3. **Audit**
   Inspection of system state and artifacts.

4. **Runtime**
   Guarding of actions before they occur.

5. **Execution**
   Control of effectful operations.

No Rule may span multiple Phases.

---

### 4. Authority

**Authority** defines *who has the final right to decide*.

Every Rule has **exactly one Authority**.

CORE recognizes only the following Authorities:

1. **Meta**
   Authority over structure and validity.

2. **Constitution**
   Authority over system invariants and boundaries.

3. **Policy**
   Authority over domain-specific law.

4. **Code**
   Authority over implementation details only.

A Rule MAY NOT derive authority from implication or context.

---

## Article II — Rule Definition

A Rule is constitutionally valid **only if all four primitives are explicit**.

A valid Rule therefore has:

* a **statement**
* an **enforcement strength**
* a **phase**
* an **authority**

Nothing else is required.
Nothing else is permitted at the constitutional level.

---

## Article III — Enforcement Strength

CORE recognizes exactly three enforcement strengths:

1. **Blocking**
   Violation MUST prevent continuation.

2. **Reporting**
   Violation MUST be recorded.

3. **Advisory**
   Violation MAY be communicated.

Enforcement strength does not imply Phase.
Phase does not imply enforcement strength.

---

## Article IV — Evaluation Model

Rules are **evaluated**, not interpreted.

* A Rule either holds or does not.
* Partial compliance is forbidden unless explicitly modeled.
* Heuristics may exist, but are not law.

If a Rule cannot be evaluated deterministically at its Phase, it is invalid.

Conflicts between rules of equal Authority and Phase are governed by
CORE-Rule-Conflict-Semantics.


---

## Article V — Non-Existence of Implicit Law

CORE explicitly forbids:

* implicit authority
* derived rules
* inferred phases
* contextual enforcement

If a requirement is not expressed as a Rule, it does not exist.

---

## Article VI — Equality of Expression

There is no constitutional distinction between:

* schema constraints
* constitutional protections
* policy requirements
* runtime guards

They differ **only** by:

* Phase
* Authority
* Enforcement strength

All are Rules.

---

## Article VII — Change Discipline

Changes to this Constitution are:

* rare,
* explicit,
* breaking by default.

Compatibility is not a constitutional goal.

Stability is achieved through clarity, not preservation.

This Constitution may be amended only by explicit replacement.
Replacement invalidates prior constitutional authority.
In-place modification is not permitted.


---

## Article VIII — Silence Is Intentional

This Constitution intentionally does **not** define:

* taxonomies
* categories
* indexes
* registries
* editors
* storage formats
* enforcement engines

Those are **implementation concerns**, not law.

---

## Closing Statement

If CORE becomes clever, this Constitution has been violated.

If CORE becomes boring, this Constitution is working.
