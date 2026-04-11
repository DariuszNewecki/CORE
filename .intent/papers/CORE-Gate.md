<!-- path: .intent/papers/CORE-Gate.md -->

# CORE — Gates

**Status:** Canonical
**Authority:** Constitution
**Scope:** All validation boundaries in CORE

---

## 1. Purpose

This paper defines the Gate — the blocking validation point in CORE — and
its three implementations: ConservationGate, IntentGuard, and Canary.

---

## 2. Definition

A Gate is a validation point that must pass before execution continues.

A Gate:
- evaluates a condition deterministically
- blocks if the condition does not hold
- has no override
- has no emergency bypass

If a Gate is wrong, the Gate must be changed. It must not be circumvented.

A Gate is not a check. A check observes and reports. A Gate blocks.

---

## 3. Constitutional Basis

Gates derive their authority from the Phase model. Each Gate operates at
a declared Phase. A Gate that operates outside its Phase is a governance
violation — not a safety measure.

---

## 4. The Three Gates

### 4.1 ConservationGate

**Phase:** Runtime
**What it evaluates:** LLM-produced code against the original it replaces.
**What it blocks:** Code that silently deletes logic.

An LLM can produce syntactically valid, stylistically correct code that
removes behavior. The ConservationGate measures the ratio of preserved
logic to original logic. Below the declared threshold, the output is
rejected — regardless of any other quality measure.

Logic evaporation is a silent failure. The ConservationGate makes it loud.

### 4.2 IntentGuard

**Phase:** Runtime
**What it evaluates:** Every file write, before it happens.
**What it blocks:** Writes that violate constitutional rules.

IntentGuard is the perimeter. No file may be written to the live codebase
without passing IntentGuard. It evaluates the target path, the content,
and the constitutional rules applicable to that file's layer.

IntentGuard does not evaluate intent. It evaluates compliance.

### 4.3 Canary

**Phase:** Execution
**What it evaluates:** A Crate, in a sandbox, before it is applied.
**What it blocks:** Crates that introduce new blocking violations.

The Canary creates a complete sandbox replica of the repository, applies
the Crate's changes, and runs the constitutional audit. A Crate that
produces new blocking violations not present in the baseline does not
reach production.

The Canary is the last line of defense before a change is permanent.

---

## 5. Gate Ordering

Gates execute in this fixed order:

```
ConservationGate → IntentGuard → Canary
```

**ConservationGate runs first** because it evaluates LLM-produced code
before anything is written. A Crate whose logic conservation ratio falls
below threshold is rejected before any write is attempted.

**IntentGuard runs second** because it evaluates each file write against
constitutional rules. It runs after ConservationGate has confirmed the
content is logically sound.

**Canary runs last** because it requires a complete, assembled Crate to
validate in a sandbox. It is the final gate before the change is applied
to the live repository.

A failure at any gate halts the pipeline immediately. Gates that follow
a failed gate do not run.

---

## 6. Gate Verdicts and Disagreement

Each Gate returns an independent verdict. When Gates disagree — for
example, IntentGuard passes but ConservationGate fails — the pipeline
halts at the first failure. There is no reconciliation between gate
verdicts. The earliest gate to fail is authoritative for that execution.

---

## 7. Non-Goals

This paper does not define:
- the specific rules IntentGuard evaluates
- the Canary sandbox implementation
- the ConservationGate threshold value

Those are declared in `.intent/rules/` and `.intent/enforcement/`.
