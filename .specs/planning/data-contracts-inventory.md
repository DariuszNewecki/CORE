# Data Contracts Inventory

**Path:** `.specs/planning/data-contracts-inventory.md`
**Date:** 2026-05-17 (status overlay refreshed 2026-05-24)
**Status:** Planning artifact — not constitutional
**Authority:** ADR-056

---

## Purpose

This document is the implementation plan for ADR-056. It inventories
all structured objects in `src/` that cross a governed boundary (per
ADR-056 D7) and therefore require a `.intent/enforcement/contracts/` schema.

It is the sequencing reference for schema authoring, enum additions,
rule authoring, and mapping authoring across three waves.

---

## Status as of 2026-05-24

Wave 1 has landed substantially. The `.intent/enforcement/contracts/`
directory currently holds **40 contract files**. The authoritative status
record is the ADR-056 row in `CORE-A3-plan.md §Architectural Decisions
Made`; per that record, D1, D2, D3, D5, D6, D7 are complete (2026-05-18),
and Wave 1 Session 3 (2026-05-19) added ProposalConsequence,
ConstitutionalViolationPayload, and WorkerDeclaration as dataclass +
contract + governance rule + enforcement mapping triples. D4 (Proposal
state-conditional contract with `allOf`/`if`/`then` per `ProposalStatus`)
is the residual Wave 1 follow-up tracked as #367.

**Status convention in the tables below:** ✅ in the **Notes** column
means a contract file exists at `.intent/enforcement/contracts/<name>.json`.
It does not necessarily mean the contract is enforced under a governance
rule yet — Finding/CheckResult, ConstitutionalViolationPayload, and
WorkerDeclaration are the three currently carrying governance rules +
enforcement mappings; the rest are schemas-only.

Naming reconciled per ADR-056 D3: contract files are `<name>.json`
(not `<name>.schema.json`); the engine dispatch resolves
`.intent/enforcement/contracts/<schema_ref>.json`.

---

## Wave plan

| Wave | Scope | Criterion |
|---|---|---|
| Wave 1 | Consequence chain + universal result family + AI invocation + vocabulary enums | Drift here silently breaks the autonomous loop |
| Wave 2 | Governance decisions + execution routing + flow/worker declarations + self-healing | Drift here degrades evidence quality or routing correctness |
| Wave 3 | API DTOs + run-table JSONB + agent/learning ORM + workflow models | Drift here costs observability and API stability |

Rules for all waves introduced at `severity: INFO`. Tightened per
findings from the audit loop.

---

## Wave 1 — Consequence chain and universal results

### Schemas

