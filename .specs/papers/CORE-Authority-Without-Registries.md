<!-- path: papers/CORE-Authority-Without-Registries.md -->

# CORE: Authority Without Registries

**Status:** Draft (Greenfield)

**Depends on:**

* `papers/CORE-Constitutional-Foundations.md`
* `papers/CORE-Rule-Evaluation-Semantics.md`
* `papers/CORE-Phases-as-Governance-Boundaries.md`

---

## Abstract

This paper defines how CORE handles authority without static registries, persisted indexes, or hardcoded catalogs. Authority in CORE is a constitutional property of Rules, evaluated in memory at runtime and derived solely from declared law. By rejecting registries, CORE avoids authority drift, duplication, and ossification, while preserving determinism and auditability.

---

## 1. Motivation

Registries promise clarity but introduce rigidity. In governance systems, static registries often become de facto sources of truth, creating hidden coupling between law and machinery. This coupling leads to drift: the registry becomes authoritative, while the law decays.

CORE explicitly rejects this pattern.

Authority must be *declared*, not *registered*.

---

## 2. Definition of Authority

**Authority** defines who has the final right to decide for a Rule.

Authority is:

* explicit,
* singular per Rule,
* non-inferable,
* non-derivable.

If authority is not declared, it does not exist.

---

## 3. Why Registries Are Forbidden

Registries centralize power outside the law.

They introduce:

* implicit precedence,
* accidental overrides,
* silent shadow authorities.

In CORE, these effects are constitutionally unacceptable.

Authority must live with the Rule that exercises it.

---

## 4. In-Memory Authority Resolution

CORE resolves authority dynamically at load time.

### 4.1 Resolution Process

At system start:

1. Documents are parsed.
2. Rules are extracted.
3. Each rule’s declared Authority is read.
4. Conflicts are detected by evaluation, not lookup.

No persisted index is created.
No authority table is stored on disk.

---

## 5. Conflict Detection Without Registries

Conflicts are evaluated, not prevented by construction.

Examples of conflicts:

* two rules claiming incompatible authority over the same action,
* a policy rule attempting to override a constitutional rule,
* a code-level constraint asserting authority beyond implementation scope.

These conflicts are detected during the **Load** or **Audit** Phase as violations of declared law.

---

## 6. Authority Precedence

Authority precedence is defined constitutionally, not operationally.

From highest to lowest:

1. Meta
2. Constitution
3. Policy
4. Code

This ordering is law. It is not configurable.

Lower authority rules may not weaken higher authority rules.

---

## 7. Authority and Phase Interaction

Authority does not determine *when* a rule applies.
Phase does not determine *who* decides.

Both must be explicitly declared.

A high-authority rule evaluated in the wrong Phase is invalid.
A correctly phased rule with insufficient authority is invalid.

---

## 8. Auditability Without Persistence

CORE remains auditable without registries by ensuring:

* rules are immutable within a run,
* evaluation outputs capture authority and phase,
* evidence is recorded alongside outcomes.

Audit artifacts reference rule identifiers and declarations, not registry entries.

---

## 9. Failure Modes Avoided

By rejecting registries, CORE avoids:

* stale authority caches,
* partial migrations,
* split-brain governance between disk and memory,
* “fix the registry” operational rituals.

---

## 10. Non-Goals

This paper does not define:

* editor tooling,
* serialization formats,
* persistence strategies for proposals.

Those may exist but must not become authority.

---

## 11. Conclusion

Authority in CORE is a property of law, not infrastructure.

By resolving authority in memory from declared rules and forbidding registries, CORE preserves constitutional primacy, prevents drift, and keeps governance boring, explicit, and correct.
