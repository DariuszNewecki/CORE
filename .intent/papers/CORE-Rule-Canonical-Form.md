<!-- path: .intent/papers/CORE-Rule-Canonical-Form.md -->

# CORE Rule Canonical Form

**Status:** Constitutional Companion Paper
**Authority:** Constitution (derivative, non-amending)
**Scope:** All present and future CORE Rules

---

## Purpose

This paper defines the **only constitutionally valid canonical form** of a Rule in CORE.

Its purpose is to:

* eliminate structural drift,
* prevent implicit law,
* forbid polymorphic rule shapes,
* and make machine-readable governance **boring, explicit, and irreversible**.

This document does **not** define tooling, schemas, storage formats, or enforcement engines.
It defines **law shape only**.

---

## Constitutional Context

This paper derives its authority from:

* CORE Constitution — Article I (Primitives)
* CORE Constitution — Article II (Rule Definition)
* CORE Constitution — Article IV (Evaluation Model)
* CORE Constitution — Article V (Non-Existence of Implicit Law)

If any implementation contradicts this paper, the implementation is invalid.

---

## Canonical Rule Definition

A Rule is constitutionally valid **if and only if** it is expressible using **exactly five fields**.

No additional fields are permitted.
No field is optional.
No field may be inferred.

### Canonical Fields

| Field         | Description                           | Constitutional Source |
| ------------- | ------------------------------------- | --------------------- |
| `id`          | Stable, unique identifier of the Rule | Identity requirement  |
| `statement`   | Atomic normative requirement          | Rule primitive        |
| `authority`   | Who has final decision power          | Authority primitive   |
| `phase`       | When the Rule is evaluated            | Phase primitive       |
| `enforcement` | Effect of violation                   | Enforcement strength  |

These five fields form the **complete and closed representation** of a Rule.

---

## Field Semantics

### 1. `id`

* MUST be unique within the intent universe
* MUST be stable across time
* MUST NOT encode structure, hierarchy, or semantics

The `id` identifies the Rule — nothing more.

---

### 2. `statement`

* MUST express exactly **one** normative requirement
* MUST be declarative and unconditional
* MUST be evaluable as holding or not holding
* MUST NOT reference other Rules
* MUST NOT explain rationale or intent

Valid example:

> "All effectful file system writes MUST be guarded."

Invalid examples:

* Multi-condition statements
* Explanatory paragraphs
* References to enforcement mechanisms
* Procedural logic

---

### 3. `authority`

* MUST be one of: `Meta`, `Constitution`, `Policy`, `Code`
* MUST be explicit
* MUST NOT be derived from location, file path, or tooling context

Authority defines **who decides**, not **when** or **how**.

---

### 4. `phase`

* MUST be one of: `Parse`, `Load`, `Audit`, `Runtime`, `Execution`
* MUST be explicit
* MUST NOT span multiple phases

Phase defines **when evaluation occurs**, not severity or authority.

---

### 5. `enforcement`

* MUST be one of: `Blocking`, `Reporting`, `Advisory`
* MUST be explicit
* MUST NOT encode severity, logging level, or remediation strategy

Enforcement defines **the consequence of violation**, nothing else.

---

## Forbidden Fields (Non-Exhaustive)

The following concepts are **explicitly not part of a Rule**:

* `check`
* `check_type`
* `data`
* `scope`
* `category`
* `exceptions`
* `applies_when`
* `rationale`
* `implementation`
* `severity`
* `priority`

If such concepts are needed, they must exist as:

* derived artifacts, or
* tooling constructs, or
* documentation

They are **not law**.

---

## Non-Polymorphism Rule

All Rules share **the same shape**.

There are no:

* special rule types
* structural variants
* phase-specific schemas
* authority-specific extensions

Any Rule that cannot be expressed in canonical form **does not exist constitutionally**.

---

## Relationship to Legacy Rules

Legacy rule inventories demonstrate structural drift caused by:

* optional fields
* implicit phase inference
* mixed enforcement semantics
* embedded evaluation logic

Such rules are **invalid under this Canon**.

They may be:

* discarded,
* rewritten,
* or archived as historical artifacts.

They may **not** be grandfathered.

---

## Derivation Boundary

Canonical Rules are **source law**.

All of the following, if needed, must be **derived**:

* schemas
* checks
* evaluators
* execution guards
* reporting formats
* indexes
* registries

Derivation MUST be one-way.

Derived artifacts MUST NOT influence canonical law.

---

## Anti-Entropy Guarantee

By enforcing:

* a closed field set,
* explicit primitives,
* and zero inference,

CORE prevents:

* rule shape proliferation
* semantic drift
* governance-by-tooling

Structural boredom is a feature.

---

## Closing Statement

If a Rule cannot be expressed in canonical form, it is not a Rule.

If a system requires more structure, the Constitution must be amended.

Law does not bend to tooling.

**End of Canon.**
