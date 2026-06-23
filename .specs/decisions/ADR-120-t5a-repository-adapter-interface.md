---
kind: adr
id: ADR-120
title: 'ADR-120 — T5a: Repository adapter interface — the concrete F-41/F-42/F-43 binding'
status: proposed
---

<!-- path: .specs/decisions/ADR-120-t5a-repository-adapter-interface.md -->

# ADR-120 — T5a: Repository adapter interface — the concrete F-41/F-42/F-43 binding

**Status:** Proposed
**Date:** 2026-06-21
**Grounding papers:** `CORE-BYOR.md` §3 (Repository as the single parametrization seam),
  §7 (GRC as first non-code Repository type), §9 (T5a as "the concrete F-41/F-42/F-43 binding").
**Builds on:** ADR-090 (F-41 artifact type registry), ADR-091 (F-42 pluggable sensor model),
  ADR-092 (F-43 exit criterion — D4 declaration site deferred to implementation session).
**Required by:** T5b (GRC document/records Repository type + regulation→Intent representation).
**Resolves:** ADR-092 D4 (F-43 declaration site); ADR-091 D4/D5 (supported_sensors cross-
  validation, scheduled Phase 7 blocking); ADR-090 D5 (supported_actions still empty forward).

---

## Context

### What F-41/F-42/F-43 shipped, and what remains open

**ADR-090 (F-41)** declared the artifact type registry. Eleven types are live; every declaration
carries `supported_sensors` (authored) and `supported_actions: []` (forward-declared, ADR-090 D5).
The schema is a published contract (ADR-084 D1).

**ADR-091 (F-42)** shipped the pluggable sensor model: `Worker` base class, canonical subject
format `<artifact_type>::<sub_namespace>::<identity_key_value>`, `mandate.scope.artifact_type`
field on sensor declarations. Cross-validation rule `governance.taxonomy.sensor_supported_by_
declaration` is authored and on a Phase-7 blocking-promotion schedule.

**ADR-092 (F-43)** amended the exit criterion to registry-coupling enforcement: `ActionExecutor
.execute()` refuses dispatch when an action's declared `artifact_type` is not registered in F-41.
At least one atomic action must carry the field. The declaration site was explicitly deferred to
"the implementation session" (D4). The `governance.taxonomy.action_supported_by_declaration` rule
and population of `supported_actions` arrays are parked until a second non-Python action ships (D2).

Three items converge at T5a:

1. **F-43 declaration site** (ADR-092 D4) — not yet resolved; no action declares `artifact_type`;
   the `ActionExecutor` refusal gate is not yet wired.
2. **supported_sensors cross-validation** (ADR-091 D4 + ADR-090 D5) — the authored `supported_
   sensors` lists exist and are accurate (as of current declarations), but `IntentRepository
   .initialize()` does not yet verify them. ADR-091's Phase 7 blocking promotion is the runtime-
   audit layer; initialize()-time validation is the earlier fail-closed chokepoint that is missing.
3. **Adapter contract gap** — F-41/F-42/F-43 are three separately-ratified infrastructure ADRs
   with no unified statement of what "registering a new Repository type" requires. T5b needs that
   contract to know what to author.

### Why now

T5b (GRC document corpus) is the first non-Python Repository type to land. It needs to know
concretely: what artifact type declaration to write, what sensor shape to implement, where to
declare the action's `artifact_type`. Without a defined adapter contract, T5b authors three
declarations against three separately-documented infrastructure ADRs and hopes they cross-validate.
T5a makes the contract explicit and wires the enforcement that catches authoring errors early.

The GRC use case adds one new requirement not addressed by the code-Repository artifact types:
**project-authored discovery**. A Python artifact type has a fixed `discovery: ["src/**/*.py"]`
baked into the framework declaration — the same for every CORE installation. A GRC document
corpus artifact type has a customer-specific directory layout; the discovery patterns are the
project author's decision, not CORE's. The adapter contract must accommodate this without
requiring schema changes.

---

## Decision

### D1 — F-43 declaration site: extend `action_risk.yaml` per-action entry

The `.intent/enforcement/config/action_risk.yaml` per-action entry gains an optional
`artifact_types` field (list of artifact type IDs):

