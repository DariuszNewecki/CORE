<!-- path: .intent/papers/CORE-Rule-Authoring-Discipline.md -->

# CORE Rule Authoring Discipline

**Status:** Constitutional Companion Paper
**Authority:** Constitution (derivative, non-amending)
**Scope:** Human authors of CORE Rules

---

## Purpose

This paper defines **how Rules may be authored** under the CORE Constitution and the *CORE Rule Canonical Form*.

Its purpose is to:

* prevent semantic and structural drift at the moment of creation,
* eliminate "helpful" but invalid shortcuts,
* ensure that every Rule is atomic, explicit, and constitutionally valid,
* make authoring Rules a deliberately constrained activity.

This document governs **human behavior**, not machines.

---

## Constitutional Context

This discipline derives from:

* CORE Constitution — Article II (Rule Definition)
* CORE Constitution — Article IV (Evaluation Model)
* CORE Constitution — Article V (Non-Existence of Implicit Law)
* CORE Rule Canonical Form

A Rule authored in violation of this discipline is **invalid**, regardless of intent or usefulness.

---

## The Author’s Burden

The burden of correctness lies entirely with the Rule author.

Tooling MUST NOT:

* infer missing fields,
* split rules automatically,
* weaken statements,
* reinterpret intent,
* guess phases or authorities.

If a Rule is difficult to write, that difficulty is intentional.

---

## Rule Atomicity

### One Rule — One Obligation

A Rule MUST express exactly **one** obligation.

If a sentence contains:

* "and"
* "or"
* "unless"
* "except"
* conditional clauses

then it is almost certainly **not atomic** and MUST be split into multiple Rules.

---

### Forbidden Patterns

The following patterns are constitutionally invalid:

* Compound requirements
* Conditional enforcement
* Embedded exception logic
* Procedural descriptions
* Multi-phase intent

If a requirement cannot be stated without these constructs, it is **not a Rule**.

---

## When NOT to Write a Rule

A Rule MUST NOT be written if:

* the requirement is aspirational
* the requirement cannot be deterministically evaluated
* the requirement depends on context not available at its Phase
* the requirement describes *how* rather than *what*
* the requirement exists only to support tooling

Such concerns belong in:

* documentation
* implementation
* derived artifacts
* future constitutional amendments

---

## Phase Selection Discipline

The Phase of a Rule MUST be chosen **first**, before wording the statement.

If the author cannot answer:

> "At what exact moment must this hold?"

then the Rule MUST NOT be written.

Rules MUST NOT:

* rely on earlier or later phases
* assume retroactive enforcement
* observe outcomes from other phases

---

## Authority Selection Discipline

The Authority of a Rule MUST be justified explicitly by its scope:

* **Meta** — structure and validity only
* **Constitution** — system invariants and boundaries
* **Policy** — domain law
* **Code** — implementation constraints

If there is ambiguity between two authorities, the Rule MUST be escalated upward.

Rules MUST NOT rely on delegation, implication, or inheritance of authority.

---

## Enforcement Selection Discipline

Enforcement MUST reflect **constitutional consequence**, not preference.

* **Blocking** is reserved for violations that MUST halt progress
* **Reporting** is reserved for violations that MUST be observed
* **Advisory** is reserved for guidance only

If the author is unsure which enforcement applies, the Rule MUST NOT be Blocking.

---

## Language Discipline

Rules MUST be written in:

* declarative language
* present tense
* unconditional form

Rules MUST NOT:

* include rationale
* reference enforcement mechanisms
* describe remediation
* instruct tooling

The Rule is the law, not its explanation.

---

## Splitting Rules (Required)

If a requirement appears to need:

* multiple Phases
* multiple Authorities
* multiple Enforcement strengths

then it MUST be split into **multiple independent Rules**.

Cross-rule relationships are **not expressed in law**.

---

## Zero Backward Compatibility

Legacy rules, formats, and structures provide **no precedent**.

Authors MUST NOT:

* preserve legacy identifiers for convenience
* encode legacy semantics
* grandfather historical behavior

Continuity is not a constitutional value.

---

## Review Standard

A Rule is acceptable **only if** a reviewer can answer all of the following without inference:

1. What exactly must hold?
2. When must it hold?
3. Who has authority to decide?
4. What happens if it fails?

If any answer requires interpretation, the Rule is invalid.

---

## Failure Classification

Invalid Rules represent:

* governance failure, not tooling failure
* authoring error, not evaluation error

Invalid Rules MUST be rejected, not repaired.

---

## Closing Statement

Rules are law.

Law is expensive.

If authoring a Rule feels slow, restrictive, or frustrating, the discipline is working.

**End of Discipline.**
