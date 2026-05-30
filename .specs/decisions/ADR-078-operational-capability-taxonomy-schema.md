<!-- path: .specs/decisions/ADR-078-operational-capability-taxonomy-schema.md -->

# ADR-078 — Operational-Capability Taxonomy Schema

**Date:** 2026-05-30
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (operational-capability schema session 2026-05-30)
**Grounding paper:** `papers/CORE-Capability-Scoped-Filesystem-Authority.md` §9 bullet 2 (the data-model schema deferral this ADR fulfills)
**Related:** ADR-068 (first `.intent/taxonomies/` precedent — `cognitive_roles.yaml`; fail-closed loader pattern); ADR-077 (audit-time protected-namespace access; declares the sibling `.intent/taxonomies/filesystem_operations.yaml` whose `fs_operation_class` vocabulary this schema references); Paper `CORE-Cognitive-Role-Capability-Resource-Taxonomy.md` (parent framework for `.intent/taxonomies/`)

---

## Context

`papers/CORE-Capability-Scoped-Filesystem-Authority.md` (landed 2026-05-30, commit 8ed705a8) defines three principles — single chokepoint, capability-scoped authority, mode dimension — and defers six items to follow-on ADRs in §9. This ADR fulfills exactly one of those deferrals: **the data-model schema for the operational-capability taxonomy YAML** (§9 bullet 2). It owns nothing else from the §9 list; the chokepoint-implementation ADR, the mode-flag startup mechanism (#492), the governor-token machinery, the identity-propagation implementation, and the migration plan from today's `scope.excludes`-based perimeter all sit in their own ADRs.

The forcing inventory at `var/tmp/operational_capabilities_inventory_2026-05-30.md` enumerates the live `@atomic_action` surface across nine clusters: a capability count plus four chokepoint primitives (`file.create`, `file.edit`, `file.read`, `file.tag_metadata`). It is not governance — its self-declared authority is "planning document, NOT governance" — and it cannot become governance until a stable schema exists for it to land on. This ADR provides that schema.

Four pre-existing patterns constrain the choice space:

- **`.intent/taxonomies/` precedent (ADR-068 applied to cognitive_roles 2026-05-29):** the four sibling taxonomies (`cognitive_roles.yaml`, `capability_taxonomy.yaml`, `governance_namespaces.yaml`, `principal_roles.yaml`) are validated by a fail-closed Python loader, not by a `.intent/META/*.schema.json`. The loader is the sole sanctioned reader; structural deviation raises a typed `<Name>TaxonomyError`. No META schemas exist for these files.
- **ADR-077-declared `filesystem_operations.yaml`** establishes the operation-class vocabulary (`read`, `create`, `modify`, `delete`) and the call-name → op-class mapping. This ADR's `fs_profile` field references operation-classes from that vocabulary. Both YAMLs are pre-implementation artifacts of pre-implementation ADRs; they will be authored in their respective implementation phases. Together they form the operation half and the capability half of the capability-scoped chokepoint model.
- **`.intent/META/enums.json`** is the canonical home for cross-document closed vocabularies (per `feedback_enum_subset_canonicalize_and_fail_closed` precedent, runtime pattern shipped 2026-05-27).
- **`.intent/enforcement/config/action_risk.yaml`** is the existing source of truth for per-action risk classification (`safe`, `moderate`, `dangerous`). Each capability already carries a risk classification there.

Three inventory findings have direct schema consequences:

- **Finding 2** — `format.code` and `fix.format` are the same function with two `@atomic_action`/`@register_action` decorators; one capability, two ids.
- **Finding 3** — `crate.create` and `create.crate` are two functions with identical filesystem profiles; naming inconsistency that violates a `<noun>.<verb>` convention.
- **Finding 4** — `test_execution` uses underscore where every other action_id uses dot; layered under a `test.system` wrapper.

A schema that does not enforce a grammar leaves these warts in the taxonomy on day one. A schema that enforces a grammar forces the rename change-set into the same commit. The latter is preferred (per `feedback_no_tooling_for_retiring_artifacts` discipline: fix the surface as you set the contract).

## Decisions

### D1 — Location

The taxonomy lives at:

```
.intent/taxonomies/operational_capabilities.yaml
```

Mirroring the four sibling taxonomy locations. No subdirectory, no per-capability files. One document, one map.

### D2 — Top-level document shape

The document header is the three-of-four sibling-taxonomy shape — `version`, `status`, `authority`, `title`, `description` — copied verbatim from sibling pattern (`cognitive_roles.yaml`, `governance_namespaces.yaml`, `principal_roles.yaml`):

```yaml
version: "1.0.0"
status: active
authority: constitutional
title: CORE Operational Capability Taxonomy
description: >
  Canonical declaration of operational capabilities in CORE. An operational
  capability is a named unit of what CORE-as-a-system does — distinct from a
  cognitive capability per CORE-Capability-Taxonomy.md, which describes what an
  LLM model can do. This file is the authoritative source of the operational-
  capability name set and the filesystem profile per capability used by the
  runtime chokepoint to authorize writes. Framework authority:
  .specs/papers/CORE-Capability-Scoped-Filesystem-Authority.md. Schema declared
  by ADR-078.

capabilities:
  <capability_id>:
    description: <one-line declaration of what the capability does and why it exists>
    risk: safe | moderate | dangerous
    fs_profile:
      read:    [ <fs_pattern_entry>, ... ]
      create:  [ <fs_pattern_entry>, ... ]
      modify:  [ <fs_pattern_entry>, ... ]
      delete:  [ <fs_pattern_entry>, ... ]
```

No additional top-level fields. Extension is a schema-change concern (a future amendment to this ADR), not a data-change concern.

**Note on `authority: constitutional`.** This value mirrors the three-of-four sibling taxonomies that declare an `authority:` line. It is **not** currently present in `.intent/META/enums.json`'s `authority` enum (`{meta, constitution, policy, code}`), which `$ref`-s into `rule_document.schema.json` and governs `.intent/rules/`. The mismatch does not produce a load-time failure because no META schema covers `.intent/taxonomies/` — validation is loader-only per ADR-068 pattern. The cross-surface drift is documented here and recorded for a future governor decision on whether to (a) add `constitutional` to the `authority` enum, (b) align the four taxonomies to `constitution`, or (c) declare a separate `taxonomy_authority` enum. This ADR does not resolve it; it inherits the dominant sibling form.

### D3 — Capability entry shape

Each entry under `capabilities:` is keyed by `capability_id` (the YAML key) and carries exactly three required fields:

| Field | Type | Notes |
|---|---|---|
| `description` | string | One line. Why the capability exists, not how it's implemented. |
| `risk` | string | Must resolve to a defined entry in `.intent/enforcement/config/action_risk.yaml`. Closed set: `safe`, `moderate`, `dangerous`. |
| `fs_profile` | mapping | The filesystem authorization profile. See D4. |

Capability entries carry no other fields. In particular:
- No `status` field. Dormant capabilities are absent from the taxonomy (D9).
- No `phase`, `cluster`, or `layer` field. The inventory's clustering is a planning aid, not governance.
- No `notes` or free-form description block. Single-line `description:` is the documented surface.

### D4 — `fs_profile` shape

The `fs_profile` mapping carries exactly four keys — **the singular operation-class names declared in the `fs_operation_class` enum (D5), verbatim**. No pluralization, no synonym surface, no mapping layer between enum values and YAML keys:

```yaml
fs_profile:
  read:    [ {path_pattern: ".intent/rules/code/style.json", modes: [dev, live]} ]
  create:  []
  modify:  [ {path_pattern: "src/**/*.py",  modes: [dev, live]},
             {path_pattern: "tests/**/*.py", modes: [dev, live]} ]
  delete:  []
```

- **All four keys are required**, present as lists. An empty list explicitly declares "no authority for this operation," which is structurally different from absence (which the loader rejects). Forcing all four keys makes the absence of authority a positive declaration.
- The four key names are sourced from `fs_operation_class` (D5) — one closed vocabulary, one spelling, used identically in `filesystem_operations.yaml` (call-name → op-class) and `operational_capabilities.yaml` (per-capability fs_profile keys). The D9 loader derives the expected key set from the enum directly.
- Each pattern entry has exactly two required fields:
  - `path_pattern`: a glob string. Same convention as `scope.excludes` patterns elsewhere in `.intent/`. No regex; no negation.
  - `modes`: a list of mode strings from the closed `operational_mode` enum (D5).
- An entry with `modes: []` is rejected by the loader — an entry with no authorized modes is a configuration mistake, not a declaration. To deny an operation in all modes, omit the entry; do not declare it with an empty modes list.

### D5 — Closed vocabularies promoted to `.intent/META/enums.json`

Two new enums land in `.intent/META/enums.json`:

```json
{
  "fs_operation_class": {
    "values": ["read", "create", "modify", "delete"],
    "authority": "ADR-077 + ADR-078",
    "description": "Operation-class vocabulary used by both filesystem_operations.yaml (call-name → op-class) and operational_capabilities.yaml (per-capability fs_profile keys). Same spelling at both surfaces; no pluralization or synonym variants."
  },
  "operational_mode": {
    "values": ["dev", "live"],
    "authority": "papers/CORE-Capability-Scoped-Filesystem-Authority.md §6 + ADR-078",
    "description": "Process-level mode flag. dev = governor in the loop; live = no governor in the loop. Immutable for the process lifetime per paper §6."
  }
}
```

**First-materialization.** Both this ADR and ADR-077 target `fs_operation_class` in `.intent/META/enums.json` with the same values. Whichever ADR is implemented first creates the entry; the other implementation no-ops for that key. The `authority:` field records both ADRs' co-authority. Divergent values or descriptions between the two implementations are a load-time failure of any loader that consumes the enum, and trigger the standard cross-ADR coordination path. `operational_mode` has no such ambiguity — this ADR is its sole declarer.

These enums are referenced by the loader (D10) and may be `$ref`-ed by future META schemas or rule documents. Sole-source declaration; no inline subset enums per `feedback_enum_subset_canonicalize_and_fail_closed`.

The fs_profile keys in D4 are not a separate vocabulary — they are `fs_operation_class.values` consumed as YAML keys. The D10 loader iterates over `fs_operation_class.values` to determine which keys an `fs_profile` mapping must declare; this is structurally tighter than maintaining a parallel "valid_fs_profile_keys" list anywhere.

### D6 — Capability-ID grammar (regex-enforced)

The capability_id (the YAML key) must match:

```
^[a-z][a-z_]*\.[a-z][a-z_]+$
```

Exactly one dot, no nested namespaces. Both halves lowercase + underscore. No digits in this iteration (none of the inventoried capabilities use digits; if a future capability needs them, the regex is amended in a separate ADR). The loader fails closed on any violation.

This regex is the forcing function for D7. It rejects three inventoried action_ids on grammar grounds: `format.code` (legal but duplicate), `test_execution` (underscore, no dot), `create.crate` (legal but inconsistent with sibling `crate.create`).

### D7 — Naming consolidation in the same change-set

The following renames land in the change-set that introduces this ADR's `operational_capabilities.yaml`:

| Today | Replacement | Rationale |
|---|---|---|
| `format.code` (`@atomic_action`) | retired | Same function as `fix.format` (per inventory Finding 2). The `@atomic_action(action_id="format.code")` decorator is removed; `@register_action(action_id="fix.format")` remains. |
| `test_execution` (`@atomic_action`) | `test.execute` | Restore dot grammar (D6); `test_execution` violates the regex. |
| `create.crate` (`@atomic_action`) | `crate.create_from_spec` | Match `<noun>.<verb>` convention; `crate.create` (the general entry point) keeps its name. The convenience wrapper for SpecificationAgent gets a name that identifies it as the specialized variant. |

`test.system` is preserved unchanged: it is a legal dispatch wrapper, and the layering (`test.system` → `test.execute`) becomes explicit and consistent under the new grammar.

The post-consolidation capability count is **not** declared as a literal in this ADR. It is derived from a rule:

> `live capability count = inventoried capabilities − dormant capabilities (per D9) − duplicate-id retirements (per D7 row 1)`

The exact integer is a verification check against the inventory at implementation time (see Verification item 2), not a number this ADR claims to know.

Implementation work attached to this ADR:
- Update `body/atomic/fix_actions.py:55-90` to drop the duplicate `@atomic_action(action_id="format.code")` decorator.
- Update `shared/infrastructure/validation/test_runner.py` to rename the `@atomic_action` to `test.execute`; update the caller wrapper at `mind/enforcement/audit.py:75-93`.
- Update `body/services/crate_creation_service.py:197` to rename the `@atomic_action` to `crate.create_from_spec`.
- Update `.intent/enforcement/config/action_risk.yaml` to reflect the three renames.
- Grep `src/` and `.intent/` for any other references to the retired ids; update each.

**Note 2026-05-30 — D6 is the governing rule; D7's table was authoring-time enumeration, not closed scope.**

During implementation of this ADR's change-set, a fresh `grep` of every `action_id` literal in `src/` revealed 5 additional ids that fail the D6 regex (`^[a-z][a-z_]*\.[a-z][a-z_]+$`). The 3 ids enumerated in D7's table above were the renames visible at ADR authoring; they were not the complete set.

D6 is the governing rule. **Any capability id failing D6 is renamed in the change-set that lands this ADR, whether or not D7's table enumerated it at authoring time.** D7's table records the renames known at the moment of ADR authoring; it is not an exclusive list. This resolves the "is the table exhaustive?" ambiguity that would otherwise leave grammar-driven renames without an explicit ADR basis.

The 5 additional renames landing in the same change-set:

| Today | Replacement | D6 failure mode |
|---|---|---|
| `check.body-contracts` | `check.body_contracts` | Hyphen — regex allows only `[a-z_]` |
| `fix.body-ui` | `fix.body_ui` | Hyphen — same |
| `manage.define-symbols` | `manage.define_symbols` | Hyphen — same |
| `sync.vectors.code` | `sync.vectors_code` | Nested dot — D6 requires exactly one dot |
| `sync.vectors.constitution` | `sync.vectors_constitution` | Nested dot — same |

`sync.vectors.*` flattening rather than D6 amendment is a governor decision recorded at implementation (2026-05-30): the cluster's other live siblings (`sync.db`, `sync.knowledge_graph`) are already flat, making the nested form an outlier within its own cluster. Amending D6 to admit nesting for two ids and reverting on convention drift is worse than a one-time rename. A future D6 amendment to admit nesting will require actual grouping pressure justifying a sub-namespace.

**D7 row 1 implementation reconciliation.** D7's row 1 text above describes the implementation as "the `@atomic_action(action_id="format.code")` decorator is removed." Implementation chose the equivalent end-state via retargeting rather than removal: the `format.code` id is retired, but the `@atomic_action` decorator on `action_format_code` in `body/atomic/fix_actions.py` is retained with its `action_id` set to `fix.format` (matching the function's `@register_action`). This preserves the dual-decorator convention shared by every other action in that module and avoids making `action_format_code` an anomaly without `@atomic_action` governance. End-state is unchanged from D7's intent: exactly one capability id (`fix.format`) for this function, with `format.code` retired from the action_id namespace.