```yaml
# .intent/enforcement/config/action_risk.yaml
actions:
  fix.format:
    impact_level: moderate
    artifact_types: [python]     # ← new optional field; absent = unconstrained
  file.create:
    impact_level: moderate
    # artifact_types absent → unconstrained; dispatches for any artifact type
```

`ActionRegistry.apply_risk_config()` (the existing method that overlays `impact_level`) is
extended to also overlay `artifact_types` onto `ActionDefinition.artifact_type`. The
`ActionRegistry.apply_artifact_type_config()` stub — which anticipated the overlay arriving from
`operational_capabilities.yaml` — is retired and removed.

**Closed vocabulary:** values in `artifact_types` must be IDs present in
`IntentRepository.list_artifact_types()`. `apply_risk_config()` fails with a `GovernanceError`
on any unregistered ID — same fail-closed guarantee as the sensor side.

**Unconstrained actions:** entries without `artifact_types`, or with `artifact_types: []`, are
unconstrained — `ActionExecutor.execute()` dispatches them for any artifact type. This is the
correct default for internal bookkeeping actions (`file.create`, `action.execute`, etc.) that
operate on the infrastructure layer rather than a governed artifact type.

**Rationale for this site over the three ADR-092 D4 alternatives:**

- Keeps artifact_type binding in `.intent/` (not Python decorator), consistent with F-42: sensor
  `artifact_type` is declared in `.intent/workers/*.yaml`, not in the Python class.
- Per-action granularity without per-file ceremony: `action_risk.yaml` already has one entry per
  action, already loaded by `ActionRegistry`, already fail-closed on missing entries.
- `operational_capabilities.yaml` is coarser (capability, not action) and the
  `apply_artifact_type_config()` stub's comment acknowledging it was provisional.
- A new `.intent/atomic_actions/<id>.yaml` surface adds declaration ceremony with no new
  expressiveness over the existing per-action entry in `action_risk.yaml`.

### D2 — Repository adapter contract: three-part declaration

A Repository type is **fully registered** when three declarations are present and cross-validated:

| Part | Declaration surface | Governs |
|------|---------------------|---------|
| **Type** (F-41) | `.intent/artifact_types/<type_id>.yaml` | What instances of this type are: identity_key, change_record, vector_collection, discovery, supported_sensors, supported_actions |
| **Sensor(s)** (F-42) | `.intent/workers/<name>.yaml` + `Worker` impl | How instances are read; what findings they produce; canonical subject format |
| **Action(s)** (F-43) | `action_risk.yaml` entry with `artifact_types: [<type_id>]` + `@atomic_action` impl | How instances are remediated |

This is the **Repository adapter** — not a class, not a plugin interface, but a set of
declarations registered under the three existing governance surfaces. No new abstraction is added;
the adapter identity emerges from cross-validated declarations.

**Sensor part is required.** A type with no sensor cannot enumerate its instances or produce
findings. `IntentRepository.initialize()` fails closed if a loaded artifact type has
`supported_sensors: []` (unless the type explicitly sets `discovery_only: true` — a future
extension; no such flag exists today, so the invariant is unconditional).

**Action part is optional at registration time.** A newly registered type operates in audit-only
mode until at least one action is declared. Progressive adoption is correct: register the type,
author a sensor, run audits, add remediation actions as the finding volume justifies it.

### D3 — `supported_sensors` becomes load-bearing at `IntentRepository.initialize()`

`IntentRepository.initialize()` gains a cross-validation step after both artifact_types and worker
declarations are loaded. The four predicates are all required to hold:

```
For each artifact type T:
  For each sensor_name s in T.supported_sensors:
    [P1] s exists in loaded worker declarations
    [P2] T.id appears in workers[s].mandate.scope.artifact_type

For each worker W with class: sensing:
  For each type_id in W.mandate.scope.artifact_type:
    [P3] type_id exists in loaded artifact types
    [P4] W.declaration_name appears in artifact_types[type_id].supported_sensors
```

Failure on any predicate is fail-closed: `initialize()` raises `GovernanceError` citing the
specific asymmetry (P1/P2: sensor listed in type but declaration absent or doesn't claim the type;
P3/P4: sensor claims type but type's list doesn't include that sensor).

