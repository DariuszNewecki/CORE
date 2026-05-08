<!-- path: .intent/CHANGELOG.md -->

# CORE — Changelog

This changelog records **constitutional-level changes** during the modernization of CORE.

It documents *what changed and why*, not how changes were implemented.

This file is descriptive only.
It carries no authority.

---

## Versioning Model

Current versions do not follow semantic versioning.

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

  * Load
  * Parse
  * Interpret
  * Audit
  * Execution
* Required all rules to declare governing artifacts
* Forbade silent rule emergence
* Defined enforcement strengths:

  * advisory
  * required
  * blocking
* Defined Authority hierarchy:

  * Constitutional
  * Policy
* Required dual-key amendment for the Constitution
* Set non-goals explicitly:

  * Not a framework
  * Not configuration
  * Not a runtime system
  * Not workflow logic
* Forbade emergent rule creation by Workers, Phases, or LLM components
* Required every rule and decision to be traceable to declared intent

**Constitutional Documents:**

* `constitution/CORE-CONSTITUTION.md`
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

## v0.2 — ShopManager Class Reservation

**Status:** Clarifying amendment (non-primitive)

**Intent:**

This version closes the constitutional coherence finding F-11 surfaced by
the 2026-04-28 audit. The ShopManager paper was Canonical but had drifted
from its implementation: workers fulfilling the supervisory mandate were
named `*_auditor` and declared `class: governance`, neither of which the
paper recognized. This amendment aligns code to the paper rather than the
paper to the code.

No primitives were added.
No scope expansion occurred.

### Added

* **`identity.class: supervision` reservation**

  * Reserved the `supervision` worker class exclusively for ShopManagers
  * Distinguishes ShopManagers from sensing, acting, and governance workers
  * No worker outside the ShopManager paper's scope may declare this class
  * Artifact: `papers/CORE-ShopManager.md` §2

* **§3a Implementation Status table in CORE-ShopManager.md**

  * Authoritative implementation map for the three supervisory responsibilities
  * Each row pairs a responsibility with its implementing worker and current status
  * Drift between this table and `.intent/workers/` is itself an audit finding

* **Deferral discipline for Proposal Pipeline Health**

  * §3 responsibility 3 marked "Not Yet Implemented" with reference to issue #170
  * Same deferral discipline already applied to OptimizerWorker
  * Implementation seed identified at `src/cli/resources/runtime/health.py:439-448`

### Changed

* **Worker rename: `*_auditor` → `*_shop_manager`**

  * `worker_auditor` → `worker_shop_manager`
  * `blackboard_auditor` → `blackboard_shop_manager`
  * Worker UUIDs preserved (constitutional identity per ADR-011)
  * Database `worker_registry` rows migrated; FK integrity intact

* **`CORE-OptimizerWorker.md` §3 currency** (finding F-12)

  * Removed claim that "ViolationExecutor is not yet implemented"
  * VE is implemented and active; the OptimizerWorker's deferral is now
    correctly grounded in the absence of accumulated discovery data, not
    the absence of VE

### Not Changed

* Primitive set
* Authority hierarchy
* Phase definitions
* Enforcement strengths
* Non-goals and scope boundaries

### Tracked Follow-Ups

* Issue #170 — Implement proposal-pipeline-health ShopManager (§3.3 deferred work)

---

## v0.3 — Vocabulary Governance Enforcement Triangle

**Status:** Clarifying amendment (non-primitive)

**Intent:**

This version closes the constitutional coherence findings N-01 and N-02
surfaced by the 2026-05-08 audit. ADR-023 (Vocabulary Canonical Store)
authored six vocabulary governance rule_ids across two rule files but did
not ship the corresponding enforcement mappings. The rules were declared
law but had no enforcement path — an incomplete triangle. This amendment
completes the triangle by delivering both mapping files.

No primitives were added.
No scope expansion occurred.

### Added

* **`mappings/governance/vocabulary_canonical_store.yaml`** (ADR-023, finding N-01)

  * Closes the enforcement triangle for four rule_ids:
    `governance.vocabulary.projection_must_match_canonical`,
    `governance.vocabulary.canonical_format_must_validate`,
    `governance.vocabulary.authoritative_source_must_be_paper`,
    `governance.vocabulary.no_direct_json_import`
  * Rules 1-3 use `artifact_gate` engine with vocabulary-specific check_types;
    engine implementation is pending ADR-023 Part 3/4 delivery
  * Rule 4 (`no_direct_json_import`) is immediately enforceable via `regex_gate`
    on `src/`, excluding the sanctioned loader

* **`mappings/governance/vocabulary_registers.yaml`** (finding N-02)

  * Closes the enforcement triangle for two rule_ids:
    `governance.vocabulary_registers.operational_fields_must_be_lowercase`,
    `governance.vocabulary_registers.diagnostic_fields_must_be_uppercase`
  * Both rules use `python_runtime` engine with `register_casing_validation`
    check_type; structured YAML/JSON field parsing required
  * Scope: all `.intent/` YAML and JSON files, excluding `.intent/META/`

### Not Changed

* Primitive set
* Authority hierarchy
* Phase definitions
* Enforcement strengths
* Non-goals and scope boundaries

### Tracked Follow-Ups

* ADR-023 Part 3/4 — implement `artifact_gate` vocabulary check_types to
  activate enforcement for rules 1-3 of vocabulary_canonical_store
* `python_runtime` `register_casing_validation` check_type implementation
  required to activate vocabulary_registers enforcement

---

## Notes

* This changelog intentionally avoids implementation detail
* No legacy compatibility is implied
* Silence on future versions is intentional
