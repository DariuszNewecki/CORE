# Irritation Heuristic

*Foundational Cognitive Pattern for Guided System Evolution*

**Status:** Foundational Cognitive Pattern
**Version:** 1.0.0
**Last Updated:** 2025-12-07

---

## 1. Introduction

The **Irritation Heuristic** formalizes an observed truth in human–system interaction:

> **Where the human consistently feels friction, the system is misaligned.**

CORE interprets emotional or intuitive “irritation” not as noise, but as a form of *signal*. It is evidence of:

* architectural drift,
* unclear abstractions,
* redundant complexity,
* missing patterns or capabilities,
* misalignment between intention and implementation.

The heuristic gives CORE a way to transform human qualitative intuition into structured evolutionary guidance.

---

## 2. Purpose & Meaning

Humans detect problems before they can articulate them.
AI detects structure, but not discomfort.

The Irritation Heuristic creates a bridge between them.

| Human Experience                   | System Interpretation                    |
| ---------------------------------- | ---------------------------------------- |
| “This file annoys me.”             | Structural incoherence or code smell     |
| “This module feels heavy.”         | Poor abstraction or domain leakage       |
| “Why does this always confuse me?” | Missing capability or ambiguous patterns |
| “This workflow irritates me.”      | Friction or misaligned responsibilities  |

This principle allows CORE to treat *human friction* as a truly meaningful architectural indicator.

---

## 3. Formal Definition

The Irritation Heuristic is:

> **A governance-level meta-signal indicating local or global misalignment between the intent encoded in `.intent/` and the system’s current implementation.**

It is not emotion modelling.
It is *semantic drift detection*, informed by human perception.

---

## 4. How the Heuristic Guides Evolution

When irritation is detected (reported explicitly or implicitly), CORE prioritizes investigation.

It will:

1. **Inspect domain boundaries** for leakage or improper placement
2. **Search for redundancy** or unused patterns
3. **Evaluate the capability graph** for missing or overloaded capabilities
4. **Check for abstraction inconsistencies**
5. **Propose simplifications or refactors** via the Will
6. **Generate a governed remediation plan**

This makes irritation a catalyst for *intentional system improvement*, not random change.

---

## 5. The Cognitive Loop

```
Human Discomfort
      ↓
Irritation Heuristic triggers
      ↓
System introspection (AST, patterns, KB, capabilities)
      ↓
Misalignment detection
      ↓
Proposal generation (Will)
      ↓
Governance validation (Mind)
      ↓
Refactor / remediation (Body)
```

This creates a **safe evolutionary loop** grounded in both intelligence and governance.

---

## 6. Governance Constraints

The heuristic **never overrides governance**.

It cannot bypass:

* constitutional rules
* domain boundaries
* capability schemas
* proposal workflows
* human signatures

It is: **a prioritization signal**, not an authorization mechanism.

Put differently:

> **Irritation tells CORE what to investigate first, not what it is allowed to change.**

---

## 7. What the Heuristic Is Not

It is **not**:

* subjective chaos in the system
* a free pass to make ungoverned changes
* emotional modelling inside agents
* an override of audits or constraints

It *is*:

* a structured amplifier of intuition,
* a human-in-the-loop prioritization signal,
* a philosophical root for guided system evolution.

---

## 8. Why This Matters in CORE

CORE is designed to extend human reasoning, not replace it.

The Irritation Heuristic captures a uniquely human ability:

> **Humans feel architecture problems before they can explain them.**

CORE turns those feelings into:

* introspection triggers,
* structural diagnostics,
* improvement proposals,
* safe, governed evolution pathways.

This ensures CORE evolves *with* its human operator, not beside them.

---

## 9. Related Documents

* `01_PHILOSOPHY.md`
* `02_ARCHITECTURE.md`
* `03_GOVERNANCE.md`
* `05-autonomy-ladder.md`
* `.intent/charter/patterns/*` (constitutional patterns)

---

**End of Document**
