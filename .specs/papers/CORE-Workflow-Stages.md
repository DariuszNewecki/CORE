<!-- path: .specs/papers/CORE-Workflow-Stages.md -->

# CORE: Workflow Stages

**Status:** Experimental

**Depends on:**

* `papers/CORE-Phases-as-Governance-Boundaries.md`
* `papers/CORE-Rule-Evaluation-Semantics.md`

---

# Abstract

This paper introduces the concept of **Workflow Stage**.

Workflow Stages define operational progression within a Phase without altering constitutional governance boundaries. While Phases determine *when rules may be evaluated*, Workflow Stages structure *how systems perform work inside those boundaries*.

Workflow Stages are therefore **organizational constructs**, not governance primitives. They exist to structure actions while preserving the determinism and authority constraints defined by CORE Phases.

---

# 1. Motivation

Phases intentionally define **coarse governance boundaries**.

They ensure that:

* rules are evaluated at predictable times,
* authority does not drift,
* enforcement remains deterministic.

However, phases do not describe **how work progresses operationally** inside those boundaries.

Without an intermediate abstraction, systems tend to accumulate unordered actions such as:

```
fix.imports
fix.format
fix.headers
fix.ids
```

This produces several governance problems:

* action ordering becomes implicit,
* agent responsibilities become unclear,
* operational reasoning becomes difficult.

Workflow Stages provide structured operational progression **without modifying the constitutional phase model**.

---

# 2. Definition of Workflow Stage

A **Workflow Stage** is a bounded operational step that groups related actions executed within a single Phase.

A stage defines:

* a coherent operational objective,
* a constrained action surface,
* optional ordering relative to other stages within the same Phase.

A stage does **not** introduce new governance authority.

---

# 3. Stage Invariants

The following invariants apply to all Workflow Stages:

1. A stage belongs to exactly one Phase.
2. A stage may contain multiple actions.
3. A stage must not redefine rule evaluation.
4. A stage must not cross phase boundaries.
5. Stage execution must respect all rules of its Phase.

Violation of these invariants constitutes a governance design error.

---

# 4. Relationship to Phases

Phases remain the **only governance boundary** in CORE.

Workflow Stages exist strictly **inside** phases. A stage that appears to
span two phases is in fact two stages — one in each phase — sequenced
across a phase transition. A single stage may never straddle a phase
boundary.

```
Interpret → Parse → Load → Audit → Runtime → Execution
               ↑
           Workflow Stages exist inside each Phase only
```

A stage cannot alter:

* phase inputs,
* rule evaluation semantics,
* enforcement authority.

Stages are therefore **operational constructs**, not legal constructs.

---

# 5. Relationship to Actions

Workflow Stages organize **Actions**.

An action remains the smallest executable unit of work.

Stages provide:

* grouping
* ordering
* specialization

Example:

```
Phase: Runtime

Stage: code_validation
    actions:
        check.imports
        check.format

Stage: code_repair
    actions:
        fix.imports
        fix.format
```

Each action must still comply with all runtime rules.

---

# 6. Stage Ordering

Stages may define ordering constraints within their Phase.

Ordering defines **operational sequencing**, not governance sequencing.

Example — stages within Runtime phase:

```
plan → generate → validate → repair
```

All four stages in this example exist inside the same Phase. If a
sequence requires work from two different phases (e.g. validate in
Audit, then repair in Runtime), those are two separate stages in two
separate phases, sequenced via a phase transition — not a single stage
crossing a boundary.

Ordering must never reopen an earlier phase.

---

# 7. Agent Specialization

Stages enable safe specialization of autonomous agents.

Example:

```
Stage: planning
    agent_role: Planner

Stage: generation
    agent_role: Coder

Stage: validation
    agent_role: Auditor
```

This separation improves operational clarity without affecting constitutional authority.

---

# 8. Relationship to Rule Evaluation

Rules remain:

* atomic,
* phase-bound,
* deterministic.

Workflow Stages do not evaluate rules.

Rules are evaluated **by the phase enforcement surface**.

Stages may influence **which actions occur**, but not **how rules are interpreted**.

---

# 9. Non-Goals

Workflow Stages do not define:

* rule semantics
* enforcement engines
* authority structures
* phase definitions

They must not:

* create new phases
* bypass rule evaluation
* reinterpret governance authority
* cross phase boundaries

---

# 10. Conclusion

Workflow Stages introduce operational structure without altering CORE's constitutional model.

Phases remain the exclusive governance boundaries.
Rules remain atomic and phase-bound.
Actions remain the smallest executable unit.
Stages exist inside one phase only — never across boundaries.

Workflow Stages simply organize how systems perform work inside those constraints.

The result is improved operational clarity while preserving deterministic governance.

---

**End of Paper.**
