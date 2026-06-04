<!-- path: .specs/decisions/ADR-090-f41-artifact-type-registry-as-unified-governance-contract.md -->

# ADR-090 — F-41 artifact type registry as the unified governance contract

**Date:** 2026-06-04
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-04 — drafted under Path A execute-verb authorization, "start the F-41 ADR draft" + subsequent confirmation "we go with Option A" after governor reframed CORE as a general consistency/compliance engine rather than a Python-specific code governor)
**Grounding papers:** `papers/CORE-Features.md` §1 (the open/commercial line as constitutional commitment) and §3.11 (extension interfaces F-41–F-43 as plugin APIs); ADR-084 §D1 (plugin shape requires F-41/F-42/F-43 as published contracts); ADR-085 §"Why this matters" (F-41 is load-bearing for the open-base completeness commitment).
**Related:** ADR-084 (the commercial-surface taxonomy this ADR realises by shipping the first plugin-interface contract); ADR-085 (the open-completeness gate this ADR closes a load-bearing item of); F-42 #416 (pluggable sensor model, attaches to this registry); F-43 #417 (pluggable action model, attaches to this registry); F-04 (Constitution authoring — the rule-author surface that becomes artifact-type-aware once this lands).
**Supersedes (partial):** the informal `artifact_type` field in `.intent/enforcement/config/crawl_scopes.yaml`. That file's role is absorbed into D7 of this ADR.

---

## Context

### CORE is a consistency/compliance engine; source code is one artifact class

The implementation today reads as a Python source-code governor. The thesis is wider. The core loop —

> sense artifacts → audit against declared rules → propose remediation → gate approval → commit

— is artifact-agnostic. Source code is one instance of "an artifact governed by rules." A governance documentation set audited against a regulatory framework is another instance of the same task. The "execution" piece that distinguishes code from documentation (running tests, compiling) is a Python-specific addendum on top of the loop, not the heart of the loop.

This framing was implicit but not architecturally encoded. Until "artifact type" is a declared parameter to the engine instead of an implicit convention, the product cannot honestly claim generality.

### Three artifact-type pipelines already exist, grown separately

CORE today governs three artifact classes through three bespoke code paths that nobody planned together:

| Artifact class | Validator/sensor | Location |
|---|---|---|
| Python source files | `AuditViolationSensor` + AST gate | `src/will/workers/audit_violation_sensor.py` |
| `.intent/` YAML files | `IntentValidator` + META schema enforcement | `src/shared/infrastructure/intent/intent_validator.py` |
| `.specs/` markdown (ADRs, papers) | CCC (Constitutional Coherence Checker) | `src/mind/` |

Each pipeline has its own discovery path, its own validation surface, its own failure reporting shape. There is one informal cross-cutting reference — the `artifact_type` field in `.intent/enforcement/config/crawl_scopes.yaml` — but it is read only by the repo crawler for Qdrant collection routing. The pipelines themselves do not consult it.

The multi-artifact-type reality is therefore not a future feature. It is the present, stitched together with bespoke wiring per type. The honesty question is whether to keep three implicit conventions or to unify them under one declared model.

### Why this matters more than "adding a future extension point"

The risk of building F-41 as a hypothetical extension point — abstraction for consumers that may never arrive — was real and explicitly considered. The exploration that preceded this ADR rejected the framing for two reasons:

1. **The consumers already exist.** Three of them, in this very repo. Building F-41 is not adding an extension point; it is consolidating three pipelines that grew separately under one model.
2. **The thesis demands the parameterisation.** The product claim — *deterministic governance of artifacts against declared rules with autonomous remediation* — is only honest if "artifact type" is a parameter the user controls, not a property the engine hardcodes.

The compliance-documentation use case that justifies CORE's wider applicability (governance docs against regulatory frameworks, consistency across compliance evidence) is a real near-term audience even if not a signed user yet. Without F-41, governing a non-Python artifact requires forking the engine. With F-41, it requires writing one declaration.

