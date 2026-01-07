<!-- path: .intent/REBIRTH/papers/CORE-Constitution-Read-Only-Contract.md -->

# CORE — Constitution Read-Only Contract

**Status:** Constitutional Semantics Paper

**Scope:** Interaction between CORE and the Constitution

**Authority:** Constitution-level (derivative, non-primitive)

---

## 1. Purpose

This paper defines the strict interaction contract between CORE and the Constitution.

Its purpose is to eliminate ambiguity about CORE’s rights, obligations, and prohibitions with respect to constitutional law, and to permanently prevent constitutional bypass, mutation, or erosion through tooling or execution logic.

---

## 2. Read-Only Invariant

The Constitution is **read-only** for CORE.

CORE:

* MAY read constitutional documents.
* MAY validate their internal consistency.
* MAY report contradictions, gaps, or violations.

CORE:

* MUST NOT modify constitutional content.
* MUST NOT bypass constitutional restrictions.
* MUST NOT reinterpret constitutional meaning.
* MUST NOT compensate for constitutional defects through execution logic.

This invariant is absolute.

---

## 3. No Write-Back Authority

CORE possesses **no authority** to:

* amend constitutional law,
* suppress or ignore constitutional rules,
* introduce temporary exemptions,
* auto-correct contradictions,
* generate replacement constitutions.

CORE may observe and report.
It may not legislate.

---

## 4. Complaint Without Override

CORE is permitted to **complain**.

Complaints may include:

* contradictory rules,
* unsatisfiable constraints,
* indeterminate evaluation conditions,
* governance deadlocks.

Complaints:

* do not grant permission,
* do not relax enforcement,
* do not alter outcomes.

A complaint never authorizes bypass.

---

## 5. Behavior Under Constitutional Defect

If the Constitution is:

* internally inconsistent,
* incomplete,
* unsatisfiable,
* or unrepresentable in execution,

CORE must:

1. Halt progression at the affected Phase.
2. Block execution for blocking rules.
3. Surface the defect explicitly.

CORE must not invent behavior to preserve continuity.

---

## 6. Separation of Constitutional Tooling

Any tool responsible for creating, editing, or replacing the Constitution:

* MUST be autonomous.
* MUST be logically and operationally separate from CORE.
* MUST NOT share execution paths with CORE runtime.

CORE may consume outputs of such tools only as finalized constitutional documents.

---

## 7. REBIRTH Trigger Boundary

Constitutional replacement (REBIRTH):

* MAY be initiated externally.
* MUST NOT be initiated autonomously by CORE.

CORE may detect the need for replacement.
It may not perform replacement.

---

## 8. Prohibition of Shadow Governance

CORE MUST NOT create or rely on:

* shadow constitutions,
* cached authoritative interpretations,
* heuristic relaxations,
* fallback governance logic.

Law exists only where declared.

---

## 9. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in accordance with the CORE amendment mechanism.

---

## 10. Closing Statement

CORE is a governed system.

Its strength lies not in adaptability, but in obedience.
