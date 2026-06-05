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

1. **Phase 1 atomic migration covers only the 12 true sensors.** The D1 conditional constraint `if class == sensing then artifact_type required` is staged behind a separate reclassification pass — the nine misclassified declarations would otherwise fail schema validation. In Phase 1, the schema fields are **optional** for `class: sensing`; the conditional enforcement promotes when the reclassification lands.

2. **A sub-issue is filed (#570)** tracking the reclassification: "sensing-class taxonomy audit — reclassify embedders / crawlers / transformers before F-42 invariant goes blocking." The ADR-091 D8 promotion (advisory → blocking) waits behind #570's closure.

The D1 stability commitment is unaffected: the schema field *shape* is final; only the conditional *enforcement* is staged.

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

- **Phase 3 — `AuditViolationSensor` end-to-end migration.** The sensor reads its declared `artifact_type` from the declaration (replacing the hardcoded `"python"`). All `post_finding` calls switch to the typed API; the framework constructs subjects in canonical form (`python::<rule_namespace>::<file_path>`). Concurrent consumer migration: `ViolationRemediatorWorker` (and any other consumer filtering on `audit.violation::*` subject prefixes — to be enumerated during the phase) updates its dedup queries to consume the canonical format. One-shot blackboard subject migration runs in the same commit: existing `audit.violation::*` rows are rewritten to `python::*` under the deterministic transform `audit.violation::<ns>::<path> → python::<ns>::<path>`. Verification: finding set before vs after is identical under the transform; consumer dedup behaviour unchanged. Closes F-41 verification gate 4 (fully).

- **Phase 4 — CCC sub-discovery routes through registry.** `CoherenceChecker` runs inline during the audit cycle, not as a Worker (per D3 amendment). Eight discovery surfaces migrate — `_adr_paths`, `_northstar_paths`, `_phase_paths` in `checker.py`, and `mind.coherence.checks.{row2_grounding, row3_citation, row4_naming, vocabulary}` — consulting `IntentRepository.get_artifact_type("spec_markdown")` for ADR/paper/northstar discovery, `get_artifact_type("intent_yaml")` for `.intent/` YAML discovery (`_phase_paths` and the row4 intent walk), and `get_artifact_type("intent_json")` for `.intent/` JSON discovery (row4 intent walk). The `vocabulary` check was missed from the original draft; recon added it as it carries the same spec_markdown discovery shape. CCC findings retain their existing subject format; D2's canonical subject format applies to Worker-emitted findings only, so a separate CCC subject migration is out of scope here and tracked separately if pursued. Verification: CCC outcome (finding identifier set) before vs after migration is identical. Closes F-41 verification gate 6 (fully).

- **Phase 5 — `TestCoverageSensor`, `TestRunnerSensor`, and `CoherenceSensorWorker` end-to-end migration.** Discovery + observation walks consult the registry for `[python, test]` (test sensors) and `[python]` (coherence sensor). Sensors switch to typed API. Concurrent consumer migration: `TestRemediatorWorker` dedup queries updated; `coherence_sensor` is detection-only per ADR-027 so no remediator dedup updates are needed. One-shot blackboard subject migration: `test.run_required::*` → `python::test.coverage::*`; `test.missing::*` → `python::test.runner.missing::*`; `test.failure::*` → `python::test.runner.failure::*`; `coherence.incoherence::*` → `python::coherence.incoherence::*`. Verification: coverage-gap, test-execution, and incoherence finding sets before vs after migration are identical under the transform.

- **Phase 6 — Remove old `post_finding(subject, payload)` API.** With all four sensor families on the typed API, the string-subject overload is deleted from `shared.workers.base.Worker`. Any remaining caller is a regression (covered by Phase 7's blocking rule). The single-API state is the F-42 published contract.

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

---

## Verification

This ADR closes — and F-42 ships — when all of the following hold:

1. **Schema extension present and validating.** `META/worker.schema.json` declares `mandate.scope.artifact_type` as an array (`minItems: 1`) and treats it required for `class: sensing` declarations. `rule_namespace` is required for every sensing-class declaration. An intentionally-malformed sensor declaration (missing `artifact_type`, unregistered artifact_type id, missing `rule_namespace`) fails `IntentRepository.initialize()` with a clear error citing the field.
2. **Framework-derived subject format enforced.** `shared.workers.base.Worker.post_finding(artifact_type, sub_namespace, identity_key_value, payload)` is the only API. The string-subject overload is removed. The framework constructs subjects per D2; a sensor that calls `post_finding` with an artifact_type outside its declared list, or a sub_namespace that does not equal or extend its declared `rule_namespace`, raises with a clear error.
3. **Four sensor declarations updated.** `audit_sensor_purity.yaml`, `audit_sensor_architecture.yaml`, `audit_sensor_logic.yaml`, `audit_sensor_modularity.yaml`, `audit_violation_sensor.yaml` (paused base), `test_coverage_sensor.yaml`, `test_runner_sensor.yaml`, `coherence_sensor.yaml` all carry the new fields per D3.
4. **`supported_sensors` populated across the registry.** Every artifact_type declared by any sensor (`python`, `test`, `spec_markdown`, `intent_yaml`) lists every backing sensor. The invariant D4 holds at `blocking` enforcement after Phase 7.
5. **`AuditViolationSensor` migrated end-to-end.** Reads `artifact_type` from declaration. Posts under canonical format. Existing `audit.violation::*` Blackboard rows rewritten to `python::*` under the deterministic transform. Consumer dedup queries updated. Finding output identical under transform. F-41 verification gate 4 fully met.
6. **CCC sub-discovery migrated.** `CoherenceChecker._adr_paths`, `_northstar_paths`, `_phase_paths`, and the row-check discovery surfaces in `mind.coherence.checks.{row2_grounding, row3_citation, row4_naming, vocabulary}` consult the spec_markdown / intent_yaml / intent_json registry discovery globs as applicable. CCC runs inline during audit (not as a Worker per D3) — its subject format is unchanged by this ADR. CCC outcome (finding identifier set) under registry-routed discovery identical to pre-migration outcome. F-41 verification gate 6 fully met.
7. **`TestCoverageSensor`, `TestRunnerSensor`, and `CoherenceSensorWorker` migrated.** Discovery and observation walks consult the registry. Subjects rewritten under transform. Consumer dedup queries updated (test sensors) or verified detection-only (coherence_sensor per ADR-027). Coverage-gap, test-execution, and incoherence finding sets identical under transform.
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