### Why now, in this scope

ADR-085 names F-41 as a load-bearing open-completeness gate item. ADR-084 D1 names F-41 as one of the three "published contracts" the plugin shape attaches to. The commercial BYOR (Bring Your Own Repository) product — multi-language code governance against the user's repository — is the canonical commercial consumer of F-41: each additional language ships as an artifact-type declaration plugin against the open contract, per ADR-084 D1.

Per ADR-085 §"Why this matters" the engineering capacity routed to F-41 is the open-base completeness commitment paying off. Per ADR-084 D1 the open base ships the contract; commercial BYOR ships additional declarations against it.

---

## Decisions

### D1 — Artifact type declarations live at `.intent/artifact_types/<type_id>.yaml`

Each artifact type CORE governs is declared in a single YAML file under `.intent/artifact_types/`, validated by `META/artifact_type.schema.json`, loaded at daemon start through `IntentRepository`.

This follows the `.intent/taxonomies/` precedent for cross-cutting declared models (capability_taxonomy, filesystem_operations, cognitive_roles, etc.). The location is deliberate: artifact types are constitutional in the same way principal roles or capability tiers are — they govern how the engine behaves, and changing one is a governance action, not a code change.

Loading is fail-closed: an invalid declaration (missing required field, malformed glob, unknown schema reference) fails `IntentRepository.initialize()` with a clear error. No artifact type silently misregisters.

### D2 — Required declaration fields

The `META/artifact_type.schema.json` mandates these fields on every artifact type:

- **`id`** — short stable identifier (`python`, `intent_yaml`, `spec_markdown`). Used everywhere this type is referenced. Once published it does not change without a governance amendment.
- **`discovery`** — list of glob patterns (relative to repo root) that select instances of this artifact. Replaces the role of `crawl_scopes.yaml`.
- **`identity_key`** — how a single artifact instance is uniquely addressed. For path-based artifacts (source code, YAML, markdown), this is `path`. For sub-document artifacts (e.g. individual ADR sections), this could be `path + heading_anchor`. Closed vocabulary: `path`, `path_plus_anchor`, `uri`.
- **`schema_ref`** — optional pointer to a JSON Schema (or other validation contract) for structured artifacts. Omitted for prose-shaped types. When present, validation routes through this schema.
- **`change_record`** — how an edit to an instance is represented. Closed vocabulary: `text_diff` (line-level for prose and source), `structured_patch` (JSON Patch / RFC 6902 for structured artifacts), `replace` (full-content for atomic small artifacts).
- **`vector_collection`** — Qdrant collection routing. Absorbs the role of the `_QDRANT_COLLECTION_MAP` in the crawler.
- **`supported_sensors`** — list of sensor IDs (F-42 forward-declared). Empty list permitted until F-42 ships.
- **`supported_actions`** — list of atomic action IDs (F-43 forward-declared). Empty list permitted until F-43 ships.

The closed vocabularies for `identity_key` and `change_record` are intentional. The honest set today is small; extending it is a governance amendment, not an ad-hoc field.

### D3 — Three reference declarations ship in this ADR

The registry without consumers is just a schema. F-41 ships three reference artifact-type declarations on day one — one per existing pipeline — proving the model and forcing the schema to accommodate three concrete consumers from the start:

- **`python`** — wraps the existing Python source pipeline. `discovery: ["src/**/*.py", "tests/**/*.py"]`. `identity_key: path`. `schema_ref: null` (AST parser, not schema-validated). `change_record: text_diff`. `vector_collection: code`.
- **`intent_yaml`** — wraps `IntentValidator`. `discovery: [".intent/**/*.yaml"]`. `identity_key: path`. `schema_ref: META/intent_tree.schema.json` (existing). `change_record: structured_patch`. `vector_collection: constitution`.
- **`spec_markdown`** — wraps CCC. `discovery: [".specs/**/*.md"]`. `identity_key: path`. `schema_ref: null` (semantic checks, not JSON-schema-validated). `change_record: text_diff`. `vector_collection: constitution`.

