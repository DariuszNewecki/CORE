<!-- path: .intent/REBIRTH/CHANGELOG.md -->

# CORE — REBIRTH Changelog

This changelog records **constitutional-level changes** during the REBIRTH of CORE.

It documents *what changed and why*, not how changes were implemented.

This file is descriptive only.
It carries no authority.

---

## Versioning Model

REBIRTH versions do not follow semantic versioning.

Each version represents a **constitutional state**.

Replacement invalidates all prior constitutional authority.
Minor versions indicate clarification within the same constitutional intent.

---

## v0 — Foundational Constitution

**Status:** Initial constitutional declaration

**Description:**

* Introduced CORE as a legal system, not a framework
* Declared four irreducible primitives:

  * Document
  * Rule
  * Phase
  * Authority
* Established explicit phase discipline:

  * Parse
  * Load
  * Audit
  * Runtime
  * Execution
* Defined enforcement strengths:

  * Blocking
  * Reporting
  * Advisory
* Rejected:

  * implicit law
  * interpretation
  * precedent
  * registries
  * backward compatibility

**Artifacts:**

* `constitution/CORE-CONSTITUTION-v0.md`
* Foundational papers under `papers/`
* `CORE-CHARTER.md`

---

## v0.1 — Governance Semantics Hardening

**Status:** Clarifying amendment (non-primitive)

**Intent:**

This version hardens CORE against known governance failure modes identified during external constitutional review.

No primitives were added.
No scope expansion occurred.

### Added

* **Rule Conflict Semantics**

  * Defined handling of conflicts between rules of equal Authority and Phase
  * Classified such conflicts as governance errors
  * Explicitly forbade precedence, ordering, and interpretation
  * Artifact: `papers/CORE-Rule-Conflict-Semantics.md`

* **Amendment by Replacement Only**

  * Made explicit that the Constitution may be amended only via replacement
  * Forbade in-place modification
  * Anchored REBIRTH as the amendment mechanism

* **Evidence as Input Semantics**

  * Defined evidence as evaluation input, not law
  * Bound evidence to phases
  * Required reproducibility
  * Clarified indeterminate outcomes
  * Artifact: `papers/CORE-Evidence-as-Input.md`

* **Emergency and Exception Stance**

  * Explicitly rejected emergency sovereignty and exception mechanisms
  * Forbade break-glass logic
  * Required replacement, not override, when law is insufficient
  * Artifact: `papers/CORE-Emergency-and-Exception-Stance.md`

### Changed

* Article IV — Evaluation Model

  * Added explicit reference to rule conflict semantics

* Article VII — Change Discipline

  * Clarified amendment mechanism as replacement-only

### Not Changed

* Primitive set
* Authority hierarchy
* Phase definitions
* Enforcement strengths
* Non-goals and scope boundaries

---

## Notes

* This changelog intentionally avoids implementation detail
* No legacy compatibility is implied
* Silence on future versions is intentional
  n
