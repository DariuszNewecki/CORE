<!-- path: .intent/constitution/CORE-CONSTITUTION.md -->

# CORE Constitution

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

CORE recognizes **exactly five constitutional primitives**.

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

1. **Interpret**
   Conversion of natural language intent into canonical task structure.

2. **Parse**
   Validation of document structure and shape.

3. **Load**
   Validation of cross-document consistency.

4. **Audit**
   Inspection of system state and artifacts.

5. **Runtime**
   Guarding of actions before they occur.

6. **Execution**
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

### 5. Register

A **Register** defines *the form a vocabulary item takes for its audience*.

Every governance vocabulary item belongs to **exactly one Register**.

CORE recognizes only the following Registers:

1. **Conceptual**
   Title Case or PascalCase. Used in prose for human readers.

2. **Operational**
   `snake_case` lowercase. Used in enum-typed fields for machine routing.

3. **Diagnostic**
   `UPPER_CASE`. Used for severity and verdict signals.

A vocabulary item MAY NOT have two forms within the same Register.

---

## Article II — Rule Definition

A Rule is constitutionally valid **only if its statement, enforcement
strength, phase, and authority are all explicit**.

A valid Rule therefore has:

* a **statement** (the Rule's content)
* an **enforcement strength** (Article III)
* a **phase** (Article I §3)
* an **authority** (Article I §4)

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
* recorded.

Compatibility is not a constitutional goal.
Stability is achieved through clarity, not preservation.

CORE recognizes two kinds of constitutional change:

1. **Additive amendment** — introduction of a new primitive, a new
   subsection, or a new clause that does not contradict existing law.
   Permitted in place. MUST be recorded in the Amendments log.

2. **Semantic replacement** — change to what an existing primitive,
   clause, or article *means*. Permitted only by explicit replacement
   of the affected text. MUST be recorded in the Amendments log.

Replacement supersedes prior versions of this document. It does NOT
invalidate the dependent authority chains derived from prior versions.
Rules declared at `authority: constitution` retain their authority
across constitutional revisions unless a specific revision explicitly
revokes them.

Every constitutional change — additive or replacing — MUST appear in
the Amendments log below. A change made without a log entry is not
a constitutional change; it is a violation.


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

---

## Amendments

This log records all changes to the Constitution since its founding.
Each entry: date, change kind (additive / semantic-replacement),
summary, and the ADR or paper that triggered it.

| Date | Kind | Summary | Trigger |
|---|---|---|---|
| 2026-05-04 | additive | Article I §3 — added Interpret as the first Phase, bringing Article I §3 into alignment with `.intent/phases/interpret.yaml`, `CORE-Constitutional-Foundations.md`, and `CORE-Phases-as-Governance-Boundaries.md`, all of which already declared six phases. | Investigation surfaced cardinality drift between the Constitution and the runtime; correction recorded in this session. |
| 2026-05-04 | additive | Article I §5 — added the Register primitive, declaring three vocabulary registers (Conceptual, Operational, Diagnostic). | `.specs/papers/CORE-Vocabulary-Registers.md`. |
| 2026-05-04 | semantic-replacement | Article VII rewritten — distinguishes additive amendment from semantic replacement; clarifies that replacement supersedes prior versions of the document but does NOT invalidate dependent authority chains; requires every change to appear in this Amendments log. | Recognition that the prior Article VII forbade in-place modification absolutely, while ordinary governance evolution requires it. The same session also dropped filename versioning from the document path. |
| 2026-05-04 | additive | Filename de-versioned — file moved from `CORE-CONSTITUTION-v0.md` to `CORE-CONSTITUTION.md`. Filename-level versioning removed; version history is recorded here. | Pragmatic alignment: filesystem-level versioning duplicated what git already provides at byte-level and what this Amendments log provides at semantic-level. The version suffix served no governance function. |
| 2026-05-23 | semantic-replacement | Article I — primitive count corrected from "exactly four" to "exactly five" to match §5 Register added 2026-05-04. Article II reworded to enumerate the four required Rule fields (statement, enforcement strength, phase, authority) directly, removing the misleading "all four primitives" phrasing that conflated Article I's primitive count with Article II's field count. | Surfaced 2026-05-23 during issue triage; the contradiction had been latent since 2026-05-04 when Register was added to Article I without propagation to Article II. |
