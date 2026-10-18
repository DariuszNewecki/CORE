# CORE decisions

One entry per accepted ADR, in ID order: the decision as it holds today and
what enforces it. Where a later ADR, an amendment, a governor ruling or a
commit changed the decision, the entry states the current wording and an
"Amended" line names the source (ADR, amendment date, or short sha and
date). Where `.intent/` and an entry disagree, `.intent/` wins. The full ADR
texts, with their amendments, are in git history and tag
`archive/pre-cleanup-2026-10`.

"Enforced by" lists the ENFORCED rules whose rule or mapping cites the ADR;
when none does, the src/ files that cite it; otherwise "not enforced".

## Thesis and baselines (2026-10-13)

Supersedes ADR-159's thresholds. Measured by `scripts/thesis_baseline.py`.  
**Thesis:** a non-programmer governs untrusted AI through deterministic checks and ships working
software, at a governance cost that falls over time.  
**Measures, with the 2026-10-13 baselines:**
- Unverified writes to main = 0 since 2026-10-12 (every write a governor-merged, CI-green PR).
- AI authorship of commits merged into main >= 63%, never lower.
- Waste trips per merged change = 2.0, falling month on month.
- Convergence = findings resolved (not abandoned) / findings created >= 100%; currently 89%.

**Refuted by:** an unverified write on main; waste per change rising with scale; or convergence
below 100% for two consecutive months once it has first reached 100%.

## ADR-001 — Establish the .specs/ layer

2026-04-15 · was `ADR-001-specs-layer-established.md`  
Non-operational documents move out of .intent/ into a new top-level directory, .specs/, organized
as: The admission test for .specs/ is the inverse of the .intent/ test: *a file belongs in .specs/
if CORE does not read it at runtime to make a governance decision.* Architectural …  
Enforced by: not enforced

## ADR-002 — Shared Layer Boundary Enforcement

2026-04-18 · was `ADR-002-shared-boundary-enforcement.md`  
Extract governance constants to .intent/enforcement/constitutional_envelope.yaml and modify the code
to read them dynamically via IntentRepository.load_document(). Move shared/cli_utils/ →
src/cli/utils/ with full import updates across 114 files and 4 .intent/ governance mappings. …  
Enforced by: not enforced

## ADR-003 — task_type as a first-class field on ExecutionTask

2026-04-19 · was `ADR-003-task-type-first-class-field-on-execution-task.md`  
task_type becomes a first-class field on ExecutionTask.  
Enforced by: not enforced

## ADR-004 — Govern task_type → phase mapping in .intent/ and retire the vestigial context CLI

2026-04-19 · was `ADR-004-govern-task-type-phase-mapping.md`  
The task_type → phase mapping moves to .intent/enforcement/config/task_type_phases.yaml, loaded via
IntentRepository. Both live call sites (ContextService.build_for_task and
src/cli/resources/context/build.py) read from the same governed source through a single new …  
Enforced by: src/cli/resources/context/build.py,
  src/shared/infrastructure/intent/task_type_phases.py, src/shared/models/execution_models.py

## ADR-005 — Govern audit verdict policy in .intent/

