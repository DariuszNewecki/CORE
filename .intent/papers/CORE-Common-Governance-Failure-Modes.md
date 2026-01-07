<!-- path: papers/CORE-Common-Governance-Failure-Modes.md -->

# CORE: Common Governance Failure Modes

**Status:** Draft (Greenfield)

**Depends on:**

* `papers/CORE-Constitutional-Foundations.md`
* `papers/CORE-Rule-Evaluation-Semantics.md`
* `papers/CORE-Phases-as-Governance-Boundaries.md`
* `papers/CORE-Authority-Without-Registries.md`
* `papers/CORE-Deliberate-Non-Goals.md`

---

## Abstract

This paper enumerates governance failure modes observed in complex, evolving systems and formalizes why CORE’s constitutional model makes them structurally impossible. The purpose is not backward compatibility, migration guidance, or remediation of legacy mechanisms. The purpose is prevention.

---

## 1. Alignment Statement

This paper explicitly ignores:

* existing auditors,
* current checks,
* legacy enforcement engines,
* backward compatibility.

Only constitutional correctness matters.

---

## 2. Failure Mode: Implicit Authority

**Description:**
Decisions are made because a component "has always done it" or because authority is inferred from location, naming, or convention.

**Observed Effects:**

* silent overrides,
* unclear escalation paths,
* governance disputes resolved socially rather than legally.

**CORE Prevention:**
Authority must be declared per Rule. Undeclared authority does not exist.

---

## 3. Failure Mode: Temporal Leakage

**Description:**
Rules intended for observation (audit) influence decisions (runtime), or execution-time constraints rewrite earlier judgments.

**Observed Effects:**

* retroactive blocking,
* inconsistent enforcement,
* brittle pipelines.

**CORE Prevention:**
Phases are closed boundaries. Rules evaluated outside their Phase are invalid.

---

## 4. Failure Mode: Partial Enforcement

**Description:**
Rules are "partially enforced" due to tooling limitations or phased rollout.

**Observed Effects:**

* false sense of compliance,
* ambiguous audit results,
* gradual erosion of law.

**CORE Prevention:**
Partial compliance is forbidden unless explicitly modeled as multiple Rules.

---

## 5. Failure Mode: Registry Drift

**Description:**
A registry or index becomes the de facto authority, diverging from declared law.

**Observed Effects:**

* stale governance,
* hidden precedence rules,
* operational rituals to "fix the registry".

**CORE Prevention:**
Registries are forbidden as authorities. Law lives with Rules.

---

## 6. Failure Mode: Interpretive Enforcement

**Description:**
Human judgment or heuristic reasoning determines rule outcomes.

**Observed Effects:**

* inconsistent decisions,
* audit disputes,
* politicized governance.

**CORE Prevention:**
Rules must be deterministically evaluable. Interpretation is not enforcement.

---

## 7. Failure Mode: Overloaded Rules

**Description:**
Single rules attempt to express multiple conditions, exceptions, or intentions.

**Observed Effects:**

* unclear violations,
* untestable enforcement,
* combinatorial complexity.

**CORE Prevention:**
Rules are atomic. Aggregation is forbidden.

---

## 8. Failure Mode: Tool-Driven Law

**Description:**
Law evolves to accommodate tooling limitations rather than vice versa.

**Observed Effects:**

* constitutional erosion,
* entrenched technical debt,
* governance paralysis.

**CORE Prevention:**
Tooling is non-authoritative. Law precedes machinery.

---

## 9. Failure Mode: Backward Compatibility as Constraint

**Description:**
Legacy behavior constrains future governance decisions.

**Observed Effects:**

* frozen mistakes,
* layered exceptions,
* duct-tape architectures.

**CORE Prevention:**
Compatibility is not a constitutional goal. Correctness is.

---

## 10. Failure Mode: Cleverness Accumulation

**Description:**
Incremental optimizations introduce hidden coupling and conceptual density.

**Observed Effects:**

* rising cognitive load,
* brittle abstractions,
* loss of trust.

**CORE Prevention:**
Intentional boredom is enforced. Cleverness is suspect.

---

## 11. Conclusion

Every failure mode described here arises from implicitness, ambiguity, or misplaced authority. CORE prevents these failures not through sophistication, but through reduction. By closing its constitutional model and rejecting backward compatibility pressure, CORE makes entire classes of governance failure structurally impossible.
