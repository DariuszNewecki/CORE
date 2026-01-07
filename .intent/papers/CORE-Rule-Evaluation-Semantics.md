<!-- path: papers/CORE-Rule-Evaluation-Semantics.md -->

# CORE: Rule Evaluation Semantics

**Status:** Draft (Greenfield)

**Depends on:** `papers/CORE-Constitutional-Foundations.md`

---

## Abstract

This paper defines how CORE evaluates rules. CORE treats every governance constraint as a Rule evaluated deterministically at a declared Phase under a declared Authority. The evaluation model rejects interpretation, partial compliance, and implicit law. This paper defines what it means for a rule to be evaluable, how violations are represented, how enforcement strength is applied, and how failures in evaluation are handled without undermining constitutional clarity.

---

## 1. Problem Statement

Rules that cannot be evaluated deterministically become social contracts rather than enforceable law. In acting systems—especially those capable of autonomous change—social contracts are insufficient.

CORE therefore defines rules as *evaluations*, not *interpretations*.

---

## 2. Definitions

### 2.1 Rule

A Rule is an atomic normative statement.

A rule is **valid** only if it is:

* **atomic** (one requirement),
* **decidable** (true/false),
* **phase-bound** (exactly one phase),
* **authority-bound** (exactly one authority).

### 2.2 Evaluation

An **evaluation** is the act of determining whether a Rule holds.

Evaluation produces one of three outcomes:

* **Holds** – the system satisfies the rule.
* **Violates** – the system violates the rule.
* **Indeterminate** – the evaluator could not decide.

Indeterminate is not a “soft” outcome; it is a governance defect.

---

## 3. Determinism Contract

A rule is evaluable only if, at its declared phase, the evaluator can decide consistently.

### 3.1 Determinism Requirements

For a rule to be deterministic:

* Inputs MUST be fully defined at evaluation time.
* Evaluation MUST be repeatable given identical inputs.
* Output MUST not depend on human judgment.

If a rule requires human judgment, it is not a rule; it is guidance.

---

## 4. Enforcement Strength

CORE defines enforcement strength as an output handling policy.

### 4.1 Blocking

* A violation MUST prevent continuation of the governed action.
* Blocking rules MUST have an enforcement surface capable of prevention.

### 4.2 Reporting

* A violation MUST be recorded.
* Recording MUST be reliable and append-safe.

### 4.3 Advisory

* A violation MAY be communicated.
* Advisory rules MUST NOT be treated as governance coverage.

Enforcement strength does not change rule truth; it changes system response.

---

## 5. Evaluation Failures

Evaluation failures are not rule violations. They are failures of governance machinery.

CORE distinguishes:

* **Rule violation** – system failed the law.
* **Evaluation failure** – CORE failed to evaluate the law.

### 5.1 Indeterminate Outcome Handling

Indeterminate outcomes MUST be handled explicitly:

* If the rule is **Blocking**, Indeterminate MUST be treated as Blocking.
* If the rule is **Reporting**, Indeterminate MUST be recorded as Indeterminate.
* If the rule is **Advisory**, Indeterminate MAY be communicated.

This prevents “unknown” from becoming a bypass.

---

## 6. Partial Compliance

Partial compliance is forbidden unless explicitly modeled.

If a requirement has parts, then:

* it is multiple rules, or
* it is not a rule.

“Partially enforced” is a governance statement, not a rule state.

The proper representation is:

* separate rules per enforceable condition, and
* separate advisory notes for future intent.

---

## 7. Phase-Specific Evaluation Constraints

### 7.1 Parse Phase

* Input: a single document.
* Allowed evaluation: structure, required fields, types.
* Forbidden: cross-document assumptions.

### 7.2 Load Phase

* Input: a set of documents.
* Allowed evaluation: cross-document consistency, duplicate identifiers, referential integrity.
* Forbidden: code execution, environment dependence.

### 7.3 Audit Phase

* Input: system artifacts and state.
* Allowed evaluation: static inspection, computed measures, trace verification.
* Forbidden: preventing actions (audit observes; runtime prevents).

### 7.4 Runtime Phase

* Input: a proposed action and its immediate context.
* Allowed evaluation: allow/deny based on declared constraints.
* Forbidden: long-running analysis that changes decision timing.

### 7.5 Execution Phase

* Input: effectful operation with controlled execution surface.
* Allowed evaluation: sandboxing, risk gating, transactional control.
* Forbidden: retroactive reinterpretation of law.

---

## 8. Representation of Findings

All evaluation outputs should be representable as a single normalized structure:

* rule identifier
* phase
* authority
* outcome (holds/violates/indeterminate)
* enforcement strength
* evidence (minimal, reproducible)

Evidence is for verification, not persuasion.

---

## 9. Non-Goals

This paper does not define:

* rule storage format
* engine selection
* policy file layouts
* indexing strategies

Those are implementation concerns.

---

## 10. Conclusion

CORE rule evaluation is intentionally strict. The moment a rule becomes interpretive, it stops being law. CORE therefore requires determinism, forbids partial compliance unless explicitly modeled, and treats evaluation failures as defects in governance machinery rather than defects in the governed system.