| Contract | Source | Boundary | Notes |
|---|---|---|---|
| `Finding.json` | conceptual (blackboard entity) | consequence chain | ✅ Canonical nucleus: rule_id, severity, subject, evidence, worker_uuid. Rule `data.contracts.finding_nucleus_conforms` ships at `enforcement: reporting`; currently governs `CheckResult` only — `governed_classes` extension to AuditFinding and BlackboardEntry payload families is pending Wave 1 follow-up. |
| `CheckResult.json` | `src/body/services/cim/models.py:279` | phase boundary | ✅ Renamed from `Finding` (ADR-056 D2, commit `b182ec38`); engine output only. |
| `AuditFinding.json` | `src/shared/models/audit_models.py:34` | persistence boundary | ✅ Schema landed. Extends Finding nucleus; `governed_classes` declaration to come in Wave 1 follow-up. |
| `BlackboardEntry.json` | `src/shared/infrastructure/database/models/workers.py:57` | worker + persistence boundary | ✅ Whole row contract. Per-subject payload sub-schemas (rows below) remain to be authored. |
| `BlackboardEntry.payload.worker_heartbeat.schema.json` | `src/shared/workers/base.py:189` | worker boundary | ❌ Payload shape for subject=worker.heartbeat. Not yet authored. |
| `BlackboardEntry.payload.worker_error.schema.json` | `src/shared/workers/base.py:153` | worker boundary | ❌ Payload shape for subject=worker.error. Not yet authored. |
| `BlackboardEntry.payload.run_complete.schema.json` | multiple workers | worker boundary | ❌ Core nucleus for *.run.complete subjects. Not yet authored. |
| `BlackboardEntry.payload.sync_db_complete.schema.json` | `src/body/workers/` | worker boundary | ❌ Not yet authored. |
| `BlackboardEntry.payload.repo_crawl_complete.schema.json` | `src/body/workers/` | worker boundary | ❌ Not yet authored. |
| `Proposal.json` | `src/will/autonomy/proposal.py:201` | consequence chain | ✅ Schema landed. State-conditional invariants per ADR-056 D4 / ProposalStatus are the residual Wave 1 follow-up (#367). |
| `ProposalScope.json` | `src/will/autonomy/proposal.py:47` | consequence chain | ✅ Schema landed. Sub-object; files non-emptiness invariant (ADR-026). |
| `ProposalAction.json` | `src/will/autonomy/proposal.py:105` | consequence chain | ✅ Schema landed. action_id XOR flow_id invariant. |
| `RiskAssessment.json` | `src/will/autonomy/proposal.py:78` | consequence chain | ✅ Schema landed. `overall_risk` `$ref`s `proposal_risk` per ADR-059 D1 (commit `13055f38`). |
| `ProposalConsequence.json` | `infra/sql/db_schema_live.sql:1930` | consequence chain + persistence | ✅ Schema + dataclass landed in Wave 1 Session 3 (commit `77330a3d`); ADR-015 load-bearing query path. |
| `ActionResult.json` | `src/shared/action_types.py:48` | atomic-action boundary | ✅ Schema landed. "Universal result contract for all atomic actions" — was a Critical-Risks Wave 1 blocker; gap closed at schema level. |
| `ComponentResult.schema.json` | `src/shared/component_primitive.py:68` | phase boundary | ❌ "Universal result structure for all components." Not yet authored. |
| `FlowResult.schema.json` | `src/body/flows/result.py:49` | flow boundary | ❌ CORE-Flow §6: "FlowExecutor always returns a FlowResult. No exceptions." Not yet authored. |
| `StepResult.schema.json` | `src/body/flows/result.py:19` | flow boundary | ❌ Wraps ActionResult or FlowResult per step. Not yet authored. |
| `RefusalResult.json` | `src/shared/models/refusal_result.py:27` | phase + persistence boundary | ✅ Schema landed. `refusal_type` enum confirmed in `enums.json` (8 values per ADR-056 #366). |
| `ViolationReport.json` | `src/mind/governance/violation_report.py:16` | phase boundary | ✅ Schema landed. Structured violation passed via exception. |
| `ConstitutionalViolationPayload.json` | `src/mind/governance/violation_report.py:72` | persistence boundary | ✅ Schema + dataclass + governance rule + enforcement mapping landed in Wave 1 Session 3 (commits `fef9aad0` + `c5789320`). |
| `ConstitutionalValidationResult.json` | `src/shared/models/constitutional_validation.py:36` | phase boundary | ✅ Schema landed. Formalizes the ViolationLike duck-typed Protocol. |
| `PromptModelManifest.json` | `src/shared/models/prompt_model.py:48` | AI invocation boundary | ✅ Schema landed. "Sole governed surface for AI invocations." |
| `ContextPacket.json` | `src/shared/infrastructure/context/models.py:44` | AI invocation boundary | ✅ Schema landed. AI evidence envelope; 8 dict[str, Any] fields. |
| `ContextBuildRequest.json` | `src/shared/infrastructure/context/models.py:15` | AI invocation boundary | ✅ Schema landed. Single entrypoint for all context assembly. |
| `EmbeddingPayload.json` | `src/shared/models/embedding_payload.py:13` | vector store boundary | ✅ Schema landed. Docstring claim of "strict schema" formalized. |

### Enums (additions to `.intent/META/enums.json`)

| Key | Values | Notes |
|---|---|---|
| `blackboard_entry_type` | finding, claim, proposal, report, heartbeat | D5 — ship first, no new engine needed. |
| `blackboard_entry_status` | open, claimed, awaiting_reaudit, resolved, abandoned, deferred_to_proposal, dry_run_complete, indeterminate, suppressed | ✅ Already governed in `.intent/META/enums.json` — 9 canonical values per ADR-045 and issue #263. (Inventory's original 4-value undercount was an authoring error.) |
| `blackboard_subject` | worker.heartbeat, worker.error, *.run.complete, sync.db.complete, repo.crawl.complete, violation_remediator.completed | ✅ `blackboard_subject` key present in `enums.json`. |
| `proposal_status` | draft, pending, approved, executing, completed, failed, rejected | Implicit in D4; needs explicit enum entry. |
| `action_impact` | READ_ONLY, WRITE_METADATA, WRITE_CODE, WRITE_DATA | Used by every atomic action. |
| `action_category` | FIX, SYNC, CHECK, BUILD, STATE | ActionDefinition classification. |
| `component_phase` | INTERPRET, PARSE, LOAD, AUDIT, RUNTIME, EXECUTION | Phase ordering invariants. |
| `refusal_type` | boundary, confidence, contradiction, assumption, capability, extraction, quality, unspecified | ✅ Present in `enums.json` (description references ADR-056 #366; mirrors `src/shared/models/refusal_result.py:79` valid_types set). |
| `step_kind` | action, flow | Flow step discriminator. |
| `risk_tier` | ROUTINE, STANDARD, ELEVATED, CRITICAL | ✅ Present in `enums.json` as lowercased name strings (governor decision 2026-05-18: intentionally separate from `proposal_risk`; pre-decision input vs self-assessment). |
| `approval_type` | autonomous, validation_only, human_confirmation, human_review | GovernanceDecision output. |
| `audit_severity` | info, low, medium, high, block | ✅ Reconciled per ADR-059 D2 (commit `9551e972`) — 5-value finding severity scale; WARNING→HIGH and ERROR→BLOCK mapped across 24 src/ files + 2 test files. |
| `task_type` | QUERY, REFACTOR, FIX, ANALYSIS, BUILD, TEST, DOCUMENT, SYNC, AUDIT, PLAN, ORCHESTRATE, UNKNOWN | Governed by ADR-003 YAML; formalize in enum. |

---

## Wave 2 — Governance decisions and execution routing

### Schemas

| Contract | Source | Boundary | Notes |
|---|---|---|---|
| `GovernanceDecision.json` | `src/body/services/constitutional_validator.py:55` | phase boundary | ✅ Schema landed. State-conditional risk_tier ↔ approval_type combinations — conditional invariant authoring may be pending. |
| `ActionDefinition.json` | `src/body/atomic/registry.py:53` | atomic-action boundary | ✅ Schema landed. Declares impact_level, policies, remediates. |
| `ExecutionTask.json` | `src/shared/models/execution_models.py:35` | phase boundary | ✅ Schema landed. task_type governed by ADR-003. |
| `TaskStructure.json` | `src/will/interpreters/request_interpreter.py:62` | phase boundary | ✅ Schema landed. INTERPRET-phase output; universal workflow handoff. |
| `FlowDefinition.json` | `src/body/flows/registry.py:77` | flow boundary | ✅ Schema landed. Existence in `.intent/flows/` is constitutional standing. |
| `FlowStep.json` | `src/body/flows/registry.py:37` | flow boundary | ✅ Schema landed. Governs `consumes` whitelist (ADR-033). |
| `WorkerDeclaration.json` | `src/shared/workers/base.py:226` | worker boundary | ✅ Schema + dataclass + governance rule + enforcement mapping landed in Wave 1 Session 3 (commit `607a2c24`). |
| `ActionRiskConfig.schema.json` | `.intent/enforcement/config/action_risk.yaml` | atomic-action boundary | ❌ Missing entry raises ConstitutionalError; shape ungoverned. Not yet authored. |
| `RemediationResult.json` | `src/body/self_healing/remediation_models.py:131` | phase boundary | ✅ Schema landed. Full audit→fix→validate report. |
| `FixResult.json` | `src/body/self_healing/remediation_models.py:79` | phase boundary | ✅ Schema landed. Per-fix outcome. |
| `AutoFixablePattern.json` | `src/shared/models/remediation.py:23` | phase boundary | ✅ Schema landed. Maps check_id→action_handler at runtime. |
| `PatternViolation.json` | `src/shared/models/pattern_graph.py:14` | phase boundary | ✅ Schema landed. Pattern checker output. |
| `ValidationResult.json` | `src/shared/models/validation_result.py:13` | phase boundary | ✅ Schema landed. Canonical validation result; divergence risk with ConstitutionalValidationResult tracked. |
| `DecisionTrace.entries.schema.json` | `src/shared/infrastructure/database/models/decision_traces.py:29` | persistence boundary | ❌ `decisions` JSONB array. Not yet authored. |
| `Task.plan.schema.json` | `src/shared/infrastructure/database/models/operations.py:94` | persistence boundary | ❌ `plan` JSONB; structure implicit. Not yet authored. |
| `Action.payload.schema.json` | `src/shared/infrastructure/database/models/operations.py:132` | persistence boundary | ❌ `payload` + `result` JSONB open-ended. Not yet authored. |

---

## Wave 3 — API, workflow, and observability

### Schemas

| Contract | Source | Boundary | Notes |
|---|---|---|---|
| `api/AuditRequest.schema.json` | `src/api/v1/` | API boundary | ❌ One schema per route family; not yet authored. |
| `api/FixRequest.schema.json` | `src/api/v1/` | API boundary | ❌ Not yet authored. |
| `api/ProposalRequest.schema.json` | `src/api/v1/` | API boundary | ❌ Not yet authored. |
| *(remaining 21 API request/response shapes)* | `src/api/v1/` | API boundary | ❌ Not yet authored. |
| `WorkflowResult.json` | `src/shared/models/workflow_models.py:48` | flow boundary | ✅ Schema landed. |
| `PhaseWorkflowResult.json` | `src/shared/models/workflow_models.py:110` | flow boundary | ✅ Schema landed. |
| `DetailedPlan.json` | `src/shared/models/workflow_models.py:207` | phase boundary | ✅ Schema landed. A3 blueprint handoff. |
| `DetailedPlanStep.json` | `src/shared/models/workflow_models.py:145` | phase boundary | ✅ Schema landed. |
| `AuditRunResult.schema.json` | `src/shared/infrastructure/database/models/governance.py` | persistence boundary | ❌ One per *Run.result JSONB column (×7). Not yet authored. |
| `AgentDecision.json` | `src/shared/infrastructure/database/models/learning.py:30` | persistence boundary | ✅ Schema landed. `options_considered` JSONB sub-shape remains a documented gap (no writer in `src/` per ADR-056 Wave 1 Session 3 note). |
| `VectorizableItem.json` | `src/shared/models/vector_models.py:18` | vector store boundary | ✅ Schema landed. |
| `RepoCensus.json` | `src/body/services/cim/models.py:181` | phase boundary | ✅ Schema landed. Already self-versioning. |
| `PolicyEvaluation.json` | `src/body/services/cim/models.py:291` | phase boundary | ✅ Schema landed. Governs CI exit codes. |
| `DriftReport.json` | `src/shared/models/drift_models.py:14` | phase boundary | ✅ Schema landed. |

Additional contract on disk not in the original inventory: **`FeatureIssue.json`** — landed alongside the Feature Registry / ADR-065 work to govern the F-21..F-43 issue shape.

---

## Critical risks (Wave 1 blockers) — status as of 2026-05-24

The original critical-risks table named gaps where drift produced silent
failures with no Python error, no audit finding, no observable signal.
Five of six are now addressed at the schema level (contract file exists);
enforcement under a governance rule has shipped for one (ConstitutionalViolationPayload)
and is pending for the rest at `enforcement: reporting` / `severity: INFO`
per the ADR-056 D6 SchemaConformanceChecks dispatch.

| Original gap | Silent failure mode | Status |
|---|---|---|
| `ActionResult` ungoverned | ConstitutionalViolationError provenance lost in proposal.execution_results | ✅ **Schema landed** — `ActionResult.json`. Enforcement mapping pending. |
| `ProposalConsequence` shape in raw SQL | `find_cause_for_file()` attribution returns None silently | ✅ **Schema + dataclass landed** (commit `77330a3d`). |
| `BlackboardEntry.subject` not in vocab | Sensors and shop managers return zero rows; worker appears healthy | ✅ **`blackboard_subject` present in `enums.json`**. Per-subject payload sub-schemas (5 rows in Wave 1 table) remain. |
| `GovernanceDecision` risk_tier ↔ approval_type unconstrained | Autonomy granted on CRITICAL risk without constitutional catch | ⚠ **Schema landed** — `GovernanceDecision.json`. Conditional invariant (state-conditional risk_tier ↔ approval_type combinations) may still require `allOf`/`if`/`then` encoding; verify before closing. |
| `PromptModelManifest` empty must_contain | `ai.prompt.model_required` rule passes; validation is vacuous | ⚠ **Schema landed** — `PromptModelManifest.json`. `must_contain` non-empty invariant verification pending. |
| `ViolationLike` duck-typed Protocol | Missing severity/rule_name/message silently treated as "error" | ✅ **Schemas landed** — `ViolationReport.json`, `ConstitutionalValidationResult.json`, `ConstitutionalViolationPayload.json` (the last with full governance rule + enforcement mapping per Wave 1 Session 3). |

**Remaining true blockers:** none of the original six are now silent at the
schema-existence level. The residual concerns (⚠ rows) are about whether
the conditional invariants encoded in each schema match the intended
constraint — a verification task per contract, not a "no schema exists"
gap.

---

## Implementation notes

**Enums ship first.** D5 has no dependency on D6 (SchemaConformanceChecks).
The D5 enum-extension pattern landed across 2026-05-18 → 2026-05-19; most
enums named in the Wave 1 table are now in `enums.json`. Remaining additions
should follow the same pattern (extend `enums.json`, extend the
vocabulary canonical store rule mapping).

**SchemaConformanceChecks dispatch.** D6 shipped 2026-05-18 (commit
`e3d1d852`): check class with three static methods
(`extract_class_annotated_fields`, `check_schema_contract_fields`,
`extract_governed_classes`); `schema_conformance` registered in
`_SUPPORTED_CHECK_TYPES`; dispatch wiring resolves
`.intent/enforcement/contracts/<schema_ref>.json` from the contract
directory. `governed_classes` is declared **on the contract side**
(rejection of the `@schema_contract` decorator alternative on
authority-inversion grounds — see `.specs/papers/CORE-DataContracts.md`,
commit `061e9eaf`).

**Rules at INFO.** Per ADR-056, all `schema_conformance` rules ship at
`severity: INFO` / `enforcement: reporting`. The `data.contracts.finding_nucleus_conforms`
rule ships in this posture and currently governs `CheckResult` only;
extending `governed_classes` to AuditFinding and BlackboardEntry payload
families is the next Wave 1 step. Promote to LOW/MEDIUM/HIGH per
findings from the audit loop, not on a schedule.

**`audit_severity` enum.** ✅ Reconciled per ADR-059 D2 to the 5-value
finding severity scale (info/low/medium/high/block), 2026-05-19 (commit `9551e972`).

**`ViolationLike` Protocol migration.** The Protocol was created to
avoid an upward Mind-layer import dependency. The schema (`ConstitutionalValidationResult.json`)
enforces shape without reintroducing the import. The AST gate check
must recognize Protocol-conforming classes as equivalent to explicit
class declarations; otherwise duck-typed validators fail schema
conformance at audit time despite correct runtime behavior.
