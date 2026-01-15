<!-- path: .intent/papers/CORE-Phases-as-Governance-Boundaries.md -->

# CORE: Phases as Governance Boundaries

**Status:** Constitutional (Active)

**Depends on:**
* `papers/CORE-Constitutional-Foundations.md`
* `papers/CORE-Rule-Evaluation-Semantics.md`

---

## Abstract

This paper defines Phases as the primary governance boundaries in CORE. A Phase determines *when* a rule may be evaluated and, equally important, *what is forbidden* at that moment. By enforcing strict phase separation, CORE prevents authority leakage, eliminates temporal ambiguity, and ensures that enforcement remains predictable even in autonomous or AI-assisted systems.

---

## 1. Motivation

Most governance failures are temporal rather than semantic. Rules are often correct in content but applied at the wrong time, leading to retroactive enforcement, hidden vetoes, or implicit authority shifts.

CORE addresses this by elevating Phase to a constitutional primitive.

A Phase is not an implementation detail. It is law.

---

## 2. Definition of Phase

A **Phase** defines a closed temporal window during which a rule may be evaluated.

A Phase:
* constrains available inputs,
* constrains permissible actions,
* constrains enforcement behavior.

Rules evaluated outside their declared Phase are constitutionally invalid.

---

## 3. Phase Invariants

The following invariants apply to all Phases:

1. A rule belongs to exactly one Phase.
2. A Phase has a finite and known input surface.
3. A Phase does not retroactively affect earlier Phases.
4. Later Phases may assume earlier Phases were valid.

Violation of these invariants constitutes governance failure.

---

## 4. The Six CORE Phases

CORE defines exactly six Phases. No extension is permitted at the constitutional level.

### 4.1 Interpret Phase

**Purpose:** Convert natural language intent into canonical task structure.

**Inputs:**
* user request (natural language),
* conversation context.

**Permitted:**
* intent classification,
* task structure generation,
* clarification requests,
* goal parsing.

**Forbidden:**
* file system access,
* code execution,
* policy creation,
* authority assertion.

Interpret establishes *intent*, not action.

This phase bridges the ungoverned (human communication) with the governed (system execution). It is the constitutional entry point for the Will layer.

---

### 4.2 Parse Phase

**Purpose:** Validate document shape.

**Inputs:**
* a single document.

**Permitted:**
* structural validation,
* required field checks,
* type validation.

**Forbidden:**
* cross-document reasoning,
* semantic interpretation,
* authority inference.

Parse establishes *legibility*, not meaning.

---

### 4.3 Load Phase

**Purpose:** Validate document consistency.

**Inputs:**
* a set of validated documents.

**Permitted:**
* cross-document references,
* identifier uniqueness checks,
* consistency constraints.

**Forbidden:**
* execution,
* environment inspection,
* policy enforcement.

Load establishes *coherence*, not compliance.

---

### 4.4 Audit Phase

**Purpose:** Observe system state.

**Inputs:**
* system artifacts,
* logs,
* static code,
* derived metrics.

**Permitted:**
* inspection,
* reporting,
* evidence collection.

**Forbidden:**
* prevention of actions,
* mutation of state,
* retroactive authority.

Audit establishes *visibility*, not control.

---

### 4.5 Runtime Phase

**Purpose:** Guard actions before they occur.

**Inputs:**
* a proposed action,
* immediate context.

**Permitted:**
* allow/deny decisions,
* constraint checks,
* short-circuit evaluation.

**Forbidden:**
* long-running analysis,
* policy discovery,
* reinterpretation of rules.

Runtime establishes *control*, not deliberation.

---

### 4.6 Execution Phase

**Purpose:** Control effectful operations.

**Inputs:**
* an authorized operation,
* controlled execution surface.

**Permitted:**
* sandboxing,
* transactional guarantees,
* risk-limited execution.

**Forbidden:**
* rule creation,
* authority escalation,
* post-hoc justification.

Execution establishes *containment*, not judgment.

---

## 5. Phase Transitions

Phase transitions are one-way and monotonic:

**Interpret → Parse → Load → Audit → Runtime → Execution**

No Phase may reopen a prior Phase.

If a violation is detected late, it must be handled within that Phase's authority and enforcement strength.

---

## 6. Mind-Body-Will Alignment

The six phases map to CORE's architectural layers:

**Will Layer:** Interpret
* Strategic and tactical decision-making
* Natural language → structured intent

**Body Layer:** Parse, Load, Audit
* Fact extraction and validation
* No decisions, only observations

**Will Layer:** Runtime
* Tactical execution decisions
* Within constitutional bounds

**Body Layer:** Execution
* Pure effectful operations
* Governed by Runtime decisions

This alignment ensures the Will layer has constitutional legitimacy from user input through to execution.

---

## 7. Failure Modes Prevented by Phase Discipline

Strict phase boundaries prevent:
* retroactive blocking based on audit findings,
* hidden policy enforcement during load,
* runtime decisions based on incomplete context,
* execution-time reinterpretation of law,
* ungoverned intent interpretation.

Most governance duct tape arises from ignoring these boundaries.

---

## 8. Relationship to Authority

Phase determines *when*.
Authority determines *who*.

Neither substitutes for the other.

A constitutional authority rule evaluated in the wrong Phase is invalid.
A policy rule evaluated at runtime without authorization is invalid.

---

## 9. Rationale for Six Phases

The choice of exactly six phases reflects:

1. **Interpret** - Required for AI systems that accept natural language
2. **Parse/Load** - Necessary for any document-based governance
3. **Audit** - Required for observable compliance
4. **Runtime** - Required for preventive control
5. **Execution** - Required for safe effectful operations

Extension beyond six would indicate either:
* inappropriate phase granularity, or
* confusion between phases and workflow steps.

---

## 10. Non-Goals

This paper does not define:
* enforcement engines,
* execution platforms,
* tooling pipelines,
* workflow composition.

Those must conform to phase law but are not part of it.

---

## 11. Conclusion

Phases are not convenience layers. They are governance boundaries.

By enforcing strict temporal separation across six constitutional phases, CORE ensures that authority does not drift, enforcement does not surprise, and autonomy does not erode governance.

The addition of Interpret as the first constitutional phase completes the Mind-Body-Will architecture, ensuring that even the translation of human intent into system action is governed by law.

Boredom at phase boundaries is a sign of correctness.

---

**End of Paper.**
