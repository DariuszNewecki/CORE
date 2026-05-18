# Data Contracts Inventory

**Path:** `.specs/planning/data-contracts-inventory.md`
**Date:** 2026-05-17
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
| `Finding.schema.json` | conceptual (blackboard entity) | consequence chain | Canonical nucleus: rule_id, severity, subject, evidence, worker_uuid |
| `CheckResult.schema.json` | `src/body/services/cim/models.py:279` | phase boundary | Renamed from `Finding` (ADR-056 D2); engine output only |
| `AuditFinding.schema.json` | `src/shared/models/audit_models.py:34` | persistence boundary | Extends Finding nucleus; adds file_path, line_number, context |
| `BlackboardEntry.schema.json` | `src/shared/infrastructure/database/models/workers.py:57` | worker + persistence boundary | Whole row contract; payload governed per entry_type+subject family |
| `BlackboardEntry.payload.worker_heartbeat.schema.json` | `src/shared/workers/base.py:189` | worker boundary | Payload shape for subject=worker.heartbeat |
| `BlackboardEntry.payload.worker_error.schema.json` | `src/shared/workers/base.py:153` | worker boundary | Payload shape for subject=worker.error |
| `BlackboardEntry.payload.run_complete.schema.json` | multiple workers | worker boundary | Core nucleus for *.run.complete subjects |
| `BlackboardEntry.payload.sync_db_complete.schema.json` | `src/body/workers/` | worker boundary | |
| `BlackboardEntry.payload.repo_crawl_complete.schema.json` | `src/body/workers/` | worker boundary | |
| `Proposal.schema.json` | `src/will/autonomy/proposal.py:201` | consequence chain | State-conditional invariants per ADR-056 D4 |
| `ProposalScope.schema.json` | `src/will/autonomy/proposal.py:47` | consequence chain | Sub-object; files non-emptiness invariant |
| `ProposalAction.schema.json` | `src/will/autonomy/proposal.py:105` | consequence chain | action_id XOR flow_id invariant |
| `RiskAssessment.schema.json` | `src/will/autonomy/proposal.py:78` | consequence chain | Drives approval_required |
| `ProposalConsequence.schema.json` | `infra/sql/db_schema_live.sql:1930` | consequence chain + persistence | ADR-015 load-bearing query path; shape in raw SQL strings today |
| `ActionResult.schema.json` | `src/shared/action_types.py:48` | atomic-action boundary | "Universal result contract for all atomic actions" — largest single gap |
| `ComponentResult.schema.json` | `src/shared/component_primitive.py:68` | phase boundary | "Universal result structure for all components" |
| `FlowResult.schema.json` | `src/body/flows/result.py:49` | flow boundary | CORE-Flow §6: "FlowExecutor always returns a FlowResult. No exceptions." |
| `StepResult.schema.json` | `src/body/flows/result.py:19` | flow boundary | Wraps ActionResult or FlowResult per step |
| `RefusalResult.schema.json` | `src/shared/models/refusal_result.py:27` | phase + persistence boundary | First-class outcome; 8 refusal_type values in Python set today |
| `ViolationReport.schema.json` | `src/mind/governance/violation_report.py:16` | phase boundary | Structured violation passed via exception |
| `ConstitutionalViolationPayload.schema.json` | `src/mind/governance/violation_report.py:72` | persistence boundary | to_dict() envelope persisted into proposal.execution_results |
| `ConstitutionalValidationResult.schema.json` | `src/shared/models/constitutional_validation.py:36` | phase boundary | Formalizes the ViolationLike duck-typed Protocol |
| `PromptModelManifest.schema.json` | `src/shared/models/prompt_model.py:48` | AI invocation boundary | "Sole governed surface for AI invocations" — rule exists, schema does not |
| `ContextPacket.schema.json` | `src/shared/infrastructure/context/models.py:44` | AI invocation boundary | AI evidence envelope; 8 dict[str, Any] fields today |
| `ContextBuildRequest.schema.json` | `src/shared/infrastructure/context/models.py:15` | AI invocation boundary | Single entrypoint for all context assembly |
| `EmbeddingPayload.schema.json` | `src/shared/models/embedding_payload.py:13` | vector store boundary | Docstring already claims "strict schema" — formalize it |

