<!-- path: .intent/papers/CORE-Gate.md -->

# CORE — Gates

**Status:** Canonical
**Authority:** Constitution
**Scope:** All validation boundaries in CORE

---

## 1. Purpose

This paper defines the Gate — the blocking validation point in CORE — and
its three implementations: IntentGuard, Canary, and ConservationGate.

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

### 4.1 IntentGuard

**Phase:** Runtime
**What it evaluates:** Every file write, before it happens.
**What it blocks:** Writes that violate constitutional rules.

IntentGuard is the perimeter. No file may be written to the live codebase
without passing IntentGuard. It evaluates the target path, the content,
and the constitutional rules applicable to that file's layer.

IntentGuard does not evaluate intent. It evaluates compliance.

### 4.2 Canary

**Phase:** Execution
**What it evaluates:** A Crate, in a sandbox, before it is applied.
**What it blocks:** Crates that fail structural or behavioral validation.

The Canary creates a complete sandbox replica of the repository, applies
the Crate's changes, and runs the constitutional audit. A Crate that
produces new violations in the sandbox does not reach production.

The Canary is the last line of defense before a change is permanent.

### 4.3 ConservationGate

**Phase:** Runtime
**What it evaluates:** LLM-produced code against the original it replaces.
**What it blocks:** Code that silently deletes logic.

An LLM can produce syntactically valid, stylistically correct code that
removes behavior. The ConservationGate measures the ratio of preserved
logic to original logic. Below the declared threshold, the output is
rejected — regardless of any other quality measure.

Logic evaporation is a silent failure. The ConservationGate makes it loud.

---

## 5. Gate Ordering

In the execution ceremony, Gates run in this order:


ConservationGate (Runtime) → IntentGuard (Runtime) → Canary (Execution)

ConservationGate runs first because it evaluates LLM output before anything
is written. IntentGuard runs on every write. Canary runs last because it
requires a complete Crate to validate against.

---

## 6. Non-Goals

This paper does not define:
- the specific rules IntentGuard evaluates
- the Canary sandbox implementation
- the ConservationGate threshold value

Those are declared in `.intent/rules/` and `.intent/enforcement/`.
