# CORE — A3 Governed Autonomy Plan

**Status:** Closed (Historical) — A3 milestone fully achieved 2026-05-12; preserved as the A3-era record.
**Post-A3 tracking:** [`CORE-Operational-Completeness.md`](../CORE-Operational-Completeness.md) (ADR-085 5+3 — five feature commitments closed 2026-06-02/03/05/06; three quality goals #561/#562/#563 remain).
**ADR index in this doc:** frozen at ADR-076 (2026-05-29). ADR-077+ are post-A3 polish; canonical record lives in `.specs/decisions/`.
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-05-24 — content frozen.
**Archived:** 2026-06-07.
**Definition:** The daemon runs continuously, the Blackboard clears, the codebase converges, and every action is visible.

---

## What A3 Is

A3 is not a feature. It is a state.

In A3, CORE's daemon finds problems in its own codebase, proposes fixes, executes approved fixes, and verifies the result — without the human writing a single line of code. The human role is: define goals, review proposals that require architectural judgment, approve constitutional changes.

**A3 capabilities:**
- Write its own tests
- Modularize what needs modularization
- Refactor what needs refactoring
- Keep all CLI commands working and clean
- Delegate correctly when human judgment is required
- Be demonstrable as a POC — observable via `tail -f`

---

## A3 Gates

A3 is a state. These four gates define the state. A3 is claimable when all four are cleared and held, not before.

| Gate | What it means | Status |
|------|---------------|--------|
| **G1 — Loop closure** | An autonomous fix lands end-to-end on a non-synthetic example: finding detected → proposal created → proposal approved → execution succeeded → re-audit confirms resolution. Single clean run is the minimum. | ✅ Demonstrated — completed round-trips observed live on `core.autonomous_proposals` via the proposal-consequence path; `approval_required=false` on safe actions correctly bypasses the pending/approved lane. |
| **G2 — Convergence** | Sustained state where rate of finding resolution exceeds rate of finding creation. Per the Convergence Principle, this is the fundamental operational metric — it is what makes "governed autonomy" truthful rather than aspirational. | ✅ Closed 2026-05-12. Circuit-breaker (ADR-038, #281) ensures systematic errors surface as governance signals rather than unbounded churn. Thresholds governed in `.intent/enforcement/config/circuit_breaker.yaml`. Band D milestone 16 closed. |
| **G3 — Consequence chain** | Finding → Proposal → Approval → Execution → File changes → New findings is continuously materialized as a queryable causality chain. Required for regulated environments, autonomous debugging, and for a non-programmer governor to trust the system without reading code. | ✅ Closed 2026-05-01. All six edges delivered. Epic #110 closed; Band B milestone 14 closed. |
| **G4 — Governance in `.intent/`** | No enforcement logic, path mappings, policy thresholds, or governance decisions live in `src/`. All of it lives in `.intent/` (or, for human-intent documents, `.specs/`). This is the claim that makes the "non-programmer governor" role coherent. | ✅ Closed 2026-05-10. All known governance leaks resolved: path mappings route through `shared.infrastructure.intent.test_coverage_paths`; hardcoded runtime directory paths at 0 violations (ADR-031/032); flow parameter routing governed via `FlowStep.consumes` (ADR-033); `action_executor` JIT guards are dead code — bootstrap already injects at composition root (ADR-025); `impact_level` externalized to `.intent/enforcement/config/action_risk.yaml`, `@register_action` no longer accepts the parameter (ADR-008, commit ae07f839); 32 operational config sections wired to `.intent/enforcement/config/operational_config.yaml` (ADR-040). Audit-verified: PASS, 20 findings. |

**Gate coupling:** G1 cannot be *proved* without G3 (you can't demonstrate the loop closed without the chain). G2 cannot be *measured* without G1 (no resolution rate without autonomous resolution). G4 is orthogonal but load-bearing: it is the reason a non-programmer can operate the system, and without it the other three gates describe a system that still requires its author.

---

## A3 Phases

### Phase 0 — Clean Slate ✅
Known-good starting point before activating anything.

### Phase 1 — Single Loop, Proven Convergence ✅
Purity sensor loop, Blackboard empty.

### Phase 2 — Expand Sensors ✅
All seven audit sensors active.

### Phase 3 — Capability Gaps ✅

**Framing:** Phase 3 is the **trust-hardening phase** — the machinery producing the verdict is being qualified. G1 and portions of G3/G4 close here.

**Status:** Complete. Stream A (ViolationExecutor) complete. Stream B (test writing) complete — ContextBuilder wiring confirmed working via ADR-025; test stream verified running end-to-end. Stream C (delegation) infrastructure complete. Band A (attribution) closed via ADR-011. Band D (Engine Integrity) closed 2026-05-12, milestone 16, 107 issues.

### Phase 4 — CLI Health ✅
`proposals show` logger bug — fixed 2026-05-10. Output routed through `Console` instance; Rich markup stripped from logger calls.

### Phase 5 — Visibility ✅
G3 closed 2026-05-01. Consequence chain materialized end-to-end. Band B milestone 14 closed.

---

## Bands

Operational work tracking lives entirely on GitHub. Bands are strategic groupings; closure criteria live on each milestone.

**All Band D work complete.** All four A3 gates closed. Band E (Outward-Facing) is the currently-advancing band per SESSION-PROTOCOL §3 Step 5; Band C (Historical Debt) remains deferred (milestone open with 0 unresolved items as of 2026-05-24).

- **Band A — Attribution** (closed): https://github.com/DariuszNewecki/CORE/milestone/13
- **Band B — Consequence Chain** (closed): https://github.com/DariuszNewecki/CORE/milestone/14
- **Band C — Historical Debt** (deferred): https://github.com/DariuszNewecki/CORE/milestone/15
- **Band D — Engine Integrity** (closed): https://github.com/DariuszNewecki/CORE/milestone/16
- **Band E — Outward-Facing** (active): https://github.com/DariuszNewecki/CORE/milestone/17

---

## Architectural Decisions Made

Full rationale lives in each ADR file under `.specs/decisions/`. This table is the index.

| ADR | Date | Title | One-line decision |
|-----|------|--------|-------------------|
| ADR-001 | 2026-04-15 | `.specs/` layer established | Non-operational documents move out of `.intent/` into `.specs/`. |
| ADR-002 | 2026-04-18 | Shared layer boundary enforcement | All shared/ violations resolved by architectural moves, not rule exceptions. |
| ADR-003 | 2026-04-19 | `task_type` as first-class field on `ExecutionTask` | Test generation routes through `audit` phase; `build_tests_action` sets `task_type="test_generation"`. |
| ADR-004 | 2026-04-19 | Govern task_type → phase mapping in `.intent/` | Three-way drift collapsed to `.intent/enforcement/config/task_type_phases.yaml`. |
| ADR-005 | 2026-04-20 | Govern audit verdict policy in `.intent/` | Severity→verdict mapping codified at `.intent/enforcement/config/audit_verdict.yaml`. |
| ADR-006 | 2026-04-20 | Align `modularity.needs_split` with its statement | Rule statement is law; implementation corrected to measure responsibility, not import proxy. |
| ADR-007 | 2026-04-21 | `modularity.class_too_large` split from `modularity.needs_split` | Separate rule for dominant-class case (non-automatable); 1-rule-to-1-method pattern. |
| ADR-008 | 2026-04-22 / 2026-05-08 | Constitutionalize `impact_level` | `impact_level` externalized to `.intent/enforcement/config/action_risk.yaml`; `@register_action` no longer accepts the parameter. Commit ae07f839. |
| ADR-009 | 2026-04-24 | CLI-depth block transient — passive instrumentation | No rule modified; full `ConstitutionalViolationError` attribution persisted into `action_results`. |
| ADR-010 | 2026-04-24 | Wire the §7 + §7a Finding/Proposal contract | Correct terminal status, forward link, and revival implemented in one coordinated change. |
| ADR-011 | 2026-04-24 | Workers own blackboard attribution; services do not post | Every INSERT into `blackboard_entries` must originate from a Worker. Band A closed. |
| ADR-012 | 2026-04-25 | Centralize globstar matching via `pathspec` | Eight `Path.match` sites migrated to `src/shared/utils/glob_match.py` using `GitWildMatchPattern`. §6 addendum 2026-05-03: path input contract (normalize leading `./` and `/`); all 7 in-scope sites confirmed migrated; Issue #143 closed. |
| ADR-013 | 2026-04-26 | Retire `core.proposals`; reserve name for `core.autonomous_proposals` | `core.proposals` retired (0 rows, no writers); name reserved for when "autonomous" becomes redundant. |
| ADR-014 | 2026-04-26 | Development-phase priority: loop liveness before artifact quality | Priority order: liveness > productivity > quality. First application: `build.tests` reclassified to `safe`. |
| ADR-015 | 2026-04-27 | Consequence chain attribution: write paths and storage shapes | Seven sub-decisions (D1–D7) covering finding_ids, approval_authority, claimed_by, and sensor attribution. |
| ADR-016 | 2026-04-27 | Test environment architecture | Schema authority = SQLAlchemy models; `core_test` ephemeral; isolation via `TRUNCATE CASCADE`. |
| ADR-017 | 2026-04-28 | `claim.proposal` as atomic action | approved→executing transition via constitutional action; `mark_executing` removed from state manager. |
| ADR-018 | 2026-05-01 | Decomposed crawler/embedder supersedes vector_sync_worker | Autonomous path split into `repo_crawler` + `repo_embedder`; `sync.vectors.code` kept for CLI. |
| ADR-019 | 2026-05-01 | Edge 5 git-boundary attribution posture | Orphan-commit detection via `CommitReachabilityAuditor`; prefix widened to 16 chars. |
| ADR-020 | 2026-05-02 | Worker liveness derived from heartbeat, not registry status | `status` column dropped; `last_heartbeat` + per-worker thresholds are canonical liveness. |
| ADR-021 | 2026-05-02 | Scoped autonomous git operations | `commit_paths` + `restore_paths` primitives; scope-collision yield pre-claim; C-light during dev phase. |
| ADR-022 | 2026-05-03 | ContextBuilder vector evidence scope | Vector evidence scoped to intent layer; `core-code` intentionally not queried; code-similarity earns its own method when a consumer surfaces. |
| ADR-023 | 2026-05-04 | Vocabulary canonical store — paper-first, machine projection derived | `CORE-Vocabulary.md` is canonical; `vocabulary.json` is a generated projection with `source_hash`; drift-detection rules + DEGRADED loader + CI gate enforce convergence. |
| ADR-024 | 2026-05-05 | Local LLM cognitive role assignments — governed evaluation over assumption | Local role-to-model assignments derived from `scripts/eval_ollama.py` qualification, not parameter-count assumption. |
| ADR-025 | 2026-05-05 | ArchitecturalContextBuilder wiring via CoreContext factory | `context_builder_factory` + lazy `@property context_builder` mirrors `context_service` pattern; rejected agent-internal and action-local construction. |
| ADR-026 | 2026-05-05 | Validate proposal.scope.files non-emptiness | scope.files non-empty enforced at Proposal.validate() with validation-error-to-caller; resolves ADR-021 D5. |
| ADR-027 | 2026-05-07 | Sensor-fixer coherence detection via consequence chain query | `CoherenceSensorWorker` queries `core.proposal_consequences` periodically; posts `coherence.incoherence::` findings; DELEGATE class. |
| ADR-028 | 2026-05-08 | Describe rules; don't quote forbidden syntax | Rule documentation must paraphrase what is forbidden — never reproduce the exact pattern the rule detects. |
| ADR-029 | 2026-05-08 | Explicitly map non-automatable rules in RemediationMap | Absence-from-map is not a valid human-only signal; non-automatable rules must carry an explicit PENDING entry. First application: `modularity.class_too_large`. |
| ADR-030 | 2026-05-08 | Daemon stale-code detection posture | Detect-and-DEGRADE on `src/` drift; self-restart rejected. |
| ADR-031 | 2026-05-09 | No hardcoded runtime directory paths | Runtime output dirs must resolve through PathResolver; direct string literal construction is a blocking violation. 40 findings surfaced; all resolved. |
| ADR-032 | 2026-05-10 | Tighten `no_hardcoded_runtime_dirs` regex to path-construction context | 15 false positives eliminated, 25 true violations confirmed. |
| ADR-032+ | 2026-05-10 | Band D infrastructure hardening | #273 approve rowcount, #274 Unicode sanitization, #275 execution_results key collision, #270 FileService resolve, #276 fix.path_resolver Form 1 — all closed. |
| ADR-033 | 2026-05-10 | Flow→step parameter routing contract | `consumes: tuple[str, ...] \| None` added to `FlowStep`; routing auditable from YAML. Closes #216, unblocks #215. |
| ADR-034 | 2026-05-10 | OptimizerWorker formal deferral | Deferred until VE accumulates ≥20 discovery candidates across ≥5 rule namespaces. |
| ADR-035 | 2026-05-11 | One finding, one proposal | `ViolationRemediatorWorker` grouping key changed to `(action_id, file_path)`; each proposal scoped to one file. Closes #284. |
| ADR-036 | 2026-05-11 | PathResolver excluded from `modularity.needs_split` | Catalog class with one responsibility; exclusion added to `modularity.yaml` with documented removal condition. |
| ADR-037 | 2026-05-11 | Flow refs exempt from ADR-035 per-file scoping | Flow proposals grouped by `(ref_id, None)`; atomic actions by `(ref_id, file_path)`. Categorical exception. Commit 0941fd07. |
| ADR-038 | 2026-05-11 | Circuit-breaker on repeated proposal failures | After N consecutive identical-signature failures, findings marked DELEGATE, hazard finding posted. Threshold governed in `.intent/enforcement/config/circuit_breaker.yaml`. Closes #281. G2 closed. |
| ADR-039 | 2026-05-12 | Audit-input cache invalidation | `AuditorContext._file_list_cache` and `IntentRepository` invalidated at every audit run start. Closes #298. |
| ADR-040 | 2026-05-12 | Operational config wiring campaign | 32 operational config sections moved from hardcoded `src/` literals to `.intent/enforcement/config/operational_config.yaml`; 48 typed dataclasses; 113 files importing loader. Closes #282. G4 completed. |
| ADR-041 | 2026-05-12 | Worker liveness thresholds — per-worker governance | Per-worker liveness thresholds governed in `.intent/`; `WorkerShopManager` and dashboard derive stale/alive verdicts from governed config, not hardcoded values. |
| ADR-042 | 2026-05-12 | `modularity.class_too_large` recalibration | LOC threshold raised 400→500; pre-selector/verdict separation formalised; `governed_exclusions` register introduced for facade-large and algorithm-large classes pending `llm_gate` operationalisation. |
| ADR-043 | 2026-05-13 | `llm_gate` audit throughput — pre-selector primary, semaphore secondary | `requires_findings_from:` field on enforcement mappings narrows llm_gate candidate set; `LLMClient._request_with_retry` restructured so retries release the semaphore slot during backoff; per-provider shared cache. Amended same day: D4 engine-layer semaphore retracted — `LLMClient` already owns concurrency control. Closes #308. Unblocks ADR-042 D4. |
| ADR-044 | 2026-05-13 | Incremental llm_gate verdict cache | Backing table `core.llm_gate_verdicts` keyed by `(rule_id, file_path, file_content_hash, rule_content_hash)` caches PASS/FAIL/ERROR verdicts; re-evaluation is skipped when both content and rule hash are unchanged. Targets the ~8–10 min llm_gate cost paid every 600s on a stable codebase (`purity.docstrings.required` alone was ~6 min/audit on a warm qwen2.5-coder:3b). Relates to ADR-039, ADR-043. |
| ADR-045 | 2026-05-13 | Quarantine state `awaiting_reaudit` for findings revived after rejection | Closes the reject-revive-reclaim divergence loop when proposals are rejected for finding-staleness rather than proposal-quality reasons. Revival from rejection puts the finding into `awaiting_reaudit` instead of `open`; only the audit sensor (not the remediator) may transition it back. Landed commit `4be78c05`. |
| ADR-046 | 2026-05-15 | Flow risk derived from constituent steps; test-format heal loop closed | D1: `Proposal.compute_risk()` resolves `flow_id` via `flow_registry` and computes flow risk as the max of step impact levels (recursive for nested flows); hardcoded `"moderate"` literal retired, conservative fallback preserved on registry miss. D2: `TestRemediatorWorker` emits a flow-kind proposal against `flow.build_tests` (build.tests → fix.imports → fix.headers → fix.format), classified `safe` and auto-approved through the existing path; executor branches on `ref_kind == "flow"` and dispatches via `FlowExecutor`. D3: optional-step failure must be discoverable, not log-only. Closes #290. |
| ADR-047 | 2026-05-15 | Move `purity.docstrings.required` from `llm_gate` to `ast_gate` | Verdict instability on the LLM gate (11 of 14 fix.docstrings proposals stale within 33 hours) made the rule unreliable. The rule is purely structural ("does this public symbol have a docstring?") and reducible to `ast.get_docstring(node) is None`; it does not require LLM judgement. Rule retired from `llm_gate`; `ast_gate check_docstrings_present` becomes the canonical check. Informs #311. |
| ADR-048 | 2026-05-15 | `fix.docstrings` walks the AST instead of the knowledge graph | Two stacked bugs (knowledge-graph-only symbol discovery; call to a non-existent `write.docstring` atomic action) caused `fix.docstrings` to log "All public symbols have docstrings" and commit zero changes on every invocation despite returning `ok=True`. D1: rewrite `_async_fix_docstrings` to walk the AST directly with the same predicate ast_gate uses. D2: inline AST-based insertion replaces the missing atomic action. Detection and remediation converge on a single predicate. Pairs with ADR-047. |
| ADR-049 | 2026-05-15 | Restore parity between architectural doctrine and enforced rules | The code passed audit because the rules were narrower than the doctrine papers claimed. Per-boundary verdict (D1): §7.2 shared independence — close the excludes list (no new entries without a closure ADR); §5.4 Body → Will — tighten `forbidden:` to bare-prefix match (`will`, `src.will`); §6 API infrastructure — soften paper to match the rule (DB-sessions-only). D2: every normative paper claim about imports/layer boundaries must name its enforcing rule or be marked aspirational. D3: every `excludes:` entry requires a companion closure ADR with a deadline; audit warns on overdue closures. |
| ADR-050 | 2026-05-15 (revised 2026-05-17) | CLI is a standalone HTTP client; `src/cli/` extracted from CORE | Supersedes the original 2026-05-15 text. Resolves the previously-deferred network-boundary decision: CLI communicates with CORE exclusively over HTTP via the API — no Python import from any `src/` module (including `api.*`) is permitted in CLI. The original logical-boundary rule fired 499 unfixable findings (no remediator, no API surface yet) — a Convergence Principle violation embedded in the ADR itself. D1: HTTP-only topology (`Operator → CLI → HTTP → src/api/ → Will → Body/Mind`); physical, not logical, boundary. D2: `src/cli/` is extracted to a standalone repository (`core-cli`), versioned and deployed independently. D3: Will → CLI inversions verified zero across `src/will/` on 2026-05-17 (closed condition, not a prerequisite step). D4: `architecture.cli.api_only` disabled during migration and retired on extraction; per-finding audit replaced by a single tracking issue. D5: `src/api/cli/client.py` (internal HTTP client library for API-to-API testing) remains in CORE. D6: `CORE-Mind-Body-Will-Separation.md` §2/§6 updated — CLI no longer appears inside the system boundary. Resolution sequence: disable rule → ship API phases per ADR-054 → extract `src/cli/` → retire rule. |
| ADR-051 | 2026-05-15 | `file_handler.py` `shared/` excludes closure | Defers structural resolution with a 2026-09-12 deadline (120 days, per ADR-049 D3). `file_handler.py` currently imports `body.governance.intent_guard` and `mind.governance.violation_report`; resolution is one of two successor-ADR paths: Path X — composition-root exemption (aligns with parked #157 framing for `api/main.py`); Path Y — extract `MutationGuardProtocol` to `shared/protocols/` and relocate `ConstitutionalViolationError`. Closes the final bullet of #315 Tier B/1. |
| ADR-052 | 2026-05-16 | LLM configuration domain — final schema | Completes the migration from `runtime_settings` (transitional `.env`-shaped KV) to typed tables. `llm_resources` gains typed columns (`model_name`, `api_url`, `locality`, concurrency, retry, cost, health). New tables: `role_resource_assignments` (priority-ordered fallback), `system_config` (typed singleton replacing the three duplicate `llm_enabled` flags), `secret_store` (typed credential replacement for `is_secret=true` rows), `config_migration_log` (`.env` → final-table audit trail), `capability_alignment_tests` + `model_performance_results` (benchmark registry), `llm_exchange_log` (partitioned monthly, GxP append-only). FKs added to `semantic_cache.cognitive_role` and `agent_memory.cognitive_role`. `cognitive_roles.assigned_resource` retired in favour of `role_resource_assignments`. `runtime_settings` dropped in Phase 4 once `config_migration_log` shows zero `migrated_at IS NULL`. Epic #324; phases #325–#328; partition maintenance #329; GxP retention #330. Surfaces schema work for G4 cleanup. Closes #268 (partial). |
| ADR-053 | 2026-05-16 | CORE API as resource-oriented governance interface | The API is CORE's single governed entry point; long-running operations are modeled as resources with reconciliation loops (Kubernetes / Vault / AWS control-plane pattern) rather than RPC calls. D1: API is the governance interface. D2: operations are resources. D3: standard protocol contract. D4: ten domain namespaces map the migration surface. D5: CLI becomes a typed HTTP client importing only `api.*`. D6: papers updated before any endpoint ships. D7: request-level attribution for GxP readiness. Closes the API incompleteness gap surfaced by the ADR-050 capability audit. |
| ADR-054 | 2026-05-16 (amended 2026-05-17) | API Phase 1 — `/audit` + `/proposals` | First capability cluster under ADR-053. D1: audit runs are resources (`POST /audit/runs`, `GET /audit/runs/{id}`). D2: `/proposals/{id}/execute` included in Phase 1 scope. D3: no auth — loopback binding only for Phase 1. D4: completion is verified by removing suppress entries for six CLI files (`proposals/{integrate,manage,list,create}.py`, `code/{audit,lint}.py`) until each reaches zero direct `mind/*`, `will/*`, `body/*`, `shared/*` imports. **Amendment 2026-05-17**: adds `findings jsonb` column to `core.audit_runs`; writers (sync + async) persist findings to the column; `GET /audit/runs/{id}` returns them as the `findings` field; pre-amendment rows return `[]`. Overrides the "no new infrastructure" constraint for this column only; the relational alternative (Option A — `audit_findings.run_id` FK) is parked as #345 (Band E) for GxP audit-trail readiness. Closes #335 and #340. |
| ADR-055 | 2026-05-17 (D6 implementation complete 2026-05-18) | API Phase 2: /fix + /quality | /fix and /quality namespaces defined; fix_runs resource table; generic atomic dispatch via ActionExecutor; FlowExecutor for /fix/all; sync/async split for quality checks. **D6 (CLI cutover) complete 2026-05-18:** 23 of 24 in-scope CLI files migrated to `api.*` + `cli.*` only across 16 commits (`43b2adf1`..`3eea5b87`) — 2 C0 prep, 5 batch migrations (C1–C5), 7 Stage B reopens, 1 action_risk classification. Registry grew 22 → 28 atomic actions. Two governance-debt carries: `integrity.py` parked (#353 — needs `POST /v1/integrity/{baseline,verify}`); `all_commands.py` dropped `db-registry` step (#356 — needs `fix.sync_commands` action). Postmortem and lessons: `var/d6-stage-c-migration-plan.md`. |
| ADR-056 | 2026-05-17 | Runtime data contracts as first-class constitutional artifacts | Closes the three-surface "Finding" drift (Pydantic class, `audit_runs.findings` jsonb, `BlackboardEntry`) and unguarded state-conditional `Proposal` invariants. D1: new `.intent/enforcement/contracts/` artifact class governed by ADR; meta-schema extended with `data_contract` kind. **✅ D1 complete 2026-05-18 (commit `8042aa00`):** `META/data_contract.schema.json` authored; `GLOBAL-DOCUMENT-META-SCHEMA.json` kind enum extended with `data_contract`; bootstrap validator (`intent_validator.py`) allowlist includes `META/data_contract.schema.json` and adds it to `_BOOTSTRAP_REQUIRED_FILES`. D2: rename `Finding` (Pydantic, `body/services/cim/models.py`) → `CheckResult` — name freed for the blackboard governance entity. **✅ D2 complete 2026-05-18 (commit `b182ec38`):** class renamed; six call sites in `cim/policy.py` updated; class UUID preserved (rename is not a new definition); no external callers, no test references. D3: canonical `Finding.json` nucleus (`rule_id`, `severity`, `subject`, `evidence`, `worker_uuid`) all three surfaces must satisfy. **✅ D3 complete 2026-05-18 (commit `8042aa00`):** `.intent/enforcement/contracts/Finding.json` (`.json`, not `.schema.json` — naming convention reconciled to the engine dispatch's `{schema_ref}.json` resolution) declares the canonical nucleus, currently governing `CheckResult` only; rule `data.contracts.finding_nucleus_conforms` ships at `enforcement: reporting`; pipeline produces seven expected findings on `CheckResult` (four undeclared extension fields + three missing required fields — the actual constitutional drift ADR-056 identified, now visible at audit time). AuditFinding and BlackboardEntry payload families to be added to `governed_classes` in subsequent Wave 1 work. D4: `Proposal.schema.json` with state-conditional field invariants per `ProposalStatus` (DRAFT / APPROVED / EXECUTING / COMPLETED / FAILED); `ProposalStateManager` remains the enforcement site, the schema makes invariants auditable. D5: govern `BlackboardEntry.entry_type` via `enums.json`, enforced via `$ref` from JSON Schemas (precedent: `phase`, `worker_status`, `artifact_status` constrained via `workflow_stage.schema.json` and `worker.schema.json`). Python-source enforcement deferred to D6 + Wave 1 schemas. D6: `SchemaConformanceChecks` as a new check class inside the existing AST gate (precedent: `PurityChecks`, `NamingChecks`); static-pass verification. **✅ D6 scaffolding complete 2026-05-18 (commit `e3d1d852`):** check class shipped with three static methods (`extract_class_annotated_fields`, `check_schema_contract_fields`, `extract_governed_classes`); `schema_conformance` registered in `_SUPPORTED_CHECK_TYPES`; dispatch wiring resolves `.intent/enforcement/contracts/<schema_ref>.json` from the contract directory. Design rationale recorded in `.specs/papers/CORE-DataContracts.md` (commit `061e9eaf`): contract-side `governed_classes` declaration rejected the `@schema_contract` decorator alternative on authority-inversion and decorator-proliferation grounds. D1, D2, D3, D5, D6, D7 all complete this session (2026-05-18). **✅ Wave 1 Session 3 — 2026-05-19:** ProposalConsequence dataclass + data contract (commit `77330a3d`); ConstitutionalViolationPayload dataclass + data contract + governance rule + enforcement mapping (commits `fef9aad0` + `c5789320`); WorkerDeclaration dataclass + data contract + governance rule + enforcement mapping (commit `607a2c24`). All three Wave 1 deferral items now landed (AgentDecision.options_considered remains a documented JSONB sub-shape gap with no writer in src/ — not workable as Wave 1 dataclass work). Remaining: D4 — Proposal state-conditional contract with JSON Schema if/then conditional logic per `ProposalStatus` (#367); Wave 1 schema authoring to follow (extend `Finding.json` `governed_classes` to AuditFinding and BlackboardEntry payload families; author universal-result-family contracts ActionResult / ComponentResult / FlowResult / StepResult / RefusalResult). Tracking issues: #352 (original D1–D6); #366 (broadened scope + D7 boundary criteria + ~70-contract Wave plan); #367 (D4 follow-up). |
| ADR-057 | 2026-05-18 | API Phase 3: /coverage + /refactor + /inspect | Third capability cluster under ADR-053. Endpoint surface: `/coverage`, `/refactor`, `/inspect`, plus deferred `POST /audit/remediations`. Three new resource tables: `coverage_runs`, `refactor_runs`, `audit_remediation_runs`. All `/inspect` endpoints are read-only with no new tables. `POST /refactor/autonomous` routes through its own `refactor_runs` record — distinct from the `autonomous_proposals` it produces — preserving GxP request-to-output traceability. Phase 4 boundary confirmed: `inspect/repo_census.py` and the `/census` namespace are excluded from Phase 3 (deferred to ADR-058). |
| ADR-058 | 2026-05-18 | API Phase 4: /census + /sync + /daemon | Final phase of the ADR-053 API surface. `/census` → `census_runs` resource table; `POST /census/runs` async, `POST /census/baselines/{name}` synchronous. `/sync` → single `sync_runs` table with `sync_type` discriminator covering `db_registry`, `vectors`, `code_vectors`, `dev_sync`. `/daemon` → no resource table; `POST /daemon/stop` uses FastAPI BackgroundTask fire-and-forget to avoid self-termination; `GET /daemon/status` governed by ADR-041 thresholds. D5 flags `/components` and `/search` as unassigned namespace items — CLI-extraction blocker, requires follow-up issue before Phase 4 closure. D8: Phase 4 completion is the ADR-050 CLI extraction trigger. |
| ADR-053+ / ADR-057+ | 2026-05-18 | Namespace assignment for unassigned capability map items | `components.py` and `search.py` — the two CLI files left unassigned in the original ADR-053 D4 capability map — formally assigned to the Inspect namespace group. ADR-053 D4 records the elimination of `/audit` (wrong backend profile — `mind.governance.*`) and `/meta` (no phase ADR; would violate D6) with constraint-based reasoning. ADR-057 D5 adds `GET /v1/components` and `GET /v1/search/capabilities` to Phase 3 surface; `GET /v1/search/commands` deferred to Phase 3b pending `hub_search_cmd` extraction from `cli.logic.hub` (tracked as #363). URL paths follow existing Inspect convention (`/v1/<resource>`, no `/v1/inspect/` prefix). Implementation complete same session: 7 files touched, ruff clean, zero `shared.*` imports remaining in either CLI file. Closes #362. Unblocks ADR-050 CLI extraction. |
| ADR-059 | 2026-05-19 | Severity vocabulary governance | Three governor decisions from ADR-056 Wave 1. D1: retire `"dangerous"` from `RiskAssessment.overall_risk`; align to the `proposal_risk` enum (safe/moderate/high). **✅ D1 implementation complete 2026-05-19 (commit `13055f38`):** `RiskAssessment.overall_risk` aligned to `proposal_risk` enum across `src/will/autonomy/proposal.py` (8 occurrences) and `src/cli/logic/autonomy/views.py`; `RiskAssessment.json` `overall_risk` field now `$ref`s the `proposal_risk` enum; input-side `action_risk` vocabulary boundary (action_risk.yaml: safe/moderate/dangerous) preserved with inline boundary documentation. D2: replace `audit_severity` 3-value set (info/warning/error) with the 5-value finding severity scale (info/low/medium/high/block). **✅ D2 implementation complete 2026-05-19 (commit `9551e972`):** 26 files renamed; CIM Literal lowercased; `enums.json` + `audit_verdict.yaml` + `AuditFinding.json` + `CheckResult.json` reconciled; mechanical mapping WARNING→HIGH, ERROR→BLOCK applied across 24 src/ files + 2 test files; #370 verification confirmed no DB-side uppercase persistence (closed 2026-05-19). D3: five severity surfaces documented as three distinct domains (audit findings, proposal risk, validator input); no unification; translation tables defined at `risk_tier → proposal_risk` and `audit_severity → log-level` boundaries as constitutional policy (governance-only — no implementation needed). ADR authoring commit `d0a0ac72`. |
| ADR-060 | 2026-05-19 | Governance input staleness closure | ADR-039 companion. `AuditorContext.reload_governance()` already landed on `auditor.py:88` (commit `e36b42f7`). D1: extend wiring to `filtered_audit.py` and `audit_violation_sensor.py` so all three audit run entry points refresh policies and enforcement mappings each cycle, matching the existing `invalidate_file_cache()` coverage. Redundant `intent_repo.reload()` removed from the sensor — `reload_governance()` invokes it internally. D2: `CORE-IntentRepository.md §4a` amended — "restart required" contract superseded; drift window bounded to one sensor interval (600 s) on all code paths. Restart still required for `META/intent_tree.yaml` structural changes and `src/` Python changes (per ADR-030). Commit `783a7f70`. |
| ADR-061 | 2026-05-19 | Composition-root sanctuary for `api/main.py` lifespan import | Codifies the existing `architecture.api.no_body_bypass` exemption at `layer_separation.yaml:237` (landed 2026-04-19, commit `f634e521`) as the permanent answer. D1: `src/api/main.py` is exempt from the rule for **exactly one import** — `body.infrastructure.lifespan.core_lifespan`, required by FastAPI's `lifespan=` constructor argument. Relocation to `src/api/` would require half a dozen new bypass imports; relocation to `src/will/` is a semantic mismatch (Will is the cognitive layer, not infrastructure ignition). D2: sanctuary scope verified correct (single-file, per-rule, no glob, rationale comment in place). D3: revisit triggers — FastAPI lifespan contract changes, a second Body import needed in `api/main.py`, or `core_lifespan`'s Body-residence challenged. Closes #157. |
| ADR-062 | 2026-05-19 | `proposal_lifecycle_actions.py` body→will closure | Closure ADR for the `architecture.layers.no_body_to_will` exclude on `src/body/atomic/proposal_lifecycle_actions.py`, which imports `ProposalStatus` from `will.autonomy.proposal` to enforce the `approved → executing` transition in the `claim.proposal` atomic action (ADR-017). Two viable refactor paths named: **Option A (preferred)** move `ProposalStatus` to `src/shared/lifecycles/proposal.py`, matching ADR-049's "shared as pure contracts" long-horizon direction; **Option B** pass enum values as strings with Will-side validation. Deadline **2026-09-16** (120 days; matches ADR-051). Closes first bullet of #313. |
| ADR-063 | 2026-05-19 | `bootstrap.py` will.tools body→will closure | Closure ADR for the three lazy `will.tools.*` imports at `src/body/infrastructure/bootstrap.py:60–64` (`ArchitecturalContextBuilder`, `ModuleAnchorGenerator`, `PolicyVectorizer`), all caught under the expanded ADR-049 D1 bare-prefix `forbidden:` list. Two paths: **Option A (preferred)** re-home the three tools to `src/shared/cognitive_tools/` since they are stateless protocol-based builders fitting ADR-049's "shared as pure contracts" direction; **Option B** invert ownership so Body owns the factory and Will instances are injected via `CoreContext`. Deadline **2026-09-16**. Closes second/third/fourth bullets of #313. |
| ADR-064 | 2026-05-19 | `fix_actions.py` capability_tagging body→will closure | Closure ADR for the `src/body/atomic/fix_actions.py:666` lazy import of `will.self_healing.capability_tagging_service.main_async`, added under the ADR-049 exclude in commit `5201b3b6`. The action is a thin Body dispatch wrapper around a Will-resident agent that uses cognitive/knowledge services. Two paths: **Option A (preferred)** Body-layer dispatch facade with injected callable (`CapabilityTaggingService` in `src/body/services/`, wired at lifespan composition); **Option B** move `main_async` to Body, keep `CapabilityTaggerAgent` as a Will-internal helper. Precedent: `BrainServicesProvider` protocol injection (commit `c9332d73`). Deadline **2026-09-16**. Closes fix-actions bullet of #313. |
| ADR-065 | 2026-05-20 | Documentation layer separation: `.specs/` vs `docs/` | Declares constitutional law for the two human-readable directories. D1: `.specs/` is the **governance layer** (authoritative artifacts, internal audience, governor-only); `docs/` is the **communication layer** (external audience, reader-facing, no constitutional authority). D2: authority and derivation are one-way: `docs/` → `.specs/`, never the reverse. D3: explicit placement rules per audience and authority. D4: specific placements confirmed — `CORE-Features.md` and `CORE-Product-Tiers.md` in `.specs/papers/`; ADRs in `.specs/decisions/`; URS in `.specs/urs/`; usage guides and tutorials in `docs/`. D5: GitHub Feature issues link to `.specs/`, not `docs/`. No automated rule; verification is governor responsibility. Closes Track 10 placement ambiguity. |
| ADR-066 | 2026-05-21 | Unmapped-rules invariant — every active rule must have an `auto_remediation.yaml` entry | Closes the silent abandoned-finding re-emission loop where an active rule with no remediation map entry produced **8,539 abandoned findings across four rules in 48 hours** (`architecture.cli.api_only` 4,282; `purity.no_orphan_files` 1,691; `architecture.channels.logger_not_presentation` 1,558; `architecture.layers.no_body_to_will` 8). Invariant: every active rule MUST have a corresponding entry in `auto_remediation.yaml`. A minimum-valid `DELEGATE` entry (confidence 0.40, below MIN_CONFIDENCE 0.80) is sufficient. New blocking audit rule `governance.remediation.all_rules_mapped` enforces the invariant at each audit cycle (severity HIGH; emits FAIL on unmapped active rules). Self-referential: the new rule must itself be mapped (DELEGATE). Closes #418. |
| ADR-067 | 2026-05-21 | Constitutional Coherence Checker — storage, CLI, LLM invocation, scheduling | Implementation decisions for the CCC instrument defined in `CORE-ConstitutionalCoherenceChecker.md`. D1: two new tables `core.coherence_runs` and `core.coherence_candidates` (no FK entanglement with proposals/findings/blackboard). D2: three CLI subcommands `core-admin coherence check [--full] \| report [RUN_ID] \| triage CANDIDATE_ID DECISION [--note TEXT]`. D3: dedicated `constitutional_coherence_analysis` cognitive role (analysis-only, read-only); R1/R2/R3/R4 batching strategy; all failure modes non-fatal (call/parse/schema/file failures → `skipped` with reason; >20% skip emits WARNING). D4: CCC is CLI-only, not a daemon worker; trigger detection (`adr_added`, `northstar_changed`, `manual`) computed at invocation time; automated triggering deferred. D5: advisory line appended to `core-admin code audit` output (does not affect verdict). Closes #374 acceptance criteria. |
| ADR-068 | 2026-05-22 | Principal Role Taxonomy | Establishes CORE's constitutional role model in three layers (Layer 1 taxonomy in `.intent/`; Layer 2 principal-to-role binding at deployment; Layer 3 action-to-role requirement in enforcement rules). D1: three-layer separation is constitutional; roles are permanently flat (no inheritance, no Layer-1 resource scoping). D2: four declared roles — `principal.governor`, `principal.operator`, `principal.auditor`, `principal.system`. D3: SoD constraint — a Governor may not sign the audit-verification record for an action they approved (declared now, enforcement deferred to multi-operator tier). D4: Single-Governor Local deployment posture defined; auth deferred when only access path is local. D5: `proposal_approval_authority` enum value `human.cli_operator` retired and replaced by `principal.governor` (migration backfills existing rows). D6: canonical replacement template for founder-sovereignty language in Tier A documents — resolves Track 10 with a derivable substitution rather than editorial judgment. Implementation deferred. |
| ADR-069 | 2026-05-23 | Claim lifecycle: lease semantics | Closes the structural orphan-claim gap (154 stuck `audit.violation` claims found 2026-05-23; ~26 fresh per daemon restart measured). D1: a `claimed` row's ownership is bounded by a declared `lease_expires_at`; expiry is intrinsic to the row, not asserted by surveillance. D2: schema adds nullable `lease_expires_at TIMESTAMPTZ` to `core.blackboard_entries`; terminal transitions set it to NULL. D3: every worker (daemon-run or CLI-triggered) MUST declare `mandate.schedule.lease_seconds`; no runtime fallback; `intent_validator.py` refuses workers omitting it. Migration values: `violation_executor` 3600 s; `proposal_consumer_worker` and `violation_remediator_body` 1800 s; all others 2× `max_interval`. D4: `BlackboardService.renew_lease(entry_ids, claimed_by, additional_seconds)` per-batch API; partial loss treated as full batch loss; `LeaseExpiredError` raised and caught at `Worker.start()`; `_on_lease_lost` hook for rollback. D5: terminal transitions release the lease. D6: re-claim on expiry uses the same query path (`status='claimed' AND lease_expires_at < now()` recognised as re-claimable); partial index on `(lease_expires_at) WHERE status='claimed'`. D7: migration backfills existing claimed rows at `claimed_at + 600 s`; `release_claimed_entries` retained as governor-override utility. Implementation deferred. Closes #439. |
| ADR-070 | 2026-05-24 | Source–projection coherence as bounded drift | Establishes representation coherence as a constitutional property across the five-surface model (`src/` + `.intent/` + `.specs/` as on-disk sources of truth; PostgreSQL + Qdrant as derived projections). D1: the property is **bounded drift**, not identity — every projection's divergence from its source is observable through audit/finding/remediation channels and bounded by a constitutional value declared in `.intent/`, not inferred by surveillance. D2: `.intent/governance/projections.yaml` (governor-authored) inventories every pair; completeness is a governor obligation (no automated discovery — D5 enforces declared-but-unsensed, not declared-vs-missing). D3: three bound shapes — **lease-style** (operational caches; `lease_seconds`), **hash-equality** (vector projections; `source_hash` comparison), **reference-set** (set-difference projections; tolerance 0). D4: coherence sensors emit findings under `coherence.*` namespace; two permitted patterns — **independent sensor** (`remediation.mode: proposal`, default) and **writer-as-sensor** (`remediation.mode: inline`, reference-set pairs only, where the writer's existing cycle naturally enumerates the source set). The current `logger.warning` anti-pattern (e.g., `repo_embedder_workers.py:112`) is constitutionally retired. D5: meta-rule `governance.coherence.all_pairs_sensed` (severity HIGH; self-referentially DELEGATE-mapped per ADR-066). D6: composite "Representation Coherence" advisory line on `core-admin code audit` output (parallel to ADR-067 D5's CCC line; advisory only, does not affect PASS/FAIL verdict). D7: existing partial mechanisms (ADR-030, ADR-039/060, `DbSyncWorker`, `core-admin inspect drift`, `CommitReachabilityAuditor`) remain — each documented as the sensor for its pair; no retrofit. D8: first incremental delivery — `repo_artifacts ↔ filesystem` reframes #441 as the framework's first pair (writer-as-sensor on `RepoCrawlerWorker`; reap is one extra SQL operation in the existing walk pass). D9: subsequent pairs sequenced by silent-blast-radius (`.intent/` ↔ `IntentRepository` cache next, then `.intent/`/`src/`/`.specs/` ↔ Qdrant collections, then operational-table sweep). Cognate with ADR-016 / ADR-066 / ADR-069 — same pattern (validity declared on the artifact, not inferred by surveillance) extended to the representation layer. |
| ADR-075 | 2026-05-28 | Framework / project namespace split | Every governance artifact under `.intent/`/`.specs/` belongs to exactly one `governance_namespace` — `framework` (ships with CORE, applies to any governed project) or `project::<name>` (specific to a named repo; CORE's own codebase is `project::core`). The split is the prerequisite for the governance-application data model. D1: namespace model is constitutional. D2: declared in an external path-to-namespace manifest, not per-file frontmatter (per-file stamping would be a big-bang touch against Topology §11 backfill-on-touch). D3: the key is `governance_namespace`, never bare `namespace`, to avoid collision with three pre-existing senses (`rule_namespace` sensor scope, blackboard subject namespace, API domain namespace). D4: two artifacts — vocabulary register at `.intent/taxonomies/governance_namespaces.yaml` + classification manifest at `.intent/governance/namespace_manifest.yaml` (ADR-068 register-plus-enforcement shape). D5: classification authority is per-artifact; file type is non-authoritative default heuristic only — a rule, ADR, or paper may be framework-general or CORE-specific regardless of type. D6: per-layer manifest — framework ships its own; each project carries its own; CORE deployment = framework + `project::core`; BYOR = framework + `project::<external>`. Mechanism `src/cli/logic/byor.py` will eventually consume. D7: reporting rule `governance.namespace.classification_complete` fails on any unclassified `.intent/`/`.specs/` file. D8: initial population is a deliberate one-shot full pass (bounded exception to Topology §11); D7 maintains the invariant going forward. Grounded in `papers/CORE-Governance-Topology.md` §8 (row 2). **✅ Acceptance commit `a24ff4ca` 2026-05-28.** **✅ Implementation commits `e6fc5552` + `e970e8a0` 2026-05-29:** vocabulary register, 406-entry manifest (152 framework + 254 project::core), rule document, enforcement mapping (`engine: artifact_gate`), DELEGATE entry in `auto_remediation.yaml`, and `_check_namespace_manifest_completeness` wired into `artifact_gate.py` alongside the cognates. Direct invocation of the check works correctly (positive provocation confirmed — produces `ok=False` with the unclassified path on probe; `ok=True` clean). ✅ **D7 enforcement is now LIVE (ADR-076 / #481, 2026-05-29).** ~~Was GATED by #480: `audit_context.get_files()` walked only `*.py` and hard-excluded `.intent/**`, so audit-cycle dispatch never invoked the check.~~ ADR-076 makes context-level dispatch a per-check-type engine property (D1–D2), gives `artifact_gate` a `verify_context` path for its six repo-level checks (D3), and derives the walker's scope from active per-file rule scopes (D5). The governance meta-rules — `governance.remediation.all_rules_mapped` (ADR-066, blocking), `governance.quarantine.namespace_has_drainer` (ADR-072), and `governance.namespace.classification_complete` (this D7) — now dispatch context-level via `verify_context`. **Proven live on the real tree:** `Dispatch:` reads `28 context-level · 160 per-file`, and the ADR-066 provocation flips `all_rules_mapped` present↔absent with an exact +1/−1 delta — the test that returned PASS before now FAILs correctly. The 8,539-finding silent-inert window is closed. Restored enforcement immediately surfaced real latent debt (first live verdict: FAIL on previously-unreportable findings) — intended behavior of live enforcement; convergence of that debt is tracked on **#482**. Cognate with ADR-068 (register pattern) and ADR-070 (projection inventory pattern). Follow-on **#479** filed for governance-application data model (#457 close-3). Closes #457. D7's #480 gate is closed: ADR-076 accepted and implemented (#481), enforcement live and provocation-verified 2026-05-29. |
| ADR-076 | 2026-05-29 | Context-level dispatch as a per-check-type engine property | Dispatch mode is engine-declared per check_type, not per-engine: extractor consults `engine.is_context_level_for(check_type)` and `CONTEXT_LEVEL_ENGINES` is retired (D1–D2); `artifact_gate` becomes mixed-mode with `verify_context` for its 6 repo-level checks, `verify` for its 3 per-file PromptModel checks (D3); effective mode surfaced in audit/inspect output (D4); walker scope derived from per-file rule scopes (D5); test-time firing-coverage gate replaces a file_path-usage proxy (D6). Un-inerts 9 audit rules incl. ADR-066's blocking invariant and ADR-075 D7; grounded in CORE-Gate.md. Closes #480 at land; implementation tracked #481. |

---

## Key Commands

```bash
# Daemon
systemctl --user start core-daemon
systemctl --user stop core-daemon
systemctl --user restart core-daemon
systemctl --user is-active core-daemon
journalctl --user -u core-daemon -f

# Audit
core-admin code audit
core-admin constitution validate

# Blackboard
core-admin workers blackboard
core-admin workers blackboard --status open
core-admin workers blackboard --filter "audit.violation"
core-admin workers purge --status <status> --rule <subject_prefix> --before <hours> --write

# Runtime
core-admin runtime health
core-admin runtime dashboard
core-admin runtime dashboard --plain
watch -n 30 core-admin runtime dashboard

# Workers
core-admin workers run <declaration_name>

# Proposals
core-admin proposals list
core-admin proposals list --full-ids

# Vectors
core-admin vectors sync --write
core-admin vectors query "<query>" --collection policies|patterns|specs --limit <n>

# Sync
poetry run core-admin dev sync --write

# DB (only when no core-admin command covers the need)
PGPASSWORD=core_db psql -U core_db -d core -h 192.168.20.23
```

---

## Architecture Reference

**The autonomous loop:**
```
AuditViolationSensor (×7 namespaces)
    → posts findings to Blackboard
ViolationRemediatorWorker (Will)       ← daemonized
    → claims MAPPED findings, creates Proposals
    → releases unmapped findings back to open
ViolationExecutorWorker (Will)         ← active, fully proven
    → claims UNMAPPED findings
    → delegates ceremony to ViolationRemediator (Body)
    → surfaces AtomicAction candidates to Blackboard
ProposalConsumerWorker                 ← daemonized
    → executes APPROVED proposals via ProposalExecutor
AuditViolationSensor
    → confirms finding resolved or re-posts
BlackboardShopManager                  ← active
    → monitors Blackboard SLA health
WorkerShopManager                      ← active
    → monitors worker liveness
CommitReachabilityAuditor              ← active (hourly)
    → detects orphan post_execution_sha commits
CoherenceSensorWorker                  ← active (every 10 min)
    → detects sensor-fixer incoherence via consequence chain query
```

**Two remediation paths:**
- Proposal Path (constitutional): Finding → RemediationMap → Proposal → AtomicAction
- ViolationExecutor Path (discovery fallback): Finding → LLM → Crate → AtomicAction candidate

**Gate order on every write:**
```
ConservationGate → IntentGuard → Canary
```

**Repository layers:**
```
.specs/     ← human intent layer (charter, papers, URS, ADRs, plans) → core_specs
.intent/    ← operational governance (constitution, rules, enforcement, workers) → core_policies, core-patterns
src/        ← implementation → core-code
infra/      ← infrastructure (DB migrations, SQL schema)
```

**Module path notes:**
- `AuditorContext` lives at `src/mind/governance/audit_context.py`.

**Vector collections:**
```
core_specs      ← .specs/ markdown documents
core_policies   ← .intent/ governance policies and rules
core-patterns   ← .intent/ architecture patterns
core-code       ← src/ code symbols
```