These declarations exercise every required field at least once. The forward-declared `supported_sensors` / `supported_actions` fields start empty; F-42/F-43 populate them.

### D4 — Migrate existing pipelines to consult the registry (Option A)

The three existing pipelines (`AuditViolationSensor`, `IntentValidator`, CCC) are refactored to discover themselves through the registry rather than carry implicit conventions. The motivation is honesty / one model — not pain-as-virtue. Two parallel systems indefinitely would re-introduce the bespoke-pipelines smell this ADR exists to retire.

Migration is phased; each phase preserves behaviour:

- **Phase 1 — Registry + schema only.** Ship `META/artifact_type.schema.json`, the three declarations, and the `IntentRepository` loader. No pipeline change yet. Verification: declarations load cleanly; no runtime change.
- **Phase 2 — `python` migration.** `AuditViolationSensor` reads its discovery glob from the registry instead of hardcoded conventions. Verification: finding set before vs after migration is identical.
- **Phase 3 — `intent_yaml` migration.** `IntentValidator` routes discovery and schema lookup through the registry. Verification: validation outcomes before vs after migration are identical.
- **Phase 4 — `spec_markdown` migration.** CCC routes ADR/paper discovery through the registry. Verification: CCC check outcomes before vs after migration are identical.

Each phase is a separate commit / PR. No big-bang. Behavioural identity is the gate.

### D5 — Forward contract for F-42 and F-43

The `supported_sensors` and `supported_actions` fields are declared in this ADR's schema but populated by F-42 and F-43. This ADR does **not** ship pluggable sensors or pluggable actions — those are the deliverables of F-42 (#416) and F-43 (#417), and each gets its own ADR.

What F-41 commits to: the field shape, the discovery model (registry-driven), and the rule that sensors/actions declaring an artifact type the registry does not know about must fail registration.

What F-41 does not commit to: how sensors/actions themselves are declared, what fields their declarations carry, or what the pluggable interface looks like. Those are open questions for the F-42/F-43 ADRs.

### D6 — Stability commitment per ADR-084 D1

`META/artifact_type.schema.json` is the first ADR-084 D1 "published contract." Once accepted:

