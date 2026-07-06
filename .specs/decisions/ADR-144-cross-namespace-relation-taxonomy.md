---
kind: adr
id: ADR-144
title: "ADR-144 — CCC Topology §3: Cross-Namespace Relation Taxonomy"
status: accepted
---

<!-- path: .specs/decisions/ADR-144-cross-namespace-relation-taxonomy.md -->

# ADR-144 — CCC Topology §3: Cross-Namespace Relation Taxonomy

**Date:** 2026-07-06
**Status:** Accepted
**Authority:** Architectural
**Band:** D — Governance Integrity
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-07-06f)
**Grounding papers:** `.specs/papers/CORE-Governance-Topology.md` §3, §8; `.specs/papers/CORE-BYOR.md`
**Grounding ADRs:** ADR-075 D1/D6 (namespace split mechanics); ADR-073 D3/D6 (CCC check taxonomy)
**Closes:** #477

---

## Context

ADR-075 declared the `framework` / `project::<name>` governance namespace split and the
`namespace_manifest.yaml` classification surface. `CORE-Governance-Topology.md` §3
governs same-namespace directional relations (rows 1–10) but explicitly deferred
cross-namespace relation types to the issue cited in §8.

Three cross-namespace patterns are visible in the governed artifact inventory but
untyped in the current topology:

1. A `project::core` rule **extends** a framework paper — adds project-specific
   constraint without contradiction.
2. A `project::core` ADR **specializes** a framework ADR — narrowly applies a
   framework default to the project context.
3. A `framework` paper **constrains** a `project::core` workflow — establishes an
   invariant the project must conform to.

Without declared types, these patterns have no unambiguous relation code and
cannot be checked structurally. The critical structural invariant — framework
artifacts must not depend on any specific project artifact — is also undeclared,
leaving the separability guarantee that motivates BYOR without a scanner signal.

---

## Decisions

### D1 — Three cross-namespace relation types

Three relation types are declared for the cross-namespace surface:

| Code | Direction | Meaning |
|------|-----------|---------|
| `extends` | `project::* → framework` | The project artifact adds project-specific constraint on top of a framework artifact, without contradiction. Editorial; citation expected. |
| `specializes` | `project::* → framework` | The project artifact narrows a framework default for its specific context — a subset binding. Editorial; citation expected. |
| `constrains` | `framework → project::*` | The framework artifact establishes an invariant that all project artifacts must conform to. Constitutional; no per-project citation required. |

These codes join the existing relation taxonomy (ADR-073 D3) as cross-namespace
entries. They are documentary rather than scanner-enforced individually; the
scanner enforces the prohibition in D2 row 14.

### D2 — Directional permission grid (cross-namespace)

| # | Cross-namespace relation | Verdict | Mechanism |
|---|---|---|---|
| 11 | `framework` constrains `project::*` | **constitutional** | Framework invariants bind all deployments; no per-artifact citation required. The `constrains` relation is implicit in the namespace hierarchy. |
| 12 | `project::*` extends `framework` | **editorial** | Project artifact builds on framework; citation expected in the artifact's References block, not required for compliance. |
| 13 | `project::*` specializes `framework` | **editorial** | Project artifact narrows a framework default; citation expected, not required. |
| 14 | `framework` references `project::*` | **forbidden (strict)** | A framework artifact MUST NOT cite or embed a path reference to a specific project artifact. Framework must be project-agnostic for BYOR separability (ADR-075 D1/D6, CORE-BYOR.md). |

Row 14 is the load-bearing enforcement target: a framework artifact that names a
specific project artifact cannot be shipped unchanged to a BYOR deployment — the
reference encodes a dependency on a project that may not exist.

### D3 — §3 amendment to CORE-Governance-Topology.md

`CORE-Governance-Topology.md` §3 is amended to add rows 11–14 to the relation
grid and a §3.4 subsection explaining the cross-namespace directional principles.
The amendment is append-only; rows 1–10 and §3.1–§3.3 are unchanged.

### D4 — CCC check class CROSS_NS_DIRECTION

A new structural check class `CrossNsDirectionCheck` is added to
`src/mind/coherence/checks/cross_ns_direction.py` and registered in
`src/mind/coherence/checker.py`.

The check:
1. Reads `.intent/governance/namespace_manifest.yaml` to build the set of
   project-classified paths.
2. Scans every framework-classified `.specs/` artifact (all papers; accepted ADRs
   only — draft ADR content may contain speculative cross-references) for text
   references to project-classified paths.
3. Emits `CROSS_NS_DIRECTION` for each framework artifact that contains an
   explicit path reference (`.specs/…` or `.intent/…` string) to a
   project-namespace artifact.
4. Raises `CheckSkipped("namespace_manifest_absent")` if the manifest does not
   exist (pre-migration state).

Scope of v1: explicit path-string references only. ADR-ID-only references (e.g.
`"see ADR-143"` without an accompanying path) are out of scope — their
directional significance requires semantic context that a structural scan cannot
reliably determine. Escalation to ADR-ID scanning is a follow-on decision.

No LLM. No vectors. Structural grep over the `namespace_manifest`.

---

## Consequences

**Positive:**
- The cross-namespace relation surface is no longer unnamed. Authors can
  annotate directional dependencies in References blocks using the typed
  vocabulary from D1.
- The BYOR separability invariant (framework must be project-agnostic) is
  structurally enforced for explicit path references.
- The CCC check returns zero candidates on a clean manifest, providing a
  positive signal rather than silence.

**Neutral:**
- ADR-ID-only references are not checked in v1. The practical risk is low:
  framework ADRs that cite project ADRs by ID alone are already rare and
  are surfaced by ROW4_NAMING or human triage.

**Risk:**
- The manifest must remain classified-complete for the check to be
  meaningful. `governance.namespace.classification_complete` (ADR-075 D7)
  is the maintenance gate; if it fires, CROSS_NS_DIRECTION coverage shrinks.

---

## Phases

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **D1/D2** | Relation vocabulary + permission grid | Done |
| **D3** | §3 amendment to Topology paper | Done |
| **D4** | `CrossNsDirectionCheck` + checker registration + tests | Done |