Implementation surface for the 5 additional renames is a `src/` ripple of ~15 files spanning `api/`, `body/`, `cli/`, `will/`, and `shared/`, plus `.intent/` ripple into `auto_remediation.yaml`, `flow.sync_state.yaml`, and `governance_paths.yaml`. `CHANGELOG.md` historical mentions are deliberately left unchanged per append-only convention — those entries are accurate as of when written; renaming them falsifies the record. All 8 renames (3 original + 5 grammar-driven) land in the same change-set as this ADR's implementation.

### D8 — Chokepoint primitives are not capabilities

`file.create`, `file.edit`, `file.read`, `file.tag_metadata` are the chokepoint itself (paper §4 + inventory Cluster 0). They authorize writes — they are not themselves subject to capability-scoped authorization. They do **not** appear in `operational_capabilities.yaml`.

The schema's loader (D10) rejects any capability_id matching `^file\.` to enforce this exclusion as a structural property rather than a comment.

The chokepoint-implementation ADR (a separate paper §9 deferral) governs how the chokepoint distinguishes "this is a `file.*` primitive being invoked from inside a capability's atomic action" from "this is a `file.*` call with no capability context" (which paper §7 deems unauthorized). This ADR does not.

### D9 — Dormant capabilities excluded

A capability that is structurally non-functional today (e.g. `fix.policy_ids` per #493) does **not** appear in this taxonomy. The inventory enumerates them as a planning concern; governance enumerates only live capabilities.

Dormancy is tracked as governance debt (one issue per dormant capability), not as a taxonomy field. The schema has no `status: dormant` or `enabled: false` field.

Rationale: a `dormant`-marked entry would create two parallel authorization vocabularies in one file (live + dormant), each with subtly different semantics. The chokepoint should answer one question — "does this capability have authority?" — without parsing a status overlay. Dormant capabilities are absent until their governance debt clears; their reintroduction is a YAML edit, reviewable in the same way as any new capability.

This makes `operational_capabilities.yaml` the **live-authorization surface**, not a complete enumeration of the `@atomic_action` registry. The two diverge by exactly the dormant set. That divergence is documented in the taxonomy's `description:` header.

### D10 — Validation strategy: fail-closed Python loader

Per ADR-068, the taxonomy is validated by a fail-closed Python loader, not by a META JSON schema. Sole sanctioned reader:

```
src/shared/infrastructure/intent/operational_capabilities.py
```

Public entry point:

```python
def load_operational_capabilities(
    repo_root: Path | None = None,
) -> frozenset[OperationalCapability]:
    """Return the declared operational-capability set as a frozenset of immutable records."""
```

The loader's contract:

- Reads `.intent/taxonomies/operational_capabilities.yaml`.
- Reads `.intent/META/enums.json` and resolves `fs_operation_class.values` and `operational_mode.values` to derive the expected `fs_profile` key set and the accepted `modes` vocabulary. Both vocabularies are sourced from enums.json, not hardcoded in the loader.
- Returns a `frozenset[OperationalCapability]` where `OperationalCapability` is a frozen dataclass with fields `(id, description, risk, fs_profile)`. To keep `OperationalCapability` hashable (required for `frozenset` membership), `fs_profile` is stored internally as `tuple[tuple[str, tuple[FsPatternEntry, ...]], ...]` — a hashable tuple of `(op_class, pattern_entries)` pairs, ordered by `fs_operation_class.values`. `FsPatternEntry` is itself a frozen dataclass with `path_pattern: str` and `modes: tuple[str, ...]` (tuple, not list, for hashability). Mapping access is exposed via an `as_mapping()` property returning a `Mapping[str, tuple[FsPatternEntry, ...]]` view. The tuple-of-pairs shape — rather than a fixed dataclass with one field per op-class — is deliberate: the key set is sourced from enums.json at load time, so adding a fifth op-class to the enum requires a coordinated YAML migration across every capability entry but does not require a Python representation change. The pairs are constructed by iterating `fs_operation_class.values` and pulling the corresponding YAML key; a missing key is a load-time failure (per the D10 rejection list).
- Raises `OperationalCapabilityTaxonomyError` (a `GovernanceError` subclass) on any of:
  - Missing file
  - Malformed YAML
  - Top-level document not a mapping
  - Missing or non-mapping `capabilities:` block
  - Empty `capabilities:` map
  - Any capability_id failing the D6 regex
  - Any capability_id matching `^file\.` (D8)
  - Any capability entry missing `description`, `risk`, or `fs_profile`
  - Any capability entry carrying unknown fields
  - Any `risk` value not present in `.intent/enforcement/config/action_risk.yaml`
  - Any `fs_profile` mapping whose key set is not exactly `fs_operation_class.values`
  - Any pattern entry missing `path_pattern` or `modes`
  - Any `modes` list empty or containing a value outside `operational_mode.values`
  - Any pattern entry carrying unknown fields
  - Inability to load `.intent/META/enums.json` or resolve either of the two referenced enum entries

No META JSON schema is added. The loader is the validation chokepoint; precedent matches `cognitive_roles.py`.

The loader cross-references `action_risk.yaml` and `enums.json` on every load. This creates a load-order coupling: both must be readable before `operational_capabilities.yaml` is loadable. The coupling is intentional — taxonomy entries must not drift from the risk classification surface, and the fs_profile keys must not drift from the enum vocabulary.

## State at ADR acceptance

| Item | State |
|---|---|
| Schema declared | D2–D4, D8 |
| Closed vocabularies declared | D5 — pending `enums.json` patch |
| Capability-ID grammar declared | D6 |
| Naming consolidation list declared | D7 — pending decorator + YAML rename change-set |
| Chokepoint-primitive exclusion declared | D8 |
| Dormant-capability handling declared | D9 |
| Validation strategy declared | D10 |
| `.intent/META/enums.json` `fs_operation_class` + `operational_mode` | **Not yet patched** |
| `.intent/taxonomies/operational_capabilities.yaml` | **Not yet authored** |
| `src/shared/infrastructure/intent/operational_capabilities.py` loader | **Not yet authored** |
| Three D7 renames in `src/` + `action_risk.yaml` | **Not yet applied** |
| `authority` enum cross-surface drift (D2 Note) | **Documented, deferred** |

The schema exists. The artifact does not. The chokepoint that will consume it is a separate ADR.

## Consequences

**Positive:**

- The paper's §9 bullet 2 deferral (data-model schema) is closed. The chokepoint-implementation ADR can now reference a stable shape.
- "Who can write to path X" becomes a YAML query against `operational_capabilities.yaml`, not a grep across `src/`. The answer is enumerable and attributable, satisfying paper §5's "structural property, not a discipline" claim.
- Capability-ID drift is structurally prevented: the loader rejects malformed ids on read. The three existing warts (D7) get resolved alongside the framing, not as later cleanup.
- The `fs_operation_class` and `operational_mode` enums promote to `enums.json` and become referenceable by future META schemas and rule documents, closing the "subset enum inlined at consumer" anti-pattern at a new surface before it appears.
- `fs_profile` keys are sourced from `fs_operation_class.values` rather than hardcoded — one closed vocabulary, one spelling, used identically in `filesystem_operations.yaml` and `operational_capabilities.yaml`. No synonym surface; no pluralization map.
- ADR-077-declared `filesystem_operations.yaml` (call-name → op-class) and this ADR's `operational_capabilities.yaml` (capability → op-class authority) together form the two halves of the chokepoint's policy decision table. Both halves are governed, both are loader-validated, both are reviewable as YAML edits.

**Negative:**

- The D7 rename change-set has non-zero blast radius: three `@atomic_action` decorator updates, plus call-site sweeps, plus `action_risk.yaml` updates, plus blackboard reports that may reference the old ids by string. Mitigation: blast radius is internal (no public API exposes these ids per ADR-054 D3); a single audit run with the updated `action_risk.yaml` surfaces any stragglers.
- D10's load-order coupling is now three-way: `action_risk.yaml` and `enums.json` must both load before `operational_capabilities.yaml`. Mitigation: this is the right direction — capabilities should not declare a risk class that doesn't exist in the risk surface, nor an fs_profile key that doesn't exist in the enum vocabulary — and the fail-closed loader makes the coupling loud rather than silent.
- D9's exclusion of dormant capabilities means `fix.policy_ids` simultaneously exists as a CLI command, an `@atomic_action`-decorated function, and an entry in `action_risk.yaml`, while being absent from this taxonomy. The taxonomy is therefore not a complete enumeration of the system's `@atomic_action` surface — it is a complete enumeration of the **live** authorization surface. Mitigation: the dormancy itself is tracked as #493; the taxonomy's role as the live-capability source of truth is documented in its `description:` header.
- Every new `@atomic_action` going forward must carry an entry in this YAML, or the runtime chokepoint (once implemented) will deny it with no capability context. The chokepoint-implementation ADR will codify this; the schema ADR documents the discipline.
- The D2 Note records a cross-surface drift: `authority: constitutional` is not in `.intent/META/enums.json`'s `authority` enum. Mitigation: drift is inherited from sibling taxonomies, unenforced at load (loader-only validation per ADR-068 pattern), and recorded for separate governor resolution. This ADR does not propagate the drift further than its inheritance.

## Verification

Deferred to implementation. At implementation:

1. `.intent/META/enums.json` declares `fs_operation_class` (`["read", "create", "modify", "delete"]`) and `operational_mode` (`["dev", "live"]`) per D5.
2. `.intent/taxonomies/operational_capabilities.yaml` exists, declares the D2 header verbatim, and contains exactly `(inventoried − dormant − duplicate-id retirements)` entries under `capabilities:`. The exact integer is computed against `var/tmp/operational_capabilities_inventory_2026-05-30.md` (or its successor) at implementation time; any mismatch is investigated before the YAML lands.
3. Every capability_id in the YAML matches the D6 regex.
4. No capability_id in the YAML matches `^file\.` (D8 exclusion).
5. Every `fs_profile` mapping in the YAML has exactly the four keys from `fs_operation_class.values` — no other keys, no plural variants.
6. `fix.policy_ids` is absent from the YAML (D9 dormancy + #493).
7. `format.code` is absent from the YAML and from any `@atomic_action`/`@register_action` decorator in `src/`; `fix.format` carries the union of the two former responsibilities (D7).
8. `test_execution` is absent from any decorator in `src/`; `test.execute` is present and matches the inventory's Finding 4 implementation (`shared/infrastructure/validation/test_runner.py`).
9. `create.crate` is absent from any decorator in `src/`; `crate.create_from_spec` is present at `body/services/crate_creation_service.py:197`.
10. `.intent/enforcement/config/action_risk.yaml` carries entries for `fix.format`, `test.execute`, `crate.create_from_spec`, and does not carry entries for `format.code`, `test_execution`, `create.crate`.
11. `src/shared/infrastructure/intent/operational_capabilities.py` exists; `load_operational_capabilities()` is the sole sanctioned reader; it sources `fs_profile` keys and accepted `modes` values from `.intent/META/enums.json` rather than hardcoded constants; it raises `OperationalCapabilityTaxonomyError` for each of the failure modes enumerated in D10. Unit tests exercise each failure mode.
12. `core-admin code audit` produces no findings related to operational-capability vocabulary drift.

## References

- Paper: `.specs/papers/CORE-Capability-Scoped-Filesystem-Authority.md` §9 bullet 2 (the data-model schema deferral this ADR fulfills); §5 (capability-scoped least authority); §6 (mode dimension); §4 (chokepoint).
- Paper: `.specs/papers/CORE-Cognitive-Role-Capability-Resource-Taxonomy.md` (parent taxonomy framework for `.intent/taxonomies/`).
- ADR-068 — Principal Role Taxonomy; established the `.intent/taxonomies/` location and fail-closed loader pattern that this ADR follows.
- ADR-077 — Config-driven protected-namespace access; declares the sibling `.intent/taxonomies/filesystem_operations.yaml` whose `fs_operation_class` vocabulary this schema references. Both YAMLs are pre-implementation artifacts of pre-implementation ADRs.
- ADR-074 — Failure-mode scalar → failure_modes map across phase YAMLs; precedent for closed-vocabulary enum promotion to `enums.json`.
- Inventory: `var/tmp/operational_capabilities_inventory_2026-05-30.md` — the bottom-up survey grounding this schema. The schema is grounded *in* the inventory; the inventory's counts are not promoted into this ADR's text.
- `.intent/META/enums.json` — destination for the two new enums declared in D5; current home of the `authority` enum referenced in D2's drift note.
- `.intent/enforcement/config/action_risk.yaml` — risk-classification source-of-truth referenced by D3.
- `.intent/taxonomies/cognitive_roles.yaml`, `governance_namespaces.yaml`, `principal_roles.yaml` — sibling taxonomies whose `authority: constitutional` header pattern this ADR inherits (D2).
- `.intent/taxonomies/capability_taxonomy.yaml` — sibling taxonomy that omits the `authority:` line entirely; noted as the four-sibling asymmetry that the D2 drift note records.
- `src/shared/infrastructure/intent/cognitive_roles.py` — the loader pattern this ADR's D10 loader copies.
- Issue #492 — mode-provenance ADR (separate paper §9 deferral; prerequisite for the chokepoint-implementation ADR, not for this schema).
- Issue #493 — `fix.policy_ids` dead CLI command; D9 absence rationale.
- Issue #494 — `intent_guard.py:368` dead `is_metadata` variable (out of scope here; recorded for chokepoint-implementation ADR).
