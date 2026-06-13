---
kind: adr
id: ADR-091
title: ADR-091 — F-42 pluggable sensor model as the second published contract
status: accepted
---

<!-- path: .specs/decisions/ADR-091-f42-pluggable-sensor-model-as-second-published-contract.md -->

# ADR-091 — F-42 pluggable sensor model as the second published contract

**Date:** 2026-06-05
**Status:** Accepted (Revision B implemented in tree; **D2 Amendment 2026-06-12** accepted by governor decision 2026-06-12 — see "D2 Amendment — disposition transitions own `resolution_mechanism`" at end; tracking #628)
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-05 — drafted under Path A execute-verb authorization, "proceed as suggested" + named topic ADR-091 + execute-verb "draft directly to disc"; revised under governor direction to unify three open questions into canonical contracts rather than per-sensor grandfather clauses)
**Grounding papers:** `papers/CORE-Features.md` §3.11 (extension interfaces F-41–F-43 as plugin APIs against the open-base contract) and §F-42 (the abstract sensor interface); `CORE-CHARTER.md` (the open-completeness commitment under which the audit loop must be artifact-agnostic, not Python-shaped).
**Related:** ADR-090 (the artifact-type registry this ADR consumes — `supported_sensors` is the field this ADR populates); ADR-084 §D1 (plugin shape requires F-41/F-42/F-43 as published contracts — this ADR ships the second); ADR-085 §"Why this matters" (the open-completeness gate item this ADR closes after F-41); ADR-079 §D9 (the taxonomy_gate YAML↔AST coherence pattern this ADR mirrors for sensor↔artifact_type coherence); ADR-081 §D2 (process-isolation classification — sensors declaring heavy artifact-type discovery may need `requires_dedicated_process: true`); ADR-072 §D5 (awaiting-reaudit drain pattern preserved across migration); ADR-039 (governance-refresh contract sensors honor); ADR-015 §D5 (cause attribution payload fields preserved across the subject migration); F-43 #417 (pluggable action model — gains the same `artifact_type` field and canonical subject format via its own ADR); F-41 #415 (substantially shipped at gates 1–3, 5, 7, 8, 9; gates 4 and 6 close when this ADR's D5 phases complete); #566 (engine check for `architecture.artifact_discovery_through_registry` — advisory today, promotion path declared in D8).
**Supersedes (partial):** the implicit per-sensor artifact_type convention currently expressed only in code comments (e.g. `AuditViolationSensor`'s `get_artifact_type("python")` hardcode introduced in F-41 Phase 2); the three heterogeneous subject-string conventions currently in use (`audit.violation::*`, `test.run_required::*`, `test.missing::*` / `test.failure::*`) which converge under D2's canonical format.

---

## Reader orientation — this ADR carries two contracts

A navigation aid (added 2026-06-12); nothing below is changed or removed.

1. **Pluggable sensor model** (F-42) — Decisions **D1–D7**. The second ADR-084
   D1 published contract: sensor declarations, the canonical subject format,
   `supported_sensors` cross-validation, and the migration phases.
2. **Blackboard finding-lifecycle contract** — **D2 Revision B** (the
   `resolution_mechanism` field + the reaudit-eligibility invariant) and the
   **2026-06-12 D2 Amendment** (field-ownership on disposition transitions;
   #628). This contract is anchored as "ADR-091 D2" across ~60 code/`.intent`
   sites, so it lives here rather than in a separate ADR.

Sections headed `Note —` are dated, append-only implementation history;
`Revision A` / `Revision B` preserve the D2 review trail. New readers: start at
**## Decisions**.

---

## Context

### The audit engine claims artifact-agnosticism; the sensor layer encodes Python

ADR-090 reframed CORE as a consistency/compliance engine where source code is one artifact class. F-41 made artifact type a declared parameter at the registry layer. But the sensor layer — the entry point for "observe artifacts → emit findings" — still encodes the connection to Python implicitly. Three of the four shipping sensors take no artifact-type input; the fourth (`AuditViolationSensor`) reaches into the registry by passing the literal string `"python"`. A third party who declares a new artifact type in `.intent/artifact_types/` has nowhere to plug in observation: there is no published contract for what a sensor is.

This ADR ships that contract. It is the second ADR-084 D1 published contract after `META/artifact_type.schema.json`.

### The four shipping sensors, three patterns, three subject conventions

Today CORE runs four sensors with three distinct declaration patterns and three distinct subject-string formats:

| Sensor class | Pattern | Subject format | Declares artifact_type? |
|---|---|---|---|
| `AuditViolationSensor` | one class × N namespace declarations (audit_sensor_purity, audit_sensor_architecture, …) | `audit.violation::<rule_id>::<file_path>` | implicit (hardcoded `"python"` lookup) |
| `TestCoverageSensor` | one class × one declaration | `test.run_required::<source_file>` | no |
| `TestRunnerSensor` | one class × one declaration, posts to two namespaces | `test.missing::<src>` / `test.failure::<src>` | no |
| `CoherenceSensorWorker` | one class × one declaration, delegates to CCC | (CCC-internal, multi-row) | no |

The three subject formats are not principled. They reflect the order each sensor was written and the absence of a shared contract. The audit-violation pattern (namespace-driven, multi-declaration) is honest where multiple rule namespaces sensibly group under one observation strategy. The single-declaration pattern is honest where the sensor is intrinsically singular. F-42 does not pick a multiplicity winner — but it does pick a subject-format winner: one canonical format the framework computes from declaration metadata, removing every per-sensor authoring escape hatch.

### What "pluggable sensor" actually means

The plugin-shape commitment in ADR-084 D1 is: third parties extend CORE by writing declarations and importable modules, never by patching the engine. For sensors, this means:

1. **The sensor class is ordinary code.** Subclasses `shared.workers.base.Worker`. No new base class. No new Protocol. The Worker contract is unchanged.
2. **The sensor's constitutional standing is one YAML file.** `.intent/workers/<sensor_id>.yaml` declares the implementation module, the artifact_type(s) observed, and the audit topic evaluated. Per D2 the framework derives every other surface — subject strings, discovery globs, identity-key extraction — from those declarations.
3. **The sensor's discovery globs come from the artifact_type list it declares.** Not from inline `rglob` calls. F-41 made this possible; F-42 makes it required.
4. **The sensor's findings flow through the standard Blackboard with framework-computed subjects.** Authors call `post_finding(artifact_type, sub_namespace, identity_key_value, payload)`; the framework constructs the subject string. No per-sensor `subject_prefix` field. Single canonical format guaranteed at compile-time (no string concatenation in sensor code).

The "abstraction" is therefore minimal: two worker declaration fields, one registry handshake, one framework-side subject builder. The temptation to invent a `Sensor` base class above `Worker` is rejected — `[[protocols-reflex-check]]` applies. The Worker contract is already the abstraction; F-42 parameterises two declaration fields and centralises subject construction.

### Why now, in this scope

F-41's verification gates 4 (Python pipeline migration) and 6 (spec_markdown CCC migration) are partial by design — closing them requires a sensor-side contract that says "this sensor observes artifact_type X, here is its discovery glob." That contract is F-42. Shipping F-42 closes F-41's partial gates without retroactive ADR-090 edits, per the ADR-090 close-out comment on #415.

Per ADR-085 §"Why this matters," F-42 is the next open-completeness gate item after F-41. Engineering capacity routes here. Per ADR-084 D1, the commercial BYOR multi-language story attaches its language-specific sensors (Go sensor for Go source, JS sensor for JS source, etc.) to this contract. Without F-42, BYOR plugins must fork the engine.

---

## Decisions

### D1 — Sensor declaration extension on `META/worker.schema.json` (list-form, framework-derived subject)

Two changes to the worker schema, applicable when `identity.class == "sensing"`:

1. **`mandate.scope.artifact_type`** added — **array** of strings (`type: array`, `minItems: 1`). Each element must be the `id` of a registered artifact_type declaration. Required for sensing workers; absent for non-sensing classes. Single-element arrays are the common case (e.g. `[python]`); multi-element arrays declare joint observation (e.g. `[python, test]` for sensors that cross-reference instances of multiple types). The array-as-canonical shape eliminates a "string-or-array" branch the validator would otherwise have to handle, and forces every sensor — single or multi — through the same framework dispatch.

2. **`mandate.scope.rule_namespace`** generalised — the field is now required for every sensing-class declaration (today's schema makes it optional). Its semantics widen from "rule ID prefix this sensor scopes to" to "audit topic this sensor emits under." Where the topic happens to match a declared rule namespace (the `AuditViolationSensor` case today), rule-ID resolution proceeds as before. Where it does not (the `TestCoverageSensor` case today: `test.coverage` as a sensor topic with no rule IDs at that prefix), resolution returns an empty rule set and the sensor's `run()` does not iterate over rules — but the topic field still anchors the canonical subject format declared in D2. The schema description is updated to reflect the dual use.

No `subject_prefix` field is added. Subject construction is the framework's responsibility per D2.

### D2 — Canonical subject format, framework-computed (closed vocabulary)

The framework computes every subject string a sensor posts. Authors do not concatenate strings; they call typed APIs. Two subject shapes are declared as the closed contract:

**Findings** (`post_finding`):

```
<artifact_type_id>::<sub_namespace>::<identity_key_value>
```

- `artifact_type_id` — one of the sensor's declared `artifact_type` array entries. The framework validates membership at call time.
- `sub_namespace` — must equal the sensor's declared `rule_namespace`, or extend it via dotted-suffix (e.g. a sensor with `rule_namespace: test.runner` may emit under `test.runner.missing` and `test.runner.failure`). The framework validates the prefix relation at call time.
- `identity_key_value` — the value of the artifact instance's identity key. For `identity_key: path` artifact types (the universal case today), this is the file path. For `identity_key: path_plus_anchor` or `uri`, the value shape follows the declared key form.

**Reports** (`post_report`):

```
<worker_declaration_name>.<event_kind>
```

- `worker_declaration_name` — the sensor's YAML stem (e.g. `audit_sensor_purity`).
- `event_kind` — sensor-authored event identifier (`run.complete`, `cycle.skipped`, etc.). Lowercase dotted segments; no `::` separator.

**Heartbeats** — framework-managed, no author concern.

Updated sensor base API:

```python
async def post_finding(
    self,
    artifact_type: str,
    sub_namespace: str,
    identity_key_value: str,
    payload: dict[str, Any],
) -> None: ...
```

The old `post_finding(subject: str, payload: dict)` signature is removed in D5. The two-argument variant remains for `post_report` since reports are framework-routed by the worker_declaration_name prefix and the canonical format is mechanical from it.

The format is the closed vocabulary. Extending it (a third subject shape, a fourth segment, a different separator) is a governance amendment, not an ad-hoc per-sensor decision.

### D3 — Twelve true-sensor declarations updated under canonical format; nine misclassified `class: sensing` workers flagged for reclassification

Following the ADR-090 D3 precedent (reference declarations shipped alongside the schema), this ADR's implementation updates the **12 declarations whose workers genuinely observe artifact instances** — the F-42 contract's intended population. Each declaration update is part of the atomic Phase 1+2 change-set.

**The 12 true sensors migrated (artifact observers):**

- **Eight `audit_sensor_*.yaml`** (purity, architecture, logic, modularity, cli, layout, linkage, style) — each gains `mandate.scope.artifact_type: [python]`. `rule_namespace` remains as today (the sensor's rule-prefix). Subject format under the new contract: `python::<rule_namespace>::<file_path>`, replacing today's `audit.violation::<rule_namespace>::<file_path>`. The hardcoded `get_artifact_type("python")` lookup in `AuditViolationSensor.run` becomes a read of `self.artifact_types[0]`.

- **`audit_violation_sensor.yaml`** (paused base) — gains `mandate.scope.artifact_type: [python]` and a placeholder `rule_namespace: audit.violation`. Required for schema validation; the worker stays paused.

- **`test_coverage_sensor.yaml`** — gains `mandate.scope.artifact_type: [python, test]` and `mandate.scope.rule_namespace: test.coverage`. Joint declaration: observes Python sources to detect absence of corresponding tests. Subject format: `python::test.coverage::<source_file>`, replacing today's `test.run_required::<source_file>`.

- **`test_runner_sensor.yaml`** — gains `mandate.scope.artifact_type: [python, test]` and `mandate.scope.rule_namespace: test.runner`. Two sub-namespaces per D2's dotted-extension allowance: `test.runner.missing` and `test.runner.failure`. Subject formats: `python::test.runner.missing::<source_file>` and `python::test.runner.failure::<source_file>`, replacing today's `test.missing::<src>` / `test.failure::<src>`.

- **`coherence_sensor.yaml`** — gains `mandate.scope.artifact_type: [python]` and `mandate.scope.rule_namespace: coherence.incoherence`. This worker is the **ADR-027 fixer-sensor incoherence detector** (queries `proposal_consequences` for executed proposals; checks whether the same `check_id + file_path` was re-detected after execution). It is NOT the Constitutional Coherence Checker (CCC) — CCC runs inline during the audit via `CoherenceChecker`, not as a Worker. The artifact class whose violations this sensor tracks is `python` (the substrate where `check_id + file_path` apply). Subject format: `python::coherence.incoherence::<check_id_plus_file_hash>`, structurally consistent with today's `coherence.incoherence::<check_id>::<file_hash>`.

**Nine misclassified `class: sensing` workers — NOT migrated in this ADR:**

Pre-implementation recon enumerated `.intent/workers/*.yaml` for `class: sensing` and found nine workers whose actual role is not artifact observation: `audit_ingest_worker` (transformer of audit findings into core), `capability_tagger` (tagger), `commit_reachability_auditor` (commit-graph auditor), `governance_embedder` and `repo_embedder` (vector-index writers), `intent_inspector` (inspector), `observer_worker` (needs classification), `prompt_extractor_worker` (extractor), `repo_crawler` (crawler).

These workers crawl, embed, transform, or audit aggregates — they do not observe artifact *instances* in the F-42 sense. Forcing them to declare `artifact_type` would be a category error: an embedder does not "observe" the YAML it embeds, it indexes it. The `class: sensing` label has drifted to cover roles the F-42 contract does not fit.

Two consequences for ADR-091 scope:

1. **Phase 1 atomic migration covered only the 12 true sensors.** The D1 conditional constraint `if class == sensing then artifact_type required` was staged behind a separate reclassification pass — the nine misclassified declarations would otherwise have failed schema validation. In Phase 1, the schema fields were **optional** for `class: sensing`.

2. **A sub-issue was filed and closed (#570)** tracking the reclassification: "sensing-class taxonomy audit — reclassify embedders / crawlers / transformers before F-42 invariant goes blocking." Closed 2026-06-05 with the reclassification landing: five workers → `acting` (audit_ingest_worker, capability_tagger, governance_embedder, prompt_extractor_worker, repo_embedder), two → `governance` (commit_reachability_auditor, observer_worker), one retained `sensing` with declared artifact_type (intent_inspector → `[intent_yaml, intent_json]`), one retained `sensing` with broader artifact_type per ADR-070 D8 writer-as-sensor pattern (repo_crawler → `[python, test, doc, prompt, report, infra, intent_yaml, intent_json, spec_markdown]`).

**The D1 conditional enforcement is now live.** With every `class: sensing` worker honestly declaring its artifact_type list, the `allOf` block in `META/worker.schema.json` requires `mandate.scope.artifact_type` and `mandate.scope.rule_namespace` for sensing-class declarations. Daemon-load validation rejects sensing-class workers missing either field.

The D1 stability commitment is unaffected: the schema field *shape* is final; the conditional *enforcement* has now landed.

The D8 advisory→blocking promotion of `sensor_supported_by_declaration` remains for Phase 7 (gated on Phase 6 legacy `post_finding(subject, payload)` API removal), independent of the #570 closure.

**No registry-side coverage gap (pre-Phase-4 recon correction).** The original draft of this D3 amendment claimed `.specs/phases/*.yaml` was un-typed and parked `_phase_paths` until a gap-resolution sub-issue closed. Pre-implementation recon for Phase 4 surfaced that CCC's `_phase_paths` actually reads `.intent/phases/*.yaml` — fully covered by `intent_yaml`'s `.intent/**/*.yaml` discovery glob. `.specs/phases/` does not exist. The original gap claim was based on incorrect path assumption; `_phase_paths` migrates normally in Phase 4 with no sub-issue needed.

### D4 — Cross-validation invariant: `supported_sensors` ≡ introspected set (list-form)

F-41 declared `supported_sensors` as a forward-contract field on every artifact_type, populated by F-42. This ADR completes the contract by making the field authored ∧ introspectively verified — the same shape as ADR-079 §D9's `governance.taxonomy.operational_capabilities_decorator_backing` pattern (YAML ⊆ AST, fail-closed). The list-form extension is mechanical: a sensor with N artifact_types contributes N pairs to the introspected set.

At `IntentRepository.initialize()`:

1. Build the introspected set: for each loaded worker declaration with `class: sensing`, record one pair `(artifact_type_id, worker_id)` per element in the worker's `mandate.scope.artifact_type` array.
2. Build the authored set: for each loaded artifact_type, record one pair `(artifact_type_id, sensor_id)` per entry in its `supported_sensors` list.
3. The two sets must be equal. A sensor declaring an artifact_type whose worker_id is not listed in that artifact_type's `supported_sensors` array fails registration. An entry in `supported_sensors` that no sensor declaration backs is a phantom (ADR-079 D9 class) and fails initialization.

The invariant is enforced by a new advisory→blocking rule, `governance.taxonomy.sensor_supported_by_declaration`, modelled on `operational_capabilities_decorator_backing`. Ships as `reporting` in the same change-set as D5 Phase 1 (so existing declarations can populate without immediate fail-closed); promotes to `blocking` at D5 Phase 7 completion together with the cleared phantom set.

This closes the drift surface ADR-090 D5 left open: "empty list permitted until F-42 lands" is replaced with "list must match worker declarations or registration fails."

### D5 — Migration phases (behavioural identity is the gate, including under deterministic subject transform)

Following the ADR-090 D4 phased pattern. Each phase is a separate commit. Behavioural identity verification gates each step — under the deterministic subject-format transform where subjects migrate.

- **Phase 1 — Schema extension + framework subject builder + invariant rule (advisory).** Extend `META/worker.schema.json` per D1. Add the framework-side `post_finding(artifact_type, sub_namespace, identity_key_value, payload)` typed API on `shared.workers.base.Worker` alongside the existing `post_finding(subject, payload)`. Add `governance.taxonomy.sensor_supported_by_declaration` as advisory. No behavioural change yet; sensors continue to use the old API. The two-API coexistence window spans Phases 1–6.

- **Phase 2 — Author the four reference declarations.** Update the audit_sensor_*.yaml family, test_coverage_sensor.yaml, test_runner_sensor.yaml, coherence_sensor.yaml with the new `artifact_type` arrays and `rule_namespace` topic declarations per D3. Populate `supported_sensors` on `python.yaml`, `test.yaml`, `spec_markdown.yaml`, `intent_yaml.yaml` to match. Verification: `IntentRepository.initialize()` indexes all sensor declarations and all artifact_types without error; D4 invariant holds at advisory. File the `.specs/phases/*.yaml` registry-coverage sub-issue (D3 gap).

- **Phase 3 — `AuditViolationSensor` end-to-end migration + consumer-distinction predicate.** The sensor reads its declared `artifact_type` from the declaration (replacing the hardcoded `"python"`). All `post_finding` calls switch to the typed API; the framework constructs subjects in canonical form (`python::<rule_namespace>::<file_path>`). Concurrent consumer migration: the producer/consumer surfaces decompose on different axes (producer: `(artifact_type, sub_namespace)`; consumer: "which sub_namespaces fall within my pipeline?"), so the consumer's interest set is **derived from `IntentRepository`, not hardcoded**. A centralized predicate `shared.infrastructure.intent.audit_namespaces.is_audit_violation_subject(subject)` ships in the same change-set, reading `IntentRepository.rule_namespaces()` at call time and compiling to a parameterised LIKE-disjunction for SQL callers. Every site in `src/` that today encodes "audit-violation finding" via the literal `audit.violation::*` prefix or its constants migrates to the predicate — the complete enumeration is a Phase 3 commit artifact (initial recon at amendment time surfaces ~17 sites across `body.services.blackboard_service`, `will.workers.violation_remediator`, `will.workers.violation_executor`, `will.workers.violation_remediator_body.blackboard`, `will.workers.audit_violation_filter`, `will.workers.audit_violation_normalizer`, `will.workers.violation_remediator_blackboard`, `will.self_healing.remediation_interpretation.finding_normalizer`, `mind.governance.auditor`, `mind.logic.engines.artifact_gate`, `mind.logic.engines.workflow_gate.checks.audit`, `body.atomic.remediate_cognitive_role`, `body.services.consequence_log_service`, `cli.resources.runtime.health`, `cli.resources.workers.remediate`; final enumeration is the commit-time grep). One-shot blackboard subject migration runs in the same commit: existing `audit.violation::*` rows are rewritten to `python::*` under the deterministic transform `audit.violation::<ns>::<path> → python::<ns>::<path>` (5,620 rows at amendment time per live count; row-cap and partial-walk guards per the destructive-autonomous discipline). Verification: finding set before vs after is identical under the transform; the predicate over the rewritten rows yields the same row identity-key set as the pre-migration LIKE filter over the originals; consumer dedup behaviour unchanged. Closes F-41 verification gate 4 (fully).

- **Phase 4 — CCC sub-discovery routes through registry.** `CoherenceChecker` runs inline during the audit cycle, not as a Worker (per D3 amendment). Eight discovery surfaces migrate — `_adr_paths`, `_northstar_paths`, `_phase_paths` in `checker.py`, and `mind.coherence.checks.{row2_grounding, row3_citation, row4_naming, vocabulary}` — consulting `IntentRepository.get_artifact_type("spec_markdown")` for ADR/paper/northstar discovery, `get_artifact_type("intent_yaml")` for `.intent/` YAML discovery (`_phase_paths` and the row4 intent walk), and `get_artifact_type("intent_json")` for `.intent/` JSON discovery (row4 intent walk). The `vocabulary` check was missed from the original draft; recon added it as it carries the same spec_markdown discovery shape. CCC findings retain their existing subject format; D2's canonical subject format applies to Worker-emitted findings only, so a separate CCC subject migration is out of scope here and tracked separately if pursued. Verification: CCC outcome (finding identifier set) before vs after migration is identical. Closes F-41 verification gate 6 (fully).

- **Phase 5 — `TestCoverageSensor`, `TestRunnerSensor`, and `CoherenceSensorWorker` end-to-end migration + test-remediation predicate.** Discovery + observation walks consult the registry for `[python, test]` (test sensors) and `[python]` (coherence sensor). Sensors switch to typed API. Concurrent consumer migration: a centralized predicate `shared.infrastructure.intent.test_namespaces.is_test_remediation_subject(subject)` ships in the same change-set, mirroring the Phase 3 shape — derived from the sub_namespace set declared by `test_coverage_sensor.yaml` and `test_runner_sensor.yaml`'s `mandate.scope.rule_namespace` plus their D2-permitted dotted extensions (`test.coverage`, `test.runner.missing`, `test.runner.failure`). `TestRemediatorWorker`'s dedup queries call it. `coherence_sensor` is detection-only per ADR-027 so no remediator dedup updates are needed (verified via grep that no production code consumes its subjects for dedup). One-shot blackboard subject migration: `test.run_required::*` → `python::test.coverage::*`; `test.missing::*` → `python::test.runner.missing::*`; `test.failure::*` → `python::test.runner.failure::*`; `coherence.incoherence::*` → `python::coherence.incoherence::*` (93 rows total across test subjects at amendment time; 0 coherence.incoherence rows; row caps + partial walks identical to Phase 3). Verification: coverage-gap, test-execution, and incoherence finding sets before vs after migration are identical under the transform; the test-remediation predicate over the rewritten rows yields the same row identity-key set as the pre-migration filters over the originals.

- **Phase 6 — Remove old `post_finding(subject, payload)` API + retire legacy subject-prefix constants.** With all four sensor families on the typed API, the string-subject overload is deleted from `shared.workers.base.Worker`. Any remaining caller is a regression (covered by Phase 7's blocking rule). Concurrent removal: the legacy `_FINDING_SUBJECT_PREFIX = "audit.violation::"` constant family and any equivalent string-literal forms surfaced by Phases 3 and 5 are deleted — every consumer surface uses the predicates landed in Phases 3 and 5. The single-API state plus the predicate-only consumer state is the F-42 published contract.

- **Phase 7 — Promote `sensor_supported_by_declaration` to `blocking`; promote F-41's `architecture.artifact_discovery_through_registry` to `blocking` once #566 engine check is ready.** The phantom set is empty by end of Phase 6; advisory→blocking happens with zero outstanding findings. Mirrors ADR-079 D10 Stage 2 promotion pattern. F-41's rule promotion is a separate change-set tracked at #566 but unblocked by this ADR's completion.

Each phase is independently shippable. Behavioural identity verification under the deterministic subject transform is the close-out criterion per phase.

### D6 — Forward contract for F-43 (extended to canonical subject format)

The action-side equivalent of D1–D5 is F-43's deliverable, not this ADR's. What this ADR commits to on F-43's behalf:

- **The artifact_type list pattern.** Action declarations gain `mandate.scope.artifact_type` as an array, mirroring the sensor field. F-43 may extend the pattern (e.g. action-specific artifact-type semantics) but the array-as-canonical shape is shared.
- **The invariant.** F-41's `supported_actions` field becomes authored ∧ introspectively verified by the same mechanism declared in D4 — a new `governance.taxonomy.action_supported_by_declaration` rule mirrors D4's sensor rule. F-43 ships that rule.
- **The registry-coupling.** F-43 actions declaring an unregistered artifact_type fail registration, exactly as sensors do.
- **The canonical emission format.** Where actions emit findings (e.g. proposal outcomes posted to the Blackboard), the subject format follows the D2 closed vocabulary, suitably adapted. Where actions emit ActionResults (the dominant case — F-43 actions return `ActionResult` objects, not Blackboard findings), no subject format applies. F-43 specifies the boundary.

What this ADR does NOT commit to on F-43's behalf:

- Action declaration shape — F-43 may declare `mandate.scope.artifact_type` on the existing atomic-action registry surface, on worker declarations for action-bearing workers, or on a new artifact entirely. That is F-43's design decision.
- Confidence-level and execution-contract semantics — F-43 §F-43 spec items, not F-42's.

### D7 — Stability commitment per ADR-084 D1 — second published contract

`META/worker.schema.json` plus the canonical subject format declared in D2 plus the typed `post_finding` API on `shared.workers.base.Worker`, post-ADR-091, constitute the second ADR-084 D1 "published contract" after `META/artifact_type.schema.json`. The commitment carries the same shape:

- Field additions to `worker.schema.json` are backward-compatible only (new optional fields permitted; existing fields' semantics do not change).
- Field removals or semantic changes to existing fields require a governance amendment and a deprecation window.
- The closed vocabulary for `identity.class` (sensing, acting, governance, supervision) extends by governance amendment only. Today's four classes are the universe.
- `mandate.scope.artifact_type` as an array of registered ids, required for `class: sensing`, is part of the contract; making it optional later requires a deprecation window.
- The canonical subject format (D2) — finding shape `<artifact_type>::<sub_namespace>::<identity_key_value>`, report shape `<worker_declaration_name>.<event_kind>` — is the closed format. Extending the format (a third shape, a fourth segment, a different separator) is a governance amendment.
- The typed `post_finding(artifact_type, sub_namespace, identity_key_value, payload)` API on `shared.workers.base.Worker` is part of the contract; signature changes are governance amendments.

`.intent/CHANGELOG.md` records the second published-contract status in the change-set that lands D5 Phase 1.

### D8 — Anti-regression: promote F-41's advisory rule + add this ADR's

Two rules govern the artifact-discovery-through-registry posture:

1. **F-41's `architecture.artifact_discovery_through_registry`** — currently advisory (per F-41 gate 9 close-out comment on #415 and the engine-check tracking issue #566). With D5 Phase 5 complete, every shipping sensor consults the registry; the rule can be promoted to `blocking` as part of the same Phase 7 change-set that lands the engine check at #566. Promotion is not in F-42's primary scope but is unblocked by it and tracked in the same phase.
2. **This ADR's `governance.taxonomy.sensor_supported_by_declaration`** — ships at `reporting` in D5 Phase 1; promoted to `blocking` in D5 Phase 7. Constitutional pair with `operational_capabilities_decorator_backing` (ADR-079 D9): together the two rules express the "every declared entry has a code backing AND every code-side entry has a declared entry" invariant for the F-41 ↔ F-42 boundary.

A third `governance.taxonomy.action_supported_by_declaration` lands in F-43, completing the triad.

---

## Consequences

### Opens

- **Commercial BYOR multi-language sensors** become a plugin shape. A Go sensor for Go source code ships as: a `go` artifact_type declaration (per ADR-090), a `go_audit_violation_sensor.yaml` worker declaration with `artifact_type: [go]` and a chosen `rule_namespace`, and a Python class subclassing `Worker` that calls `post_finding(artifact_type="go", sub_namespace=..., identity_key_value=..., payload=...)`. No engine fork; no per-sensor subject format authoring. ADR-084 D1 plugin shape realised.
- **Compliance-evidence sensors** become writable. A customer with a regulatory evidence corpus declares their own artifact_type (per ADR-090) and pairs it with a sensor declaration that observes that corpus and emits findings into the standard Blackboard via the typed API. The audit loop runs unchanged.
- **F-41 #415 closes.** Verification gates 4 and 6 are fully met at D5 Phase 4 completion. The issue closes per ADR-090's stated criterion.
- **F-43 becomes implementable** as its own ADR. The artifact_type-as-declared-parameter pattern and the canonical subject format are established; F-43's scope contracts from "design the model" to "extend the model to actions, decide where action declarations live."
- **The four-sensor heterogeneity collapses to one contract.** Subject-format variance is eliminated, not just documented. The canonical format is the single source of truth across every sensor today and every sensor that ships later.
- **Subject-search and dedup become artifact-type-aware by default.** A query for "all findings about artifact `python`" is now a clean prefix scan on `python::*`. Today this requires knowing which subject conventions various sensors used. The canonical format makes the registry the natural query key.

### Closes

- The Python-shaped sensor layer. Every sensor declares its artifact_type list; none assume Python.
- The drift surface ADR-090 D5 left open. `supported_sensors` becomes authored ∧ verified, not authored ∧ ignored.
- F-41 verification gates 4 and 6 (partial → fully met).
- The hardcoded `get_artifact_type("python")` in `AuditViolationSensor.run` (introduced in F-41 Phase 2 as an explicit forward-pointer to F-42).
- The three accidental subject-format conventions. One canonical format replaces them.
- The string-subject `post_finding(subject, payload)` API. Sensors cannot author subject strings; the framework computes them.

### Defers (filed)

- **F-43 implementation** (#417) — pluggable action model. D6 declares the forward contract; the ADR is F-43's deliverable.
- **`architecture.artifact_discovery_through_registry` engine check** (#566) — promoting the rule from advisory to blocking requires the engine-side check distinguishing legitimate non-discovery rglob sites from artifact-discovery bypass. Tracked in Phase 7 alongside the sensor_supported_by_declaration promotion.
- **`.specs/phases/*.yaml` artifact_type coverage** — registry gap surfaced by D3 coherence analysis. Filed as a sub-issue of F-42 during Phase 2; resolution chooses between extending `intent_yaml`'s discovery glob or declaring a new `phase_yaml` type. CCC's phase-row sub-namespace is parked until the gap closes.

### Defers (newly identified — to file as GH issues during implementation)

- **Subject migration data-rewrite tooling.** Phases 3 and 5 each include a one-shot Blackboard subject rewrite. The rewrite logic is deterministic but the data-volume risk is non-trivial on a long-running deployment. File a sub-issue to specify the rewrite as a governed atomic action (`migrate.blackboard.subjects.<phase>`) with row-cap and partial-walk guards per [[destructive-autonomous-needs-rails-first]].
- **Worker schema documentation surface.** The contract is distributed across `worker.schema.json` field descriptions and ADR text. A canonical `.specs/papers/` surface describing what each `class` value means and what fields each demands would consolidate. File as a follow-up.
- **Sub_namespace prefix-relation validation framework hook.** D2 specifies that emitted sub_namespaces must equal the declared rule_namespace or extend it via dotted suffix. The framework validates at `post_finding` call time. The exact error shape and observability (does it raise, log, refuse, surface as a finding?) is implementation detail to file during Phase 1.

### Risks

- **Schema-extension regression risk.** Adding required fields to `worker.schema.json` can break declarations not covered by D3's Phase 2 update. Mitigation: the required-only-for-`class: sensing` constraint scopes the requirement; all four sensing-class declarations are updated in Phase 2 in the same change-set; the advisory invariant in D4 surfaces any missed declarations before they fail-closed in Phase 7.
- **Subject-migration regression risk.** Phases 3 and 5 each rewrite Blackboard subjects. A consumer query that escapes the audit (e.g. a CLI ad-hoc filter, a dashboard widget, an external script) and still expects the old format breaks silently. Mitigation: per-phase verification under the deterministic transform requires finding-set equivalence; consumer enumeration is done explicitly during each phase's pre-flight; a one-cycle observation window post-migration confirms no orphaned consumers. The risk is bounded because every consumer in `src/` is grep-able for the old prefix strings.
- **Behavioural-identity verification under transform.** Phases 3–5 verify identity under the deterministic subject transform, not raw byte equivalence. A bug in the transform definition or the rewrite implementation could pass identity verification while introducing real drift. Mitigation: the transform is a documented closed mapping (D5 phase text); the rewrite is a single SQL update per phase; both are reviewable in the phase commit before merge.
- **F-43 contract divergence risk.** D6 commits to the artifact_type-as-array pattern and the canonical subject format but leaves action declaration shape open. If F-43's action declarations land in a fundamentally different surface than worker declarations, the cross-validation rule pattern needs adapting. Mitigation: D6 explicitly declares which commitments are forward-shared and which are F-43's choice; the ADR-079 D9 pattern is robust to either shape.
- **Heavy artifact-type discovery starving the daemon loop.** A new sensor declaring an artifact_type whose discovery globs walk a large tree may need ADR-081 D2 process isolation. Mitigation: the `requires_dedicated_process` field already exists; this ADR adds a recommendation in the schema description that sensor authors profile their first run and set the flag if the cycle observes a long synchronous stretch. No automatic detection — same posture as ADR-081.
- **Two-API coexistence window.** Phases 1–6 leave both the string-subject API and the typed API live. A new sensor authored during this window might pick the wrong one. Mitigation: the deprecation marker on the string-subject API surfaces in IDE/linter output; Phase 1 lands the advisory rule that flags any new caller; the window closes mechanically at Phase 6.
- **Consumer-distinction predicate drift.** The Phase 3 / Phase 5 predicates are derived from `IntentRepository`. A future audit sensor declaring a `rule_namespace` whose `.intent/rules/<ns>/` directory is empty would silently fall outside `is_audit_violation_subject`'s domain — findings posted by that sensor become invisible to the violation_remediator pipeline. Mitigation: the per-phase transform-equivalence verification catches any pre-existing silent-namespace case (predicate over rewritten rows MUST match LIKE filter over originals; divergence flags exactly this risk); D1's daemon-load check makes the namespace declaration itself visible. If a real BYOR case lands a rule_namespace with no backing rules, file as a coherence check candidate at that point.

---

## Verification

This ADR closes — and F-42 ships — when all of the following hold:

1. **Schema extension present and validating.** `META/worker.schema.json` declares `mandate.scope.artifact_type` as an array (`minItems: 1`) and treats it required for `class: sensing` declarations. `rule_namespace` is required for every sensing-class declaration. An intentionally-malformed sensor declaration (missing `artifact_type`, unregistered artifact_type id, missing `rule_namespace`) fails `IntentRepository.initialize()` with a clear error citing the field.
2. **Framework-derived subject format enforced.** `shared.workers.base.Worker.post_finding(artifact_type, sub_namespace, identity_key_value, payload)` is the only API. The string-subject overload is removed. The framework constructs subjects per D2; a sensor that calls `post_finding` with an artifact_type outside its declared list, or a sub_namespace that does not equal or extend its declared `rule_namespace`, raises with a clear error.
3. **Four sensor declarations updated.** `audit_sensor_purity.yaml`, `audit_sensor_architecture.yaml`, `audit_sensor_logic.yaml`, `audit_sensor_modularity.yaml`, `audit_violation_sensor.yaml` (paused base), `test_coverage_sensor.yaml`, `test_runner_sensor.yaml`, `coherence_sensor.yaml` all carry the new fields per D3.
4. **`supported_sensors` populated across the registry.** Every artifact_type declared by any sensor (`python`, `test`, `spec_markdown`, `intent_yaml`) lists every backing sensor. The invariant D4 holds at `blocking` enforcement after Phase 7.
5. **`AuditViolationSensor` migrated end-to-end + audit-violation predicate centralized.** Reads `artifact_type` from declaration. Posts under canonical format. Existing `audit.violation::*` Blackboard rows rewritten to `python::*` under the deterministic transform. `shared.infrastructure.intent.audit_namespaces.is_audit_violation_subject` is the only mechanism distinguishing audit-violation findings across the consumer surface; no `audit.violation::` string literal survives in `src/`. Finding output identical under transform; predicate over rewritten rows yields the same row identity-key set as the pre-migration LIKE filter over the originals. F-41 verification gate 4 fully met.
6. **CCC sub-discovery migrated.** `CoherenceChecker._adr_paths`, `_northstar_paths`, `_phase_paths`, and the row-check discovery surfaces in `mind.coherence.checks.{row2_grounding, row3_citation, row4_naming, vocabulary}` consult the spec_markdown / intent_yaml / intent_json registry discovery globs as applicable. CCC runs inline during audit (not as a Worker per D3) — its subject format is unchanged by this ADR. CCC outcome (finding identifier set) under registry-routed discovery identical to pre-migration outcome. F-41 verification gate 6 fully met.
7. **`TestCoverageSensor`, `TestRunnerSensor`, and `CoherenceSensorWorker` migrated + test-remediation predicate centralized.** Discovery and observation walks consult the registry. Subjects rewritten under transform. `shared.infrastructure.intent.test_namespaces.is_test_remediation_subject` is the only mechanism distinguishing test-remediation findings; `TestRemediatorWorker`'s dedup queries call it; no `test.run_required::`, `test.missing::`, or `test.failure::` string literal survives in `src/`. `coherence_sensor` is detection-only per ADR-027 — verified via grep that no production code consumes its subjects for dedup. Coverage-gap, test-execution, and incoherence finding sets identical under transform; predicate over rewritten rows yields the same row identity-key set as pre-migration filters over the originals.
8. **D4 invariant blocking.** `governance.taxonomy.sensor_supported_by_declaration` is at `blocking` enforcement. Live audit shows zero findings — every sensor declares a registered artifact_type AND every `supported_sensors` entry has a backing sensor declaration.
9. **Stability commitment recorded.** `.intent/CHANGELOG.md` carries an entry marking the worker.schema.json + canonical subject format + typed post_finding API as the second ADR-084 D1 published contract, with the F-42 effective date.
10. **F-43 forward contract referenced.** F-43's GitHub issue (#417) carries a back-reference to this ADR's D6, confirming the action-side will follow the same artifact_type-as-array pattern and (where actions emit Blackboard findings) the canonical subject format.

When all ten hold, F-42 #416 closes. The remaining open-completeness gate item is F-43 #417.

---

## Note — D3 scope correction and sensing-class taxonomy finding (2026-06-05, same day as acceptance)

Pre-implementation recon for Phase 1 surfaced two errors in the originally-drafted D3 + Phase 4 + Phase 5 + verification gates. The amendments above are in-line; this note records what changed and why for archaeological visibility.

1. **`coherence_sensor` identity.** The original draft conflated `coherence_sensor.yaml` (the ADR-027 fixer-sensor incoherence detector) with the Constitutional Coherence Checker (CCC). They are different: CCC runs inline during the audit cycle via `CoherenceChecker`; it is not a Worker. `coherence_sensor` is a `class: sensing` worker that queries `proposal_consequences` for re-detected violations. D3's coherence_sensor entry corrected to `artifact_type: [python]` (the substrate where check_id+file_path violations apply); Phase 4 / Phase 5 / verification gates 6–7 amended to reflect that CCC migration affects internals only and `CoherenceSensorWorker` migrates alongside the test sensors in Phase 5.

2. **Scope: 12 true sensors, 9 misclassified `class: sensing` workers.** The original draft named four sensor families. Filesystem enumeration found 21 workers carrying `class: sensing`. Twelve are true artifact observers; nine (embedders, crawlers, transformers, aggregate auditors) are not. Forcing artifact_type on the nine would be a category error. D3 amended to enumerate the 12 explicitly and to declare the conditional schema enforcement (`if class == sensing then artifact_type required`) staged behind a separate reclassification pass, tracked at a sub-issue filed alongside this amendment.

These corrections do not alter the substantive decisions: D1 field shape, D2 canonical subject format, D4 invariant, D6 forward contract, D7 stability commitment all hold as accepted. D3's scope tightens to match recon-discovered reality; D8 advisory→blocking promotion gains an additional prerequisite (sensing-class reclassification).

---

## Note — Phase 4 pre-implementation recon corrections (2026-06-05)

Pre-implementation recon for D5 Phase 4 surfaced two further corrections to the D3 amendment + Phase 4 description + verification gate 6 above. The amendments are in-line; this note records what changed and why.

1. **`_phase_paths` registry-gap claim was wrong.** The D3 amendment originally claimed `.specs/phases/*.yaml` was un-typed and parked `_phase_paths` until a follow-up sub-issue closed. Filesystem recon found that CCC's `_phase_paths` actually reads `.intent/phases/*.yaml` (not `.specs/phases/`). `.specs/phases/` does not exist as a directory. `intent_yaml`'s `.intent/**/*.yaml` discovery glob fully covers the six phase files (`audit.yaml`, `execution.yaml`, `interpret.yaml`, `load.yaml`, `parse.yaml`, `runtime.yaml`). No gap, no sub-issue. `_phase_paths` migrates normally in Phase 4.

2. **`vocabulary` check was missed from Phase 4 scope.** The original Phase 4 description named three row checks (`row2_grounding`, `row3_citation`, `row4_naming`). The recon enumeration of CCC discovery surfaces surfaced a fourth: `vocabulary._iter_governance_markdown` walks `.specs/{decisions,papers,northstar}/*.md` and carries the same spec_markdown discovery shape. Without including vocabulary in Phase 4, one CCC discovery surface would remain bypassing the registry. Amended above.

Neither correction alters the substantive Phase 4 decision: CCC discovery routes through the registry, behavioural identity is the gate. Scope tightens to include eight surfaces (not seven) and `_phase_paths` migrates rather than parks.

---

## Note — #570 closed; D1 conditional enforcement landed (2026-06-05)

The sensing-class taxonomy audit filed alongside D3's Phase 1 amendment (#570) closed same-day with the reclassification of the nine workers identified in that amendment:

- **Five → `acting`**: `audit_ingest_worker` (translator: previous-audit-run findings → blackboard findings), `capability_tagger` (LLM-driven capability assignment writer), `governance_embedder` (Qdrant `governance_claims` writer), `prompt_extractor_worker` (source-file prompt extractor), `repo_embedder` (Qdrant collection writer per ADR-018).
- **Two → `governance`**: `commit_reachability_auditor` (commit-graph aggregate auditor per ADR-019 D1), `observer_worker` (system-state observer feeding `core.system_health_log`).
- **One retained `sensing` with declared artifact_type**: `intent_inspector` → `[intent_yaml, intent_json]` with `rule_namespace: intent.inspection`.
- **One retained `sensing` with broader declared artifact_type**: `repo_crawler` → `[python, test, doc, prompt, report, infra, intent_yaml, intent_json, spec_markdown]` with `rule_namespace: coherence.repo_artifacts`. The full list reflects the ADR-070 D8 writer-as-sensor pattern: the crawler walks every crawler-indexed type and emits `coherence.repo_artifacts.drift` findings inline.

No new `identity.class` value was needed. The four existing classes (`sensing`, `acting`, `governance`, `supervision`) covered every reclassified worker honestly.

**The D1 conditional enforcement landed in the same change-set.** `META/worker.schema.json` now carries an `allOf` block requiring `mandate.scope.artifact_type` and `mandate.scope.rule_namespace` for `class: sensing` declarations. Daemon-load validation rejects sensing-class workers missing either field. Phase 1's staged conditional is now active.

Cross-validation invariant (D4) verified post-reclassification: 25 introspected pairs ≡ 25 authored pairs, symmetric diff empty. Adds: 1× `intent_yaml::intent_inspector`, 1× `intent_json::intent_inspector`, 9× repo_crawler across its declared artifact_types. The new `class: sensing` population is 14 workers (12 from Phase 1 + intent_inspector + repo_crawler).

The Phase 7 advisory→blocking promotion of `sensor_supported_by_declaration` remains gated on Phase 6 (legacy `post_finding(subject, payload)` API removal), independent of #570.

---

## Note — D5 Phase 3 + Phase 5 consumer-distinction strategy (2026-06-05, same day as acceptance)

Pre-implementation recon for D5 Phase 3 surfaced an architectural fork the original D5 phase text under-specified. After migration, `AuditViolationSensor`'s findings share the `python::*` subject prefix with `TestCoverageSensor`, `TestRunnerSensor`, `CoherenceSensorWorker`, and (per #570) `repo_crawler`. The legacy `audit.violation::*` prefix discriminator — used at ~17 sites across `body.services.blackboard_service`, `will.workers.violation_*`, `will.self_healing.remediation_interpretation.finding_normalizer`, `mind.governance.auditor`, `mind.logic.engines.{artifact_gate, workflow_gate.checks.audit}`, `body.atomic.remediate_cognitive_role`, `body.services.consequence_log_service`, `cli.resources.runtime.health`, and `cli.resources.workers.remediate` — disappears under canonical-format migration. The consumer surface needs a replacement mechanism.

Five candidate strategies were evaluated against CORE values (honest contracts, no escape hatches, bootstrap on itself, two-surface principle, no over-engineering):

- **A1 — hardcoded sub_namespace inclusion list** in SQL. Rejected: literal list scattered across ~17 sites; drift vector for new audit namespaces; BYOR-unfriendly.
- **A2 — derived predicate** computed from `IntentRepository.rule_namespaces()` at call time, centralized in `shared.infrastructure.intent.audit_namespaces`. **Selected.** The audit-namespace set is `.intent/rules/`'s top-level keys — already in IntentRepository. No new YAML field, no new column, no new constitutional vocabulary. A third-party BYOR audit sensor declaring `rule_namespace: go.security` with rules at `.intent/rules/go.security/` automatically counts.
- **B — payload metadata filter** (`payload->>'kind' = 'audit_violation'`). Rejected: requires GIN index for the per-cycle hot path, adds a new payload field requiring framework-side write discipline across every sensor and a payload schema audit across every consumer site, all for one query class.
- **C — new `producer_class` column on `core.blackboard_entries`**. Rejected: schema migration on a 5,620+ row hot table for one query class; denormalizes producer identity into consumer's index; adjacent to ADR-080's two-surface anti-pattern.
- **D — JOIN to `worker_registry` on `declaration_name` pattern `audit_sensor_%`**. Rejected: pattern is out-of-band convention; BYOR audit sensors with different names silently invisible.
- **E — consumer-declared (`mandate.consumes` on `violation_remediator.yaml`) + A2 derivation hybrid**. Deferred: E adds a new YAML field shape on top of A2's mechanism. A2 alone derives the same answer from already-present declarations. If a third consumer pipeline ever materialises with the same shape, E.A2 becomes the natural factor-up to a `shared.infrastructure.intent.consumer_domains` framework — file at that point, not now.

The selected mechanism (A2) is encoded in D5 Phase 3 + Phase 5 + Phase 6 text in-line, with a Risks entry on predicate-derivation drift and one-sentence extensions on verification gates 5 and 7 requiring the predicate centralization. The pattern is **not** codified as a new constitutional decision — the abstraction is used twice in this single ADR (audit-violation, test-remediation), inside one change-set; the third use would earn its own decision-level naming per the protocols-reflex discipline.

Pre-implementation recon also corrected one factual claim in the strategy framing: the original prompt cited ~5 consumer sites; filesystem grep across `src/` found ~17. The Phase 3 description now treats consumer enumeration as a Phase 3 commit artifact rather than naming a count.

The substantive decisions D1, D2, D3, D4, D6, D7, D8 are unaffected by this amendment.

---

## Note — D5 Phase 3 implementation: predicate-source correction (2026-06-05, same day as Phase 3 ship `0854243e`)

Implementation of D5 Phase 3 surfaced a semantic over-claim in the A2 strategy text above. The amendment said the predicate derives from `IntentRepository.rule_namespaces()` — "the audit-namespace set is `.intent/rules/`'s top-level keys." Pre-rewrite smoke testing showed this matches more subjects than belong to the audit-violation pipeline:

```
[FAIL] python::coherence.incoherence::abc123              → True  (expected False)
[FAIL] python::coherence.repo_artifacts.drift::x.yaml     → True  (expected False)
```

The 24 top-level segments of `_rule_index` include `coherence`, `ai`, `async`, `atomic_actions`, etc. — only 8 of which are backed by an `audit_sensor_*.yaml` declaration. The remaining 16 are rule directories consumed by CCC inline, by `CoherenceSensorWorker`, by `repo_crawler`, or by no production sensor at all. Phase 5 will migrate `coherence_sensor` and `repo_crawler` to post under `python::coherence.*::*` — if the predicate stayed on top-level-segment derivation, `violation_remediator` would start claiming their findings and try to remediate them through the wrong pipeline.

**Correction encoded in `0854243e`:** the predicate's namespace set derives from the `mandate.scope.rule_namespace` values declared by worker declarations whose `implementation.class == "AuditViolationSensor"`, not from `IntentRepository.rule_namespaces()`'s top-segment view. The producer-side declarations ARE the authoritative consumer filter — if no audit sensor is declared to emit under `<ns>`, the violation_remediator pipeline has no business claiming `python::<ns>::*` findings.

`IntentRepository.rule_namespaces()` ships as the general utility the original amendment named (top-level segments of `_rule_index`). The audit-violation predicate uses the tighter, declaration-derived set. This is a Phase 3 module-internal helper (`_audit_violation_namespaces()` in `shared.infrastructure.intent.audit_namespaces`), not a public IntentRepository surface — Phase 5's test-remediation predicate will adopt the same shape against `test_coverage_sensor.yaml`/`test_runner_sensor.yaml`.

**BYOR contract preserved.** A third-party audit sensor shipped as `.intent/workers/audit_sensor_<x>.yaml` with `mandate.scope.rule_namespace: <ns>` and rules at `.intent/rules/<ns>/` is automatically claimed by the predicate. No enumeration drift across consumer call sites; no constitutional vocabulary change.

**Risk re-evaluation.** The Risks entry on predicate-derivation drift in D5 still applies but tightens: a sensor declaring a `rule_namespace` whose `.intent/rules/<ns>/` tree is empty still registers in the predicate set (matched by declaration). `_resolve_rule_ids` returns an empty rule list, so the producer never emits findings, and the predicate stays correct by vacuous truth. The original Risk framing (silent-invisible findings) does not apply under the corrected derivation.

The substantive decisions D1, D2, D3, D4, D6, D7, D8 — and A2's selection over A1/B/C/D/E — are unaffected by this correction. Only the prose specifying the derivation source tightens.

---

## Note — D5 Phase 5 implementation: test-remediation predicate scope correction (2026-06-05, same day as Phase 5 ship `e0640a0d`)

Implementation of D5 Phase 5 surfaced a parallel scope over-claim in the Phase 5 prose. The amendment text said the test-remediation predicate is "derived from the sub_namespace set declared by `test_coverage_sensor.yaml` and `test_runner_sensor.yaml`'s `mandate.scope.rule_namespace` plus their D2-permitted dotted extensions (`test.coverage`, `test.runner.missing`, `test.runner.failure`)." Pre-implementation tracing showed this conflates two distinct consumer pipelines:

| Producer subject (Phase 5) | Consumer | Lifecycle role |
|---|---|---|
| `python::test.coverage::*` | **TestRunnerSensor** | Work-to-do signal: pick up gap, run pytest on the corresponding test file, emit a runner.* finding |
| `python::test.runner.missing::*` | **TestRemediatorWorker** | Drive `flow.build_tests` proposal — generate the missing test |
| `python::test.runner.failure::*` | **TestRemediatorWorker** | Drive `flow.build_tests` proposal — fix the failing test |

Pre-Phase-5 code honored this split: `test_remediator/_operations.py` claimed `test.missing::%` and `test.failure::%` only, never `test.run_required::%` (that was TestRunnerSensor's intake). If the predicate included TestCoverageSensor's namespace, TestRemediator would race-claim against TestRunnerSensor over `python::test.coverage::*` rows under `FOR UPDATE SKIP LOCKED` and route gap signals straight to `build.tests` proposals — bypassing the pytest verification step that establishes whether the test is missing (`runner.missing`) or merely failing (`runner.failure`).

**Correction encoded in `e0640a0d`:** the predicate's namespace set derives from the `mandate.scope.rule_namespace` value declared by workers whose `implementation.class == "TestRunnerSensor"` (today: `{"test.runner"}`), accepting that value AND its D2-permitted dotted extensions (`test.runner.missing`, `test.runner.failure`). TestCoverageSensor's `test.coverage` namespace is intentionally outside the predicate.

The internal helper class set is named `_REMEDIATION_SENSOR_CLASS_NAMES` rather than the broader `_TEST_SENSOR_CLASS_NAMES` from the first draft, to encode the semantic distinction: "test-remediation pipeline interest" ≠ "test-sensor output." If a third test sensor ships later whose output IS routed to TestRemediator, it joins this frozenset.

**Pattern with Phase 3.** The two predicate-source corrections (audit-violation Phase 3 → declaration-derived not rule-tree-derived; test-remediation Phase 5 → remediation-consumer-derived not test-sensor-derived) share a structural lesson: the ADR prose framed each predicate around its OBVIOUS source (rule directories; test sensors), but the HONEST source is "what does the downstream consumer actually claim?" Producer/consumer pipelines route on consumer-side intent, not producer-side classification. The two Notes record the prose→implementation refinement; the substantive decision (A2 derived predicate) holds in both cases.

The third predicate use earns the `consumer_domains` factor-up per the protocols-reflex discipline noted at the end of the D5 Phase 3 + Phase 5 amendment.

The substantive decisions D1, D2, D3, D4, D6, D7, D8 — and Phase 5's selection of the same predicate shape as Phase 3 — are unaffected by this correction. Only the prose specifying the derivation source tightens.

## Note — D5 Phase 6 implementation: class:acting allowance + compound identity (2026-06-05, same day as Phase 6 commit 0)

Pre-implementation recon for D5 Phase 6 surfaced two prose/implementation gaps in the D2 contract text. Both are framing under-claims, not behavioural drift — the runtime API and the `sensor_supported_by_declaration` rule already encode the corrected reading; only the ADR prose lagged. This Note closes the gaps in the same shape as the Phase 3 and Phase 5 Notes (`16980564`, `73ad4afc`).

### Gap 1 — "Phase 1 transition allowance" is the permanent class:acting escape

The D2 prose framed `post_artifact_finding`'s no-declaration branch as a "Phase 1 transition allowance — sensor declarations not yet updated" (`shared.workers.base.Worker.post_artifact_finding` docstring, lines around 305). That framing assumed every caller of the typed API is or will become a `class: sensing` worker that declares `mandate.scope.artifact_type`.

Phase 6 recon mapped every surviving `post_finding(subject, payload)` caller and found the assumption wrong. The non-sensor caller set splits cleanly by worker class:

- `class: sensing` workers (`intent_inspector` is the only one in the surviving call set) declare `mandate.scope.artifact_type` and route through the validating branch of `post_artifact_finding`.
- `class: acting` workers (`prompt_artifact_writer`, `prompt_extractor_worker`, `audit_ingest_worker`, the shop managers, `proposal_consumer_worker` itself) structurally do not declare `mandate.scope.artifact_type` — they emit findings as a consequence of action, not as observation. The "no declared artifact_type" branch is their *permanent* dispatch path, not a transition state.

The constitutional pair `sensor_supported_by_declaration` already encodes this: `taxonomy_gate.py:207-211` excludes worker declarations without `artifact_type` from the introspected set "during the Phase-1 transition window so the nine misclassified `class: sensing` workers... do not surface as phantoms before reclassification." The exclusion is named transient but is structurally permanent for `class: acting` workers — they have nothing to declare and nothing to be paired against. The rule's name (`sensor_supported_by_declaration`, not `worker_supported_by_declaration`) is the corrected reading made explicit.

**Correction.** The Phase 1 transition framing in the `post_artifact_finding` docstring and in the `taxonomy_gate.py` comment is a `class: sensing` reading. The honest framing across worker classes is:

- `class: sensing` workers MUST declare `mandate.scope.artifact_type`; their emissions are validated against the declaration and they participate in the constitutional pair.
- `class: acting` workers MAY emit via `post_artifact_finding` without declaring `mandate.scope.artifact_type`; the validation no-ops by design and they are structurally outside the constitutional pair (they are not sensors).

The `class: sensing` rule promotion in Phase 7 (`sensor_supported_by_declaration` advisory → blocking) is unaffected by this clarification — the rule already scopes to declaring workers. The clarification only relabels what was named "transition" as what it has always been structurally: the `class: acting` dispatch path.

### Gap 2 — `identity_key_value` MAY contain `::` separators (compound identity)

The D2 prose specified the canonical subject format as `<artifact_type>::<sub_namespace>::<identity_key_value>` and described `identity_key_value` as "a single string." Pre-implementation review for Phase 6 surfaced that two of the existing prompt-pipeline subject families already use compound identity:

- `prompt_artifact_writer.py:184` emits `prompt.artifact::<file_path>::<line_number>` — identity is per-call-site, naturally compound.
- `proposal_pipeline_shop_manager.py:191` emits `proposal.repeated_failure::<action_id>::<rule_id>` — identity is per-action-per-rule, naturally compound.

The runtime already permits this: `Worker.post_artifact_finding` concatenates `f"{artifact_type}::{sub_namespace}::{identity_key_value}"` without parsing `identity_key_value`; the predicate functions (`is_audit_violation_subject`, `is_test_remediation_subject`) and SQL claim filters (`LIKE 'python::prompt.artifact::%'`) use prefix matching, not split-based parsing. Compound identity "just works" under the existing infrastructure — the ADR prose just hadn't said so.

**Correction.** `identity_key_value` MAY contain `::` separators when the artifact has natural compound identity (e.g., file+line, action_id+rule_id, file+function_name). The framework treats `identity_key_value` as an opaque string passed through to the canonical subject.

**Constraint that keeps compound identity safe** — and the constitutional invariant Phase 6 makes explicit: any consumer that needs to extract `artifact_type` or `sub_namespace` from a subject MUST do so via prefix matching (e.g., `subject.startswith(f"{artifact_type}::{sub_namespace}::")`) or via `split("::", 2)` keeping at most three segments. Consumers MUST NOT call `subject.split("::")` without a limit, because the resulting list length depends on whether the producer's identity is simple or compound. The recon found zero current consumers that violate this invariant; the constraint is documented now so future consumers inherit it.

### Phase 6 commit 0 scope

The substantive Phase 6 work begins with commit 0, which migrates the `prompt.artifact::*` subject family to canonical format. Four files change in one commit:

- `body/atomic/remediate_cognitive_role.py` — return shape switches from `{"subject", "payload"}` to typed `{"artifact_type": "python", "sub_namespace": "prompt.artifact", "identity_key_value": <file_path>, "payload": ...}`.
- `body/workers/prompt_artifact_writer.py` — `post_finding(subject=f"prompt.artifact::{file}::{line}", ...)` migrates to `post_artifact_finding(artifact_type="python", sub_namespace="prompt.artifact", identity_key_value=f"{file}::{line}", ...)`. Compound identity by design (Gap 2).
- `body/workers/call_site_rewriter.py` — claim-filter prefix updates from `prompt.artifact::%` to `python::prompt.artifact::%` so the consumer matches the new canonical subject.
- `will/workers/proposal_consumer_effects.py` — dispatch site at `apply_success_effects` switches from `worker.post_finding(subject, payload)` to `worker.post_artifact_finding(artifact_type, sub_namespace, identity_key_value, payload)` forwarding the typed parameters from the action's finding_to_post. `ProposalConsumerWorker` is `class: acting` (Gap 1); no declaration change.

No blackboard row rewrite was needed — a pre-flight count returned zero `prompt.artifact::*` rows. The `class: sensing` legacy callers (intent_inspector + setup_error sites) and the remaining `class: acting` callers (shop managers, completion/failure reports, instrument signals) migrate in subsequent Phase 6 commits per the recon report; this Note's scope is the prompt.artifact pipeline and the two D2 clarifications that apply across the remaining Phase 6 work.

### Pattern with Phases 3 and 5

Phase 6 is the fourth same-shape ADR-091 prose/implementation gap closed by a same-day Note. The pattern across the four (D3 sensing-class taxonomy, Phase 3 audit-violation predicate source, Phase 5 test-remediation predicate scope, Phase 6 class:acting allowance + compound identity): the ADR prose framed a contract narrowly (specific sensors, specific rule directories, single-component identity), and the implementation surface was always slightly broader (the API takes worker class as a structural input; identity is opaque). Each Note records the implementation's broader honest reading and confirms the substantive D1–D8 decisions are unaffected.

The substantive decisions D1, D2, D3, D4, D6, D7, D8 — and Phase 6's selection of `post_artifact_finding` as the single canonical emission API — are unaffected by these clarifications. The prose of D2 tightens around what `identity_key_value` may contain and what `class: sensing` vs `class: acting` mean for the declaration requirement; the runtime API and the rule do not change.

## Note — D5 Phase 6 commit 1 implementation: Gap 1 supervision class + Gap 3 runtime-state findings (2026-06-05, same day as Phase 6 commit 0)

Pre-implementation recon for D5 Phase 6 commit 1 surfaced two further D2 prose/implementation gaps. Both are scope clarifications, not behavioural drift — the runtime is unchanged. This Note records them in the same append-only shape as the prior four. It also pins commit 1's actual landed scope, which is narrower than the recon's first framing.

### Gap 1 amendment — `class: supervision` workers also use the no-declaration branch

The prior Note's Gap 1 enumerated two classes for `post_artifact_finding` callers: `class: sensing` (must declare `mandate.scope.artifact_type`, validated) and `class: acting` (MAY emit without declaring, structurally outside the constitutional pair). Phase 6 commit 1 recon mapped the surviving non-sensor caller set against `.intent/workers/*.yaml` and found three `class: supervision` workers that the prior Note labelled `class: acting`:

- `blackboard_shop_manager` — declared `class: supervision`
- `worker_shop_manager` — declared `class: supervision`
- `proposal_pipeline_shop_manager` — declared `class: supervision`

The structural argument the prior Note made still holds: workers that do not declare `mandate.scope.artifact_type` route through the validation no-op branch of `post_artifact_finding`. The branch is keyed on absence-of-declaration, not on `identity.class`. The prior Note's per-class enumeration was incomplete; the corrected reading is:

- `class: sensing` workers MUST declare `mandate.scope.artifact_type`; their emissions are validated and they participate in the constitutional pair (`sensor_supported_by_declaration`).
- `class: acting` and `class: supervision` workers MAY emit via `post_artifact_finding` without declaring `mandate.scope.artifact_type`; validation no-ops by design and they are structurally outside the constitutional pair (they are not sensors).
- `class: governance` workers do not call `post_artifact_finding` in the current surviving set.

The rule promotion in Phase 7 (`sensor_supported_by_declaration` advisory → blocking) remains unaffected — the rule already scopes to declaring workers.

### Gap 3 — runtime-state findings (shop managers) do not fit the D2 canonical subject shape

The shop-manager workers emit findings about **runtime DB entities**, not about source-code artifacts on disk:

- `blackboard_shop_manager` emits `blackboard.entry_stale::<entry_uuid>` when a blackboard entry exceeds its SLA tier. The "artifact" is a row in `core.blackboard_entries`, addressed by uuid.
- `worker_shop_manager` emits `worker.silent::<worker_uuid>` when a worker stops heartbeating. The "artifact" is a row in `core.worker_registry`, addressed by uuid.
- `proposal_pipeline_shop_manager` emits `proposal.{stuck_approved,stuck_executing,repeated_failure}::*` when a proposal is stuck or an action repeatedly fails. The "artifact" is a row in `core.proposals`, addressed by `proposal_id` or by compound `(action_id, rule_id)`.

These findings have legitimate `open → resolved` lifecycles: the shop managers themselves transition the finding to `resolved` (or `abandoned`) when the underlying runtime state recovers (`worker_shop_manager.py:201-208` calls `resolve_entries([entry_id])` in-process; `blackboard_service.resolve_stale_alerts_for_terminal_targets` SQL-updates open `blackboard.entry_stale::*` findings when the target row transitions terminal). They are not terminal-at-creation observations, so `post_observation` is the wrong API.

Fitting them into D2's canonical `<artifact_type>::<sub_namespace>::<identity_key_value>` shape requires either:

- Registering new `artifact_type` declarations (`runtime_blackboard_entry`, `worker_registry`, `proposal`) in `.intent/artifact_types/` — but the artifact_type schema (`.intent/META/artifact_type.schema.json`) currently requires `discovery` (a glob list, `minItems: 1`), `vector_collection` (qdrant routing), and a closed `identity_key` enum (`path`, `path_plus_anchor`, `uri`). Runtime DB entities have no on-disk discovery glob, no semantically meaningful vector collection, and need uuid-shaped identity keys. Registering them under the current schema is impossible; registering them after schema relaxation is a governance amendment to ADR-090 D2's closed vocabulary, not a Note-shape change.
- Re-using an existing artifact_type as a placeholder (e.g., `runtime`) — but no such artifact_type is registered, and inventing one without backing it with a declaration is the closed-vocabulary violation #566 will eventually flag.

The honest read is that ADR-091 D2's canonical subject shape was designed for findings about **observable code artifacts**, and runtime-state findings are a fourth subject family alongside findings (`<artifact_type>::<sub_namespace>::<identity_key_value>`), reports (`<worker_declaration_name>.<event_kind>`), heartbeats (`worker.heartbeat`), and observations (free string subject + terminal status). The Phase 6 prose did not name this fourth family; commit 1 surfaces it.

**Resolution.** Gap 3 is deferred to its own sub-decision (commit 1c), scoped to the five shop-manager emission sites. The sub-decision answers: extend the artifact_type schema to admit runtime-state entities (ADR-090 amendment), introduce a fourth canonical subject shape under D2 for runtime-state findings (ADR-091 amendment), or keep the shop managers on `post_finding(subject, payload)` permanently and exempt them from the Phase 6 closure. Each of the three options is heavier than a Note can carry honestly.

### Phase 6 commit 1 scope

With Gap 3 deferred, commit 1 ships the **seven sites that fit the current D2 contract** without schema or vocabulary changes:

- **Two `class: acting` sites** → `post_artifact_finding(artifact_type="python", ...)`:
  - `will/workers/audit_ingest_worker.py:105` — sub_namespace `ai.prompt.model_required`, compound identity `<file>::<line>`. Self-dedup at `:206` updates to canonical prefix.
  - `will/workers/prompt_extractor_worker.py:152` — sub_namespace `prompt.extraction`, compound identity `<file>::<line>`. Cross-worker claim filter at `:217` updates to match audit_ingest's new canonical prefix.
- **Two `post_report` sites** (completion records that were misusing `post_finding` for terminal-resolved events):
  - `body/workers/call_site_rewriter.py:251` — subject `prompt.rewrite.complete::<file>::<line>`.
  - `will/workers/violation_remediator_body/worker.py:499` — subject `audit.remediation.complete::<file>`.
- **Three `post_observation` sites** (terminal-at-creation failure/instrument records, `status=abandoned`):
  - `body/workers/call_site_rewriter.py:397` — subject `prompt.rewrite.failed::<file>`.
  - `will/workers/circuit_breaker.py:311` — subject `governance.circuit_breaker_tripped` (singleton).
  - `will/workers/violation_remediator.py:121` — subject `governance.instrument_degraded` (singleton).

No blackboard row rewrite is needed — pre-flight psql counts returned zero rows for all seven subject families. No schema changes. No new artifact_types.

### Deferred to subsequent Phase 6 commits

- **Commit 1b — `intent_inspector`.** Five sites (`:142`, `:277`, `:319`, `:352`, `:387`). Migration is non-mechanical: API switch + sub_namespace rename `intent_inspector.{structural,coherence,alignment}` → `intent.inspection.{structural,coherence,alignment}` to match the worker's declared `rule_namespace`, plus per-finding `artifact_type` selection between `intent_yaml` and `intent_json` based on path extension. Worker is `metadata.status: paused`; zero rows in flight. The two setup-error sites (`:277`, `:352`) move to `post_observation(status="abandoned")` in the same commit.
- **Commit 1c — shop managers (Gap 3 resolution).** Five sites across `blackboard_shop_manager`, `worker_shop_manager`, `proposal_pipeline_shop_manager`. Gated on Gap 3's sub-decision. SQL UPDATE migration for ~6140 in-flight legacy rows (`blackboard.entry_stale::*` 5209, `worker.silent::*` 897, `proposal.stuck_approved::*` 34) lands here, scoped to the chosen subject shape. Three lifecycle-drift consumers update atomically with the migration: `blackboard_query_service.py:280-281` (NOT LIKE stale-finder exclusions), `health.py:403` (`worker.silent` F-19 type_a classification), and `blackboard_service.py:45` (auto-resolve sweep for `blackboard.entry_stale::*`).
- **Commit 2 (delete `post_finding(subject, payload)` from `shared/workers/base.py`)** — gates on commits 1b AND 1c. Until both deferrals land, the legacy API survives as the structural escape for class: sensing intent_inspector (1b) and the unresolved runtime-state question (1c).

### Pattern with the prior Notes

The prior Note's pattern (D2 prose framed narrowly, implementation surface broader) holds here twice over. Gap 1 supervision is a pure prose under-claim that the runtime API already encoded. Gap 3 is structurally different — it surfaces that D2's `<artifact_type>::<sub_namespace>::<identity_key_value>` shape was authored against the on-disk-artifact-with-discovery model and does not cleanly extend to runtime-state DB entities. That gap deserves its own decision-level treatment, which is why commit 1c defers rather than carrying a Note correction.

The substantive D1–D8 decisions remain unaffected by Gap 1's amendment. Gap 3 will require D2 amendment when commit 1c lands; recording the question here now lets the sub-decision begin without re-discovering the recon.

## Note — D5 Phase 6 commit 1b shipped: scope simpler than commit 1's Note anticipated (2026-06-05, same day)

Commit 1b shipped at `9974fdd5` — single-file migration of `intent_inspector`'s 5 surviving `post_finding(subject, payload)` callers. The commit 1 Note (immediately above) anticipated "per-finding `artifact_type` selection between `intent_yaml` and `intent_json` based on path extension" as the genuinely-new shape of commit 1b. The pre-implementation recon falsified that anticipation: `intent_inspector._load_all_documents` at `:411-412` loads only `**/*.yaml` and `**/*.yml`. JSON documents in `.intent/` (101 of them) and markdown files (5) are never scanned. Every finding the worker emits is about a YAML document, so every emission uses the single `artifact_type="intent_yaml"`. No per-finding selection logic was needed.

The `intent_json` line in `intent_inspector.yaml`'s declared `mandate.scope.artifact_type: [intent_yaml, intent_json]` is aspirational — claimed but not yet emitted under. The constitutional pair `sensor_supported_by_declaration` is structurally one-directional: it enforces that every `supported_sensors` entry in an artifact_type declaration has a backing worker declaration, but it does not enforce the reverse (that every declared `artifact_type` in a worker's `mandate.scope` has actual emissions). The aspirational `intent_json` claim is permitted under the existing rule; it stays in place as a forward-looking signal until JSON inspection is implemented.

D2 is unaffected. The dotted-suffix sub_namespace extension (`intent.inspection` → `intent.inspection.{structural,coherence,alignment}`) was already documented in D2 prose (`post_artifact_finding` validator at `shared/workers/base.py:328-337`); commit 1b is the first non-test caller to exercise it.

Surviving `post_finding(subject, payload)` callers after commit 1b: 5, all in the three shop managers (Gap 3 deferral). Phase 6 commit 2 (delete legacy API) gates on commit 1c.

## Amendment — D2 third emission case: runtime-state findings with observable lifecycle (proposed 2026-06-05, pending governor acceptance)

### Status

**Revision B is the accepted D2 amendment** (governor decision 2026-06-05). The decision text, schema extension, runtime enforcement, F-42 mapping, and commit 1c implementation scope below are constitutional under ADR-091 from this commit forward. Revision A and the original draft are preserved as record of the review trail; both are superseded.

Implementation of commit 1c per Revision B's section (e) is the next change-set. Pending: that change-set has not landed yet — the amendment is accepted as a governance decision; the code/schema/rule work is queued for its own commit with its own pre-implementation recon.

### Revision A — incorporating external review (2026-06-05)

External adversarial review (ChatGPT, reading the repo via GitHub connector) accepted the load-bearing claim that the shop managers have a legitimate open → resolved lifecycle, but surfaced three concrete refinements and one wording clarification. All four are folded into the text below:

1. **Caller-class scope tightened from `supervision + acting` to `supervision` only.** The original draft permitted both classes. Live evidence in `src/will/workers/` shows runtime-state finding callers are supervision-class workers only; the inclusion of `acting` was a reflexive carryover from Note 4's `class: acting` allowance for `post_artifact_finding`'s no-declaration branch — which is the artifact-finding case, not the runtime-state case. Acting workers stay on `post_artifact_finding`. Tightening the scope removes a future temptation for acting workers to escape `artifact_type` declaration via the runtime API.

2. **Resolver-obligation invariant added** as the structural backing for the runtime-state case. Without it, `post_runtime_finding` is a free-string-subject escape hatch — exactly the constitutional fork risk the original draft warned about. The invariant converts the category boundary from descriptive to enforceable.

3. **`post_observation` docstring fix added to commit 1c's implementation scope.** The current docstring at `shared.workers.base.Worker.post_observation` names `worker.silent` as a canonical `status="abandoned"` example, internally inconsistent with the same docstring's "no remediation pathway" framing (`worker.silent` has observable recovery). The example must be removed; the implementation is more authoritative than the example. Failure to fix it leaves a future trap pointing readers toward exactly the wrong migration call this amendment prevents.

4. **Wording clarified** on the "three emission cases" framing, which mixed finding cases with all emission entry-types. Per the review: *D2 names two finding cases (artifact + runtime-state); observations are a separate terminal finding-record contract; reports and heartbeats are separate Blackboard entry types.*

Revision A also expands commit 1c's implementation scope to honour the resolver obligation: each surviving call site requires a documented resolver path in its worker module's docstring plus an open → resolved unit test. Commit 1c grows from "mechanical rename" to "mechanical rename + 5 resolver tests + 3 worker docstring updates + 1 docstring fix on `post_observation` + 2 governance rules" — still smaller than any of the original Gap 3 options.

### Why this amendment

> **SUPERSEDED by Revision B.** Revision B re-grounds the "why" on `awaiting_reaudit` ineligibility (ADR-045) rather than "observable open → resolved lifecycle"; the latter framing is incidental (one of three workers actually has an in-Python resolution pass; one delegates to SQL; one's yaml says "recovery is out of scope"), while the former is structural and uniform.

Commit 1's Gap 3 Note framed runtime-state findings (the shop managers' emissions) as a "gap in D2" — a problem to close by extending the artifact_type vocabulary, introducing a fourth canonical subject shape, or carving out a narrow legacy-API exemption. Commit 1c recon surfaced that the framing itself was the error. The three options were all reasoning inside the assumption that *every* finding-shaped blackboard emission must fit D2's `<artifact_type>::<sub_namespace>::<identity_key_value>` shape, and the recon kept hitting resistance because that assumption is false.

The shop managers' lifecycle — `post_finding(open)` once per stale entity, `resolve_entries` when the entity recovers — is **not deprecated drift**. It is the correct lifecycle for findings whose subject *has observable recovery*: `worker.silent::<uuid>` IS open while the worker is silent and IS resolved when the worker resumes heartbeating. The `worker_shop_manager` resolution pass and the `blackboard_service.resolve_stale_alerts_for_terminal_targets` SQL sweep aren't legacy cruft — they're the constitutional mechanism that makes the open→resolved transition meaningful.

The honest read of D2's contract is that **two finding cases exist** (artifact findings and runtime-state findings), only one of which D2 currently names. Observations are a separate terminal finding-record contract that sits alongside the finding cases; reports and heartbeats are separate Blackboard entry types.

### What D2 currently names

> **SUPERSEDED by Revision B.** The "third case D2 doesn't name" framing presumed two finding APIs were the right shape. Revision B replaces this with a single-API + `resolution_mechanism` field design; the cut is between three closing-authority values, not three subject-shape families.

D2 (the canonical subject format decision) names two cases explicitly:

- **Findings** about observable code artifacts: shape `<artifact_type>::<sub_namespace>::<identity_key_value>`, emitted via `post_artifact_finding`, lifecycle open → resolved by a remediation worker.
- **Reports** about completed worker cycles: shape `<worker_declaration_name>.<event_kind>`, emitted via `post_report`, terminal at creation with `status="resolved"`.

A third case has been load-bearing in the runtime since `post_observation` landed at #450:

- **Observations**: terminal-at-creation records the system observed but will not transition. Free string subject, emitted via `post_observation(subject, payload, status=<terminal>)`. Lifecycle is "terminal at creation with explicit caller-chosen terminal status." Canonical examples: `loop_hold.sample::*`, `governance.edge5.orphan_sha::*`, `autonomy.yielded.scope_collision::*`.

The D2 prose does not name the observation case; it landed as an API extension and the prose was never updated. That is itself a D2 prose gap (call it Gap 4 if needed), but a small one because observations are terminal and don't interact with the artifact-finding lifecycle.

The case D2 also doesn't name — and which commit 1c recon surfaced as the *real* third class — is:

- **Runtime-state findings**: findings about runtime DB entities (blackboard rows, worker registry rows, proposal pipeline rows) whose subject has *observable recovery*. The emitter detects the bad state, posts a finding with `status="open"`, and resolves the finding when the bad state clears in a later cycle. No artifact backing on disk; lifecycle is genuinely open → resolved (not terminal-at-creation, not artifact-bound).

### The two finding cases + observations — comparison

> **SUPERSEDED by Revision B.** Revision B's comparison table is keyed on `resolution_mechanism` values (one API column, three field values) rather than on per-API rows.

| Case | API | Subject shape | Lifecycle | Resolver | Caller class | Constitutional pair |
|---|---|---|---|---|---|---|
| Artifact findings | `post_artifact_finding(artifact_type, sub_namespace, identity_key_value, payload)` | `<artifact_type>::<sub_namespace>::<identity_key_value>` | open → resolved | remediation worker (separate from emitter) | sensing, acting, supervision | scoped by `sensor_supported_by_declaration` |
| Runtime-state findings | `post_finding(subject, payload)` [proposed rename: `post_runtime_finding`] | `<observed_subsystem>.<condition>::<identity>` (string, observer-chosen) | open → resolved | emitter (or named service) owns recovery | supervision **only** | scoped by `runtime_finding_caller_class` + `runtime_finding_resolver_owned` (proposed) |
| Observations | `post_observation(subject, payload, status=<terminal>)` | free string | terminal at creation | none — no transition | any | not scoped (terminal at creation) |

Reports (`post_report`) and heartbeats (`post_heartbeat`) are separate Blackboard entry types, not finding-case emissions; they sit alongside this taxonomy.

### D2 amendment text (proposed)

> **SUPERSEDED by Revision B.** Revision B replaces the "two structural cases, each with its own canonical contract" language with "one finding-posting contract carrying a declared `resolution_mechanism` field"; the subject shape concern dissolves once the cut is moved from API surface to data field.

Replace D2's "the canonical subject format is closed" phrasing with:

> CORE's blackboard finding emissions split into two structural cases, each with its own canonical contract:
>
> 1. **Artifact findings** — findings about observable code artifacts CORE governs. Canonical subject shape is `<artifact_type>::<sub_namespace>::<identity_key_value>`. Emitted via `post_artifact_finding(artifact_type, sub_namespace, identity_key_value, payload)`. The framework constructs the subject from typed parameters; the emitter never builds the string. Lifecycle is open → resolved by a remediation worker. Scoped by the constitutional pair `sensor_supported_by_declaration`: emitters must declare `mandate.scope.artifact_type` (sensing class) or route through the no-declaration branch (acting and supervision classes).
>
> 2. **Runtime-state findings** — findings about runtime entities (blackboard rows, worker registry rows, proposal pipeline rows, etc.) with observable open → resolved lifecycle. Canonical subject shape is a free string chosen by the emitter, conventionally `<observed_subsystem>.<condition>::<identity>`. Emitted via `post_runtime_finding(subject, payload)` (the renamed `post_finding(subject, payload)`). Lifecycle is open → resolved by the emitter itself, or by an explicitly named service the emitter delegates to, when the underlying condition recovers in a subsequent cycle. Not scoped by `sensor_supported_by_declaration` (no artifact_type to validate against). **Reserved for `class: supervision` workers only**; `class: sensing` and `class: acting` workers MUST use `post_artifact_finding` (acting workers use its no-declaration branch per the Phase 6 commit 0 Note's Gap 1 amendment).
>
> **Resolver-ownership invariant.** A `post_runtime_finding` subject prefix is valid only if the emitting worker (or a service the emitter explicitly names) owns the recovery transition for that same prefix. The recovery path must be documented in the emitting worker's module docstring and covered by a test proving open → resolved when the underlying runtime condition clears. The category boundary between artifact findings (remediation worker resolves) and runtime-state findings (emitter resolves) is enforced by this invariant, not by subject shape alone; without it, `post_runtime_finding` is a free-string escape hatch for findings that should have been artifact-bound.
>
> Extending either format (a third finding case, a fourth segment, a different separator) is a governance amendment.
>
> Observations (`post_observation(subject, payload, status=<terminal>)`) are a separate entry-type contract for terminal-at-creation records; they sit alongside findings, not within them.

### Implementation

> **SUPERSEDED by Revision B.** Revision B's implementation drops the rename (no more `post_finding` → `post_runtime_finding`); instead `post_finding` gains a non-omittable keyword-only `resolution_mechanism` argument. The 5 site updates are still 5 sites, but pass a field value rather than calling a renamed function. Schema extension + reaudit guard land in commit 1c; ChatGPT's resolver-obligation invariant carries through, re-targeted at `self_resolve` findings.

Phase 6 commit 1c becomes a mechanical scope-narrowing of the existing API, plus the resolver-obligation backing:

- **Rename**: `post_finding(subject, payload)` → `post_runtime_finding(subject, payload)` on `shared.workers.base.Worker`. The implementation does not change; only the name and docstring scope (the new docstring names the scope-narrowing and the resolver-ownership invariant).
- **5 mechanical call-site updates**: in `blackboard_shop_manager.run`, `worker_shop_manager.run`, and the three sites in `proposal_pipeline_shop_manager.run`.
- **No subject-format change. No artifact_type passing. No declaration changes. No SQL row rewrite.** The 132 open `blackboard.entry_stale::*` rows stay open; the existing resolution passes (`worker_shop_manager`'s in-Python `resolve_entries` for recovered workers; `blackboard_service.resolve_stale_alerts_for_terminal_targets` SQL sweep for terminal targets) continue to work unchanged. They are the resolver-ownership invariant's evidence, not legacy cruft to remove.
- **Resolver-obligation backing — 3 worker docstring updates** (one per shop manager module) naming the resolver path for that worker's subject prefix(es). For example, `worker_shop_manager`'s docstring must name "resolution via in-process `resolve_entries` in the next `run()` cycle when the worker's `seconds_silent` drops below threshold."
- **Resolver-obligation backing — 5 unit tests** (one per surviving call site), each seeding a runtime-state condition, asserting `post_runtime_finding` opens a finding, clearing the condition, and asserting the next `run()` cycle (or the SQL auto-resolve sweep) transitions the finding to `resolved`.
- **`post_observation` docstring fix on `shared.workers.base.Worker.post_observation`**: remove `worker.silent` from the canonical `status="abandoned"` examples (it is internally inconsistent with the docstring's "no remediation pathway" framing; `worker.silent` belongs in the runtime-state case under the resolver-ownership invariant). Remaining canonical examples (`sync.db.failed`, `loop_hold.sample::*`, yield receipts) are genuinely terminal-at-creation.
- **Governance rule 1 — `governance.taxonomy.runtime_finding_caller_class`**: flags any non-`class: supervision` worker calling `post_runtime_finding`. Ships as `reporting` initially; promotes to `blocking` once the surviving caller set is verified clean (it already is — recon mapped only supervision-class callers).
- **Governance rule 2 — `governance.taxonomy.runtime_finding_resolver_owned`**: flags any `post_runtime_finding` subject prefix that lacks a documented resolver in its emitter's module docstring AND a passing open → resolved unit test. Ships as `reporting` initially; promotes to `blocking` once the 5 surviving sites are covered.

Phase 6 commit 2 (formerly "delete the legacy API") is reframed:

- The API is not deleted; it is renamed and scope-narrowed.
- The "two-API coexistence window" closes when commit 1c lands. The two APIs going forward are `post_artifact_finding` (artifact case) and `post_runtime_finding` (runtime case). Both are first-class; neither is deprecated.
- The "single canonical emission API" framing in D2's prior text becomes "two canonical emission APIs, scoped by case." The prose adjustment lives in D2 itself, not in a Note.

Phase 7 (`sensor_supported_by_declaration` advisory → blocking promotion) is unaffected. The constitutional pair already scopes to artifact findings; runtime-state findings are explicitly outside it under this amendment.

### Effect on prior Notes

Commit 1's Gap 3 Note named three options (A schema extension, B fourth canonical subject shape, C narrow-and-rename). All three were reasoning inside the false-choice frame that runtime-state findings must "fit into" D2 somehow. With this amendment, the framing is reversed: D2 *names a second case explicitly* rather than carving an exemption to a single case.

Option C (narrow-and-rename) was structurally closest to this amendment but framed as a "legacy escape" rather than as a documented case. The honest framing is "two cases, two APIs" not "one API with a legacy carve-out."

Commit 1's Gap 1 amendment (supervision-class workers also use `post_artifact_finding`'s no-declaration branch) stands unchanged — it correctly described the artifact-finding case's per-class behavior. This amendment adds the second case alongside it; it does not contradict Gap 1.

### Why this didn't surface earlier

Three structural reasons, recorded for future recon discipline:

1. **The phasing absorbed the design.** "Phase 6 commit 2 deletes the legacy API" was treated as immovable from Phase 1 onward. When commit 1c recon found the shop managers' case, it was treated as a problem to fit into the closure rather than as evidence that the closure framing was incomplete.

2. **Reaching for abstractions four times in one session triggered no pause.** Across commit 1c recon: register 3 new artifact_types (A), introduce a fourth subject shape (B), ad-hoc artifact_type strings, re-anchor to backing types (D). Each was a new abstraction. The [[feedback-protocols-reflex-check]] discipline says "pause if reaching for an abstraction twice in a session" — four times was a missed signal that the existing constitutional surface was right and the goal was wrong.

3. **Recursion fatigue.** Three Phase 6 commits in one day shaped the recon toward "find the next migration to ship" rather than toward "question whether the next migration should ship at all." When the recon hits resistance, the honest move is to interrogate the goal, not to keep refining options for hitting it.

### Pattern with prior Notes

Prior Notes on this ADR have been corrigenda — recording prose under-claims the implementation already encoded. This amendment is structurally different: it surfaces a case D2 *never* named, that the runtime already supported via the API surface (`post_observation` for terminal observations, `post_finding(subject, payload)` for runtime findings with lifecycle). D2's prose lagged the API contract; this amendment closes that lag.

If accepted, this is the first ADR-091 amendment that adds a substantive D2 decision rather than clarifying existing D2 prose. It deserves heightened governor review for that reason.

### External review record

**Review 1 — ChatGPT (informed Revision A).** Read the repo via GitHub connector; verified claims against `src/shared/workers/base.py`, `src/will/workers/{worker,blackboard,proposal_pipeline}_shop_manager.py`, and `src/body/services/blackboard_service/blackboard_service.py`. The review accepted the load-bearing claim that the shop managers have a legitimate open → resolved lifecycle but flagged three concrete refinements: tighten scope to `class: supervision` only, add the resolver-ownership invariant as structural backing for the category boundary, and fix the internally-inconsistent `post_observation` docstring. All three are incorporated in Revision A above. The review's "constitutional fork risk" framing — that without the resolver obligation `post_runtime_finding` becomes a free-string escape hatch — is the load-bearing reason for the invariant. The resolver-obligation invariant carries through to Revision B unchanged (re-targeted at `self_resolve` findings); the `post_observation` docstring fix also carries through.

**Review 2 — Claude.ai (informed Revision B).** Read the repo via GitHub connector; could not see `post_observation` / `post_artifact_finding` in the indexed snapshot (those APIs postdate the stale `context_core.txt` export — verified by the reviewer who flagged this honestly), so they tested the live code at the three shop-manager call sites and the resolution mechanism, treating docstring claims as inferred rather than verified. Their findings on the structural axis falsified Revision A's load-bearing framing:

1. **"Observable open → resolved lifecycle" is an over-fit** to the one of three workers that has an in-Python resolution pass. `worker_shop_manager` self-resolves; `blackboard_shop_manager`'s `run()` has no resolution pass (the resolution happens at the service layer via `_sweep_resolved_stale_alerts`); `proposal_pipeline_shop_manager`'s declaration says verbatim *"Detection only — recovery is out of scope (issue #170)"* even though the code does close findings when conditions clear. The three workers don't share an identical lifecycle pattern.

2. **The structural cut that does unite all three is `awaiting_reaudit` ineligibility per ADR-045.** That status is the only automated finding-resolution path in CORE, and ADR-045 defines it as gated on owning audit sensor + rule_namespace. Supervision findings have neither. They are constitutionally barred from `awaiting_reaudit`. The artifact/runtime distinction is not about lifecycle — it's about which closing-authority class may transition the finding. This is grounded, all-three-uniform, and survives the factual variability in resolution implementation.

3. **The BlackboardEntry row is already uniform** — `entry_type='finding', status='open'` is identical schema for every finding. The artifact-vs-runtime distinction lives today in subject-string convention and in which worker closes the finding, not in the data contract. Splitting the post API into two functions (Revision A) would hardcode at the API layer a distinction the data layer expresses as state, and would hand F-42's pluggable-sensor contract a two-headed finding format — exactly the constitutional fork Revision A claimed to be preventing.

4. **The cleaner expression is one finding API + a closed-vocabulary field** (`resolution_mechanism ∈ {reaudit, self_resolve, human}`). F-42's pluggable sensors all post through one API and declare a field value; the daemon routes resolution by reading the column. The second published contract stays single-headed.

Revision B incorporates all four findings, with three caveat corrections after pre-revision verification:

- **The `approval_authority` precedent cite is wrong.** That column does not exist on `core.blackboard_entries` (verified via `\d core.blackboard_entries`); the only existing CHECK is `blackboard_entry_status_closed_set`. Revision B's precedent cite for the closed-set + conditional-NULL CHECK pattern is the existing `blackboard_entry_status_closed_set` constraint on the same table.
- **`post_artifact_finding` integration position must be named.** That API exists in the tree (post-commit 1b) and was exercised by today's commits 0, 1, and 1b. Revision B's position: `post_artifact_finding` becomes a thin wrapper that constructs the canonical subject AND forwards to `post_finding(..., resolution_mechanism='reaudit')`. Preserves the typed-parameter validation (artifact_type-in-declared-list, sub_namespace dotted-suffix); no revert of prior commits needed.
- **`blackboard.entry_stale::*` should classify as `self_resolve`, not `human`.** Claude.ai's draft classification was too conservative — `blackboard_service.resolve_stale_alerts_for_terminal_targets` IS an automated SQL recovery path that closes the finding when the target row reaches terminal status. The resolver is a named service the emitter delegates to (satisfying the resolver-ownership invariant); the `human` value is reserved for findings with no automated closer at all.

The structural reframing from Revision A to Revision B is the load-bearing reason this amendment merits heightened governor review. Both reviews were genuinely adversarial — neither echoed the prior reasoning back. The trail is preserved in this section and in the SUPERSEDED markers above so the governance record of how the decision was reached is auditable.

## Revision B — single finding API + `resolution_mechanism` field (proposed 2026-06-05, pending governor acceptance)

This section is the **current authoritative proposal**. It supersedes the original draft and Revision A; both are preserved above as record of the review trail.

### Why Revision B exists

Revision A's load-bearing axis was "observable open → resolved lifecycle". Claude.ai's verification of the three shop-manager workers falsified this as the unifying property — they share a different structural property: ineligibility for ADR-045's `awaiting_reaudit` automated resolution path. Revision A's design (two finding APIs — `post_artifact_finding` + `post_runtime_finding`) hardcoded at the API layer a distinction the data contract carries as state, and would have made F-42's pluggable sensor contract two-headed permanently. Revision B re-grounds the axis on `awaiting_reaudit` eligibility and moves the cut from API surface to a declared field on the finding row.

### The load-bearing invariant

> **A finding may be transitioned to `awaiting_reaudit` if and only if its `resolution_mechanism = 'reaudit'`.**

Per ADR-045, `awaiting_reaudit` is the parked-revival status for findings that the owning audit sensor must re-evaluate before closing. The status is gated on having an owning audit sensor + rule_namespace. Supervision findings have neither; they are constitutionally barred from `awaiting_reaudit`. Naming this barrier as a stored, indexable column (rather than as a string-prefix convention or a function-name convention) makes the constitutional knowledge structural and enforceable in SQL.

This is what "these findings are not legacy drift" actually means. It is not a claim about lifecycle, about when the code was written, or about which function the emitter called. It is a claim about which findings the ADR-045 sensor-re-audit machinery is permitted to touch.

### D2 — Decision

A new closed-vocabulary field, `resolution_mechanism`, is added to every `entry_type='finding'` row on `core.blackboard_entries`. It declares which authority class may transition the finding to a terminal state:

| Value | Closing authority | ADR-045 reaudit eligible | Verified carriers (current tree) |
| --- | --- | :---: | --- |
| `reaudit` | The owning audit/sensor worker, re-evaluating the subject's truth claim | **yes** | `python::audit.violation::*`, `python::test.run_required::*`, `python::prompt.artifact::*` (any caller of `post_artifact_finding`) |
| `self_resolve` | The posting supervisor or a service it explicitly delegates to, on a later cycle, when live state recovers | no | `worker.silent::*` (in-Python `resolve_entries`); `blackboard.entry_stale::*` (SQL `resolve_stale_alerts_for_terminal_targets` sweep); `proposal.{stuck_approved, stuck_executing, repeated_failure}::*` (in-Python `resolve_entries` at `proposal_pipeline_shop_manager.run`) |
| `human` | A human only, via `core-admin blackboard resolve` | no | None in the surviving tree; reserved for findings with no automated closer at all. The conservative default for unclassified legacy rows during backfill. |

`resolution_mechanism` is **orthogonal to** the `abandoned`/`suppressed` re-emission axis governed by `core/enums.json` and the #263 rationale. That axis governs what a sensor does *after* a terminal state; `resolution_mechanism` governs *who may close an open finding*. They do not interact.

### (a) Schema extension on `core.blackboard_entries`

```sql
ALTER TABLE core.blackboard_entries
    ADD COLUMN resolution_mechanism text;

ALTER TABLE core.blackboard_entries
    ADD CONSTRAINT blackboard_entry_resolution_mechanism_closed_set
    CHECK (
        -- Non-omittable for findings; forbidden for every other entry_type.
        (entry_type = 'finding'
            AND resolution_mechanism IN ('reaudit', 'self_resolve', 'human'))
        OR
        (entry_type <> 'finding'
            AND resolution_mechanism IS NULL)
    );
```

Pattern precedent: matches the existing `blackboard_entry_status_closed_set` CHECK constraint on the same table — closed-set vocabulary enforced at the DB layer rather than at the application layer.

Governance artifacts updated atomically with the schema change:

- `.intent/META/enums.json` — new `finding_resolution_mechanism` enum: `reaudit | self_resolve | human`, with the closing-authority semantics above.
- `.intent/enforcement/contracts/BlackboardEntry.json` (if it exists; verified at implementation) — add `resolution_mechanism` to `properties` (description: closed vocabulary, non-omittable for findings per this ADR) and add an `allOf` clause mirroring the CHECK so the data contract and the DB constraint cannot drift.

### (b) Runtime enforcement of the field

**Write time — non-omittable in the single finding API.** `post_finding` on `shared.workers.base.Worker` gains a keyword-only, non-defaulted parameter:

```python
async def post_finding(
    self,
    subject: str,
    payload: dict[str, Any],
    *,
    resolution_mechanism: str,   # non-omittable: reaudit | self_resolve | human
) -> uuid.UUID:
    """Post a new finding. resolution_mechanism declares which authority class
    may close it, and gates ADR-045 reaudit eligibility. See ADR-091 D2."""
    return await self._post_entry(
        entry_type="finding",
        subject=subject,
        payload=payload,
        status="open",
        resolution_mechanism=resolution_mechanism,
    )
```

`_post_entry` threads the new parameter to the INSERT; `post_report` and `post_heartbeat` pass nothing (NULL), satisfied by the CHECK. Because the parameter is keyword-only and has no default on `post_finding`, every caller is forced to classify at the call site — the same discipline ADR-011 imposes on attribution. No raw-SQL bypass exists to evade it (`architecture.blackboard.worker_only_inserts`, blocking).

**`post_artifact_finding` integration.** That API stays as a typed-parameter wrapper for artifact findings (preserves the `artifact_type`-in-declared-list and `sub_namespace` dotted-suffix validation that landed in Phases 1–6). Its implementation forwards to `post_finding` with `resolution_mechanism="reaudit"` supplied automatically:

```python
async def post_artifact_finding(
    self,
    artifact_type: str,
    sub_namespace: str,
    identity_key_value: str,
    payload: dict[str, Any],
) -> uuid.UUID:
    # ...existing artifact_type and sub_namespace validation (unchanged)...
    subject = f"{artifact_type}::{sub_namespace}::{identity_key_value}"
    return await self.post_finding(
        subject=subject,
        payload=payload,
        resolution_mechanism="reaudit",
    )
```

No reversal of commits 0/1/1b is required. The migrated workers continue to call `post_artifact_finding` with the typed parameters; the artifact-finding contract is preserved as the typed-validation entry point that always implies `reaudit`.

**Resolution time — the reaudit guard.** The transition-to-`awaiting_reaudit` site is at `src/body/services/blackboard_service/blackboard_proposal_service.py` (the UPDATE on `core.blackboard_entries` that flips revived findings to `awaiting_reaudit` per ADR-045 proposal-revival flow). It acquires one predicate clause:

```sql
UPDATE core.blackboard_entries
SET status = 'awaiting_reaudit', updated_at = now()
WHERE entry_type = 'finding'
  AND resolution_mechanism = 'reaudit'   -- ADR-091 D2 invariant
  AND ...
```

A `self_resolve` or `human` finding can never be parked into `awaiting_reaudit` by a sensor, because the predicate excludes it. This makes the invariant structural rather than conventional.

### (c) F-42's pluggable sensor contract uses the single API

F-42 declares an abstract sensor interface whose contract includes "the finding format it produces." Under Revision B that format is **single-headed**: every sensor — the existing `AuditViolationSensor`, a future regulated-document sensor, a future process sensor — posts through one `post_finding(subject, payload, resolution_mechanism=...)` call. The sensor does not choose between APIs; it declares a value.

A pluggable sensor declares its resolution mechanism in its `.intent/workers/*.yaml` under `mandate`, validated against `finding_resolution_mechanism` at daemon load. The natural F-42 mapping falls straight out of the enum:

- An **artifact-type sensor** (observes a re-readable subject — a file, a config, any artifact whose truth claim can be re-evaluated) declares `reaudit`. ADR-045 applies; its findings converge through re-audit exactly as `audit.violation` does today.
- A **runtime/process sensor** (observes a live process, a queue, a liveness signal — no re-readable artifact) declares `self_resolve` (if the sensor owns the recovery transition) or `human` (if recovery is operator-mediated). ADR-045 does not apply; nothing can park its findings into `awaiting_reaudit`.

This is the payoff of the field-based design: F-42's second published contract depends on **one** finding API plus a declared field. A two-function API would have forced every pluggable-sensor author to pick a head, encoding a resolution assumption into the choice of function and making the sensor contract two-headed for all time. The field keeps the extension axis (artifact-type vs runtime sensors) as data, which is exactly where F-42 needs it.

### (d) Resolver-ownership invariant (re-targeted from Revision A / ChatGPT)

ChatGPT's resolver-obligation invariant from Revision A carries through to Revision B, re-targeted at the `self_resolve` field value:

> A finding with `resolution_mechanism = 'self_resolve'` is valid only if the emitting worker (or a service the emitter explicitly names) owns the recovery transition for that subject prefix. The recovery path must be documented in the emitting worker's module docstring and covered by a test proving open → resolved when the underlying runtime condition clears.

A new advisory→blocking governance rule (proposed: `governance.taxonomy.self_resolve_resolver_owned`) flags any `self_resolve` subject prefix lacking a documented resolver + a passing open → resolved test. Ships as `reporting`; promotes to `blocking` once the surviving sites are covered. The invariant prevents `self_resolve` from becoming a "no automated closer" escape hatch — that's what the `human` value is for.

### (e) Commit 1c implementation scope under Revision B

Commit 1c was originally "delete `post_finding(subject, payload)`." Under Revision B it becomes, with no deletion and no rename:

1. **Schema** — the `ALTER TABLE` + CHECK above; `enums.json` `finding_resolution_mechanism`; the BlackboardEntry data contract (`allOf` clause + `properties`) updated to match.
2. **API surface** — `_post_entry` threads `resolution_mechanism`; `post_finding` gains the non-omittable keyword-only field; `post_artifact_finding` becomes the typed-parameter wrapper that supplies `resolution_mechanism="reaudit"` automatically; `post_report` / `post_heartbeat` unchanged.
3. **5 call-site classifications** — every surviving direct `post_finding(subject, payload)` caller passes its `resolution_mechanism` value. Per the verified classification:
   - `worker_shop_manager` (`worker.silent::*`) → `self_resolve`
   - `blackboard_shop_manager` (`blackboard.entry_stale::*`) → `self_resolve`
   - `proposal_pipeline_shop_manager` (3 sites: `proposal.{stuck_approved, stuck_executing, repeated_failure}::*`) → `self_resolve`
4. **Reaudit guard** — add the `AND resolution_mechanism = 'reaudit'` predicate to the `awaiting_reaudit` UPDATE at `blackboard_proposal_service.py`; author the `architecture.blackboard.reaudit_requires_reaudit_mechanism` blocking rule + mapping.
5. **Resolver-ownership backing** — 3 worker docstring updates (one per shop manager module) naming the resolver path for that worker's subject prefix(es). 5 unit tests (one per surviving call site), each seeding a runtime-state condition, asserting the open finding is posted with `resolution_mechanism='self_resolve'`, clearing the condition, and asserting the next `run()` cycle (or the SQL auto-resolve sweep) transitions the finding to `resolved`.
6. **`post_observation` docstring fix** at `shared.workers.base.Worker.post_observation`: remove `worker.silent` from the canonical `status="abandoned"` examples (internally inconsistent with the same docstring's "no remediation pathway" framing; `worker.silent` belongs in the `self_resolve` case under Revision B). Remaining canonical examples (`sync.db.failed`, `loop_hold.sample::*`, yield receipts) are genuinely terminal-at-creation.
7. **Backfill** — existing rows get `resolution_mechanism` by subject-prefix match (`python::*` and any pre-canonical artifact-finding subjects → `reaudit`; `worker.silent::%`, `blackboard.entry_stale::%`, `proposal.{stuck_approved, stuck_executing, repeated_failure}::%` → `self_resolve`; everything else → `human`, the conservative default that grants no reaudit eligibility to unclassified legacy rows). Findings are the only affected rows; `report` / `heartbeat` backfill to NULL.
8. **Two governance rules** — `architecture.blackboard.reaudit_requires_reaudit_mechanism` (blocking; reaudit guard predicate must co-occur at every `awaiting_reaudit` transition) and `governance.taxonomy.self_resolve_resolver_owned` (advisory→blocking; resolver-ownership invariant).

Acceptance gate (binary): post-migration, `SELECT count(*) FROM core.blackboard_entries WHERE entry_type='finding' AND resolution_mechanism IS NULL` returns 0; the CHECK is enforced; one audit cycle parks only `reaudit` findings into `awaiting_reaudit` (the guard holds on-wire, not just in code).

### (f) Phase 6 commit 2 and Phase 7 under Revision B

- **Phase 6 commit 2** dissolves. There is no API to delete (no rename, no two-headed split). The "two-API coexistence window" closes the moment commit 1c lands with the unified `post_finding(subject, payload, resolution_mechanism=...)` signature: the only finding API is `post_finding`, and `post_artifact_finding` is a typed wrapper over it. The phasing collapses one commit.
- **Phase 7** (`sensor_supported_by_declaration` advisory → blocking promotion) is unaffected. The constitutional pair scopes to artifact findings via the existing rule; runtime-state findings carry `resolution_mechanism='self_resolve'` or `'human'` and remain outside the pair as before.

### (g) Alternatives considered (under Revision B's framing)

**Keep two published finding APIs (Revision A's design).** Rejected. The BlackboardEntry row is already uniform; two functions hardcode at the API layer a distinction the data layer carries as state, and bind F-42's pluggable sensor contract to a two-headed finding format permanently. The amendment's own counter-test — a future state where two APIs cost more than they save — is realized precisely here: every pluggable sensor author would inherit the fork.

**Delete the generic API and migrate supervision findings onto `post_artifact_finding`** (the original Phase 6 commit 2 plan). Rejected. `worker.silent::<uuid>` has no artifact and no owning sensor; `post_artifact_finding`'s resolution model (ADR-045 reaudit) has nothing to bind to. There is no migration target.

**Derive `resolution_mechanism` from subject prefix at read time instead of storing it.** Rejected. The reaudit guard is a hot-path predicate and must be a stored, indexable column, not a string-prefix computation; and subject convention is exactly the implicit signal this amendment is converting into a governed field.

**Rename `post_finding` to `post_runtime_finding` and add a separate `resolution_mechanism` argument anyway** (a hybrid of Revision A and B). Rejected as redundant. With one API plus a declared field, the rename adds no constitutional content — the field IS the classification.

### (h) Revisit triggers

- A fourth closing-authority class appears (e.g. a finding closed by a peer worker that is neither the owning sensor nor the posting supervisor nor a human). At that point `finding_resolution_mechanism` gains a value; the API and CHECK absorb it without a structural change — which is the design's intent.
- ADR-045's `awaiting_reaudit` transition is refactored or relocated. The reaudit guard predicate and its rule mapping move with it; the invariant in D2 is the fixed point.
- `resolution_mechanism` proves insufficient to distinguish `reaudit` from `self_resolve` for some sensor whose subject is both a re-readable artifact and live runtime state. Treat as a classification decision per sensor (the sensor declares one or the other in its `.intent/workers/` yaml), not a schema change.
- The resolver-ownership invariant proves too restrictive — e.g., a `self_resolve` finding whose recovery is observable only through a poll loop that takes hours, making the open → resolved test impractical. Treat as a per-test scope decision (assert posting only; record the resolver path in the docstring without an integration test), not an invariant change.

### (i) References (under Revision B)

- **ADR-011** — worker-only INSERTs; the attribution discipline this field reuses (non-omittable at the single write boundary, no raw-SQL bypass).
- **ADR-045** — `awaiting_reaudit` and the owning-sensor re-evaluation contract; the source of the reaudit-eligibility cut and the runtime guard. The load-bearing reference for Revision B's structural axis.
- **CORE-ShopManager.md §3–§5** — supervision findings, escalation, and the human-resolution path that grounds the `human` value.
- **F-42 (CORE-Features.md)** — pluggable sensor model; the second published contract that consumes the single finding API.
- **Worker base class** — `src/shared/workers/base.py`: `post_finding`, `post_artifact_finding`, `_post_entry` (INSERT site amended here).
- **Existing CHECK precedent** — `blackboard_entry_status_closed_set` on `core.blackboard_entries` (closed-set vocabulary enforced at the DB layer; the pattern Revision B mirrors for `resolution_mechanism`).

---

## D2 Amendment — disposition transitions own `resolution_mechanism`; subject-lifecycle invariant (proposed 2026-06-12, pending governor acceptance)

**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-12 — drafted directly to disc under Path A: named topic ADR-091 + execute-verb "draft the ADR-091 amendment"; not committed, surfaced for governor review)
**Tracking:** #628
**Status:** **Accepted (governor decision 2026-06-12).** The field-ownership invariant, D2-A1/A2/A3 decisions, and acceptance gate below are constitutional under ADR-091 from this commit forward. **Extends** Revision B's `resolution_mechanism` field; supersedes nothing. Implementation tracked at #628 (B+C first, then A, then D, E). Both `awaiting_reaudit`-as-status (Revision B prose) and the running system's reaudit queue (`status='indeterminate' AND resolution_mechanism='reaudit'`, per `health_log_service.py` F-19 and the live DB) are in scope; this amendment governs the field, not the status spelling.

### The defect this closes

Revision B established `resolution_mechanism` and one invariant governing a single transition direction — *entry into the reaudit queue*: a finding may be parked for reaudit iff `resolution_mechanism='reaudit'`. It left a second transition direction ungoverned: the `open → indeterminate` transition by **delegation** — `ViolationRemediatorWorker` marking a `DELEGATE`-classified finding "awaiting governor" via `mark_delegated → BlackboardService.mark_indeterminate`.

That UPDATE sets `status='indeterminate'` and `resolved_at` but **never touches `resolution_mechanism`**. The finding, born with `resolution_mechanism='reaudit'` (every `post_artifact_finding` caller carries it automatically per Revision B (b)), keeps that value while being declared "a human must decide." The two fields now contradict each other. Consequences:

1. **It masquerades as the reaudit queue.** The F-19 "open" predicate is `status='open' OR (status='indeterminate' AND resolution_mechanism='reaudit')`. A delegated finding satisfies the second clause and is counted as open convergence work, though no sensor will ever clear it.
2. **The sensor re-INSERTs it every cycle.** The violation is never auto-fixed (it is `DELEGATE` by design), so each audit cycle re-detects the subject and posts a *new* finding row — there is no subject-scoped memory to suppress the re-raise.

**Evidence (live `core` DB, 2026-06-12):** 116 "open" convergence subjects; **0** of `status='open'`; **all 116** `status='indeterminate' AND resolution_mechanism='reaudit'`; every one maps to a rule classified `DELEGATE` in `auto_remediation.yaml` (purity.no_orphan_files ×42, cli.standard_verbs ×35, …). 173 live rows for 116 subjects (re-INSERT churn — one subject carried three identical rows stamped within the same second). Full root cause in #628.

### Root cause — an asymmetric state-machine seam (ADR-072 shape)

`resolution_mechanism` is stamped once **at birth by the posting authority** (`post_artifact_finding → reaudit`), which cannot know the rule's remediation disposition — that lives downstream in `auto_remediation.yaml`. Disposition is decided **later by the remediator**, which rewrites `status` but not `resolution_mechanism`. Revision B's own design premise — *"the field IS the classification; the daemon routes resolution by reading the column"* (Revision B (g)) — is silently violated, because the one code path that re-classifies closing authority does not write the column. This is the ADR-072 failure shape: an **unscoped entry** (birth always stamps `reaudit`) with a **scoped exit** (delegation changes status only) accumulates indefinitely.

### The load-bearing invariant (field-ownership)

> **`resolution_mechanism` is owned by whichever authority last sets a finding's closing disposition — not solely by the posting authority at birth. Any transition that changes which class may close a finding MUST rewrite `resolution_mechanism` to match. In particular, delegating a finding to the governor (the `DELEGATE → indeterminate` transition) MUST set `resolution_mechanism='human'`.**

This introduces **no new value and no new mechanism.** It uses Revision B's existing `human ∈ {reaudit, self_resolve, human}`, whose definition — *"a human only, via `core-admin blackboard resolve`"* (Revision B D2 table) — is exactly a delegated finding's closer. The amendment makes the field track reality across the finding's whole lifecycle, which Revision B's routing model already assumes but never enforced on the delegation path.

### D2-A1 — Decision: delegation rewrites the field (#628 fixes B + C)

`BlackboardService.mark_indeterminate` (and its `mark_delegated` caller) set `resolution_mechanism='human'` in the same UPDATE that sets `status='indeterminate'`. Effects, both structural:

- The finding **drops out of the F-19 "open" predicate** and appears solely in the Governor Inbox (`status='indeterminate'`, any mechanism) — the human-decision queue it actually belongs to.
- It becomes **structurally ineligible for the reaudit queue** — Revision B's existing reaudit guard already excludes any finding whose `resolution_mechanism ≠ 'reaudit'`, so no sensor can re-park it.

### D2-A2 — Symmetric enforcement guard (closes the enforcement asymmetry)

Revision B shipped `architecture.blackboard.reaudit_requires_reaudit_mechanism` guarding *entry* into reaudit. Nothing guarded *exit by delegation* clearing the field. A new rule — shipped as `architecture.blackboard.indeterminate_requires_human_mechanism` (named to mirror its sibling `reaudit_requires_reaudit_mechanism`; the invariant is *any* indeterminate write, not only delegation) — requires: any UPDATE whose SET clause transitions a row to `status='indeterminate'` MUST co-assign `resolution_mechanism='human'` in the same statement, and MUST NOT leave `'reaudit'`. Ships `reporting`, promotes to `blocking` once the existing rows are migrated (D2-A1 + the one-shot backfill below). Fix-the-class-and-add-the-rule, never one without the other.

### D2-A3 — Subject-lifecycle invariant (the re-raise fix; placement is load-bearing — #628 fix A)

Independent of the field seam: the audit sensor re-INSERTs a fresh finding for an already-known subject every cycle because **the data contract has no subject-scoped memory** — every timestamp column on `core.blackboard_entries` is row-scoped (`created_at`/`updated_at`/`claimed_at`/`resolved_at`); there is no `first_raised_at`/`last_raised_at` and no one-live-row-per-subject constraint. The sensor is therefore *structurally forced* to blind re-emission.

> **The blackboard owns one live finding per `subject`. A re-detected subject that already has a live (non-terminal, or delegated-pending-governor) finding is an UPDATE/touch of the existing row, not a new INSERT.**

**This invariant lives at the posting/adjudication boundary — a universal sink for all sensors — NOT as a per-sensor pre-query guard.** The per-sensor form is rejected: it would replicate across every re-raising sensor (violating universal-sink discipline) and would read central-DB historical state to suppress a symptom — the *Centralized-Truth blindness* CORE-PAPER-004 (Octopus) names as the "Ideological Rot." The board-boundary form instead gives every sensor the subject-level memory it structurally lacks: the small, proportionate Octopus-aligned reflex. **Scope guardrail:** this is *board-owns-subject-lifecycle*, nothing grander — it is explicitly **not** "building the Octopus" (Shadow KG, Reflex loops, real-time sensation remain dormant and out of scope). `[[feedback-protocols-reflex-check]]` applies: do not abstract beyond the one invariant.

> **Correction (2026-06-12, post-implementation recon).** The premise above —
> "the subject-level memory it structurally lacks" — is **wrong**. Recon of the
> post path found the memory already exists: `fetch_active_finding_subjects_by_prefix`
> dedups sensor posts and *already includes* `status='indeterminate'`, and the
> reaudit drain scopes to `awaiting_reaudit`, never touching `indeterminate`.
> So **B alone** resolves the count inflation; the residual re-INSERT is a
> bounded *intra-run* duplication (file-level subjects collapsing multiple
> same-rule violations) plus a likely transient June-1 path-migration artifact —
> not a missing-lifecycle invariant. **A is therefore deferred to evidence:**
> after B+D deploy, observe one audit cycle; build the ~3-line `violations`
> dedup (optionally a `UNIQUE (subject) WHERE status NOT IN (terminal)` partial
> index) only if duplicates persist. This corrects an unverified assertion;
> it does not change D2-A1/A2 (B+C), which stand.

### Implementation scope (tracked at #628, fixes A–E)

| # | Maps to | Change |
|---|---------|--------|
| A | D2-A3 | One-live-finding-per-subject at the post/adjudicate boundary (re-detection = update, not insert). Load-bearing; the largest item (needs the subject-scoped lookup the schema lacks today). |
| B | D2-A1 | `mark_indeterminate`/`mark_delegated` co-set `resolution_mechanism='human'`. ≈1 line. |
| C | D2-A2 | The symmetric ast_gate guard rule + mapping. Ships in the same change-set as B. |
| D | — | One-shot backfill: existing `indeterminate AND reaudit` delegated rows → `human`; purge the ~17 absolute-path ghost subjects orphaned by the June-1 abs→relative path migration. Only meaningful after A+B (else the fountain refills). |
| E | — | Normalize sensor `identity_key_value` to repo-relative so a future path-format change cannot re-orphan subjects. |

### Acceptance gate (binary)

After migration:
1. `SELECT count(*) FROM core.blackboard_entries WHERE entry_type='finding' AND status='indeterminate' AND resolution_mechanism='reaudit'` returns **0** — no delegated finding masquerades as the reaudit queue.
2. One audit cycle over a still-violating `DELEGATE`-classified subject produces **no new row** for a subject that already has a live finding — re-INSERT churn eliminated (the same-second triple-insert cannot recur).
3. The F-19 "open" count reflects only genuinely-open and genuinely-reaudit-queued findings; delegated decisions appear **once**, in the governor inbox.

### Alternatives considered

- **Leave the field at birth; fix only the F-19 predicate to exclude `DELEGATE` rules.** Rejected — the predicate would re-derive disposition from the rule map *at query time*, re-introducing the read-time derivation Revision B (g) already rejected for the reaudit guard ("must be a stored, indexable column, not a string-prefix computation"); and it would not stop the re-INSERT churn (D2-A3), which is the larger defect.
- **Per-sensor "already raised?" guard.** Rejected — see D2-A3 (replication + Centralized-Truth blindness; it embodies the very rot it would patch).
- **A new status value (e.g. `delegated`) instead of reusing `indeterminate` + `human`.** Rejected — `status` is already uniform across findings (Revision B (3)); the discriminator is `resolution_mechanism` by design. A new status re-introduces the two-headedness Revision B eliminated.

### Revisit triggers

- A disposition class appears whose closer is neither the owning sensor, the posting supervisor, nor a human (cf. Revision B (h)'s fourth-class trigger). The field-ownership invariant absorbs it automatically: whoever sets the disposition sets the field.
- A subject legitimately needs multiple concurrent live findings (e.g. distinct payload variants under one subject). Revisit the one-live-finding-per-subject invariant as a per-artifact-type policy, not a global schema change.

### External review record

None yet. Per this ADR's own discipline (Revision B's "first substantive D2 amendment deserves heightened governor review" note), an adversarial external review via the GitHub connector is recommended before promotion to accepted. Two claims to verify against live code: (1) `mark_delegated → mark_indeterminate` leaves `resolution_mechanism` untouched today; (2) no consumer depends on delegated findings carrying `'reaudit'`.

### References

- **#628** — root cause writeup + A–E fix breakdown + post-boundary placement decision (this amendment's tracking issue).
- **ADR-072** — asymmetric state-machine wiring (unscoped entry + scoped exit accumulates); the precedent failure shape named above.
- **ADR-045** — `awaiting_reaudit` / reaudit eligibility; Revision B's structural axis, unchanged here.
- **Revision B D2 (this ADR)** — the `resolution_mechanism` field this amendment extends; its reaudit guard is the exact inverse of D2-A2.
- **CORE-PAPER-004 (Octopus-UNIX Synthesis)** — Centralized-Truth blindness; the framing for D2-A3's board-boundary placement.
- Code touchpoints — `src/shared/workers/base.py:post_artifact_finding` (the birth stamp); `src/body/services/blackboard_service/blackboard_service.py:mark_indeterminate` (the un-rewritten transition); `src/will/workers/violation_remediator_blackboard.py:mark_delegated`.
