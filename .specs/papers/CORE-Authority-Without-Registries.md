---
kind: paper
id: CORE-Authority-Without-Registries
title: 'CORE: Authority Without Registries'
status: canonical
doctrine_tier: constitution
---

<!-- path: papers/CORE-Authority-Without-Registries.md -->

# CORE: Authority Without Registries

**Status:** Canonical

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

---

## 12. Elevation Discipline for High-Authority Rules

This section closes the governance gap surfaced by issue #625: Constitution Article I §4
forbids rules from deriving authority by implication or context, and Article V forbids
implicit authority. Prior doctrine established that authority is declared, not inferred,
but did not constrain who may declare a rule at `authority: constitution` or what
evidence makes such a declaration valid.

### 12.1 Any author may declare any authority level

Authority-level declarations are not gated by a registry, a role, or an approval workflow.
Any author writing a rule under `.intent/rules/` may set `authority: constitution`. The
declaration is valid if and only if the rule is grounded in a constitutional paper.

### 12.2 Grounding is the elevation mechanism

A rule at `authority: constitution` MUST have a companion paper at `doctrine_tier:
constitution` in `.specs/papers/` whose doctrine justifies the rule's authority claim.
The paper is the elevation record — it explains why the rule operates at constitutional
authority rather than policy or code.

If no grounding paper exists, the rule's authority claim is unverified. An unverified
high-authority claim does not block evaluation (authority is resolved from declarations,
not grounding checks). It is governance debt: an obligation to author the companion paper
before the rule is considered constitutionally clean.

**Aspirational status:** Enforcing rule not yet authored; this is normative design intent.

### 12.3 The discipline in practice

1. **Write the paper first.** If a new rule belongs at `authority: constitution`, author
   the paper that establishes the constitutional principle. That paper becomes the ground
   truth.
2. **Declare the rule second.** Set `authority: constitution` and cite the paper's `id`
   in the rule's `grounding` or `papers` field.
3. **Never invert the order.** A rule at `authority: constitution` with no grounding paper
   is an implicit authority claim — exactly the pattern Article I §4 forbids.

### 12.4 No registry is needed

Elevation requires no central approval record, no registry of elevated rules, and no
workflow checkpoint. The paper-rule pair is self-contained evidence. Grounding checks
(CCC and ADR-grounding audits) are the detection mechanism for missing papers. This keeps
authority-level elevation consistent with the broader principle of this paper: authority
lives with its law, not in infrastructure.
