# ADR-001: Establish the `.specs/` layer

**Status:** Accepted
**Date:** 2026-04-15
**Authors:** Darek (Dariusz Newecki)

## Context

Before this decision, `.intent/` held every non-code artifact in the project: the constitution, rule documents, enforcement mappings, worker declarations, schemas, architectural papers, phase definitions, and narrative documents. The directory served two fundamentally different purposes:

1. **Operational governance** — files CORE reads at runtime to make decisions (rules, enforcement mappings, worker YAMLs, phase definitions, META schemas).
2. **Architectural reasoning** — files humans read to understand CORE (papers, charter, north-star documents, planning documents, user requirements).

This conflation created three problems:

- The trust model was unclear. The `architecture.constitution_read_only` rule protects `.intent/` from runtime writes by CORE itself. But that protection made sense for operational governance files and made much less sense for architectural papers, which are routinely edited as thinking develops.
- The `.intent/` admission test — *"does CORE read this file at runtime to make a governance decision?"* — was failing for roughly half the directory. Papers, planning documents, and north-star narratives did not pass the test. They were in `.intent/` because there was nowhere else for them to go.
- Vector search collections were coupled. `core_policies` and `core-patterns` indexed everything in `.intent/`, including narrative documents that were not policies or patterns. Query precision suffered.

A separate decision (ADR-005) would later make `.specs/` a first-class vector collection; the architectural separation needed to come first.

## Decision

Non-operational documents move out of `.intent/` into a new top-level directory, `.specs/`, organized as:

```
.specs/
├── CORE-CHARTER.md        founding declaration
├── META/                  schema for .specs/ artifacts
├── northstar/             why CORE exists
├── papers/                architectural reasoning
├── requirements/          URS documents
├── decisions/             ADRs
└── planning/              roadmaps, operational plans
```

The admission test for `.specs/` is the inverse of the `.intent/` test: *a file belongs in `.specs/` if CORE does **not** read it at runtime to make a governance decision.* Architectural papers, requirements documents, ADRs, and planning documents all satisfy this test.

The admission test for `.intent/` remains unchanged and is now enforced more cleanly: *a file belongs in `.intent/` if CORE reads it at runtime to make a governance decision.*

## Alternatives Considered

**Leave everything in `.intent/` and add a `papers/` subdirectory.** Rejected — this was the previous state. It did not resolve the mixed-purpose problem; it only organized it.

**Use `docs/` as the target.** Rejected — `docs/` is the MkDocs source directory for the public site. Architectural reasoning is authored for internal use and selectively published; mixing the two would force every paper through the publication workflow.

**Use a new directory under `.intent/`, e.g. `.intent/reasoning/`.** Rejected — this preserved the ambiguity the decision was meant to eliminate. The `.intent/` name implies runtime governance. Anything under `.intent/` inherits that connotation whether it should or not.

**Store architectural documents outside the repository.** Rejected — traceability between papers and rules is a core CORE principle. Separating them from the repo would break that.

## Consequences

**Positive:**

- The `.intent/` admission test is now honestly enforceable. Every file in `.intent/` is read at runtime by CORE.
- Architectural reasoning is versioned alongside the code it describes, without sharing the operational-governance trust model.
- Vector collections can be separated (`core_specs`, `core_policies`, `core-patterns`) and queried with better precision.
- ADRs have a canonical home. This ADR would have no obvious location under the previous structure.
- Onboarding is clearer: read `.specs/` to understand what CORE is and why; read `.intent/` to understand what CORE will enforce.

**Negative:**

- Two constitutional layers now exist where one existed before. Anyone changing structural rules must reason about which layer applies and keep them aligned.
- Links from existing documents to `.intent/papers/` (42 in `vocabulary.md` alone at the time of the move) broke and had to be repaired. Future renames of this kind will have the same cost.
- `.specs/` currently lacks a META schema layer equivalent to `.intent/META/`. Anyone authoring a paper, requirement, or ADR today has no machine-checkable shape to conform to. This is a known gap; closing it is tracked separately.
- The decision reverses two years of implicit accumulation in `.intent/`. Some historical references in external documents (e.g. Dev.to articles) still point to the old paths.

**Neutral:**

- The migration of files was purely mechanical; no content changed. Existing papers became `.specs/papers/` without modification.
- CORE's runtime behavior did not change on the day of the decision. The effect was entirely on where files live and how they are governed.

## References

- A3 plan entry, 2026-04-15 — `.specs/` layer established
- `.intent/` admission test — memory: *"a file belongs in `.intent/` if CORE reads it at runtime to make a governance decision"*
- Related: ADR-005 (`.specs/` as first-class vector collection), ADR-006 (functional requirements layer)
- Rule: `architecture.constitution_read_only` (enforces `.intent/` immutability by CORE itself)
