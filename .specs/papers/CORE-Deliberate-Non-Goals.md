<!-- path: .specs/papers/CORE-Deliberate-Non-Goals.md -->

# CORE: Deliberate Non-Goals

**Status:** Draft (Greenfield)

**Depends on:**

* `papers/CORE-Constitutional-Foundations.md`
* `papers/CORE-Rule-Evaluation-Semantics.md`
* `papers/CORE-Phases-as-Governance-Boundaries.md`
* `papers/CORE-Authority-Without-Registries.md`

---

## Abstract

This paper defines what CORE explicitly refuses to solve. In governance systems, overreach is a primary source of complexity, brittleness, and duct tape. By stating non-goals as constitutional guardrails, CORE preserves clarity, prevents scope creep, and ensures that future extensions do not undermine foundational law.

---

## 1. Motivation

Many systems fail not because their goals are unclear, but because their boundaries are.

Governance frameworks, in particular, tend to absorb concerns that properly belong to tooling, process, or organizational culture. CORE rejects this tendency.

This paper formalizes restraint.

---

## 2. Constitutional Restraint

CORE treats absence as intentional.

If something is not defined by constitutional law, it is not missing. It is excluded.

Non-goals are not future work.
They are active prohibitions against accidental complexity.

---

## 3. Explicit Non-Goals

### 3.1 CORE Does Not Define Arbitrary Taxonomies

CORE does not define:

* rule categories for external systems,
* domain hierarchies imposed on user projects,
* capability trees for purposes outside CORE's own operation.

CORE does define a capability and cognitive role taxonomy for its own
internal operation — specifically to govern how AI cognitive resources
are selected and routed. This is a constitutional artifact of CORE's
own governance, not a general-purpose taxonomy framework.

Such internal taxonomies have constitutional standing because they are
declared in `.intent/` and serve CORE's NorthStar directly. Taxonomies
imposed on external systems have no constitutional meaning.

---

### 3.2 CORE Does Not Provide Arbitrary Registries or Indexes

CORE forbids:

* persisted rule indexes as authoritative sources,
* authority registries that substitute for declared law,
* canonical lookup tables that replace explicit rule evaluation.

CORE does maintain bounded infrastructure registries — specifically
the ServiceRegistry and the atomic action registry — where explicitly
declared and constitutionally bounded. These are infrastructure
coordination mechanisms, not governance authorities. See
`CORE-Infrastructure-Definition.md` for the constitutional boundary.

---

### 3.3 CORE Does Not Manage External Workflows

CORE does not orchestrate:

* CI/CD pipelines,
* approval flows for external systems,
* human review processes outside its own governance loop.

CORE does define and govern its own internal workflows — the autonomous
remediation loop, the proposal pipeline, the execution ceremony. These
are constitutional artifacts declared in `.intent/workflows/` and
`.intent/phases/`. They govern how CORE itself operates, not how
external systems operate.

It governs *what is allowed*, not *how external work proceeds*.

---

### 3.4 CORE Does Not Define Tooling UX

CORE does not specify:

* editors,
* dashboards,
* visualizations,
* CLI ergonomics.

Tooling must adapt to law, not the reverse.

---

### 3.5 CORE Does Not Optimize Performance

CORE does not define:

* caching strategies,
* execution shortcuts,
* performance heuristics.

Correctness precedes efficiency.

---

### 3.6 CORE Does Not Encode Organizational Politics

CORE does not attempt to:

* model organizational roles,
* encode approval hierarchies,
* mirror corporate structure.

Authority in CORE is legal, not political.

---

## 4. Deferred Concerns

The following concerns are explicitly deferred:

* usability
* adoption strategy
* migration tooling
* compatibility layers

These concerns may be addressed later, but never at the expense of constitutional clarity.

---

## 5. Guarding Against Scope Creep

Any proposal that introduces a new concept must answer:

1. Which constitutional primitive does this reduce to?
2. If none, why does it deserve to exist?

If no clear reduction exists, the proposal is rejected.

---

## 6. Relationship to Boredom

Boredom is not stagnation.

Boredom indicates that the system:

* behaves predictably,
* resists embellishment,
* discourages cleverness.

CORE treats boredom as a success metric.

---

## 7. Conclusion

By defining what it refuses to do, CORE protects itself from accidental complexity. These non-goals are as important as the goals themselves. They ensure that CORE remains a constitutional framework rather than an ever-expanding platform.