This closes ADR-091 D4's cross-validation invariant at infrastructure level — earlier and harder
than the Phase 7 runtime-audit promotion. The `governance.taxonomy.sensor_supported_by_declaration`
rule continues on its Phase 7 schedule as the runtime-audit layer (catches violations introduced
after startup without a restart); initialize()-time validation is the startup-gate complement.

**Current state:** the `supported_sensors` authored lists are accurate as of today's declarations.
The cross-validation will pass on day one. Any future authoring error (sensor added to a worker
declaration without updating the artifact type, or vice versa) is caught at the next daemon restart
rather than silently passing into production.

### D4 — `supported_actions` and `action_supported_by_declaration` rule: trigger preserved from ADR-092

Per ADR-092 D2, `supported_actions: []` stays empty and `governance.taxonomy.action_supported_by_
declaration` stays parked until a **second non-Python atomic action** ships. T5b's first GRC action
(which will carry `artifact_types: [<grc_type_id>]` in action_risk.yaml) is that trigger.

The obligation is forward-recorded here:

> **ADR-092-A trigger (recorded in T5a):** When T5b ships its first GRC atomic action carrying
> `artifact_types: [<T5b type_id>]` in action_risk.yaml, the same change-set MUST:
> (a) author and file `governance.taxonomy.action_supported_by_declaration`,
> (b) populate `supported_actions` on the relevant artifact_type declaration(s),
> (c) reference this ADR and ADR-092 as the obligation chain.
>
> The implementation session for T5b owns this obligation. This ADR is the forward marker.

Until then: `supported_actions: []` on all 11 existing declarations is correct and not validated
by initialize() (only `supported_sensors` is validated by D3).

### D5 — Discovery convention for project-authored types

Artifact type declarations with `discovery: []` (empty list) are **project-authored types**: the
framework ships the sensor and action implementations but the project author writes the discovery
configuration in their own copy of `.intent/artifact_types/<type_id>.yaml`.

`IntentRepository.initialize()` enforces a corollary: if a loaded artifact type has `discovery:
[]`, at least one sensor in `supported_sensors` must be present — without discovery or a sensor,
the type cannot enumerate its instances and registration is incoherent.

For such types, the sensor is responsible for its own enumeration strategy. A document corpus
sensor, for example, may read a configured path from a project-layer `.intent/` field, or accept a
path parameter at audit-invocation time. The enumeration contract is the sensor's design; T5a only
establishes that `discovery: []` is a valid framework declaration and defines what project-authored
means.

**No schema change required.** The F-41 `META/artifact_type.schema.json` already accepts `discovery`
as a list; empty list is valid YAML and JSON-Schema-valid. The convention is this ADR's addition,
not a schema amendment.

**Existing static types** (`python`, `test`, `intent_yaml`, etc.) have non-empty `discovery` lists
— they are framework-owned and ship complete. Project-authored types are an extension pattern, not
a change to existing types.

### D6 — ActionExecutor refusal gate (F-43 exit criterion implementation)

`ActionExecutor.execute()` is extended per ADR-092 D1:

```python
# Pseudocode — exact error type is the implementation session's choice (RefusalResult / GovernanceError)
if action_def.artifact_type:  # non-empty: this action is type-constrained
    registered_ids = {t.id for t in intent_repo.list_artifact_types()}
    if not set(action_def.artifact_type).intersection(registered_ids):
        return RefusalResult.boundary_violation(
            component_id=self.component_id,
            reason=f"action '{action_def.action_id}' declares artifact_type "
                   f"{action_def.artifact_type!r} but none are registered in F-41"
        )
```

The test MUST exercise the refusal path, per ADR-092 D1's "happy-path is insufficient" requirement:
a test registers an action with `artifact_types: ["unregistered_type"]` in a mock action_risk.yaml
and asserts `execute()` returns a refusal without dispatching.

---

## Implementation change-set (single commit)

Six touch-points, all within one change-set:

1. **`action_risk.yaml`** — add `artifact_types: [python]` to Python-specific action entries
   (`fix.format`, `fix.imports`, `build.tests`, `fix.logging`, `fix.docstrings`, `fix.symbol_ids`,
   `fix.type_annotations`, `check.imports`, `check.types`, `check.style`, and any others whose
   semantics are Python-AST-specific). Leave unconstrained entries (bookkeeping, infra, cross-
   artifact) without the field. At least one entry must carry the field to satisfy ADR-092 D1.