### Enums (additions to `.intent/META/enums.json`)

| Key | Values | Notes |
|---|---|---|
| `blackboard_entry_type` | finding, claim, proposal, report, heartbeat | D5 — ship first, no new engine needed |
| `blackboard_entry_status` | open, claimed, resolved, abandoned | Verified at models/workers.py:79 |
| `blackboard_subject` | worker.heartbeat, worker.error, *.run.complete, sync.db.complete, repo.crawl.complete, violation_remediator.completed | Consequence-chain join keys; start with highest-traffic subjects |
| `proposal_status` | draft, pending, approved, executing, completed, failed, rejected | Implicit in D4; needs explicit enum |
| `action_impact` | READ_ONLY, WRITE_METADATA, WRITE_CODE, WRITE_DATA | Used by every atomic action |
| `action_category` | FIX, SYNC, CHECK, BUILD, STATE | ActionDefinition classification |
| `component_phase` | INTERPRET, PARSE, LOAD, AUDIT, RUNTIME, EXECUTION | Phase ordering invariants |
| `refusal_type` | boundary, confidence, contradiction, assumption, capability, extraction, quality, unspecified | 8 values in Python set today |
| `step_kind` | action, flow | Flow step discriminator |
| `risk_tier` | ROUTINE, STANDARD, ELEVATED, CRITICAL | GovernanceDecision input |
| `approval_type` | autonomous, validation_only, human_confirmation, human_review | GovernanceDecision output |
| `audit_severity` | INFO, LOW, MEDIUM, HIGH, BLOCK | Verify against existing enums.json before adding |
| `task_type` | QUERY, REFACTOR, FIX, ANALYSIS, BUILD, TEST, DOCUMENT, SYNC, AUDIT, PLAN, ORCHESTRATE, UNKNOWN | Governed by ADR-003 YAML; formalize in enum |

---

## Wave 2 — Governance decisions and execution routing

### Schemas

| Contract | Source | Boundary | Notes |
|---|---|---|---|
| `GovernanceDecision.schema.json` | `src/body/services/constitutional_validator.py:55` | phase boundary | State-conditional: risk_tier ↔ approval_type combinations |
| `ActionDefinition.schema.json` | `src/body/atomic/registry.py:53` | atomic-action boundary | Declares impact_level, policies, remediates |
| `ExecutionTask.schema.json` | `src/shared/models/execution_models.py:35` | phase boundary | task_type governed by ADR-003; whole shape is not |
| `TaskStructure.schema.json` | `src/will/interpreters/request_interpreter.py:62` | phase boundary | INTERPRET-phase output; universal workflow handoff |
| `FlowDefinition.schema.json` | `src/body/flows/registry.py:77` | flow boundary | Existence in .intent/flows/ is constitutional standing |
| `FlowStep.schema.json` | `src/body/flows/registry.py:37` | flow boundary | Governs consumes whitelist |
| `WorkerDeclaration.schema.json` | `src/shared/workers/base.py:226` | worker boundary | uuid/mandate.responsibility/mandate.phase/mandate.approval_required |
| `ActionRiskConfig.schema.json` | `.intent/enforcement/config/action_risk.yaml` | atomic-action boundary | Missing entry raises ConstitutionalError; shape ungoverned |
| `RemediationResult.schema.json` | `src/body/self_healing/remediation_models.py:131` | phase boundary | Full audit→fix→validate report |
| `FixResult.schema.json` | `src/body/self_healing/remediation_models.py:79` | phase boundary | Per-fix outcome |
| `AutoFixablePattern.schema.json` | `src/shared/models/remediation.py:23` | phase boundary | Maps check_id→action_handler at runtime |
| `PatternViolation.schema.json` | `src/shared/models/pattern_graph.py:14` | phase boundary | Pattern checker output |
| `ValidationResult.schema.json` | `src/shared/models/validation_result.py:13` | phase boundary | Canonical validation result; divergence risk with ConstitutionalValidationResult |
| `DecisionTrace.entries.schema.json` | `src/shared/infrastructure/database/models/decision_traces.py:29` | persistence boundary | decisions JSONB array |
| `Task.plan.schema.json` | `src/shared/infrastructure/database/models/operations.py:94` | persistence boundary | plan JSONB; structure implicit |
| `Action.payload.schema.json` | `src/shared/infrastructure/database/models/operations.py:132` | persistence boundary | payload + result JSONB open-ended |

