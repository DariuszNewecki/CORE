<!-- path: .intent/REBIRTH/papers/CORE-Evidence-as-Input.md -->

# CORE — Evidence as Input

**Status:** Constitutional Semantics Paper

**Scope:** Rule evaluation across all phases

**Authority:** Constitution-level (derivative, non-primitive)

---

## 1. Purpose

This paper defines how evidence is treated within CORE.

Its purpose is to preserve deterministic rule evaluation while preventing evidence from becoming an implicit source of authority, interpretation, or law.

Evidence is not a constitutional primitive.
Evidence is an input to evaluation.

---

## 2. Non-Primitive Status of Evidence

CORE deliberately does **not** recognize Evidence as a constitutional primitive.

Evidence:

* does not define obligations,
* does not carry authority,
* does not justify rules,
* does not modify law.

Evidence exists only to allow rules to be evaluated.

---

## 3. Evidence as Evaluation Input

For any rule evaluation, evidence is the minimal set of inputs required to determine whether the rule holds or is violated.

Evidence:

* is consumed by evaluation,
* is not retained as law,
* does not persist authority.

Evaluation outcomes depend on evidence, but authority does not.

---

## 4. Phase-Bound Evidence Constraints

Evidence is constrained by Phase.

Evidence acceptable in one Phase is not automatically acceptable in another.

Indicative constraints:

* **Parse Phase**: Document structure and declared metadata only.
* **Load Phase**: Sets of documents and their declared relationships.
* **Audit Phase**: Observed system state and derived artifacts.
* **Runtime Phase**: Immediate pre-action state.
* **Execution Phase**: Effect-limited operational context.

No Phase may rely on evidence that presupposes a later Phase.

---

## 5. Reproducibility Requirement

All evidence used in rule evaluation **MUST** be reproducible within the constraints of the Phase.

Non-reproducible evidence produces an **indeterminate** evaluation outcome.

Reproducibility is a property of governance, not tooling.

---

## 6. Evidence and Indeterminate Outcomes

Indeterminate outcomes indicate failure of evaluation, not permission.

When evidence is:

* missing,
* invalid,
* non-reproducible,

rule evaluation must be marked **indeterminate**.

For blocking rules, indeterminate outcomes block progression.

---

## 7. Prohibited Uses of Evidence

The following uses of evidence are explicitly forbidden:

* using evidence to infer new rules,
* using evidence to reinterpret rule statements,
* using evidence to derive authority,
* using evidence to resolve rule conflicts.

Evidence informs evaluation only.

---

## 8. Relationship to Rule Conflict Semantics

Evidence does not resolve conflicts between rules.

Conflicting outcomes caused by incompatible law are governed by:

`CORE-Rule-Conflict-Semantics`.

---

## 9. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in accordance with the CORE amendment mechanism.

---

## 10. Closing Statement

Evidence is necessary for evaluation.

Evidence is never law.