2. **`src/body/atomic/registry.py`** — extend `apply_risk_config()` to overlay `artifact_types`
   from each action_risk.yaml entry onto `ActionDefinition.artifact_type`. Remove
   `apply_artifact_type_config()` method and its stub call-site. Fail closed on unregistered IDs.

3. **`src/body/executors/action_executor.py`** (or equivalent executor path) — wire D6 refusal
   gate: check `action_def.artifact_type` against the F-41 registry before dispatch; return
   `RefusalResult.boundary_violation()` on miss.

4. **`src/shared/infrastructure/intent/intent_repository.py`** — wire D3 cross-validation in
   `initialize()` after loading artifact_types and workers. Four predicates, fail-closed. Add no
   new public methods — this is internal initialization logic.

5. **`.intent/enforcement/config/action_risk.yaml`** schema amendment (if META validates it) — add
   `artifact_types` as an optional list-of-strings field to the action_risk entry schema.
   (If no META schema validates action_risk.yaml entries today, this item is a no-op — the field
   is additive and the YAML loader ignores unknown fields at its existing codepath.)

6. **Tests** — three new test cases:
   - `test_initialize_cross_validation`: seed a mock IntentRepository with a sensor declaring an
     unregistered artifact_type → assert `initialize()` raises `GovernanceError`
   - `test_executor_refusal_on_unregistered_artifact_type`: per D6 above
   - `test_action_risk_overlay`: assert `apply_risk_config()` correctly overlays `artifact_types`
     onto `ActionDefinition` and fails on an unregistered ID

---

## Consequences

### Closes

- **ADR-092 D4** — F-43 declaration site resolved: `action_risk.yaml` per-action `artifact_types`
  field. This ADR is "the implementation session" D4 deferred to.
- **ADR-091 D4 initialize()-time cross-validation gap** — `supported_sensors` is now load-bearing
  at daemon startup.
- **The three-separate-infrastructure-ADRs-no-unified-contract gap** — the Repository adapter
  pattern (D2) is the contract T5b references.

### Opens / triggers

- **T5b** unblocked. T5b authors: one `.intent/artifact_types/<doc_corpus_type_id>.yaml` with
  `discovery: []` (project-authored, D5), one `Worker`-based document sensor, one or more
  action_risk.yaml entries with `artifact_types: [<doc_corpus_type_id>]`. The adapter contract
  (D2) is the checklist; D3's cross-validation is the gate.
- **ADR-092-A obligation** triggered by T5b's first GRC action (D4 forward marker).
- **`governance.taxonomy.sensor_supported_by_declaration` Phase 7 promotion** proceeds on its own
  timeline; it is now the runtime-audit complement to initialize()-time validation, not the sole
  gate.

### Does not change

- `Worker` base class and F-42 sensor contract — unchanged.
- The eleven existing artifact_type declarations — `supported_sensors` already accurate; no
  `supported_actions` added (D4 deferred).
- `supported_sensors` authoring practice — the `action_risk.yaml`-driven `artifact_types` field
  is the F-43 analog; F-42's sensor-declaration pattern in `.intent/workers/*.yaml` is unchanged.

---

## References

- `CORE-BYOR.md` §3 (Repository = artifact corpus + typed sensor), §7 (GRC first non-code
  Repository), §9 (T5a as concrete F-41/F-42/F-43 binding)
- ADR-090 D2/D5 — artifact_type schema; `supported_sensors`/`supported_actions` forward-declared
- ADR-091 D4/D5/D6 — sensor cross-validation; Phase 7 blocking promotion; F-43 forward contract
- ADR-092 D1/D2/D4 — F-43 exit criterion (refusal gate); `action_supported_by_declaration`
  parking; declaration site deferred (resolved by D1 here)
- ADR-075 — framework/project namespace (project-authored discovery convention, D5)
- `.intent/enforcement/config/action_risk.yaml` — D1 extension site
- `src/body/atomic/registry.py` — `ActionDefinition.artifact_type`, `apply_artifact_type_config()`
  stub (retired by D1)
- `src/shared/infrastructure/intent/intent_repository.py` — `initialize()`, cross-validation (D3)
- `.intent/META/artifact_type.schema.json` — published contract (D5: empty discovery list is
  already valid; no schema amendment required)
