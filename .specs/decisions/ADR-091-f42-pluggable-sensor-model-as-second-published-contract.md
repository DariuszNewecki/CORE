<!-- path: .specs/decisions/ADR-091-f42-pluggable-sensor-model-as-second-published-contract.md -->

# ADR-091 — F-42 pluggable sensor model as the second published contract

**Date:** 2026-06-05
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-05 — drafted under Path A execute-verb authorization, "proceed as suggested" + named topic ADR-091 + execute-verb "draft directly to disc"; revised under governor direction to unify three open questions into canonical contracts rather than per-sensor grandfather clauses)
**Grounding papers:** `papers/CORE-Features.md` §3.11 (extension interfaces F-41–F-43 as plugin APIs against the open-base contract) and §F-42 (the abstract sensor interface); `CORE-CHARTER.md` (the open-completeness commitment under which the audit loop must be artifact-agnostic, not Python-shaped).
**Related:** ADR-090 (the artifact-type registry this ADR consumes — `supported_sensors` is the field this ADR populates); ADR-084 §D1 (plugin shape requires F-41/F-42/F-43 as published contracts — this ADR ships the second); ADR-085 §"Why this matters" (the open-completeness gate item this ADR closes after F-41); ADR-079 §D9 (the taxonomy_gate YAML↔AST coherence pattern this ADR mirrors for sensor↔artifact_type coherence); ADR-081 §D2 (process-isolation classification — sensors declaring heavy artifact-type discovery may need `requires_dedicated_process: true`); ADR-072 §D5 (awaiting-reaudit drain pattern preserved across migration); ADR-039 (governance-refresh contract sensors honor); ADR-015 §D5 (cause attribution payload fields preserved across the subject migration); F-43 #417 (pluggable action model — gains the same `artifact_type` field and canonical subject format via its own ADR); F-41 #415 (substantially shipped at gates 1–3, 5, 7, 8, 9; gates 4 and 6 close when this ADR's D5 phases complete); #566 (engine check for `architecture.artifact_discovery_through_registry` — advisory today, promotion path declared in D8).
**Supersedes (partial):** the implicit per-sensor artifact_type convention currently expressed only in code comments (e.g. `AuditViolationSensor`'s `get_artifact_type("python")` hardcode introduced in F-41 Phase 2); the three heterogeneous subject-string conventions currently in use (`audit.violation::*`, `test.run_required::*`, `test.missing::*` / `test.failure::*`) which converge under D2's canonical format.

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

Proposed amendment to D2 surfaced during commit 1c recon. Reverses commit 1's Gap 3 framing. Pending governor review and acceptance.

If accepted, this amendment supersedes the deferral in commit 1's Gap 3 Note and replaces commit 1c's scope. If rejected, commit 1c falls back to one of the original Gap 3 options (A schema extension, B fourth canonical subject shape, C narrow-and-rename, D re-anchor, F post_observation/abandoned) and this amendment is recorded as a considered-and-rejected alternative.

### Why this amendment

Commit 1's Gap 3 Note framed runtime-state findings (the shop managers' emissions) as a "gap in D2" — a problem to close by extending the artifact_type vocabulary, introducing a fourth canonical subject shape, or carving out a narrow legacy-API exemption. Commit 1c recon surfaced that the framing itself was the error. The three options were all reasoning inside the assumption that *every* finding-shaped blackboard emission must fit D2's `<artifact_type>::<sub_namespace>::<identity_key_value>` shape, and the recon kept hitting resistance because that assumption is false.

The shop managers' lifecycle — `post_finding(open)` once per stale entity, `resolve_entries` when the entity recovers — is **not deprecated drift**. It is the correct lifecycle for findings whose subject *has observable recovery*: `worker.silent::<uuid>` IS open while the worker is silent and IS resolved when the worker resumes heartbeating. The `worker_shop_manager` resolution pass and the `blackboard_service.resolve_stale_alerts_for_terminal_targets` SQL sweep aren't legacy cruft — they're the constitutional mechanism that makes the open→resolved transition meaningful.

The honest read of CORE's three emission APIs is that they correspond to **three distinct legitimate cases**, only two of which D2 currently names.

### What D2 currently names

D2 (the canonical subject format decision) names two cases explicitly:

- **Findings** about observable code artifacts: shape `<artifact_type>::<sub_namespace>::<identity_key_value>`, emitted via `post_artifact_finding`, lifecycle open → resolved by a remediation worker.
- **Reports** about completed worker cycles: shape `<worker_declaration_name>.<event_kind>`, emitted via `post_report`, terminal at creation with `status="resolved"`.

A third case has been load-bearing in the runtime since `post_observation` landed at #450:

- **Observations**: terminal-at-creation records the system observed but will not transition. Free string subject, emitted via `post_observation(subject, payload, status=<terminal>)`. Lifecycle is "terminal at creation with explicit caller-chosen terminal status." Canonical examples: `loop_hold.sample::*`, `governance.edge5.orphan_sha::*`, `autonomy.yielded.scope_collision::*`.

The D2 prose does not name the observation case; it landed as an API extension and the prose was never updated. That is itself a D2 prose gap (call it Gap 4 if needed), but a small one because observations are terminal and don't interact with the artifact-finding lifecycle.

The case D2 also doesn't name — and which commit 1c recon surfaced as the *real* third class — is:

- **Runtime-state findings**: findings about runtime DB entities (blackboard rows, worker registry rows, proposal pipeline rows) whose subject has *observable recovery*. The emitter detects the bad state, posts a finding with `status="open"`, and resolves the finding when the bad state clears in a later cycle. No artifact backing on disk; lifecycle is genuinely open → resolved (not terminal-at-creation, not artifact-bound).

### The three emission cases — comparison

| Case | API | Subject shape | Lifecycle | Constitutional pair |
|---|---|---|---|---|
| Artifact findings | `post_artifact_finding(artifact_type, sub_namespace, identity_key_value, payload)` | `<artifact_type>::<sub_namespace>::<identity_key_value>` | open → resolved (by remediation worker) | scoped by `sensor_supported_by_declaration` |
| Runtime-state findings | `post_finding(subject, payload)` [proposed rename: `post_runtime_finding`] | `<observed_subsystem>.<condition>::<identity>` (string, observer-chosen) | open → resolved (by emitter on recovery) | not scoped (no artifact_type to validate against) |
| Observations | `post_observation(subject, payload, status=<terminal>)` | free string | terminal at creation | not scoped (terminal at creation) |

Reports (`post_report`) and heartbeats (`post_heartbeat`) are separate entry types, not finding-class emissions; they sit alongside this taxonomy, not within it.

### D2 amendment text (proposed)

Replace D2's "the canonical subject format is closed" phrasing with:

> CORE's blackboard finding emissions split into two structural cases, each with its own canonical contract:
>
> 1. **Artifact findings** — findings about observable code artifacts CORE governs. Canonical subject shape is `<artifact_type>::<sub_namespace>::<identity_key_value>`. Emitted via `post_artifact_finding(artifact_type, sub_namespace, identity_key_value, payload)`. The framework constructs the subject from typed parameters; the emitter never builds the string. Lifecycle is open → resolved by a remediation worker. Scoped by the constitutional pair `sensor_supported_by_declaration`: emitters must declare `mandate.scope.artifact_type` (sensing class) or route through the no-declaration branch (acting and supervision classes).
>
> 2. **Runtime-state findings** — findings about runtime entities (blackboard rows, worker registry rows, proposal pipeline rows, etc.) with observable open → resolved lifecycle. Canonical subject shape is a free string chosen by the emitter, conventionally `<observed_subsystem>.<condition>::<identity>`. Emitted via `post_runtime_finding(subject, payload)` (the renamed `post_finding(subject, payload)`). Lifecycle is open → resolved by the emitter itself when the underlying condition recovers in a subsequent cycle. Not scoped by the constitutional pair (no artifact_type to validate against). Reserved for class:supervision and class:acting workers; class:sensing workers MUST use `post_artifact_finding`.
>
> Extending either format (a third shape under either case, a fourth segment, a different separator) is a governance amendment.
>
> Observations (`post_observation(subject, payload, status=<terminal>)`) are a separate entry-type contract for terminal-at-creation records; they sit alongside findings, not within them.

### Implementation

Phase 6 commit 1c becomes a mechanical scope-narrowing of the existing API:

- Rename `post_finding(subject, payload)` to `post_runtime_finding(subject, payload)` on `shared.workers.base.Worker`. The implementation does not change; only the name and docstring scope.
- Update the 5 shop manager call sites mechanically (`blackboard_shop_manager`, `worker_shop_manager`, `proposal_pipeline_shop_manager`).
- No subject-format change. No artifact_type passing. No declaration changes. No SQL row rewrite. The 132 open `blackboard.entry_stale::*` rows stay open; the existing resolution passes (`worker_shop_manager` in-Python `resolve_entries`; `blackboard_service.resolve_stale_alerts_for_terminal_targets` SQL sweep) continue to work unchanged.
- Add a new governance rule (proposed name: `governance.taxonomy.runtime_finding_caller_class`) that flags any `class: sensing` worker calling `post_runtime_finding`. Ships as `reporting` initially; promotes to `blocking` once the surviving caller set is verified clean (it already is — recon mapped zero sensing-class callers of the legacy API).

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
