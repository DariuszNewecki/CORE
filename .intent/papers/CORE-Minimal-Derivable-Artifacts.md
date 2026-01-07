<!-- path: papers/CORE-Minimal-Derivable-Artifacts.md -->

# CORE: Minimal Derivable Artifacts

**Status:** Draft (Greenfield)

**Depends on:**

* `papers/CORE-Constitutional-Foundations.md`
* `papers/CORE-Rule-Evaluation-Semantics.md`
* `papers/CORE-Phases-as-Governance-Boundaries.md`
* `papers/CORE-Authority-Without-Registries.md`
* `papers/CORE-Deliberate-Non-Goals.md`
* `papers/CORE-Common-Governance-Failure-Modes.md`
* `papers/CORE-As-a-Legal-System.md`

---

## Abstract

This paper defines the minimal set of artifacts that may be *derived* from the CORE Constitution without becoming sources of authority themselves. The intent is to enable implementation while preserving constitutional primacy. Any artifact not listed here is either optional, experimental, or constitutionally irrelevant.

---

## 1. Alignment Statement

This paper does not define implementations.
It defines **permission**.

Artifacts described here may exist.
Artifacts not described here may exist, but must not acquire authority.

---

## 2. Principle of Derivation

An artifact is *derivable* if and only if:

1. It can be produced entirely from constitutional law.
2. It introduces no new authority.
3. It cannot contradict declared rules.
4. Its absence does not invalidate governance.

Derivation is one-way: Constitution → Artifact.

---

## 3. Permitted Derivable Artifacts

### 3.1 Rule Evaluation Engine

**Purpose:**
Evaluate rules at their declared phase.

**Constraints:**

* must not infer authority,
* must not merge rules,
* must not reinterpret statements.

Multiple engines may exist.
None are authoritative.

---

### 3.2 Phase Gate

**Purpose:**
Enforce phase boundaries.

**Constraints:**

* must reject cross-phase evaluation,
* must not reorder phases,
* must not skip phases.

---

### 3.3 Evidence Recorder

**Purpose:**
Record evaluation outcomes and minimal evidence.

**Constraints:**

* append-only,
* non-authoritative,
* reproducible.

---

### 3.4 Proposal Mechanism

**Purpose:**
Allow changes to be suggested.

**Constraints:**

* proposals are not law,
* acceptance requires constitutional process,
* tooling convenience has no legal effect.

---

### 3.5 Visualization Tools

**Purpose:**
Render law and outcomes intelligibly.

**Constraints:**

* must not summarize away legal meaning,
* must not imply precedence,
* must not suggest permission.

---

## 4. Explicitly Non-Derivable Artifacts

The following must not be derived as authoritative artifacts:

* rule registries,
* authority catalogs,
* precedence tables,
* compatibility layers,
* auto-migration tools that change law.

These create shadow law.

---

## 5. Multiplicity Is Allowed

CORE allows multiple implementations of the same artifact type.

Divergence between implementations is acceptable.
Divergence between implementations and law is not.

---

## 6. Failure Handling

If a derived artifact fails:

* law remains valid,
* governance pauses or degrades safely,
* authority does not shift.

Artifacts may fail.
Law must not.

---

## 7. Relationship to Evolution

Evolution in CORE occurs by:

1. amending law,
2. deriving new artifacts,
3. discarding obsolete artifacts.

Artifacts do not evolve law.

---

## 8. Conclusion

By strictly limiting what may be derived from the Constitution, CORE enables implementation without surrendering authority. This separation ensures that CORE remains a legal system first, and a technical system second.