- Field additions to the schema are backward-compatible only (new optional fields permitted; existing fields' semantics do not change).
- Field removals or semantic changes require a governance amendment and a deprecation window.
- The closed vocabularies for `identity_key` and `change_record` extend by governance amendment only.

This commitment is what makes commercial BYOR multi-language plugins viable: a third-party Go declaration written today must still load tomorrow.

### D7 — Retire `.intent/enforcement/config/crawl_scopes.yaml`

The crawl scopes file is the most direct precursor of the registry — it already tagged glob patterns with `artifact_type` labels for Qdrant routing. With the registry shipping, its role is absorbed:

- Glob patterns move to each artifact type's `discovery` field
- Qdrant collection labels move to each artifact type's `vector_collection` field
- `RepoCrawlerWorker` reads from `IntentRepository.artifact_types()` instead of loading `crawl_scopes.yaml`

`crawl_scopes.yaml` is removed in Phase 1 of the migration.

---

## Consequences

### Opens

- **Commercial BYOR multi-language support** becomes a plugin shape. Each additional language (Go, JavaScript, Rust, etc.) ships as an artifact-type declaration plus its sensor/action implementations attached to the open F-41/F-42/F-43 contracts. No engine fork.
- **Compliance documentation governance** becomes a near-term reachable use case. A customer declares their own artifact type for their evidence corpus (its own `id`, its own `discovery` patterns, its own schema if structured) and authors required-section/required-citation rules against it. The three reference declarations shipped here (`python`, `intent_yaml`, `spec_markdown`) govern CORE's own surfaces — customers add their own declarations alongside, they do not inherit or reuse CORE's self-governance types.
- **F-42 and F-43 become implementable** as separate ADRs with a real published contract to attach to. Their scope is no longer "design the registry too" — only "design the sensor/action shape that reads from the registry."
- **The open-completeness gate item for F-41** in ADR-085 closes. F-42 and F-43 are the remaining items in this triad.

### Closes

- The three-bespoke-pipelines smell. One declared model. One discovery path.
- The "Python is hardcoded" honesty problem. Python is now a parameter — the first declared type, but not a privileged one.
- The `crawl_scopes.yaml` ambiguity (informal `artifact_type` label that no pipeline consulted authoritatively).

### Defers (filed)

- **F-42 implementation** (#416) — pluggable sensor model. Forward-declared in D5; this ADR commits only to the registry's contract for it.
- **F-43 implementation** (#417) — pluggable action model. Same shape as F-42.
- **Commercial BYOR multi-language** — commercial scope, attaches to this contract via plugins. Not an open ADR.
- **Additional artifact types beyond the three references** — added by governance amendment as consumers materialise. No speculative declarations.

### Defers (newly identified — to file as GH issues during implementation)

- `RepoCrawlerWorker` constant retirement: `_CRAWL_SCOPES` and `_QDRANT_COLLECTION_MAP` are deleted as part of Phase 1. Track as a sub-issue of F-41.
- Documentation update: `.intent/CHANGELOG.md` entry for the schema's first published-contract status per ADR-084 D1.

### Risks

- **Migration regression risk.** Three pipelines refactored to consult a new layer. The mitigation is behavioural-identity verification per phase: finding/validation outputs before vs after must match. Any divergence is a phase-blocking defect.
- **Schema over-fitting risk.** Three reference declarations is the minimum honest pressure test. Risk remains that a future fourth artifact type exposes a missing field. Mitigation: D6 permits backward-compatible field additions without governance ceremony.
- **Implicit-convention re-emergence risk.** A pipeline can technically still hardcode artifact discovery and ignore the registry. Mitigation: an audit rule (`architecture.artifact_discovery_through_registry`) lands alongside D4 phases 2–4 to catch any pipeline that bypasses the registry.

---

## Verification

This ADR closes — and F-41 ships — when all of the following hold:

1. **Schema present and validating:** `META/artifact_type.schema.json` exists. Loading it through the standard META validator succeeds. An intentionally-malformed declaration (missing `id`, unknown `identity_key` value, etc.) fails with a clear error citing the field.
2. **Three reference declarations load:** `.intent/artifact_types/{python,intent_yaml,spec_markdown}.yaml` all parse and validate. `IntentRepository.initialize()` exposes them via a typed accessor.
3. **`crawl_scopes.yaml` retired:** the file is deleted. The crawler reads glob patterns and Qdrant routing from the registry. The crawl behaviour before vs after migration is identical (same file set indexed, same vector collections written).
4. **`python` pipeline migrated:** `AuditViolationSensor`'s discovery globs come from the registry. Finding output on this repo before vs after migration is identical.
5. **`intent_yaml` pipeline migrated:** `IntentValidator`'s discovery + schema lookup routes through the registry. Validation output is identical.
6. **`spec_markdown` pipeline migrated:** CCC's ADR/paper discovery routes through the registry. CCC check outcomes are identical.
7. **F-42/F-43 forward fields present:** `supported_sensors` and `supported_actions` fields are in the schema, populated as empty lists in the three reference declarations.
8. **Stability commitment recorded:** `.intent/CHANGELOG.md` carries an entry marking `META/artifact_type.schema.json` as the first ADR-084 D1 published contract.
9. **Anti-regression rule in place:** an audit rule fires on any pipeline that performs artifact discovery without consulting the registry.

When all nine hold, F-41 #415 closes. F-42 #416 and F-43 #417 then become implementable as their own ADRs.
