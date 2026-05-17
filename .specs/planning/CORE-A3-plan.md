# CORE — A3 Governed Autonomy Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-05-17
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

**All Band D work complete.** All four A3 gates closed. Next focus is Band E (Outward-Facing) or Band C (Historical Debt) — to be sequenced in the next planning session.

- **Band A — Attribution** (closed): https://github.com/DariuszNewecki/CORE/milestone/13
- **Band B — Consequence Chain** (closed): https://github.com/DariuszNewecki/CORE/milestone/14
- **Band C — Historical Debt** (deferred): https://github.com/DariuszNewecki/CORE/milestone/15
- **Band D — Engine Integrity** (closed): https://github.com/DariuszNewecki/CORE/milestone/16
- **Band E — Outward-Facing** (deferred): https://github.com/DariuszNewecki/CORE/milestone/17

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
| ADR-055 | 2026-05-17 | API Phase 2: /fix + /quality | /fix and /quality namespaces defined; fix_runs resource table; generic atomic dispatch via ActionExecutor; FlowExecutor for /fix/all; sync/async split for quality checks. |

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