---

## Wave 3 — API, workflow, and observability

### Schemas

| Contract | Source | Boundary | Notes |
|---|---|---|---|
| `api/AuditRequest.schema.json` | `src/api/v1/` | API boundary | One schema per route family |
| `api/FixRequest.schema.json` | `src/api/v1/` | API boundary | |
| `api/ProposalRequest.schema.json` | `src/api/v1/` | API boundary | |
| *(remaining 21 API request/response shapes)* | `src/api/v1/` | API boundary | |
| `WorkflowResult.schema.json` | `src/shared/models/workflow_models.py:48` | flow boundary | |
| `PhaseWorkflowResult.schema.json` | `src/shared/models/workflow_models.py:110` | flow boundary | |
| `DetailedPlan.schema.json` | `src/shared/models/workflow_models.py:207` | phase boundary | A3 blueprint handoff |
| `DetailedPlanStep.schema.json` | `src/shared/models/workflow_models.py:145` | phase boundary | |
| `AuditRunResult.schema.json` | `src/shared/infrastructure/database/models/governance.py` | persistence boundary | One per *Run.result JSONB column (×7) |
| `AgentDecision.schema.json` | `src/shared/infrastructure/database/models/learning.py:30` | persistence boundary | options_considered JSONB |
| `VectorizableItem.schema.json` | `src/shared/models/vector_models.py:18` | vector store boundary | |
| `RepoCensus.schema.json` | `src/body/services/cim/models.py:181` | phase boundary | Already self-versioning; formalize |
| `PolicyEvaluation.schema.json` | `src/body/services/cim/models.py:291` | phase boundary | Governs CI exit codes |
| `DriftReport.schema.json` | `src/shared/models/drift_models.py:14` | phase boundary | |

---

## Critical risks (Wave 1 blockers)

These are the gaps where drift produces silent failures with no Python
error, no audit finding, no observable signal:

| Gap | Silent failure mode |
|---|---|
| `ActionResult` ungoverned | ConstitutionalViolationError provenance lost in proposal.execution_results |
| `ProposalConsequence` shape in raw SQL | find_cause_for_file() attribution returns None silently |
| `BlackboardEntry.subject` not in vocab | Sensors and shop managers return zero rows; worker appears healthy |
| `GovernanceDecision` risk_tier ↔ approval_type unconstrained | Autonomy granted on CRITICAL risk without constitutional catch |
| `PromptModelManifest` empty must_contain | ai.prompt.model_required rule passes; validation is vacuous |
| `ViolationLike` duck-typed Protocol | Missing severity/rule_name/message silently treated as "error" |

---

## Implementation notes

**Enums ship first.** D5 has no dependency on D6 (SchemaConformanceChecks).
Extend `enums.json`, extend the vocabulary canonical store rule mapping.
This is the fastest visible governance improvement.

**SchemaConformanceChecks decorator.** D6 needs a class-discovery
mechanism — a decorator `@schema_contract("ActionResult")` — so the
check scales to 30+ contracts without a hand-maintained registry.
This is a Wave 1 deliverable before schema rules are authored.

**Rules at INFO.** All `schema_conformance` rules ship at
`severity: INFO`. Promote to LOW/MEDIUM/HIGH per findings from the
audit loop, not on a schedule.

**`audit_severity` enum.** Verify whether this already exists in
`.intent/META/enums.json` before adding. Flagged unverified.

**`ViolationLike` Protocol migration.** The Protocol was created to
avoid an upward Mind-layer import dependency. The schema enforces shape
without reintroducing the import. The AST gate check must recognize
Protocol-conforming classes as equivalent to explicit class
declarations; otherwise duck-typed validators fail schema conformance
at audit time despite correct runtime behavior.
