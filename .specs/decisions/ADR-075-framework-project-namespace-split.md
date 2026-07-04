---
kind: adr
id: ADR-075
title: ADR-075 — Framework / Project Namespace Split
status: accepted
---

# ADR-075 — Framework / Project Namespace Split

**Date:** 2026-05-28
**Governing paper:** `.specs/papers/CORE-BYOR.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Band:** E — Outward-Facing
**Closes:** #457 close-condition 1 (model + tagging convention + classification authority). Close-conditions 2 (manifest authored) and 3 (follow-on issue) are implementation and follow-on, tracked separately.
**Grounding paper:** `papers/CORE-Governance-Topology.md` §8
**Related:** ADR-068 (cognate register pattern), ADR-070 (projection inventory pattern)

---

## Context

CORE's `.intent/` and `.specs/` directories serve two structurally fused
purposes. The first is the **governance framework** — schemas, contracts,
enforcement primitives, and constitutional papers that define how *any*
repository can be governed. The second is **CORE's own self-governance** —
the rules, workers, mappings, and ADRs specific to CORE's own codebase.
Every artifact belongs to one of these two purposes, but today no declared
boundary separates them.

This matters because CORE is simultaneously the framework and its own first
governed project. When CORE governs an external repository (BYOR), that repo
needs a project-level constitution distinct from the framework that ships with
CORE. The two must be separable, nameable, and independently addressable
before a governance application can be designed or a DB schema reasoned about.
Without the split, the schema conflates artifacts that have different
ownership, lifecycle, and deployment semantics.

The constitutional principle is already declared. `CORE-Governance-Topology.md`
§8 (accepted 2026-05-26) states that every governance artifact belongs to a
namespace — `framework` (ships with CORE, applies to any governed project) or
`project::<name>` (specific to a named repo, CORE itself being
`project::core`) — and explicitly defers the operational mechanics (tagging
convention, classification mapping, manifest format) to this ADR. §10.1 of the
same paper names #457 as the issue this ADR closes.

A reconnaissance pass (2026-05-28) confirmed three facts that shape the
mechanics:

1. **No operational mechanism exists today.** No path→namespace classifier, no
   per-file frontmatter field, no per-artifact `namespace:` key, no manifest.
   `src/.../storage/file_classifier.py` is unrelated machinery
   (extension→language for validation routing; return set
   `{python, yaml, text, unknown}`).
2. **The term "namespace" is already overloaded** in three unrelated senses:
   `rule_namespace` (an audit-sensor rule-ID prefix, `worker.schema.json`),
   blackboard *subject namespace* (subject-string grouping), and API *domain
   namespace* (endpoint grouping, ADR-053). A new bare `namespace:` key would
   collide with the first of these at the key level.
3. **BYOR (`src/cli/logic/byor.py`) is the closest precedent.** It scaffolds a
   *monolithic* per-repo `.intent/` from a starter kit and does not stamp
   scaffolded artifacts as framework vs project. It is a known future consumer
   of this split, not an existing implementation of it.

This ADR declares the namespace model, the tagging convention, the
classification authority, and the artifacts that realize them.

---

## Decisions

### D1 — The framework/project namespace model is constitutional

Every governance artifact under `.intent/` and `.specs/` belongs to exactly one
**governance namespace**:

- `framework` — ships with CORE; applies to any governed project.
- `project::<name>` — specific to a named repository. CORE's own codebase is
  `project::core`. A BYOR repository is `project::<external>`.

A CORE deployment is `framework + project::core`. A BYOR deployment is
`framework + project::<external>`. This formalizes Topology §8 from principle
into an enforced classification.

### D2 — Namespace is declared in an external manifest, not per-file

The authoritative classification is a **path→namespace manifest**, not a tag
embedded in each artifact. Per-file frontmatter is rejected because:

- `.intent/` artifacts are heterogeneous YAML/JSON with no shared frontmatter
  convention, so a uniform in-file key is not available across the surface.
- Stamping every existing file is a big-bang touch, against the
  backfill-on-touch migration posture in Topology §11.
- #457 close-condition 2 frames the classification as a single governor-authored
  mapping, not as per-file tags.

This mirrors the ADR-068 cognate: a declared vocabulary plus an external
enforcement surface, rather than per-record annotation.

### D3 — The key is `governance_namespace`, to avoid collision

The concept is named **governance namespace**. The manifest and register key is
`governance_namespace` — never bare `namespace` — so it does not collide with
the three existing senses identified in Context (`rule_namespace`, blackboard
subject namespace, API domain namespace). The value space is `framework` and
`project::<name>`.

### D4 — Two artifacts realize the model

Following the ADR-068 register-plus-enforcement shape, and the
`.intent/` topology in Governance-Topology §2.4 (taxonomies hold vocabulary;
governance holds meta-governance inventories):

- **Vocabulary register** — `.intent/taxonomies/governance_namespaces.yaml`.
  Declares the legal value space: `framework`, and the `project::<name>` form
  with `project::core` as the reserved self-name.
- **Classification manifest** — `.intent/governance/namespace_manifest.yaml`.
  Maps every `.intent/` and `.specs/` path to exactly one
  `governance_namespace` value drawn from the register.

### D5 — Classification authority is per-artifact; type is a non-authoritative default

Namespace is a property of an artifact's *purpose*, not its file type. A rule,
ADR, or paper may be framework-general (e.g. a vocabulary-governance rule that
applies to any governed repo) or CORE-specific (e.g. a rule about CORE's own
worker layout). Because type does not determine namespace, the per-file manifest
(D4) is authoritative. Artifact type and directory may seed a *default*
heuristic during initial classification, but the governor's manifest entry is
the constitutional record, and the governor may override any heuristic per file.

### D6 — The manifest is per-layer, to serve separability and BYOR

The framework ships its own classification covering framework artifacts; each
project carries its own classification covering its project-level artifacts.
CORE's deployment manifest is the union: framework entries +
`project::core` entries. A BYOR deployment is framework entries +
`project::<external>` entries authored in that repo's own layer.

This is what gives the split the separability #457 requires — framework and
project artifacts are independently addressable — and it is the mechanism
`src/cli/logic/byor.py` will eventually consume in place of its current
monolithic per-repo scaffold. This ADR does not modify BYOR; it names BYOR as
the downstream consumer.

### D7 — Completeness is enforced by audit

A reporting rule, `governance.namespace.classification_complete`, fails when any
file under `.intent/` or `.specs/` has no entry in
`.intent/governance/namespace_manifest.yaml`. This closes the manifest's
staleness gap: a newly added governance artifact that is not classified surfaces
as a finding, converting the one-shot classification of D8 into a maintained
invariant. The rule is reporting (non-blocking) at introduction; escalation to
blocking is a later decision once the manifest is complete and stable.

### D8 — Migration is one-shot classification, then backfill-on-touch

#457 close-condition 2 requires *every* file classified, so initial population
of the manifest is a deliberate one-shot full pass — a bounded exception to
Topology §11's incremental posture, justified because partial classification
cannot unblock a data-model that must reason over the whole surface. After the
one-shot pass, the D7 completeness rule maintains the invariant: new files are
classified on introduction, which is the §11 backfill-on-touch posture applied
going forward.

---

## State at ADR acceptance

Implementation is deferred; no artifacts are created at acceptance. At
acceptance, none of the three named artifacts
(`governance_namespaces.yaml`, `namespace_manifest.yaml`,
`governance.namespace.classification_complete`) exist yet. They ship at
implementation (lifecycle step 6) under governor direction. Per Topology row 4
strict, this ADR's D-text names every affected `.intent/` artifact above; per
§7.3, deferred implementation is a first-class state and the D-text remains the
canonical reference for what will be created.

---

## Consequences

- **Unblocks the governance-application data model.** With artifacts classified
  by ownership, the future application's schema can model framework and project
  layers with distinct lifecycle and deployment semantics. The follow-on issue
  for that data model (close-condition 3) becomes a scoped problem.
- **BYOR gains a target mechanism.** The per-layer manifest (D6) is the shape
  BYOR's scaffold will adopt; until then BYOR is unchanged and its monolithic
  scaffold remains technical debt tracked separately.
- **No term collision.** `governance_namespace` (D3) is disjoint from the three
  existing uses of "namespace" in the codebase.
- **One-shot classification is bounded.** The cost is a single governor-directed
  pass over the current `.intent/`+`.specs/` surface; the D7 rule prevents
  recurrence of unclassified drift.
- **A new finding class.** `governance.namespace.classification_complete` adds
  reporting findings until the manifest is complete; this is expected
  convergence behavior, not regression.

---

## Verification

This ADR's acceptance satisfies #457 close-condition 1. Full closure of #457
requires, in addition:

- `.intent/taxonomies/governance_namespaces.yaml` authored with the legal value
  space (D4).
- `.intent/governance/namespace_manifest.yaml` authored with every current
  `.intent/` and `.specs/` path classified `framework` or `project::core` (D4,
  D8) — close-condition 2.
- `governance.namespace.classification_complete` authored and mapped, audit
  passing with zero unclassified-file findings (D7).
- A follow-on issue filed for the governance-application data model, unblocked
  by the completed classification (close-condition 3).

---

## References

- `papers/CORE-Governance-Topology.md` §8 — grounding paper; declares the
  namespace principle and defers the mechanics to this ADR (row 2).
- ADR-068 — Principal Role Taxonomy; the cognate register-plus-enforcement
  pattern (vocabulary register + value-restricting enforcement) this ADR follows.
- ADR-070 — Source-projection coherence; the projection-inventory pattern under
  `.intent/governance/` that the classification manifest sits alongside.
- `papers/CORE-Mind-Body-Will-Separation.md`, `papers/CORE-Constitutional-Foundations.md`
  — constitutional context for the artifact surface being classified (per #457).
- Issue #457 — Constitutional layer reorganization: framework vs project
  namespace split.
- `.specs/planning/CORE-band-E-planning-input-2026-05-16.md` Track 1 (Operating
  Models) and Track 3 (User Management) — downstream consumers gated by this split.
- 2026-05-28 reconnaissance pass — empirical confirmation that no operational
  namespace mechanism exists and that "namespace" is already used in three
  unrelated senses.
