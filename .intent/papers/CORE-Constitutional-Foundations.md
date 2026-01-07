<!-- path: papers/CORE-Constitutional-Foundations.md -->

# CORE: Constitutional Foundations for Governing Acting Systems

**Status:** Draft (Greenfield)

**Audience:** Systems architects, governance engineers, AI safety researchers

---

## Abstract

This paper introduces CORE, a constitutional governance framework for systems that can act. CORE is built on a deliberately minimal and closed set of primitives—Document, Rule, Phase, and Authority—designed to eliminate implicit assumptions, prevent governance duct tape, and enable predictable enforcement across the full lifecycle of system actions. The framework rejects taxonomies, registries, and static indexes in favor of explicit law evaluated deterministically at well-defined phases. This paper presents the constitutional model, its enforcement semantics, and the rationale for intentional boredom as a design goal.

---

## 1. Motivation

Modern software systems increasingly act autonomously, mutate their own artifacts, and operate across heterogeneous execution environments. Governance mechanisms for such systems often evolve incrementally, resulting in implicit authority, scattered enforcement logic, and fragile rule interactions.

CORE emerged from repeated attempts to govern such systems and the accumulated failure modes observed therein. This paper does not propose another policy framework; it proposes a constitutional reset.

---

## 2. Design Principles

CORE is founded on five non-negotiable principles:

1. **Explicitness over inference** – Nothing is assumed.
2. **Evaluation over interpretation** – Rules are checked, not debated.
3. **Closed primitives** – The foundational model is finite and fixed.
4. **Phase separation** – When a rule applies matters as much as what it states.
5. **Intentional boredom** – Predictability is a success metric.

---

## 3. Constitutional Primitives

CORE defines exactly four primitives.

### 3.1 Document

A Document is a persisted artifact that CORE may load. It declares its kind, is validated before use, and carries no implicit semantics.

### 3.2 Rule

A Rule is an atomic normative statement expressing a single requirement. Rules are evaluated as true or false and do not aggregate other rules.

### 3.3 Phase

A Phase defines when a Rule is evaluated. CORE defines five phases: Parse, Load, Audit, Runtime, and Execution. Each rule belongs to exactly one phase.

### 3.4 Authority

Authority defines who has the final right to decide. CORE recognizes Meta, Constitution, Policy, and Code as the only valid authorities.

---

## 4. Enforcement Model

Rules declare an enforcement strength: Blocking, Reporting, or Advisory. Enforcement strength is orthogonal to both Phase and Authority. A rule that cannot be deterministically evaluated at its declared phase is invalid.

---

## 5. Equality of Expression

Schema constraints, constitutional protections, policy requirements, and runtime guards are treated uniformly as Rules. They differ only by phase, authority, and enforcement strength. This eliminates special cases and collapses governance into a single evaluative model.

---

## 6. What CORE Explicitly Does Not Define

CORE intentionally omits:

* taxonomies
* registries
* indexes
* editors
* storage formats
* enforcement engines

These are implementation concerns and must not be confused with law.

---

## 7. Implications for Autonomous and AI Systems

By removing implicit law and enforcing deterministic evaluation, CORE provides a stable substrate for AI-assisted development and autonomous operation. Systems governed under CORE can reason about their own constraints without self-modifying them.

---

## 8. Conclusion

CORE demonstrates that governance systems benefit from reduction rather than expansion. By limiting itself to four primitives and rejecting cleverness, CORE achieves structural clarity, enforcement predictability, and long-term evolvability.

---

## References

This paper intentionally omits external references in its initial draft to emphasize first-principles reasoning. Comparative analysis may be added in later revisions.
