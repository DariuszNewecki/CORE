<!-- path: .intent/REBIRTH/papers/CORE-Rule-Conflict-Semantics.md -->

# CORE Rule Conflict Semantics

**Status:** Constitutional Semantics Paper

**Scope:** All rules declared under the CORE Constitution

**Authority:** Constitution-level (derivative, non-primitive)

---

## 1. Purpose

This paper defines how CORE handles conflicts between rules of equal authority.

Its purpose is to ensure that rule evaluation remains deterministic, non-interpretive, and free from implicit precedence or ordering effects.

This paper does not introduce new primitives.
It specifies interaction semantics between existing primitives.

---

## 2. Definition of a Rule Conflict

A **rule conflict** exists when all of the following conditions are true:

1. Two or more rules apply at the same **Phase**.
2. The rules have the same **Authority level**.
3. The rules produce incompatible outcomes when evaluated against the same evidence.

Incompatibility includes, but is not limited to:

* one rule requiring a condition that another explicitly forbids,
* mutually exclusive enforcement outcomes for the same action,
* logically irreconcilable requirements.

---

## 3. Conflict Is a Governance Error

Rule conflicts are not resolved by interpretation, precedence, or ordering.

A detected conflict constitutes a **governance error**.

CORE treats such errors as defects in the declared law, not as runtime contingencies.

---

## 4. Conflict Detection

Rule conflicts **MUST** be detected as early as possible.

Preferred detection phases:

* **Load Phase** — when conflicts can be determined from rule structure alone.
* **Audit Phase** — when conflicts depend on derived system properties.

Conflicts discovered in later phases indicate insufficient earlier validation but remain governance errors.

---

## 5. Conflict Handling

When a rule conflict is detected:

1. Evaluation for the affected scope **MUST NOT** proceed.
2. Runtime or Execution actions **MUST NOT** occur.
3. The system **MUST** surface the conflict explicitly.

No automatic resolution is permitted.

---

## 6. Prohibited Resolution Mechanisms

The following mechanisms are explicitly forbidden:

* implicit precedence rules,
* file or declaration ordering,
* "last rule wins" semantics,
* registry-based disambiguation,
* human interpretation during evaluation.

Any implementation employing these mechanisms violates the Constitution.

---

## 7. Relationship to Authority Hierarchy

Authority hierarchy resolves conflicts **only** between rules of different authority levels.

This paper applies exclusively to conflicts where authority levels are equal.

Higher-authority rules overriding lower-authority rules is governed by the Constitution and is not affected by this paper.

---

## 8. Relationship to Indeterminate Outcomes

A rule conflict is distinct from an indeterminate evaluation outcome.

* **Indeterminate** indicates insufficient or invalid evidence.
* **Conflict** indicates incompatible law.

Both block progression for blocking rules, but their causes are different and must be reported distinctly.

---

## 9. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in accordance with the CORE amendment mechanism.

---

## 10. Closing Statement

CORE does not attempt to resolve contradictory law.

Contradictions are not runtime problems.
They are governance failures that must be corrected at the source.