2026-04-20 · was `ADR-005-govern-audit-verdict-policy.md`  
Author .intent/enforcement/config/audit_verdict.yaml codifying the severity-to-verdict mapping, the
carve-out list, and the DEGRADED preconditions as data. Author a governed loader at
src/shared/infrastructure/intent/audit_verdict.py mirroring the task_type_phases.py pattern. …  
Amended: 2026-10-06 (#952, governor ruling A) — the bundled floor's audit_verdict.yaml is a
substrate minimum, unioned into every project's policy; a project may add entries, never remove one.  
Enforced by: src/cli/resources/code/audit.py, src/mind/enforcement/audit.py,
  src/mind/governance/auditor.py (+3 more src/ files)

## ADR-006 — Align modularity.needs_split implementation with its statement

2026-04-20 · was `ADR-006-align-needs-split-with-statement.md`  
The rule statement is governance law. The implementation is mechanism. When they disagree, the
mechanism is corrected to match the statement, not the other way around.  
Enforced by: src/mind/logic/engines/ast_gate/checks/modularity_checks.py

## ADR-008 — Constitutionalize impact_level

2026-04-22 · was `ADR-008-constitutionalize-action-impact-level.md`  
Externalize impact_level to .intent/enforcement/config/action_risk.yaml, keyed by action_id. A
loader at shared.infrastructure.intent.action_risk reads the mapping at ActionExecutor init time and
overlays it onto registered ActionDefinition instances via ActionRegistry.apply_risk_config(). …  
Enforced by: atomic_actions.impact_level_must_be_governed

## ADR-009 — CLI-depth block transient — passive instrumentation over active probe

2026-04-24 · was `ADR-009-cli-depth-block-passive-instrumentation.md`  
Do not modify .intent/enforcement/mappings/cli/interface_design.yaml or any cli.* rule. The YAML is
correct; any change would be a false fix against a phantom condition.  
Enforced by: not enforced

## ADR-010 — Wire the §7+§7a Finding/Proposal contract

2026-04-24 · was `ADR-010-finding-proposal-contract.md`  
Close all three gaps in one coordinated change. Three files, one .intent/ amendment (the enum is
already declared; no amendment needed).  
Amended: addendum 2026-04-24 — revival of a failed proposal's findings runs in
ProposalConsumerWorker, not in ProposalStateManager.mark_failed (ADR-011 attribution).  
Enforced by: src/api/v1/proposals_routes.py,
  src/body/services/blackboard_service/blackboard_proposal_service.py,
  src/will/autonomy/pending_proposal_gate.py (+6 more src/ files)

## ADR-011 — Workers own blackboard attribution; services do not post

2026-04-24 · was `ADR-011-worker-attribution-for-blackboard-entries.md`  
Every INSERT into core.blackboard_entries must originate from a registered Worker, routed through
the Worker base class's post_finding() / post_report() / post_heartbeat() / _post_entry() machinery.  
Enforced by: architecture.blackboard.worker_only_inserts,
  architecture.flows.flow_must_not_post_to_blackboard

## ADR-012 — Centralize globstar pattern matching via pathspec

2026-04-25 · was `ADR-012-centralize-globstar-pattern-matching.md`  
1. Promote pathspec from transitive to direct dependency; 2. New helper module —
src/shared/utils/glob_match.py; 3. Migrate seven call sites; 4. Test coverage; 5. Pattern rewrites
required.  
Amended: addendum 2026-05-03 (§6) — matches_glob normalizes inputs to repo-relative form (strips ./
and leading /).  
Enforced by: src/mind/logic/engines/knowledge_gate.py, src/shared/utils/glob_match.py

## ADR-013 — Retire core.proposals; Reserve Name for core.autonomous_proposals

2026-04-26 · was `ADR-013-retire-legacy-proposals-table.md`  
core.proposals (the original constitutional file-replacement table with cryptographic signing) is
retired and dropped. It was never provisioned in production — zero rows, no active writers, signing
infrastructure never created.  
Enforced by: not enforced

## ADR-014 — Development-Phase Priority: Loop Liveness Before Artifact Quality

2026-04-26 · was `ADR-014-development-phase-priority-loop-before-quality.md`  
During CORE's development phase, generation-loop liveness takes priority over individual artifact
quality. As the first application of this priority: reclassify build.tests from
impact_level="moderate" to impact_level="safe".  
Enforced by: src/api/v1/audit_routes.py, src/api/v1/fix_routes.py, src/api/v1/refactor_routes.py (+2
  more src/ files)

## ADR-015 — Consequence Chain Attribution: Write Paths and Storage Shapes

2026-04-27 · was `ADR-015-consequence-chain-attribution.md`  
D1 — finding_ids lives in constitutional_constraints jsonb (#145); D2 — approval_authority is a new
column with forward-only CHECK (#165); D3 — claimed_by mirrors the blackboard pattern onto proposals
(#147), written by the claim.proposal atomic action (ADR-017); D4 — Subsume-path attribution writes
proposal_id into payload (#164) …  
Amended by: ADR-017 (D3's write path).  
Enforced by: src/body/services/blackboard_service/blackboard_proposal_service.py,
  src/body/services/blackboard_service/blackboard_service.py,
  src/body/services/consequence_log_service.py (+6 more src/ files)

## ADR-016 — Test environment architecture

2026-04-27 · was `ADR-016-test-environment-architecture.md`  
D1 — Schema authority: the SQLAlchemy model registry; D2 — Test DB lifecycle: ephemeral core_test
per pytest session; D3 — Per-test isolation: TRUNCATE CASCADE between tests; D4 — CI: GitHub Actions
Postgres service container.  
Enforced by: src/shared/infrastructure/database/models/autonomous_proposals.py

## ADR-017 — claim.proposal as a governed atomic action

2026-04-28 · was `ADR-017-claim-proposal-as-atomic-action.md`  
D1 — claim.proposal as a registered atomic action; D2 — ProposalStateManager is reduced, not
retired; D3 — ProposalExecutor.execute and execute_batch invoke claim.proposal; D4 — CLI claimer is
a sentinel UUID constant; D5 — Relationship to ADR-015 D3.  
Amended: Note 2026-07-05 (D6) — POST /proposals/{id}/execute is a sanctioned governor-direct path,
claimer API_CLAIMER_UUID.  
Enforced by: src/api/v1/proposals_routes.py, src/body/atomic/proposal_lifecycle_actions.py

## ADR-018 — Decomposed crawler/embedder supersedes vector_sync_worker on the autonomous path

2026-05-01 · was `ADR-018-decomposed-crawler-embedder-supersedes-vector-sync-worker.md`  
D1 — vector_sync_worker is deprecated as the autonomous path; D2 — repo_crawler is activated; D3 —
repo_embedder is activated, conditional on two prerequisite fixes; D4 — repo_artifacts.chunk_count
is the work queue between the two workers; D5 — Class taxonomy is left as-declared.  
Enforced by: src/will/workers/governance_embedding/governance_embedder_worker.py

## ADR-019 — Edge 5 git-boundary attribution posture

2026-05-01 · was `ADR-019-edge5-git-boundary-attribution-posture.md`  
D1 — Orphan detection: sense, surface, preserve; D2 — Prefix widening: 16 chars on new commits,
forward-only; D3 — post_execution_sha is the authoritative Edge 5 link.  
Enforced by: src/body/services/consequence_log_service.py, src/shared/infrastructure/git_service.py,
  src/will/workers/commit_authorship_audit_worker.py (+1 more src/ files)

## ADR-020 — Worker liveness derived from heartbeat, not from registry status

2026-05-02 · was `ADR-020-worker-liveness-derived-from-heartbeat.md`  
D1 — last_heartbeat is the canonical liveness signal; D2 — Drop the status column from
core.worker_registry; D3 — Centralize liveness derivation in WorkerRegistryService, with per-worker
thresholds in the DAL (ADR-041 D2); D4 — Per-worker thresholds remain owned by
.intent/workers/*.yaml.  
Amended by: ADR-041 D2.  
Enforced by: src/body/services/worker_registry_service.py, src/cli/resources/runtime/health.py

## ADR-022 — ContextBuilder vector evidence scope

2026-05-03 · was `ADR-022-contextbuilder-vector-evidence-scope.md`  
_gather_vector_evidence continues to query intent-layer collections only: core_policies, core-
patterns, core_specs. The active code-symbol collection core-code is intentionally not queried.  
Enforced by: src/shared/infrastructure/context/builder.py

## ADR-023 — Vocabulary canonical store — paper-first, machine projection derived

2026-05-04 · was `ADR-023-vocabulary-canonical-store.md`  
.specs/papers/CORE-Vocabulary.md is the single source of truth for CORE's governance-ontology
vocabulary. It is paper-authority, human-authored, and the only place definitions, "not"
disambiguations, and authoritative-source pointers are added or revised. …  
Enforced by: governance.fs_operations.no_direct_yaml_import,
  governance.vocabulary.authoritative_source_must_be_paper,
  governance.vocabulary.canonical_format_must_validate, governance.vocabulary.no_direct_json_import,
  governance.vocabulary.projection_must_match_canonical

## ADR-024 — Local LLM cognitive role assignments — governed evaluation over assumption

2026-05-05 · was `ADR-024-local-llm-cognitive-role-assignments.md`  
Production on-prem hardware has not been specified. Role assignments for production must be re-
derived using the same harness against the production hardware profile and model set. The evaluation
harness (scripts/eval_ollama.py) is the instrument for this …  
Enforced by: not enforced

## ADR-026 — Validate proposal.scope.files non-emptiness at Proposal.validate()

2026-05-05 · was `ADR-026-proposal-scope-files-non-emptiness-validation.md`  
A sixth check in Proposal.validate(): This represents three coordinated choices:  
Enforced by: not enforced

## ADR-027 — Sensor-fixer coherence detection via consequence chain query

2026-05-07 · was `ADR-027-sensor-fixer-coherence-detection.md`  
D1 — Detection mechanism: query-based periodic audit; D2 — "Same violation" identity: check_id +
file_path; D3 — Lookback window: governed in .intent/; D4 — Signal surface: Blackboard finding; D5 —
No autonomous remediation for coherence findings; D6 — Worker class: supervisory, audit phase.  
Enforced by: src/shared/infrastructure/intent/test_namespaces.py,
  src/will/workers/coherence_sensor.py

## ADR-028 — Describe rules; don't quote forbidden syntax

2026-05-08 · was `ADR-028-describe-rules-dont-quote-forbidden-syntax.md`  
Rule documentation MUST describe what is forbidden by paraphrase, not by reproduction of the
forbidden pattern.  
Enforced by: not enforced

## ADR-029 — Explicitly map non-automatable rules in RemediationMap

2026-05-08 · was `ADR-029-explicit-non-automatable-rule-mapping.md`  
Non-automatable rules MUST be explicitly mapped in auto_remediation.yaml with confidence < 0.50
(PENDING threshold). This excludes them from the ViolationExecutorWorker fallback while keeping the
finding visible on the Blackboard for human action.  
Enforced by: not enforced

## ADR-030 — Daemon stale-code detection posture

2026-05-08 · was `ADR-030-daemon-stale-code-detection-posture.md`  
Option C — detect and DEGRADE.  
Amended: 2026-10-11 (ADR-132 D10.14) — under the release runtime, code on disk is the release
/opt/core/current names; stale means a process running another release; unreadable release metadata
fails closed. In the development tree it stays src/.  
Enforced by: src/cli/commands/daemon.py, src/shared/infrastructure/code_identity.py,
  src/shared/infrastructure/intent/operational_config.py (+2 more src/ files)

## ADR-032 — Tighten no_hardcoded_runtime_dirs regex to path-construction context

2026-05-10 · was `ADR-032-tighten-no-hardcoded-runtime-dirs-regex.md`  
Replace the two broad bare-string patterns with a single path-construction-context pattern. The new
pattern set: This catches the two structural forms of runtime path construction in the codebase;
while excluding standalone string literals in non-path contexts.  
Enforced by: architecture.path_access.no_hardcoded_runtime_dirs

## ADR-033 — Flow→Step Parameter Routing Contract

2026-05-10 · was `ADR-033-flow-step-parameter-routing-contract.md`  
D1 — consumes field on FlowStep; D2 — Filter in FlowExecutor._execute_step; D3 — YAML schema
extension for .intent/flows/*.yaml; D4 — Loader change in FlowRegistry._load_file; D5 — core_context
injection is not affected; D6 — Nested Flow steps.  
Enforced by: src/will/autonomy/violation_remediator_proposal.py

## ADR-034 — OptimizerWorker Formal Deferral

2026-05-10 · was `ADR-034-optimizer-worker-formal-deferral.md`  
D1 — OptimizerWorker is formally deferred; D2 — Review trigger; D3 — Active constitutional
commitments removed; D4 — #115 retained as the implementation epic.  
Enforced by: not enforced

## ADR-035 — One Finding, One Proposal

2026-05-11 · was `ADR-035-one-finding-one-proposal.md`  
D1 — One finding, one proposal; D2 — Deduplication preserved; D3 — Batch-safe classification
deferred; D4 — Consequence chain integrity.  
Amended: 2026-06-15 (ADR-109 D3) — in the assisted lane only, one human-gated proposal may span
several interdependent files; the autonomous loop still emits one proposal per (action, file).  
Enforced by: src/will/autonomy/lane_service.py, src/will/autonomy/proposal_consumer_revival.py,
  src/will/autonomy/violation_remediator_proposal.py (+1 more src/ files)

## ADR-036 — PathResolver excluded from modularity.needs_split

2026-05-11 · was `ADR-036-path-resolver-excluded-from-needs-split.md`  
Add src/shared/path_resolver.py to the excludes list of the modularity.needs_split enforcement
mapping.  
Amended: the excludes entry is gone. ADR-042 D3 moved it into a governed exclusion register; ADR-095
D3 replaced that with the in-file declaration CORE_ROLE = "catalog" in src/shared/path_resolver.py.  
Enforced by: not enforced

## ADR-038 — Circuit-breaker on repeated proposal failures

2026-05-11 · was `ADR-038-circuit-breaker-on-repeated-proposal-failures.md`  
D1 — Failure identity is (ref_id, file_path, error_signature); D2 — Threshold is consecutive
identical signatures, default N=5; D3 — Tripping the circuit: DELEGATE the findings, post a hazard;
D4 — Reset path; D5 — Governance values live in .intent/, not in src/ …  
Enforced by: governance.quarantine.namespace_has_drainer, governance.remediation.all_rules_mapped

## ADR-039 — Audit-input cache invalidation

2026-05-12 · was `ADR-039-audit-input-cache-invalidation.md`  
Option B — per-cycle invalidation.  
Amended: supplement 2026-05-16 (175b46e4) — invalidation also clears the AST cache; supplements
2026-06-15 (rev. b–d) — the parse cache is content-addressed (98c9f592) and there is no cross-cycle
change gate (Option B′ withdrawn).  
Enforced by: src/mind/governance/audit_context.py, src/mind/governance/auditor.py,
  src/mind/governance/filtered_audit.py (+6 more src/ files)

## ADR-040 — No Hardcoded Values in src/

2026-05-12 · was `ADR-040-no-hardcoded-config-values.md`  
D1 — The rule; D2 — Exclusions; D3 — Migration; D4 — Audit rule.  
Enforced by: governance.operational_config.no_hardcoded_thresholds

## ADR-041 — Per-worker liveness thresholds and orphan-skip in the DAL

2026-05-12 · was `ADR-041-per-worker-liveness-thresholds-and-orphan-skip.md`  
D1 — ADR-020 D1, D2, D4 (in part) preserved; D2 — Amendment to ADR-020 D3 — per-worker thresholds in
the DAL; D3 — Orphan-skip is policy, not a local supervisor heuristic; D4 — One YAML-reader for all
readers; D5 — Dashboard binary stale/alive.  
Enforced by: src/api/v1/daemon_routes.py, src/body/services/health_log_service.py,
  src/body/services/worker_registry_service.py (+6 more src/ files)

## ADR-042 — Modularity governance recalibration — responsibility-first

2026-05-13 · was `ADR-042-modularity-governance-recalibration.md`  
Line count governs whether a class is a *candidate* for responsibility review. It is not a finding
in itself. This principle governs all future modularity rule authoring.  
Amended by: ADR-095 (2026-06-06) — D4's retirement-on-unix_philosophy commitment is withdrawn; the
500-line pre-selector stays; D3's governed_exclusions register gives way to in-file CORE_ROLE
declarations.  
Enforced by: governance.exemption_debt.declared, modularity.class_too_large, modularity.needs_split

## ADR-043 — llm_gate audit throughput — pre-selector primary, semaphore secondary

2026-05-13 · was `ADR-043-llm-gate-audit-throughput.md`  
ADR-042 D1 established that for modularity.class_too_large, line count is a pre-selector* and
responsibility-count is the *verdict*. The same shape applies to the llm_gate family generally:
cheap, deterministic gates narrow the candidate set …  
Enforced by: architecture.mind.execution_signal, modernization.legacy_signal

## ADR-044 — Incremental LLM-gate verdict cache

2026-05-13 · was `ADR-044-llm-gate-verdict-cache.md`  
Option A — DB verdict cache keyed on content hash + rule hash.  
Enforced by: src/body/services/crawl_service/main_module.py,
  src/body/services/crawl_service/orchestrator.py, src/cli/resources/code/audit.py (+12 more src/
  files)

## ADR-045 — Quarantine state for findings revived after rejection

2026-05-13 · was `ADR-045-quarantine-state-for-revived-findings.md`  
Option A — awaiting_reaudit quarantine state.  
Enforced by: architecture.blackboard.indeterminate_requires_human_mechanism,
  architecture.blackboard.reaudit_requires_reaudit_mechanism,
  governance.quarantine.namespace_has_drainer

## ADR-046 — Flow risk derived from constituent steps; close the test-format heal loop

2026-05-15 · was `ADR-046-flow-risk-from-constituent-steps.md`  
D1 — Risk for a flow is computed from its constituent steps; D2 — TestRemediatorWorker emits a flow-
kind proposal; D3 — Optional-step failure must be discoverable, not log-only.  
Enforced by: src/body/atomic/sandbox_lifecycle.py, src/will/autonomy/proposal.py,
  src/will/autonomy/proposal_consumer_effects.py (+1 more src/ files)

## ADR-047 — Move purity.docstrings.required from llm_gate to ast_gate

2026-05-15 · was `ADR-047-docstring-rule-ast-gate.md`  
D1 — purity.docstrings.required moves from llm_gate to ast_gate; D2 — Add check_docstrings_present
to ast_gate; D3 — Placeholder content was left to purity.no_todo_placeholders, which ADR-114
retired; nothing mandatory checks it.  
Amended: 2026-05-16 (6c1c7270) — nested functions are not checked.  
Enforced by: purity.docstrings.required, purity.no_metadata_decorators

## ADR-048 — fix.docstrings walks the AST instead of the knowledge graph

2026-05-15 · was `ADR-048-fix-docstrings-ast-walk.md`  
D1 — Symbol discovery via ast.walk(tree), not the knowledge graph; D2 — Inline AST-based insertion
replaces the non-existent atomic action; D3 — Retire doc_writer worker.  
Enforced by: src/body/self_healing/docstring_service.py

## ADR-049 — Restore parity between architectural doctrine and enforced rules

2026-05-15 · was `ADR-049-doctrine-rule-parity.md`  
D1 — Adopt Option C per boundary; D2 — Establish doctrine-rule parity as a standing discipline; D3 —
Each excludes entry must reference a closure ADR and carry a deadline.  
Amended: 2026-05-27 (CCC #463) — D2's citation duty covers every normative paper section
(Governance-Topology Row 3), not only imports, layer boundaries and responsibilities.  
Enforced by: architecture.api.no_body_bypass, architecture.api.no_direct_database_access,
  architecture.body.no_rule_evaluation, governance.exemption_debt.declared

## ADR-050 — CLI is a standalone HTTP client; src/cli/ extracted from CORE

2026-05-15 · was `ADR-050-cli-positioning.md`  
D1 — The deferred network-boundary decision is resolved: HTTP only; D2 — only the consumer CLI is
extracted (core-cli); the operator CLI core-admin stays in src/cli/ (ADR-146); D3 — Will may not
import from CLI (already satisfied); D4 — architecture.cli.api_only is disabled during migration;
retired on extraction …  
Amended by: ADR-146 (D2); refined by ADR-110 (exposure tiers).  
Enforced by: src/body/self_healing/atomic_actions_fixer.py,
  src/body/self_healing/duplicate_id_service.py, src/body/self_healing/duplicates_service.py (+4
  more src/ files)

## ADR-052 — LLM Configuration Domain: Final Schema

2026-05-16 · was `ADR-052-llm-config-schema.md`  
1. llm_resources is the single source of truth for every resource-specific property. No resource
property may live in runtime_settings or any other table. 2. runtime_settings is retired once every
row in config_migration_log carries a non-null migrated_at. …  
Enforced by: src/body/atomic/llm_resource_authoring_actions.py, src/body/atomic/log_actions.py,
  src/body/infrastructure/repositories/llm_resource_repository.py (+15 more src/ files)

## ADR-053 — CORE API as Resource-Oriented Governance Interface

2026-05-16 · was `ADR-053-api-governance-interface.md`  
D1 — The API is CORE's governance interface; D2 — Operations are resources, not RPC calls; D3 —
Standard protocol contract; D4 — Ten domain namespaces (revised 2026-05-18); D5 — CLI becomes a
typed HTTP client; D6 — Papers first, always; D7 — Request-level attribution for GxP readiness.  
Enforced by: src/api/v1/audit_routes.py, src/api/v1/fix_routes.py, src/api/v1/inspect_routes.py (+1
  more src/ files)

## ADR-054 — API Phase 1: /audit + /proposals

2026-05-16 · was `ADR-054-api-phase-1-audit-proposals.md`  
D1 — Audit runs are resources; D2 — /proposals/{id}/execute is included in the API; D3 — No auth for
Phase 1; loopback binding only; D4 — Phase 1 completion is verified by suppress-entry removal.  
Amended: 2026-05-17 (audit_runs.findings JSONB); 2026-07-07 (audit_findings.run_id, an append-only
history). D3's no-auth: governor routes are gated by ADR-132 D10.17 (2026-10-12).  
Enforced by: src/api/cli/__init__.py, src/api/cli/client.py, src/api/v1/audit_routes.py (+12 more
  src/ files)

## ADR-055 — API Phase 2: /fix + /quality

2026-05-17 · was `ADR-055-api-phase-2-fix-quality.md`  
D1 — Fix operations are resources backed by fix_runs; D2 — /fix endpoint contract; D3 — /quality
endpoint contract; D4 — Will-layer wiring; D5 — No auth; loopback binding (inherited from ADR-054
D3); D6 — Phase 2 completion verified by the boundary rule, not a file list.  
Amended by: ADR-132 D10.17 (2026-10-12) — D5's no-auth no longer holds for governor acts: they need
the governor on CORE's Unix socket.  
Enforced by: src/api/cli/client.py, src/api/cli/integrity_client.py, src/api/v1/fix_routes.py (+6
  more src/ files)

## ADR-056 — Runtime Data Contracts as First-Class Constitutional Artifacts

2026-05-17 · was `ADR-056-runtime-data-contracts.md`  
D1 — Establish .intent/enforcement/contracts/ as a new governed artifact class; D2 — The name
Finding belongs to the blackboard entity; D3 — Finding is governed by a canonical nucleus contract,
enforced at the blackboard-write boundary, not by Finding.json (ADR-102 D1/D2); D4 — Proposal is
governed as a state-machine aggregate …  
Amended by: ADR-102 (D3).  
Enforced by: data.contracts.action_definition_conforms, data.contracts.action_result_conforms,
  data.contracts.agent_decision_conforms, data.contracts.approve_request_conforms,
  data.contracts.audit_finding_conforms, data.contracts.auto_fixable_pattern_conforms,
  data.contracts.blackboard_entry_conforms, data.contracts.check_result_conforms,
  data.contracts.constitutional_validation_result_conforms,
  data.contracts.constitutional_violation_payload_conforms,
  data.contracts.context_build_request_conforms, data.contracts.context_packet_conforms,
  data.contracts.create_audit_run_request_conforms, data.contracts.create_baseline_request_conforms,
  data.contracts.create_census_run_request_conforms,
  data.contracts.create_proposal_request_conforms,
  data.contracts.create_remediation_request_conforms, data.contracts.detailed_plan_conforms,
  data.contracts.detailed_plan_step_conforms, data.contracts.development_goal_conforms,
  data.contracts.drift_report_conforms, data.contracts.embedding_payload_conforms,
  data.contracts.execute_request_conforms, data.contracts.execution_task_conforms,
  data.contracts.fix_result_conforms, data.contracts.fix_run_result_conforms,
  data.contracts.flow_definition_conforms, data.contracts.flow_step_conforms,
  data.contracts.generate_batch_request_conforms, data.contracts.generate_request_conforms,
  data.contracts.governance_decision_conforms, data.contracts.integrate_request_conforms,
  data.contracts.integrity_request_conforms, data.contracts.interactive_tests_request_conforms,
  data.contracts.phase_workflow_result_conforms, data.contracts.policy_evaluation_conforms,
  data.contracts.prompt_model_manifest_conforms, data.contracts.proposal_action_conforms,
  data.contracts.proposal_conforms, data.contracts.proposal_scope_conforms,
  data.contracts.propose_request_conforms, data.contracts.quality_async_request_conforms,
  data.contracts.quality_gate_result_conforms, data.contracts.quality_lint_request_conforms,
  data.contracts.quality_target_request_conforms, data.contracts.quality_tests_request_conforms,
  data.contracts.refusal_result_conforms, data.contracts.reject_request_conforms,
  data.contracts.remediation_result_conforms, data.contracts.repo_census_conforms,
  data.contracts.report_request_conforms, data.contracts.risk_assessment_conforms,
  data.contracts.run_autonomous_request_conforms, data.contracts.run_fix_request_conforms,
  data.contracts.run_flow_request_conforms, data.contracts.run_ir_request_conforms,
  data.contracts.sync_request_conforms, data.contracts.task_structure_conforms,
  data.contracts.validation_result_conforms, data.contracts.vectorizable_item_conforms,
  data.contracts.violation_report_conforms, data.contracts.worker_declaration_conforms,
  data.contracts.workflow_result_conforms

## ADR-057 — API Phase 3: /coverage + /refactor + /inspect

2026-05-18 · was `ADR-057-phase3-imports.md`  
D1 — Coverage operations: read-only queries + coverage_runs for generation; D2 — Refactor
operations: read-only queries + refactor_runs for autonomous cycle; D3 — Inspect operations: all
read-only, no new tables; D4 — Audit remediations: new audit_remediation_runs table …  
Amended by: ADR-132 D10.17 (2026-10-12) — D6's no-auth no longer holds for governor acts: they need
the governor on CORE's Unix socket.  
Enforced by: src/api/cli/inspect_client.py, src/api/v1/audit_routes.py,
  src/api/v1/coverage_routes.py (+10 more src/ files)

## ADR-058 — API Phase 4: /census + /sync + /daemon

2026-05-18 · was `ADR-058-api-phase-4-census-sync-daemon.md`  
D1 — Census operations: census_runs resource table; D2 — Sync operations: sync_runs resource table
with discriminator; D3 — Daemon lifecycle: signal-based, synchronous, no resource table; D4 —
Endpoint surface; D5 — Unassigned namespace items flagged for follow-up; D6 — No auth …  
Amended by: ADR-132 D10.17 (2026-10-12) — D6's no-auth no longer holds for governor acts: they need
the governor on CORE's Unix socket.  
Enforced by: src/api/cli/census_client.py, src/api/cli/daemon_client.py, src/api/cli/sync_client.py
  (+7 more src/ files)

## ADR-059 — Severity Vocabulary Governance

2026-05-19 · was `ADR-059-severity-vocabulary-governance.md`  
"dangerous" is retired from proposal-level risk (proposal_risk: safe | moderate | high); action
impact_level keeps safe | moderate | dangerous (Note 2026-10-10). RiskAssessment.overall_risk MUST
The audit_severity enum in enums.json is replaced: These are three distinct domains serving distinct
consumers  
Amended: Note 2026-10-10 (proposal 0011).  
Enforced by: governance.vocabulary_registers.operational_fields_must_be_lowercase

## ADR-060 — Governance Input Staleness Closure

2026-05-19 · was `ADR-060-governance-input-staleness-closure.md`  
D1 — Extend reload_governance() wiring to all three audit entry points; D2 — Amend CORE-
IntentRepository.md §4a.  
Enforced by: not enforced

## ADR-061 — Composition-Root Sanctuary for api/main.py Lifespan Import

2026-05-19 · was `ADR-061-composition-root-sanctuary-api-main.md`  
D1 — Codify the composition-root sanctuary as the permanent answer; D2 — Scope check for the
sanctuary entry; D3 — Revisit triggers.  
Enforced by: not enforced

## ADR-062 — proposal_lifecycle_actions.py body→will closure

2026-05-19 · was `ADR-062-proposal-lifecycle-actions-body-will-closure.md`  
Two viable options for the eventual refactor: Option A — Move ProposalStatus to a shared lifecycle
vocabulary module.  
Enforced by: src/shared/lifecycles/__init__.py, src/shared/lifecycles/proposal.py

## ADR-063 — bootstrap.py will.tools body→will closure

2026-05-19 · was `ADR-063-bootstrap-will-tools-body-will-closure.md`  
Two viable options for the eventual refactor: Option A — Re-home the three tools to
src/shared/cognitive_tools/; or equivalent.  
Enforced by: src/shared/tools/__init__.py, src/will/tools/policy_vectorizer.py

## ADR-064 — fix_actions.py capability_tagging body→will closure

2026-05-19 · was `ADR-064-fix-actions-capability-tagging-body-will-closure.md`  
Option A — Body-layer dispatch facade with injected callable.  
Enforced by: src/body/atomic/fix/capability_tagging.py, src/body/infrastructure/lifespan.py,
  src/body/services/capability_tagging_dispatch.py (+2 more src/ files)

## ADR-065 — Documentation layer separation: .specs/ vs docs/

2026-05-20 · was `ADR-065-documentation-layer-separation.md`  
D1 — Two layers, two audiences, two authorities; D2 — Authority and derivation; D3 — Document
placement rules; D4 — Specific placement decisions; D5 — GitHub Feature issues link to .specs/, not
docs/.  
Enforced by: not enforced

## ADR-066 — Unmapped-Rules Invariant — Every Active Rule Must Have an auto_remediation.yaml Entry

2026-05-21 · was `ADR-066-unmapped-rules-invariant.md`  
Every rule that is active in the audit rule registry and capable of producing findings MUST have a
corresponding entry in .intent/enforcement/remediation/auto_remediation.yaml.  
Enforced by: ai.prompt.output_validation_required, governance.namespace.classification_complete,
  governance.quarantine.namespace_has_drainer,
  governance.remediation.active_routing_claimed_by_action, governance.remediation.all_rules_mapped,
  governance.vocabulary_registers.operational_fields_must_be_lowercase

## ADR-067 — Constitutional Coherence Checker: Storage, CLI, LLM Invocation, and Scheduling

2026-05-21 · was `ADR-067-constitutional-coherence-checker.md`  
D1 — Storage Schema; D2 — CLI Surface; D3 — LLM Invocation Model (superseded by ADR-073's
check-class taxonomy); D4 — Scheduling and Daemon Integration; D5 — Governance Dashboard Signal; D6
— Cleanup Verbs (added 2026-05-31).  
Amended by: ADR-073 (D3). Governor decision 2026-10-10: a dismissed candidate is not re-raised
unless one of its documents changed since.  
Enforced by: architecture.namespace.no_direct_protected_access

## ADR-068 — Principal Role Taxonomy

2026-05-22 · was `ADR-068-principal-role-taxonomy.md`  
D1 — Three-layer separation is constitutional; roles are flat; D2 — RBAC: a closed list of ten
permissions held by six roles (Governor, Producer, Operator, Custodian, Deployer, Executor), never
by an identity; identities: core-darek and GitHub DariuszNewecki are the Governor, core-claude and
core-claude-bot Producers, core the Operator, core-law the Custodian, core-runner the Deployer,
core-build and core-sandbox Executors; D3 — no identity holds both propose.change and
approve.change; only the Operator reads secrets; write.law only after approve.law; D4 — Three
operation modes (solo, solo-separated, platform); this deployment is solo-separated; D5 —
proposal_approval_authority: risk_classification.safe_auto_approval | principal.governor; D6 —
Host administration (darek, root) is not a CORE role, performs no governance act and is outside
CORE's trust boundary; any account, group, sudo rule or GitHub collaborator not in the register is
a blocking finding.  
Amended: amendment 2026-10-11 (A1–A3, A6.1; D4 superseded); governor redesign 2026-10-12, 2492cb8c
(two roles); amendment 2026-10-15, the governor's final RBAC proposal (D2, D3, D6; core-darek
replaces darek as the governor's account and needs no sudo; supersedes A4's account table and
D10.9's "never an account a model session runs as"). Source:
.intent/taxonomies/principal_roles.yaml 3.0.0.  
Enforced by: src/body/services/proposal_submission_service.py,
  src/mind/logic/engines/artifact_gate.py, src/shared/infrastructure/intent/cognitive_roles.py (+5
  more src/ files)

## ADR-069 — Claim Lifecycle: Lease Semantics

2026-05-23 · was `ADR-069-claim-lifecycle-lease-semantics.md`  
D1 — Claim becomes a time-bounded lease; D2 — Schema: lease_expires_at added; claimed_at retained
for forensic; D3 — Lease length is declared per worker, required; D4 — Renewal API and abandonment
contract; D5 — Terminal transitions release the lease …  
Enforced by: src/shared/workers/base.py, src/shared/workers/loop_hold_telemetry.py,
  src/will/workers/violation_executor.py

## ADR-070 — Source–Projection Coherence as Bounded Drift

2026-05-24 · was `ADR-070-source-projection-coherence.md`  
D1 — Representation coherence is constitutional, expressed as bounded drift; D2 — Projection
inventory: declared in .intent/; D3 — Each pair declares its drift bound; D4 — Coherence sensors
emit findings, not log warnings; D5 — Meta-rule: every declared projection pair must have an …  
Enforced by: atomic_actions.impact_level_must_be_governed,
  governance.namespace.classification_complete

## ADR-071 — Action Diff Coherence Enforcement

2026-05-25 · was `ADR-071-action-diff-coherence.md`  
D1 — Action diff coherence is a constitutional requirement; D2 — Two-phase enforcement: operational
protocol now, worktree sandbox later.  
Amended by: ADR-097 step 6 (Note 2026-06-08) — D2.2's write_validated_bytes carveout is retired;
propagation uses FileHandler.write.  
Enforced by: governance.logic_mutation.governed, governance.mutation_surface.filehandler_required

## ADR-072 — Quarantine-Drainer Invariant — Every awaiting_reaudit Subject Namespace Must Have a Registered Drainer

2026-05-25 · was `ADR-072-quarantine-drainer-invariant.md`  
Every subject namespace that can place findings into awaiting_reaudit MUST have a registered drainer
worker in .intent/enforcement/quarantine/drainer_registry.yaml.  
Enforced by: governance.quarantine.namespace_has_drainer

## ADR-073 — Constitutional Coherence Checker: Scanner Redesign

2026-05-26 · was `ADR-073-ccc-scanner-redesign.md`  
D1 — Suppression of structurally invalid check classes; D2 — Retention: scoped R1; D3 — Check-class
taxonomy; D4 — Governance-embedding sync worker; D5 — Tiered cosine policy for §6.1 contradiction;
D6 — Structural checks: ROW2_GROUNDING, ROW3_CITATION, ROW4_NAMING …  
Amended by: ADR-074 D13 — D7 condition 4: failure_modes is a mapping, not a list.  
Enforced by: src/body/services/governance_claims_service.py,
  src/cli/resources/coherence/__init__.py, src/cli/resources/coherence/check.py (+18 more src/
  files)

## ADR-074 — INTERPRET Phase: Contradiction and Ambiguity as Orthogonal Failure Modes

2026-05-27 · was `ADR-074-interpret-failure-modes.md`  
D1 — Failure-class taxonomy for INTERPRET; D2 — Schema migration: failure_mode: (scalar) →
failure_modes: (map); D3 — Canonical failure_mode enum in .intent/META/enums.json; D4 — Closed-enum
subset for phase YAMLs; D5 — Failure-class vocabulary discipline; D6 — Phase YAML schema …  
Enforced by: src/mind/coherence/checks/specgap.py, src/will/orchestration/workflow_orchestrator.py

## ADR-075 — Framework / Project Namespace Split

2026-05-28 · was `ADR-075-framework-project-namespace-split.md`  
D1 — The framework/project namespace model is constitutional; D2 — Namespace is declared in an
external manifest, not per-file; D3 — The key is governance_namespace, to avoid collision; D4 — Two
artifacts realize the model; D5 — Classification authority is per-artifact …  
Enforced by: governance.namespace.classification_complete

## ADR-076 — Context-Level Dispatch as a Per-Check-Type Engine Property

2026-05-29 · was `ADR-076-per-check-type-context-level-dispatch.md`  
D1 — Context-level is a per-check-type property owned by the engine; D2 — The extractor consults the
engine, not a frozenset; D3 — artifact_gate becomes explicitly mixed-mode; D4 — Effective mode is
surfaced in audit/inspect output; D5 — The audit walker admits the file set per-file rules declare …  
Amended: Note 2026-10-10 — D6 excludes passive engines (passive_gate and its aliases).  
Enforced by: cli.async_execution, cli.discovery_strict

## ADR-077 — Config-driven protected-namespace access with an introspective filesystem-operation taxonomy

2026-05-30 · was `ADR-077-protected-namespace-access.md`  
1. The access policy becomes config-driven; 2. The filesystem-operation vocabulary becomes a
governed taxonomy; 3. An introspective completeness check guards the taxonomy; 4. Guarantee boundary
(stated, not overclaimed); 5. Determinism; 6. Enforcement rollout (two dials on one policy).  
Amended by: ADR-080 D2/D4 — decision 2's op-class enum is fs_audit_op_class; its unification with
fs_operation_class is retired.  
Enforced by: architecture.namespace.no_direct_protected_access,
  governance.fs_operations.completeness, governance.fs_operations.no_direct_yaml_import

## ADR-078 — Operational-Capability Taxonomy Schema

2026-05-30 · was `ADR-078-operational-capability-taxonomy-schema.md`  
D1 — Location; D2 — Top-level document shape; D3 — Capability entry shape; D4 — fs_profile shape; D5
— Closed vocabularies promoted to .intent/META/enums.json; D6 — Capability-ID grammar (regex-
enforced); D7 — Naming consolidation in the same change-set …  
Amended by: ADR-080 D5 (D5's first-materialization clause scoped to fs_operation_class). Note
2026-05-30: D6 governs renames; D7's table is not exhaustive.  
Enforced by: governance.taxonomy.operational_capabilities_decorator_backing

## ADR-079 — Chokepoint Implementation for Capability-Scoped Filesystem Authority

2026-05-30 · was `ADR-079-chokepoint-implementation-for-capability-scoped-filesystem-authority.md`  
D1 — Location: the chokepoint is FileHandler.IntentGuard, extended in place; D2 — Capability
identity propagation: reuse _executor_token; D3 — Operation-class derivation: FileHandler-method →
op-class mapping, internal; D4 — Mode-flag consumer contract (provenance deferred to #492) …  
Amended by: ADR-097 step 6 (Note 2026-06-08) — D8 superseded: write_validated_bytes is gone; sandbox
propagation goes through FileHandler.write.  
Enforced by: architecture.blackboard.indeterminate_requires_human_mechanism,
  governance.taxonomy.operational_capabilities_decorator_backing,
  governance.taxonomy.sensor_supported_by_declaration

## ADR-080 — Filesystem-operation-class vocabulary split

2026-05-31 · was `ADR-080-fs-op-class-vocabulary-split.md`  
D1 — Two enums, not one; D2 — The unification clause is retired; D3 — fs_audit_op_class enum entry;
D4 — ADR-077 §2 stands as written; its enum reference resolves to fs_audit_op_class; D5 — ADR-078
D5's first-materialization clause is scoped down; D6 — Sequencing of dependent work.  
Enforced by: src/shared/infrastructure/intent/filesystem_operations.py

## ADR-081 — Per-worker process-isolation classification

2026-06-01 · was `ADR-081-per-worker-process-isolation-classification.md`  
D1 — requires_dedicated_process field on the worker declaration; D2 — Classification criterion; D3 —
Runtime invariant; D4 — Daemon split shape (systemd unit topology); D5 — Daemon discovery contract;
D6 — core-admin daemon up/down/restart/status wrappers; D7 — Drift detector audit rule …  
Amended: Note 2026-06-09 — D2(2)'s embedder exclusion covers only the network-await embed call;
where they disagree, D2(1)'s 5 s gate governs.  
Enforced by: src/cli/commands/daemon.py, src/mind/governance/filtered_audit.py,
  src/mind/logic/engines/runtime_gate.py (+4 more src/ files)

## ADR-082 — Writer-as-sensor retention policy

2026-06-01 · was `ADR-082-writer-as-sensor-retention-policy.md`  
D1 — Writer-as-sensor blackboard entries MUST declare retention; D2 — Mechanism 1: terminal
telemetry hard-DELETE; D3 — Mechanism 2: DELEGATE OPEN finding status transition; D4 — Sweep host:
BlackboardShopManager; D5 — Row cap rail: sweep_batch_max; D6 — Empty allowlist is fail-closed …  
Enforced by: src/body/services/blackboard_service/blackboard_service.py,
  src/mind/logic/engines/runtime_gate.py, src/shared/infrastructure/intent/operational_config.py (+1
  more src/ files)

## ADR-083 — Stamping Tier 1/2 commercial add-ons as F-44–F-47

2026-06-02 · was `ADR-083-commercial-add-on-stamping-f44-f47.md`  
D1 — Stamp F-44, F-45, F-46, F-47 with Sourcing: commercial, Status: roadmap; D2 — F-44 definition:
Premium rule libraries (industry packs); D3 — F-45 definition: Hosted findings dashboard; D4 — F-46
definition: Cloud audit export (signed); D5 — F-47 definition: Managed Qdrant …  
Amended by: ADR-093 D3 — F-44, F-45, F-46 are now E-44, E-45, E-46; F-47 stays F-47.  
Enforced by: not enforced

## ADR-084 — Commercial-surface taxonomy, add-on architecture, and the open-core honesty contract

2026-06-02 · was `ADR-084-commercial-surface-taxonomy-and-open-core-honesty.md`  
D1 — Three commercial-surface shapes, exhaustive; D2 — Plugin shape: symmetric interfaces, no
private hooks; D3 — Sidecar shape: F-40 OEM API as the only access path; D4 — Runtime fork shape:
open library dependency, no closed branches …  
Amended by: ADR-093 D3 — F-20, F-34, F-37, F-44, F-45, F-46 are now E-20, E-34, E-37, E-44, E-45,
E-46.  
Enforced by: src/api/__init__.py, src/body/__init__.py, src/cli/__init__.py (+4 more src/ files)

## ADR-086 — Installation Architecture

2026-06-02 · was `ADR-086-installation-architecture.md`  
D1 — Three distribution channels, each with a declared role; D2 — First-run wizard, single declared
command; D3 — Pre-flight checks, declared and machine-checkable; D4 — Single canonical Postgres
role; ownership leakage prohibited; D5 — Health check / readiness probe …  
Enforced by: not enforced

## ADR-087 — OEM API versioning and stability policy

2026-06-02 · was `ADR-087-oem-api-versioning-and-stability-policy.md`  
D1 — Wire version semantics: /v1/ is the major-version boundary; D2 — What constitutes a breaking
change; D3 — Field-addition + field-removal rules; D4 — Deprecation lane; D5 — Deprecation window:
minimum six months; D6 — /v2/ migration policy; D7 — Grandfathered baseline …  
Amended: 2026-10-03 (governor rulings) — D9: the authoritative OpenAPI contract lives in CORE; D4: a
deprecated route sends Deprecation: @<unix-seconds> (RFC 9745) and Sunset: <HTTP-date> (RFC 8594).  
Enforced by: src/api/__init__.py, src/api/main.py, src/api/openapi_document.py (+9 more src/ files)

## ADR-088 — PyPI version alignment with the narrative release track

2026-06-02 · was `ADR-088-pypi-version-alignment.md`  
D1 — core-runtime PyPI version aligns with the narrative release track; D2 — Honest acknowledgment
of the SemVer concession; D3 — v0.1.x tags are bootstrap artifacts, not a parallel track; D4 —
Coordination with existing ADRs; D5 — Forward versioning rules (inherited by F-48.5 #541) …  
Enforced by: not enforced

## ADR-089 — F-27 exit criterion: capability proof replaces usage window

2026-06-03 · was `ADR-089-f27-exit-criterion-capability-not-usage.md`  
D1 — F-27 exit criterion is amended to a capability demonstration; D2 — F-27 promotion does not
require a measurement window; D3 — Longitudinal local-LLM reliability is not gated by F-27; D4 —
Embedding routing is out of F-27's scope; D5 — ADR-024 D1 is the qualification …  
Amended: ADR-085, whose 5+3 exit gate this criterion served, was retired 2026-10-02; the criterion
is a record, not a gate.  
Enforced by: not enforced

## ADR-090 — Cognitive Roles DB Structural Enforcement / F-41 artifact type registry as the unified governance contract

Two accepted ADRs share this ID.

(a) Cognitive Roles DB Structural Enforcement — 2026-07-05 · was `ADR-090-cognitive-roles-db-structural-enforcement.md`  
D1 — Reconciliation trigger: migration-driven; D2 — CHECK shape: enumerated ARRAY (ADR-068 pattern);
D3 — Unknown roles: block reconciliation; D4 — tasks.assigned_role FK: tighten to match peers; D5 —
Column scope: required_capabilities in YAML; drop operating_mode + max_concurrent_tasks …  
Enforced by: architecture.artifact_discovery_through_registry

(b) F-41 artifact type registry as the unified governance contract — 2026-06-04 · was `ADR-090-f41-artifact-type-registry-as-unified-governance-contract.md`  
D1 — Artifact type declarations live at .intent/artifact_types/<type_id>.yaml; D2 — Required
declaration fields; D3 — Three reference declarations ship in this ADR; D4 — Migrate existing
pipelines to consult the registry (Option A); D5 — Forward contract for F-42 and F-43 …  
Enforced by: architecture.artifact_discovery_through_registry

## ADR-091 — F-42 pluggable sensor model as the second published contract

2026-06-05 · was `ADR-091-f42-pluggable-sensor-model-as-second-published-contract.md`  
D1 — Sensor declaration extension on META/worker.schema.json (list-form, framework-derived subject);
D2 — Canonical subject format, framework-computed (closed vocabulary); D3 — Twelve true-sensor
declarations updated under canonical format …  
Amended: Revision B (accepted 2026-06-05) — every finding carries resolution_mechanism (reaudit |
self_resolve | human); a finding enters reaudit only if its mechanism is reaudit. D2 Amendment
(accepted 2026-06-12, #628) — a transition that changes who may close a finding rewrites the field;
indeterminate requires human.  
Enforced by: architecture.blackboard.indeterminate_requires_human_mechanism,
  architecture.blackboard.reaudit_requires_reaudit_mechanism,
  architecture.blackboard.worker_only_inserts,
  governance.remediation.active_routing_claimed_by_action,
  governance.taxonomy.operational_capabilities_decorator_backing,
  governance.taxonomy.self_resolve_resolver_owned,
  governance.taxonomy.sensor_supported_by_declaration

## ADR-092 — F-43 exit criterion: contract-readiness replaces invented-proof

2026-06-06 · was `ADR-092-f43-exit-criterion-contract-readiness.md`  
D1 — F-43 exit criterion is amended to a contract-readiness demonstration; D2 — The
action_supported_by_declaration coherence rule was parked until a non-Python action shipped; ADR-121
fired the trigger and the rule is active (reporting); D3 — F-41 and F-42's existing non-code
instantiations satisfy the trio-level criterion text …  
Amended by: ADR-120 D4 and ADR-121 (D2). ADR-085, whose 5+3 exit gate this criterion served, was
retired 2026-10-02; the criterion is a record, not a gate.  
Enforced by: governance.taxonomy.action_supported_by_declaration

## ADR-093 — Feature / Extension class split + URS-line governance discipline

2026-06-06 · was `ADR-093-feature-extension-class-split-and-urs-line-discipline.md`  
D1 — Two top-level artifact classes in CORE-Features.md: F-NN (Features) and E-NN (Extensions); D2 —
Commercial-engine-shape and not-software entries stay F-NN; D3 — Six entries migrate to E-NN: F-20,
F-34, F-37, F-44, F-45, F-46; D4 — URS-line governance shape, differentiated by class …  
Enforced by: not enforced

## ADR-094 — URS Satisfaction Sensor (implementing ADR)

2026-06-06 · was `ADR-094-urs-satisfaction-sensor-implementation.md`  
D1 — Register a new urs artifact_type in the F-41 registry; D2 — Predicates live in Python, not
declared in .intent/ YAML; D3 — Run cadence: per-cycle on the existing daemon; D4 — CLI surface:
core-admin specs verify [URS_ID]; D5 — Dashboard: route through the existing Convergence …  
Note 2026-10-10 (governor decision): accepted, not built — no urs artifact type or sensor exists;
nothing verifies URS satisfaction.  
Enforced by: not enforced

## ADR-096 — Shadow KG sensation primitive; static-vs-runtime engine partition for pre-commit consequence sensing

2026-06-07 · was `ADR-096-shadow-kg-sensation-primitive.md`  
D1 — Static engines and runtime engines are categorically different question-classes; D2 — Shadow
audits skip the runtime-class engine cohort as a principled partition; D3 — Shadow materialization
is per-file-symlinked src/ + directory-symlinked siblings, with a write-through guard …  
Enforced by: not enforced

## ADR-097 — Target-class dispatch for the single filesystem write channel

2026-06-08 · was `ADR-097-target-class-dispatch-for-the-single-filesystem-write-channel.md`  
D1 — A single filesystem write channel; the channel dispatches on target class; D2 — Target-class
taxonomy; D3 — Per-class behavior matrix; D4 — Public surface: one entry point, target-aware; D5 —
Migration: shadow_materializer, sandbox, FileService consumers …  
Enforced by: src/body/atomic/sandbox_lifecycle.py, src/body/governance/intent_guard.py,
  src/body/infrastructure/storage/file_handler.py (+5 more src/ files)

## ADR-098 — Aggregate quality-gate finding shape: per-file emission with iceberg-tail rendering

2026-06-09 · was `ADR-098-aggregate-quality-gate-finding-shape.md`  
D1 — Aggregate quality gates emit per-affected-file findings, not per-tool findings; D2 — Each
finding carries structured occurrence data in context; D3 — Renderer displays an iceberg-tail
indicator for findings with context.issue_count > 1 …  
Enforced by: src/cli/commands/check/formatters.py, src/cli/renderers/audit_overview.py,
  src/mind/logic/engines/_knowledge_gate_duplication.py (+12 more src/ files)

## ADR-100 — Export-evidence-class enum: pin the E-46 / E-37 boundary as machine-readable vocabulary

2026-06-09 · was `ADR-100-export-evidence-class-enum.md`  
D1 — The enum is named export_evidence_class; D2 — The canonical location is
.intent/META/enums.json; D3 — The boundary the enum enforces is the F-46 / F-37 separation, not the
E-NN / F-NN class line …  
Enforced by: not enforced

## ADR-101 — Commit authorship integrity: every commit's diff contains only work its author produced

2026-06-09 · was `ADR-101-commit-authorship-integrity.md`  
D1 — The principle: commit authorship integrity (constitutional); D2 — Commit set is derived from
the production set, not the permission set; D3 — Rollback target is the action's touched set, not
the permission scope; D4 — ADR-021 D5 pre-claim check and autonomy_dirty_tree.yaml modes are …  
Amended: Note 2026-10-10 — rollback never uses scope.files (D2's clause saying it does is void);
D4's interim posture ended (autonomy_dirty_tree.yaml removed); D6 is delivered by ADR-129.  
Enforced by: src/api/v1/coverage_routes.py, src/body/atomic/assisted_actions.py,
  src/body/atomic/executor.py (+13 more src/ files)

## ADR-102 — Finding.json retirement: class-shape was the wrong enforcement site for the constitutional Finding nucleus

2026-06-09 · was `ADR-102-finding-contract-retirement.md`  
D1 — Finding.json is retired; D2 — ADR-056 D3's nucleus commitment narrows in scope; D3 —
CheckResult and AuditFinding continue under their existing per-class contracts; D4 — ADR-099 is
retired except for its D3 (the permitted_extensions META schema clause) and step 1's implementation.  
Enforced by: data.contracts.asymmetric_contract_findings, data.contracts.layer_scope_coherence,
  data.contracts.persistence_reach_coherence, data.contracts.rule_binding_iceberg

## ADR-103 — Worker schedule.max_interval is a cycle cap, not a sleep cap

2026-06-09 · was `ADR-103-worker-max-interval-is-cycle-cap.md`  
D1 — schedule.max_interval is the cycle cap (constitutional); D2 — The 1.1 multiplier and glide_off
are both jitter tolerance, not headroom; D3 — No mechanism change; D4 — Tactical drift response
stays tactical; D5 — What this ADR explicitly does NOT decide.  
Enforced by: src/cli/commands/daemon.py, src/mind/logic/engines/runtime_gate.py,
  src/shared/workers/schedule.py

## ADR-104 — Orphaned-claim reaper (claim lifecycle is process-scoped, not loop-scoped)

2026-06-13 · was `ADR-104-orphaned-claim-reaper.md`  
D1 — Orphaned claims are reaped continuously by BlackboardShopManager (constitutional); D2 — Release
semantics reuse the existing reset; D3 — Reclaim rail: abandon after N orphan-releases; D4 — The
reaper is not a silent instrument; D5 — Fail-safe: never reap on an unavailable liveness source …  
Amended: Revision B (2026-06-13) adds D8, a mid-run liveness lease; addendum D9 (2026-06-14) caps
the remediation-failure loop; addendum D10 (2026-09-20) sends a capped no-op loop to the governor
inbox; ruling 2026-10-03 — an exhausted remediation cap delegates the finding to the governor
(indeterminate + human) instead of abandoning it, and elapsed time never re-arms it.  
Enforced by: src/body/services/blackboard_service/blackboard_proposal_service.py,
  src/body/services/blackboard_service/blackboard_query_service.py,
  src/body/services/blackboard_service/blackboard_service.py (+19 more src/ files)

## ADR-105 — Document model for .specs/: typed headers, forked vocabulary

2026-06-13 · was `ADR-105-specs-document-model.md`  
D1 — .specs/ documents carry a typed, validated header (constitutional); D2 — The vocabulary is
.specs/-specific, not inherited; D3 — The tier axis is doctrine_tier, a distinct enum — not a reused
authority (Option B); D4 — Per-class artifact types replace the spec_markdown blob …  
Enforced by: src/body/analyzers/target_reconnaissance_analyzer.py,
  src/cli/resources/constitution/validate.py, src/mind/coherence/checks/path_ref.py (+3 more src/
  files)

## ADR-106 — Flow proposals execute in a hermetic worktree (sandboxing is per-execution, not per-action)

2026-06-13 · was `ADR-106-sandbox-flow-proposals.md`  
D1 — Flow proposals execute in one hermetic worktree (ratify); D2 — Production set + commit/rollback
derive from the flow sandbox (ratify); D3 — Failure discards the sandbox (ratify); D4 — Steps must
not nested-sandbox (ratify) …  
Enforced by: src/body/atomic/fix/format_code.py, src/body/atomic/fix/imports.py,
  src/body/atomic/sandbox_lifecycle.py (+6 more src/ files)

## ADR-107 — A flow's commit set is its steps' declared production, not the sandbox worktree diff

2026-06-13 · was `ADR-107-flow-commit-set-is-declared-production.md`  
D1 — A flow's production set is the union of its steps' declared outputs (ratify); D2 — build.tests
declares its output (ratify); D3 — propagate_changes gains an allowlist; the flow branch supplies it
(ratify); D4 — Fallback keeps un-migrated flows on current behavior (ratify).  
Enforced by: src/body/atomic/build_test_for_symbol_action.py, src/body/atomic/build_tests_action.py,
  src/body/atomic/sandbox_lifecycle.py (+3 more src/ files)

## ADR-108 — External adoption ships a minimal authored starter-intent, not a copy of CORE's .intent/

2026-06-14 · was `ADR-108-external-adoption-minimal-starter-intent.md`  
D1 — Adopters ship a minimal *authored* starter, not a copy; the four starter rules are illustrative
and Scout's fallback menu, not onboard's default output; D2 — Source of truth lives in CORE; the
demo is a one-way mirror; D3 — The core-runtime wheel bundles the machinery floor only, never rules;
the floor is delivered into the project's .intent/, not supplied by fallback; D4 — The delivered
starter actually enforces: one law root, and the gate fails closed; zero declared rules is total
collapse (ERROR).  
Amended: 2026-06-20 (ADR-119; A1, A2, and ADR-119 D9); clarification 2026-10-02 (D4); 2026-10-05 (D3
closed, #939); ADR-149 D3 (one law root means corpus co-location).  
Enforced by: src/cli/logic/byor.py, src/cli/logic/project_scaffold.py,
  src/cli/resources/code/audit.py (+10 more src/ files)

## ADR-109 — Assisted Remediation Lane

2026-06-15 · was `ADR-109-assisted-remediation-lane.md`  
Establish the Assisted Remediation Lane: a governed workflow by which a delegated finding is worked
by an external interactive agent (Claude Code) with full multi-file context, and submitted back as a
single human-gated multi-file proposal that the governor reviews and CORE executes through the …  
Enforced by: governance.dangerous_execution_primitives

## ADR-110 — Exposure is a Trust Tier on the API; Write-Safety Binds to the Operation

2026-06-16 · was `ADR-110-exposure-trust-boundary.md`  
D1 — The API/CLI relationship has an exposure (trust) axis, distinct from layer and behavior; D2 —
Exposure is a tier on the *complete* API, not a CLI-vs-API split; D3 — Write-safety binds to the
operation, never to the transport or the trust tier …  
Enforced by: src/cli/resources/admin/accessibility.py, src/cli/resources/dev/campaign_review.py,
  src/shared/cli/command_meta.py (+2 more src/ files)

## ADR-111 — project onboard delivers the authored starter-intent (BYOR code×Induce cell)

2026-06-17 · was `ADR-111-onboard-delivers-authored-starter.md`  
D1 — project onboard <target> *delivers* the machinery floor only, from the bundled
shared._machinery_floor; rules come from Scout or the author; it does not generate one; D2 — Code-
analysis generation is removed from the authoritative path; D3 — Safety and command semantics; D4 —
Source of truth and the packaging dependency, stated honestly; D5 — Namespace and ownership …  
Amended by: ADR-119 (amendment 2026-06-20, A1–A2; D9) — D4's single-source claim and wheel gate are
superseded; floor-only onboard is completed by project scout or authored rules.  
Enforced by: governance.mutation_surface.filehandler_required

## ADR-113 — Per-finding evidence class (proven / judged / attested)

2026-06-18 · was `ADR-113-per-finding-evidence-class.md`  
D1 — Every finding carries a first-class evidence_class; D2 — evidence_class is DERIVED from the
producing engine, never hand-set; D3 — The honesty invariant: never report a weaker method as a
stronger one; D4 — attested is a first-class outcome, not a failure or an omission …  
Enforced by: src/body/services/grc/__init__.py, src/body/services/grc/gap_analysis_service.py,
  src/cli/commands/check/formatters.py (+25 more src/ files)

## ADR-114 — Retire purity.no_todo_placeholders and disable its remediation

2026-06-18 · was `ADR-114-retire-no-todo-placeholders.md`  
D1 — Retire purity.no_todo_placeholders; D2 — Disable the corrupting remediation; D3 — Nothing
mandatory replaces it; a visibility lens stays available as a future option; D4 — The corruption
heals; the GRC catalog needs no special handling …  
Enforced by: purity.docstrings.required, purity.no_metadata_decorators

## ADR-115 — CI runs against ephemeral, hermetic infrastructure seeded from canonical schema

2026-06-19 · was `ADR-115-ci-ephemeral-hermetic-infrastructure.md`  
D1 — CI provisions ephemeral PostgreSQL and Qdrant per run, seeded from canonical schema; D2 — The
DB-reachability skip-guard is reclassified as a local-dev convenience, not CI behavior; D3 — Lint
runs statically in CI, not through the API server; D4 — Tests are tiered with real markers …  
Enforced by: not enforced

## ADR-116 — GRC catalog residency: law-as-data, tiered by license, consumed not bundled

2026-06-19 · was `ADR-116-grc-catalog-residency-and-licensing-tiers.md`  
D1 — The GRC catalog is law-as-data; it never lives in src/ and is never CORE's .intent/; D2 — One
unified corpus root, tiered by IP/license; D3 — licensed/ is population-method-agnostic; absent tier
is honest, not an error …  
Enforced by: src/body/services/grc/catalog_resolver.py,
  src/body/services/grc/gap_analysis_service.py, src/mind/logic/engines/grc_judge.py (+3 more src/
  files)

## ADR-117 — var/tmp is ephemeral scratch with no janitor: a bounded, age-gated reaper worker

2026-06-19 · was `ADR-117-var-tmp-janitor-worker.md`  
D1 — A scheduled reaper worker. Add var_tmp_janitor (.intent/workers/), a deterministic, no-LLM,
governance-class worker (the observer_worker system-state reporter precedent — *not* sensing, which
the schema reserves for audit-rule sensors). …  
Amended: 2026-10-06 (governor ruling) — Phase 2: the janitor deletes, through Body's FileService,
not through a dangerous tmp.reap action (D4 superseded); it never follows a symlink.  
Enforced by: src/shared/infrastructure/intent/operational_config.py,
  src/will/workers/canary_janitor.py, src/will/workers/var_tmp_janitor.py

## ADR-118 — GRC verdict unit is requirement-over-corpus, gated by domain applicability

2026-06-20 · was `ADR-118-grc-verdict-unit-requirement-over-corpus.md`  
D1 — The verdict unit is the requirement evaluated over the corpus, not per document. The unit of a
GRC verdict is one RequirementVerdict per requirement, derived from the whole in-scope corpus. Per-
document signals are inputs to it, never the reported surface.  
Enforced by: src/body/services/grc/__init__.py, src/body/services/grc/gap_analysis_service.py,
  src/cli/resources/grc/gap_analysis.py (+5 more src/ files)

## ADR-119 — Scout: BYOR Path 1 induces a fitted constitution from source code

2026-06-20 · was `ADR-119-scout-byor-path-1-induction.md`  
D1 — BYOR path codenames; D2 — Scout is Path 1: definition and two-phase delivery; D3 — Induction
mechanism: detect → suggest → confirm; D4 — Reference grammar constraint: CORE's .intent/ is
vocabulary, not template; D5 — Mandatory human ratification invariant; D6 — Command model …  
Amended: 2026-06-22, 15a3dd67 (D7 fallback menu: symbol_ids removed, no_bare_except blocking,
no_secrets added); 2026-10-02, #892 (project new may run a bootstrap stage: machinery floor and a
neutral skeleton, no rules, not auditable).  
Enforced by: governance.logic_mutation.governed, governance.mutation_surface.filehandler_required

## ADR-120 — T5a: Repository adapter interface — the concrete F-41/F-42/F-43 binding

2026-06-21 · was `ADR-120-t5a-repository-adapter-interface.md`  
D1 — F-43 declaration site: extend action_risk.yaml per-action entry; D2 — Repository adapter
contract: three-part declaration; D3 — supported_sensors becomes load-bearing at
IntentRepository.initialize() …  
Amended: Note 2026-10-10 — D4's trigger fired: ADR-121 authored action_supported_by_declaration and
supported_actions is populated.  
Enforced by: src/body/atomic/executor.py, src/body/atomic/registry.py,
  src/shared/infrastructure/intent/action_risk.py (+2 more src/ files)

## ADR-121 — T5b: Document corpus Repository type — domain-agnostic governed document corpus

2026-06-21 · was `ADR-121-t5b-grc-document-repository-type.md`  
D1 — document_corpus artifact type (F-41 declaration); D2 — DocumentCorpusSensor Worker design (F-42
binding); D3 — Project-authored corpus configuration convention; D4 — First non-Python atomic
action: document.gap_analysis (F-43 binding) …  
Enforced by: governance.taxonomy.action_supported_by_declaration

## ADR-122 — T5d: Internal corpus ingestion pipeline — Qdrant wiring, chunking, CLI surface, and judge augmentation

2026-06-21 · was `ADR-122-t5d-internal-corpus-ingestion-pipeline.md`  
D1 — Per-framework Qdrant collection, named grc-internal-{framework_id}; D2 — Structure-aware
chunking with ChunkingConfig fallback; D3 — Ingestion surface: core-admin grc ingest <framework_id>;
D4 — grc_judge augmentation: top-3 passages injected as source context …  
Enforced by: src/body/services/grc/gap_analysis_service.py,
  src/body/services/grc/internal_corpus.py, src/cli/resources/grc/ingest.py (+2 more src/ files)

## ADR-123 — T4: project onboard --stage airlock flag and project onboard promote

2026-06-21 · was `ADR-123-t4-onboard-stage-flag.md`  
D1 — --stage flag: redirect write to work/staged/<basename>/; D2 — project onboard promote <path>
completes the airlock; D3 — Stage directory lifecycle (no GC); D4 — No change to what is delivered;
no new delivery surface.  
Enforced by: governance.mutation_surface.filehandler_required

## ADR-124 — CORE OSS trusted-localhost mode: no UAC in the runtime

2026-06-10 · was `ADR-124-user-access-control.md`  
CORE is an auth-free OSS runtime. It binds to 127.0.0.1:8000 and operates in trusted-localhost mode
— no authentication, no session management, no multi-tenant user access control.  
Enforced by: cli.standard_verbs

## ADR-125 — CORE OSS has no web frontend

2026-06-10 · was `ADR-125-web-frontend-architecture.md`  
CORE is a CLI-and-API runtime. It has no web frontend, no SPA serving, and no browser-facing UI in
this repository.  
Enforced by: not enforced

## ADR-126 — Migrate FileHandler to Body and close the shared/ excludes entry

2026-06-26 · was `ADR-126-file-handler-body-migration.md`  
D1 — FileHandler migrates to body/infrastructure/storage/; D2 — Stage 1: inject FileHandler into the
two Shared instantiators; D3 — Stage 2: physical move of FileHandler; D4 — Caller migration; D5 —
shared/infrastructure/context/ long-horizon note.  
Enforced by: governance.logic_mutation.governed, governance.mutation_surface.filehandler_required

## ADR-127 — Indeterminate clean-pass drain via AuditViolationSensor

2026-06-27 · was `ADR-127-indeterminate-clean-pass-drain.md`  
D1 — AuditViolationSensor drains indeterminate findings on each cycle; D2 — Implementation via
extended adjudicate_awaiting_reaudit_findings; D3 — Only violations-gone findings are closed; still-
real findings are untouched; D4 — Dedup interaction is unchanged …  
Enforced by: src/body/services/blackboard_service/blackboard_proposal_service.py,
  src/body/services/blackboard_service/blackboard_query_service.py,
  src/body/services/blackboard_service/blackboard_service.py (+2 more src/ files)

## ADR-128 — CoreContext DI typing posture (three-tier model)

2026-06-28 · was `ADR-128-corecontext-di-typing-posture.md`  
D1 — Always-wired services: mandatory positional fields; D2 — Post-construction infrastructure:
typed Optional fields, set immediately; D3 — Genuinely-degradable services: typed Optional (not Any
| None); D4 — TYPE_CHECKING exemption for shared/context.py cross-layer annotations.  
Enforced by: src/shared/context.py, src/will/autonomy/proposal_execution_pipeline.py

## ADR-130 — Constitutional artifact regeneration via governor-applied staging

2026-06-28 · was `ADR-130-constitutional-artifact-regeneration-staging.md`  
D1 — Hard invariant is unconditional and permanent; D2 — sync vocabulary --write renamed to --stage;
output to var/drafts/; D3 — Provisional exclusions removed; D4 — DEGRADED repair instruction
updated; D5 — Canonical pattern for all derived constitutional artifacts.  
Enforced by: governance.mutation_surface.filehandler_required

## ADR-131 — Governance Application Data Model

2026-06-28 · was `ADR-131-governance-application-data-model.md`  
D1 — Filesystem authority is unchanged; the application is an authoring layer; D2 — Three-state
draft lifecycle; D3 — Schema: governance_artifacts_draft table; D4 — Write-time validation fires at
draft → staged transition; D5 — Apply is a governor-role action …  
Enforced by: not enforced

## ADR-132 — Governor Authentication Boundary

2026-06-28 · was `ADR-132-governor-authentication-boundary.md`  
D1 — platform_admin is the DB-side implementation of principal.governor; D2 — require_governor is
the enforcement dependency; D3 — governor-only routers declare the dependency at router construction
time; D4 — Single-Governor Local topology: gate is live, structurally satisfied …  
Amended: addendum D9 (2026-07-17) — per-route INTENTIONALLY_UNGATED marker. Addenda D10 (2026-10-04
to 2026-10-12) — the governor is the OS account the kernel reports (SO_PEERCRED) on CORE's Unix
socket, bound in root-owned /etc/core/principals.yaml; TCP never performs a governor act; D3's JWT
clause is withdrawn; services run an installed release; repository code runs only in the sandbox;
the gate is live (D10.17, 27265f2c, 2026-10-12). D8 no longer passes everything: a dangerous write
needs a governor-approved proposal (e422df7a, 2026-10-12). Approvals stamp approved_by = governor
and keep the OS account in approved_by_original (555d35a9, 2026-10-12) The account
bound to principal.governor is core-darek, per the register in principal_roles.yaml (ADR-068
amendment 2026-10-15); D10.9's human-only account no longer holds.  
Enforced by: architecture.api.route_module_must_declare_exposure,
  architecture.api.router_exposure_must_match_dependencies,
  architecture.sandbox.tests_run_in_sandbox, governance.logic_mutation.governed,
  governance.mutation_surface.filehandler_required

## ADR-133 — Test Gap Evaluator and Symbol-Granular Test Generation

2026-06-28 · was `ADR-133-test-gap-evaluator.md`  
D1 — TestGapEvaluator is a new BaseEvaluator (AUDIT phase); D2 — Gap detection uses AST only;
heuristic is test_<name> match; D3 — New atomic action build.test_for_symbol; D4 —
TestRemediatorWorker calls TestGapEvaluator before proposal creation …  
Amended: 2026-10-03 (governor ruling) — on the no-gap path the worker returns the finding to
awaiting_reaudit, never to open.  
Enforced by: src/body/atomic/build_test_for_symbol_action.py, src/body/atomic/build_tests_action.py,
  src/body/evaluators/test_gap_evaluator.py (+6 more src/ files)

## ADR-134 — Prompt Content Governance: Traceability and Drift Review Gate

2026-06-29 · was `ADR-134-prompt-content-governance.md`  
D1 — adr_anchor field added to model.yaml manifest schema; D2 — New blocking rule:
ai.prompt.governed_prompt_must_have_anchor; D3 — New reporting rule:
ai.prompt.constitutional_grounding_section …  
Enforced by: src/body/services/blackboard_service/blackboard_query_service.py,
  src/mind/logic/engines/artifact_gate.py, src/shared/ai/prompt_model.py (+1 more src/ files)

## ADR-135 — Dual-Mode Generation: Single-Shot and Iterative Execution Primitives

2026-07-01 · was `ADR-135-dual-mode-generation-primitives.md`  
D1 — Two named generation modes are defined as CORE primitives; D2 — IterativeCoderAgent is a new
Will-tier component; D3 — AcceptanceCondition is an injectable protocol; D4 — Iteration budget is
governed in .intent/; D5 — Flow manifests declare generation_mode …  
Amended by: ADR-140 — D5's routing runs through the cognitive flow step; D6 (pytest in the
acceptance loop) is wired by ADR-140's amendment of 2026-07-13, implemented 2026-07-14, with
acceptance [IntentGuard, Pytest]; no AuditAcceptanceCondition was built.  
Enforced by: architecture.acceptance.test_gen_must_include_sandbox_gate

## ADR-136 — Substrate-Enforcement Taxonomy and Dispatch-Parity CCC Check

2026-07-02 · was `ADR-136-substrate-enforcement-taxonomy-dispatch-parity.md`  
D1 — Substrate-enforcement taxonomy; D2 — DispatchParityCheck CCC check class; D3 — Register
DispatchParityCheck in CoherenceChecker; D4 — EngineRegistry loads passive aliases from taxonomy.  
Enforced by: src/mind/coherence/checks/dispatch_parity.py, src/mind/logic/engines/registry.py

## ADR-137 — Instrument No-Data Semantics and Sanctuary Registry

2026-07-02 · was `ADR-137-instrument-no-data-semantics-sanctuary-registry.md`  
D1 — No-data guard in AuditViolationSensor; D2 — Sanctuary registry; D3 — Update SANCTUARY comments;
D4 (future) — Graduate to a named rule.  
Enforced by: src/shared/action_logger.py, src/will/workers/audit_violation_sensor.py

## ADR-138 — Prompt Governance and Authorship Integrity Enforcement Dispatch

2026-07-02 · was `ADR-138-prompt-governance-authorship-enforcement-dispatch.md`  
D1 — passive_gate is canonical for sensor/worker-driven REPORTING rules; D2 —
governance.commit_authorship_integrity maps to passive_gate; D3 —
ai.prompt.governed_change_requires_review maps to passive_gate …  
Amended: governor decision 2026-10-10 — a passive_gate mapping on a blocking rule is invalid only
for ADR-142 Class C and D; Class A and B are legitimate.  
Enforced by: not enforced

## ADR-139 — MyPy Type Safety Remediation Strategy

2026-07-02 · was `ADR-139-mypy-type-safety-remediation.md`  
D1 — Fix Cluster A immediately (stubs install, no code changes); D2 — Remediate clusters in priority
order: B → C → D → E; D3 — Each cluster delivered as a governed atomic change-set, not a bulk
rewrite; D4 — Gate promotion to blocking after total errors reach zero …  
Enforced by: not enforced

## ADR-140 — Cognitive-Write Separation: The Flow Cognitive Step Pattern

2026-07-05 · was `ADR-140-cognitive-write-separation-flow-pattern.md`  
D1 — The Cognitive-Write Separation invariant is constitutional; D2 — StepKind.COGNITIVE — new flow
step kind; D3 — CognitiveFlowDelegate protocol in shared/protocols/; D4 — FlowExecutor: cognitive
routing and inter-step threading; D5 — Will-tier cognitive implementation: …  
Amended: 2026-07-13 — pytest runs inside the generation acceptance loop (ADR-135 D6); implemented
2026-07-14.  
Enforced by: architecture.acceptance.test_gen_must_include_sandbox_gate

## ADR-141 — Assisted Lane: Subprocess Audit for Non-Graph Engine Fixes

2026-07-05 · was `ADR-141-assisted-lane-subprocess-audit.md`  
D1 — Split the engine-touching boundary by graph dependency; D2 — Engine graph-dependency declared
on the engine class; D3 — Subprocess isolation model; D4 — Subprocess IPC; D5 — Subprocess runner in
tool_runner.py sanctuary; D6 — Verdict shape changes; D7 — What this does NOT decide.  
Enforced by: src/body/atomic/assisted_actions.py, src/body/atomic/tool_runner.py,
  src/cli/resources/constitution/verify_bind.py (+3 more src/ files)

## ADR-142 — Passive Gate Enforced-By Symbol Attestation

2026-07-05 · was `ADR-142-passive-gate-enforced-by-symbol-attestation.md`  
D1 — Classify all passive_gate rules by attestation class (data only); D2 — New rule:
governance.passive_gate.enforced_by_must_resolve (blocking); D3 — Fix the stale
features.maintenance.command_sync_service reference; D4 — Guard-behavior verification deferred.  
Enforced by: governance.passive_gate.enforced_by_must_resolve

## ADR-143 — Symbols-Drift: Governed-Anchor SSOT and Existing-Pipeline Consumption

2026-07-06 · was `ADR-143-symbols-drift-anchor-ssot.md`  
D1 — Formally retire the operational_capabilities.yaml-vs-knowledge-graph comparison; D2 — No
parallel scanner; D3 — Wire symbols-drift to existing pipeline output; D4 — Non-decisions
(explicit).  
Enforced by: src/api/dependencies.py, src/api/v1/symbols_routes.py,
  src/body/introspection/drift_service.py

## ADR-144 — CCC Topology §3: Cross-Namespace Relation Taxonomy

2026-07-06 · was `ADR-144-cross-namespace-relation-taxonomy.md`  
D1 — Three cross-namespace relation types; D2 — Directional permission grid (cross-namespace); D3 —
§3 amendment to CORE-Governance-Topology.md; D4 — CCC check class CROSS_NS_DIRECTION.  
Enforced by: src/mind/coherence/checks/cross_ns_direction.py

## ADR-145 — Process-Mode Provenance and Startup Mechanism

2026-07-07 · was `ADR-145-process-mode-provenance.md`  
D1 — The process-mode flag has exactly two canonical values; D2 — The mode flag is read at process
startup from two sources with strict precedence; D3 — The mode flag is immutable for the lifetime of
the process; D4 — Conflicting sources are themselves a governance finding …  
Enforced by: not enforced

## ADR-146 — CLI Consumer/Operator Split

2026-07-07 · was `ADR-146-cli-consumer-operator-split.md`  
D1 — Two surfaces, not one; D2 — Consumer surface namespaces (extracted to core-cli); D3 — Operator
surface stays in CORE (core-admin); D4 — superseded: core-cli has no runtime dependency on
core-runtime; the boundary is HTTP and the OpenAPI contract; D5 — Package namespace; D6 — Entry
points; D7 — ADR-050 D1 compliance timing.  
Amended: 2026-10-03 (governor ruling) — D4 superseded; D7's independence claim corrected: CORE's
internal packages are not part of the client contract.  
Enforced by: src/api/cli/project_client.py, src/api/cli/secrets_client.py,
  src/api/cli/symbols_client.py (+21 more src/ files)

## ADR-147 — work/canary/ has no janitor: a bounded, age-gated reaper, deletes from day one

2026-07-11 · was `ADR-147-canary-sandbox-janitor-worker.md`  
D1 — A scheduled reaper worker. Add canary_janitor (.intent/workers/), a deterministic, no-LLM,
governance-class worker (the var_tmp_janitor / observer_worker system-state-reporter precedent — not
sensing). …  
Amended: Note 2026-10-02 (governor ruling) — canary_janitor deletes through FileService.remove_tree
(work/ is ephemeral-scratch), not by direct shutil.rmtree.  
Enforced by: src/body/infrastructure/storage/file_handler.py,
  src/shared/infrastructure/intent/operational_config.py,
  src/shared/infrastructure/intent/target_intent_assembly.py (+2 more src/ files)

## ADR-149 — Adoptable governance packs live outside the self-law root

2026-07-14 · was `ADR-149-governance-packs-live-outside-self-law-root.md`  
D1 — Adoptable governance packs live outside the self-law root; D2 — The pack *format* schema is
self-law and stays in .intent/; D3 — Clarify ADR-108 D4: "single law root" is corpus co-location,
not physical residency; D4 — The self-audit denominator corrects structurally …  
Enforced by: src/cli/logic/byor.py, src/shared/_packs/__init__.py,
  src/shared/infrastructure/bundled_grc_catalogs.py (+2 more src/ files)

## ADR-150 — The finalizing roll-forward is bounded: cap, escalation, and the terminal that stays earned

2026-07-16 · was `ADR-150-finalizing-redrive-cap.md`  
D1 — The redrive loop gets the ADR-104 rail: counter + cap, own knob — incremented in place on the
single persistent finding. …  
Enforced by: src/body/services/blackboard_service/blackboard_proposal_service.py,
  src/body/services/blackboard_service/blackboard_service.py,
  src/body/services/proposal_supervision_service.py (+3 more src/ files)

## ADR-151 — The dead-shim reaper: declared-legacy ∧ zero-callers becomes a finding

2026-07-16 · was `ADR-151-dead-shim-reaper.md`  
D1 — The finding is a conjunction: self-declared-deprecated ∧ zero live callers. New rule
modernization.dead_shim: a public symbol that (a) declares itself the deprecated artifact and (b)
has zero inbound edges in core.symbol_calls (excluding self-edges and edges originating in …  
Enforced by: src/body/introspection/sync/engine.py, src/body/introspection/sync/visitor.py,
  src/body/services/symbol_service.py (+1 more src/ files)

## ADR-152 — Generalizing governed_exclusions for ADR-049 D3's deadline-closure discipline

2026-07-17 · was `ADR-152-exemption-schema.md`  
D1 — Generalize governed_exclusions with a closure_type discriminator; D2 — scope.applies_to may be
empty for declared context-level checks; D3 — Lifecycle, closure_type: deadline only; D4 — New rule:
governance.exemption_debt.declared, validating programmatically …  
Enforced by: governance.exemption_debt.declared

## ADR-153 — Extracting the remediation ceremony to retire ViolationExecutorWorker's worker-to-worker import

2026-07-17 · was `ADR-153-remediation-ceremony-extraction.md`  
D1 — Extract the ceremony to src/will/remediation/, a non-workers Will subdirectory; D2 — A
RemediationBlackboard Protocol covering posting *and* marking, not a bare poster; D3 — Attribution
invariant, three paths; D4 — ViolationRemediator survives, thinner …  
Amended by: ADR-154 D4 (governor decision 2026-08-24) — RemediationCeremony is candidate-only; its
write terminus is removed; worker-backed remediation ends in a human-gated DRAFT proposal.  
Enforced by: architecture.workers.no_direct_worker_import

## ADR-154 — Mutation-lane equivalence: retire RemediationCeremony(write=True) onto the ADR-109 human-gated proposal path

2026-07-19 · was `ADR-154-mutation-lane-equivalence.md`  
D1 — Reuse the ADR-109 proposal form; do not invent a new proposal type; D2 — Candidate
immutability, as a first-class frozen contract; D3 — Finding lifecycle; D3a — File-mode lineage:
candidate-export-only (resolved 2026-08-23); D3b — Candidate-submission atomicity (no new split
state) …  
Amended: governor decision 2026-08-23 — D3a resolved as above; D5: after Canary and
assisted.validate_diff pass, CORE creates the human-gated DRAFT proposal automatically, only for
live canonical findings.  
Enforced by: architecture.boundary.embedding_access, architecture.boundary.remediation_write_access

## ADR-155 — Isolated consequence-chain demo: replace scripts/demo.sh with an isolation-substrate on-ramp

2026-07-23 · was `ADR-155-isolated-consequence-chain-demo.md`  
Adopt the twelve governing decisions of the Isolated Consequence-Chain Demo specification
(.specs/planning/CORE-Isolated-Consequence-Chain-Demo.md §3) as binding architectural commitments
for the replacement. …  
Enforced by: governance.logic_mutation.governed, governance.mutation_surface.filehandler_required

## ADR-156 — Audit verdict DEGRADEs on unmapped mapping-required rules

2026-08-29 · was `ADR-156-audit-verdict-unmapped-rules-degraded.md`  
D1 — Semantic: unmapped mapping-required rule ⇒ compliance unknown ⇒ DEGRADED; D1a — Verdict
precedence is explicit, not incidental; D2 — One paired, atomic change across governance and
interpreter; D3 — Required regression tests …  
Enforced by: not enforced

## ADR-157 — CI performance: complete the ADR-115 tier split, remove the duplicate Smoke gate, target the full gate on every push

2026-08-31 · was `ADR-157-ci-performance-and-push-cadence.md`  
D1 — Delete ci.yml ("CI (Smoke)"); D2 — Add event-aware concurrency cancellation to every remaining
workflow; D3 — Complete ADR-115 D4, in a dependency-correct, risk-ordered sequence, measuring before
escalating; D4 — Target the full gate on every push and PR …  
Enforced by: not enforced

## ADR-158 — Vocabulary register-assignment corrections: severity moves to Operational, two field-list errors in the register-assignment table corrected

2026-08-31 · was `ADR-158-vocabulary-register-assignment-corrections.md`  
D1 — Reclassify Severity from Diagnostic to Operational register in §5's table, citing this ADR and
ADR-059 D2 as the joint basis. …  
Enforced by: governance.passive_gate.enforced_by_must_resolve,
  governance.vocabulary_registers.operational_fields_must_be_lowercase

## ADR-159 — Acceptance boundary for the autonomy thesis: three thresholds, the containment rule, and the adaptation line

2026-09-04 · was `ADR-159-autonomy-thesis-acceptance-boundary.md`  
D1 — The thesis, stated; D2 — Three thresholds; D3 — The containment rule; D4 — The adaptation line;
D5 — Trial 0 is a rehearsal of the apparatus, not a proof; D6 — Trial 1 is the proof; D7 — The
fifteen gates are subordinate; D8 — This ADR is the north star of record …  
Thresholds superseded by "Thesis and baselines (2026-10-13)" at the top of this file.  
Enforced by: autonomy.tracing.mandatory, governance.logic_mutation.governed,
  governance.mutation_surface.filehandler_required

## ADR-160 — Risk classification as earned trust, and the authorization boundary

2026-09-12 · was `ADR-160-risk-maturity-and-authorization-boundary.md`  
D1 — Risk level is a maturity statement, not a property of an action; D2 — The three levels take
three distinct behaviors; D3 — Authorization gates on scope, not on caller; D4 — Any level change,
in either direction, requires the Governor's signature; CORE never writes .intent/ and escalates by
refusing; D5 — Every level change is recorded with the level …  
Amended: governor rulings 2026-09-12 — D4 as above; D3 supersedes ADR-095 D7's POST /fix/modularity
exemption; D3 rolls out one caller at a time, POST /develop/goal first.  
Enforced by: src/api/v1/development_routes.py, src/body/services/proposal_submission_service.py,
  src/cli/resources/dev/refactor.py (+10 more src/ files)

## ADR-162 — Database upgrade remediation: the confirmed v2.9.1→v2.10.1 defect and the Governor ruling on its repair

2026-09-19 · was `ADR-162-database-upgrade-remediation-ruling.md`  
D1 — R1-A: migrations are explicitly operator-run; D2 — R2-A: API and daemon refuse a non-current
schema; D3 — R3-A: unrestricted --bootstrap is retired; baseline adoption is verified; D4 — R4-A:
supported upgrade range …  
Enforced by: src/body/infrastructure/lifespan.py, src/cli/commands/daemon.py,
  src/cli/resources/database/migrate.py (+12 more src/ files)

## ADR-166 — Two governed write surfaces: FileHandler inside the repository, one governed external-target writer outside it

2026-10-02 · was `ADR-166-two-governed-write-surfaces.md`  
D1 — Inside the bound repository, FileHandler is the only write surface; D2 — Outside the
repository, one governed external-target writer; D3 — shared/ reaches FileHandler through a write
port; D4 — FileHandler closes its capability gaps without loosening a guard …  
Enforced by: governance.logic_mutation.governed, governance.mutation_surface.filehandler_required

## ADR-167 — Documentation is sensed for correspondence with the live CLIs

2026-10-03 · was `ADR-167-docs-cli-correspondence.md`  
D1 — Command/docs correspondence is sensed, both ways; D2 — cli.reference_current: the generated
reference matches the live trees; D3 — cli.docs_no_phantom_commands: every mentioned command exists;
D4 — Placement; D5 — Links and anchors are a tool gate, not a rule.  
Amended: 2026-10-03 (governor ruling) — D2 compares against the core-cli version CORE declares
(Makefile CORE_CLI_DOCS_VERSION), not PyPI's latest; both rules are blocking.  
Enforced by: cli.docs_no_phantom_commands, cli.reference_current

## ADR-168 — CORE governs the assistant: law, facts and verdict for every AI producer

2026-10-04 · was `ADR-168-core-governs-the-assistant.md`  
D1 — External assistants are governed producers; D2 — The first assistant surface: three
capabilities; D3 — No conversational authority; D4 — CORE's own development adopts it first; D5 —
Priority follows the surface (conditional on D6); D6 — Northstar amendment (proposed text …  
Amended: 2026-10-06 — D2's first transport is a local MCP server over the same in-process functions
as the offline audit. 2026-10-10 (A1–A7) — the surface gains submit-a-proposal (pending only); every
producer's change enters as a proposal with anchor, problem owner and producer; governed text is
refused at submission. 2026-10-10 (R1–R5) — a governor request is an anchor; approval is typed by
the human; governed paths are declared in governance_paths.yaml.  
Enforced by: src/api/v1/fix_routes.py, src/api/v1/proposals_routes.py, src/api/v1/schemas.py (+33
  more src/ files)

## ADR-169 — CORE knows its own state: which law it evaluated, which code it ran, and what it knows about every change

2026-10-05 · was `ADR-169-core-knows-its-own-state.md`  
D1 — A state ledger, append-only; D2 — Every verdict states the law it evaluated and its relation to
the law of record; D3 — Implement ADR-030 as decided; D4 — Every change between observations carries
what CORE knows about it; D5 — Writes outside the repository are recorded …  
Amended: 2026-10-06 (#953) — D5 is a precondition: with a CORE database configured, a write refuses
when the ledger is unreachable. 2026-10-11 (ADR-132 D10.14) — loaded-code identity is the release
(commit SHA and wheel sha256). 2026-10-15 (D6–D8) — CORE's own controls are checked like code: every
control has one source in git and every audit compares the installed copy with it (D6); the commit
gate runs the deployed release (D7); every assistant commit carries the gate's verdict and CI
requires it (D8). A mismatch or a missing verdict is a blocking finding. 2026-10-15 (later) — a
merge is the only approval: core-deploy applies changed setup scripts and installs `.claude/` from
`infra/claude-hooks/` from main by itself, and a pull request touching them starts its description
with "Host change:". The commit hook is producer feedback, not a control; D8 is dropped.  
Enforced by: src/body/services/change_attribution.py, src/body/services/outside_write_ledger.py,
  src/body/services/state_ledger_service.py (+16 more src/ files)

## ADR-170 — The law has a custodian: proposed by anyone, checked by CORE, approved by the governor, written by core-law

2026-10-08 · was `ADR-170-law-custodian.md`  
D1 — Three roles, never merged; D2 — Governed text and its custodian; D3 — The amendment procedure;
D4 — The ledger; D5 — CORE checks; the governor decides; D6 — The approval is the sudo password; D7
— The landing check; D8 — Stages; D0 — The rehearsal.  
Amended: 2026-10-11 — the law has two destinations, the development tree and /opt/core/law; the
rehearsal (D0) ended at ten proposals and Stage 1 started; law apply runs data checks only; approval
is `law apply <id> --write` with a fresh sudo password every time. For a change merged through a
pull request the merge is the recorded approval: core-deploy applies it as core-law with law
apply-merge (5e2c366e, 2026-10-12), and the governor's approval of the pull request's exact last
commit counts as the merge (d5af8d7a, 2026-10-13). Record-only .specs/ proposals apply themselves
(8259af3f, 2026-10-12). The ledger of record is /opt/core/custody (97cafcf5, 2026-10-13). The
merge is the only approval of law: the governor's sudo rule for law apply is removed and the
governor holds no sudo (ADR-068 amendment 2026-10-15; D6 superseded).  
Enforced by: governance.logic_mutation.governed, governance.mutation_surface.filehandler_required

## ADR-171 — Promotion flow: main is integration, the governor approves each promotion to live

2026-10-18 · proposed (design note; nothing implements it yet)  
**Terms.** A *promotion* moves a main SHA to the branch `live`, the only code CORE runs. A
*release* stays reserved for a published version (v3, a PyPI or GitHub release); this note
changes nothing about releases.  
**Decision.** Main is integration: core-claude merges its own pull requests once the required CI
checks are green, and nothing on main runs live. Code, law and host setup become live only by a
promotion the governor approved; core-pipeline deploys nothing else.
- **One approval per promotion.** CORE proposes a promotion once a day as a promotion pull request
  (main's SHA into `live`). The governor's approval of its exact head commit is the decision.
  `live` advances by fast-forward only, to that approved head (`git push <sha>:live`, which
  GitHub records as the pull request merged); GitHub's merge button, which makes a merge commit,
  is not used. core-pipeline deploys exactly the approved head SHA, never a merge commit.
- **The summary, in plain language.** High-risk items first: `infra/` and host changes,
  `.intent/`, migrations, and auth/security paths (`src/api/dependencies.py`, principals,
  sandbox, custody). Then the CI result and the sandbox check of the candidate SHA.
- **Reject** = the governor closes the promotion pull request; core-claude reverts the rejected
  changes on main, and the next proposal carries the revert.
- **Urgent fix**: on the governor's request, an immediate promotion proposal of main as it is,
  outside the daily schedule; no cherry-picks.
- **Root host setup** (core-runtime-setup, core-one-path-setup, core-law-setup) and merged law
  (`law apply-merge`) run only when an approved promotion is deployed, never on a merge to main.
- **Thesis.** "Unverified writes" is measured against promotions: a deployed SHA that is not a
  governor-approved promotion is an unverified write. Writes to main are integration and are not
  counted.

**Implementing pull requests, in order:**
1. `CLAUDE.md` working rules: main is not live; the governor approves promotions; core-claude
   merges its own green PRs once the governor settings below are in place. With the thesis entry
   above, amended to count promotions.
2. core-pipeline: deploy exactly the head SHA of the promotion PR the governor approved and
   fast-forward `live` to it; a merge to main, or any merge commit, deploys nothing. Host change.
3. core-deploy: refuse a SHA that is not the approved promotion head, so host setup and merged
   law run only at a promotion. Host change.
4. `core-admin promote propose` and its daily timer: open or update the promotion PR with the
   summary (risk classes from the diff since the last promotion, CI and sandbox results);
   `--urgent` proposes main at once. Host change (the timer).
5. `scripts/thesis_baseline.py`: unverified writes counted against deployed promotions.

**Governor settings (GitHub, not a PR), last:** only after PRs 2 and 3 are deployed, branch
protection lets core-claude merge to main on green required checks without review, and `live`
moves only by fast-forward to a head the governor approved. Until then every merge to main still
needs the governor's approval, as today.  
Enforced by: not enforced
