# CORE — State of the Project

**Snapshot date:** 2026-04-18
**Source of truth:** `context_core.txt` export generated 2026-04-18T08:14:09 (131,109 lines, 1,025 files)
**Purpose:** Honest structural snapshot of what CORE *is*, layer by layer. No roadmap, no judgment — just what exists and how it fits together. Where the code disagrees with memory or the A3 plan, the code is the authority.

This document is descriptive, not prescriptive. Its job is to become the shared baseline for later artifacts (claims audit, risk register, capability gap analysis).

---

## 1. Scope of this snapshot

The export covers three domains:

| Domain | Files | What it is |
|--------|-------|------------|
| `src/` | 838 | Implementation — the running code |
| `.intent/` | 132 | Governance layer — rules, workers, enforcement, schemas |
| `.specs/` | 55 | Intent layer — charter, papers, requirements, plans |

The export deliberately excludes:

- `infra/` — DB migrations, SQL schema, deployment config
- `docs/` — MkDocs site source
- `tests/` — test suite (if one exists as a top-level directory)
- Project root files — `pyproject.toml`, `README.md`, `CONTRIBUTING.md`, `.pre-commit-config.yaml`, `mkdocs.yml`

Therefore, **no claim in this document depends on infra, docs, tests, or packaging**. Those are out of view and will need a separate snapshot if they matter.

---

## 2. Repository layout at a glance

```
src/        838 files   implementation
├── cli/            234   command surface (≈28% of src/)
├── will/           192   orchestration, workers, agents, phases
├── body/           167   execution, services, atomic actions
├── shared/         166   infrastructure, models, utilities
├── mind/            71   policy, governance, engines/gates
├── api/              7   FastAPI stub (health check only)
└── main.py           1   FastAPI entry

.intent/    132 files   governance
├── enforcement/     36   mappings (33), config (2), remediation (1)
├── rules/           32   rule documents across 8 namespaces
├── workers/         28   worker declarations (YAML)
├── workflows/       15   workflow definitions
├── META/            10   schemas for .intent/ artifacts
├── phases/           6   phase definitions
├── constitution/     2   CORE-CONSTITUTION-v0.md, CONSTITUTIONAL-WORKFLOWS.md
└── (taxonomies, cim, CHANGELOG — 3 more)

.specs/      55 files   intent and architectural reasoning
├── papers/          47   architectural papers
├── northstar/        3   north-star documents
├── requirements/     3   URS documents
├── planning/         1   CORE-A3-plan.md
└── CORE-CHARTER.md   1   founding declaration
```

Two layers are visibly larger than the architecture model suggests they should be:

- **`shared/`** is 166 files — larger than `mind/` (71) and comparable to `body/` (167). Of those, 89 are in `shared/infrastructure/`. ✅ **Resolved 2026-04-18:** Complete boundary audit completed via ADR-002. Constitutional violations resolved through architectural moves.
- **`cli/`** is 234 files — 28% of `src/`. 93 of those are under `cli/resources/`, distributed across 14 command groups.

---

## 3. Intent layer (`.specs/`)

### 3.1 Charter and north star

- `CORE-CHARTER.md` — founding declaration.
- `northstar/core_northstar.md`, `CORE - What It Does.md`, `CORE-USER-REQUIREMENTS.md` — three documents at the north-star layer.

### 3.2 Architectural corpus (47 papers)

The `.specs/papers/` directory holds a substantial body of architectural reasoning — 47 papers covering concepts including: Action, Blackboard, Canary, ConservationGate, Constitutional Foundations, Constitutional Envelope, ConsumerWorker, Context Packet Doctrine, Crate, Deliberate Non-Goals, Evidence as Input, Finding, Gate, IntentGuard, IntentRepository, Mind-Body-Will Separation, OptimizerWorker, Phases as Governance Boundaries, Proposal, RemediationMap, RemediatorWorker, Rule Canonical Form, Rule Conflict Semantics, Rule Evaluation Semantics, Rule Storage Minimalism, ShopManager, ViolationExecutor, ViolationSensor, Workers and Governance Model, Workflow Papers First, and more.

This is an unusually complete architectural corpus for a solo project.

### 3.3 Requirements (3 URS documents)

- `CORE-Ask-URS.md`
- `CORE-Governor-Ask-URS.md`
- `CORE-Governor-Dashboard-URS.md`

The A3 plan targets "one URS per command group" in Phase 4. With 14 command groups and 3 URS documents, the URS layer is roughly 20% populated relative to that target.

### 3.4 Gaps in `.specs/`

Two directories referenced by the plan as intended structure are **not present** in the export:

- `.specs/META/` — schema for `.specs/` artifacts (plan marks as "not yet authored")
- `.specs/decisions/` — ADRs (planned but not yet started) ✅ **Update:** ADR-002 established 2026-04-18

This matters because architectural decisions are being made actively (the A3 plan lists ten in recent weeks) and they are not being captured as ADRs. They live in the plan document, in commit messages, and in memory — none of which are durable or queryable.

---

## 4. Governance layer (`.intent/`)

### 4.1 Rules — 153 defined, 121 with explicit enforcement

Across 32 rule documents in 8 namespaces, **153 individual rule IDs** are defined. Of those, **121 have explicit enforcement fields** — matching the 121 tracked by the audit. The remaining 32 are either wrappers, duplicates, or rules without enforcement bindings; the distinction is worth resolving but does not affect runtime.

Breakdown of the 121 enforceable rules:

| Enforcement | Count |
|-------------|-------|
| `blocking` | 63 |
| `reporting` | 51 |
| `advisory` | 7 |

Breakdown by namespace (individual rule IDs):

| Namespace | Rules | Files |
|-----------|-------|-------|
| architecture | 67 | 14 |
| code | 32 | 7 |
| ai | 17 | 4 |
| infrastructure | 13 | 2 |
| will | 10 | 2 |
| cli | 8 | 1 |
| data | 4 | 1 |
| governance | 2 | 1 |

Architecture rules dominate the rule-base (55% of all rule IDs). This is consistent with the architectural discipline of the project.

### 4.2 Workers — 28 declared, 12 active, 16 paused

All worker declarations live in `.intent/workers/*.yaml`. The daemon (`src/will/commands/daemon.py`) dynamically discovers them at start-up and starts only those with `metadata.status: active`.

**12 active workers:**

| Worker | Role |
|--------|------|
| `audit_sensor_architecture` | Sensor — architecture namespace |
| `audit_sensor_purity` | Sensor — purity namespace |
| `audit_sensor_logic` | Sensor — logic namespace |
| `audit_sensor_modularity` | Sensor — modularity namespace |
| `audit_sensor_layout` | Sensor — layout namespace |
| `audit_sensor_style` | Sensor — style namespace |
| `audit_sensor_linkage` | Sensor — linkage namespace |
| `violation_remediator` | Will — claims mapped findings, creates proposals |
| `violation_executor` | Will — claims unmapped findings, surfaces candidates |
| `proposal_consumer_worker` | Executes approved proposals |
| `blackboard_auditor` | Monitors Blackboard SLA health |
| `worker_auditor` | Monitors worker liveness |

**16 paused workers:**

`audit_ingest_worker`, `audit_violation_sensor`, `call_site_rewriter`, `capability_tagger`, `doc_worker`, `doc_writer`, `intent_inspector`, `observer_worker`, `prompt_artifact_writer`, `prompt_extractor_worker`, `proposal_worker` *(superseded by `proposal_consumer_worker`)*, `repo_crawler`, `repo_embedder`, `self_healing_agent`, `test_runner_sensor` *(Stream B dependency)*, `violation_remediator_body`.

The `violation_remediator_body` being paused while `violation_remediator` is active is **noteworthy** ✅ **Resolved:** obs-8.6 clarified via ADR-002 — two distinct workers with different purposes separated properly into Will layer.

### 4.3 Enforcement mappings — 33

`.intent/enforcement/mappings/` holds 33 mapping files. Each binds a rule (or rule family) to the engine that evaluates it and, where applicable, to the remediation action that repairs it.

### 4.4 Remediation map — 14 ACTIVE, 5 PENDING

`.intent/enforcement/remediation/auto_remediation.yaml` is a single file binding finding `check_id`s to atomic-action handlers.

**14 ACTIVE mappings** (safe_only tier, confidence ≥ 0.90):

`style.import_order`, `linkage.duplicate_ids`, `purity.no_todo_placeholders`, `linkage.assign_ids`, `logic.logging.standard_only`, `architecture.channels.logger_not_presentation`, `architecture.channels.logic_no_terminal_rendering`, `purity.stable_id_anchor`, `layout.src_module_header`, `style.formatter_required`, `workflow.ruff_format_check`, `purity.docstrings.required`, `architecture.atomic_actions.must_return_action_result`, `modularity.needs_split` (high-risk tier, 0.85, two-phase LLM with Logic Conservation Gate).

**5 PENDING mappings** (documented but not dispatched, confidence < 0.80):

`modularity.needs_refactor`, `architecture.constitution_read_only`, `code.imports.no_stale_namespace`, `architecture.mind.no_body_invocation`, `governance.mutation_surface.filehandler_required`.

Coverage ratio: 14 ACTIVE mappings against 121 enforceable rules. **Roughly 88% of rules do not have an autonomous fixer.** This is not necessarily wrong — some rules are reporting-only, some require human judgment, some are waiting on PENDING actions — but it is a structural fact worth stating plainly. The daemon's autonomous reach is bounded by this ratio.

### 4.5 Constitution

Two constitutional documents:

- `.intent/constitution/CORE-CONSTITUTION-v0.md`
- `.intent/constitution/CONSTITUTIONAL-WORKFLOWS.md`

### 4.6 Schemas (META)

10 schemas in `.intent/META/` define the shape of intent-tree artifacts, rule documents, worker declarations, workflow definitions, workflow stages, and vocabulary. The `.intent/` directory has its own schema layer; `.specs/` does not.

---

## 5. Implementation layer (`src/`)

### 5.1 Mind — policy and gates (71 files)

- `mind/logic/engines/` — 44 files. Contains the full gate stack: `action_gate`, `artifact_gate`, `ast_gate` (a package with 16 individual check modules covering async, capability, conservation, generic, import_boundary, import, intent_access, knowledge_source, logging, metadata, modularity, naming, prompt_model, purity, and purity_enforcement), `glob_gate`, `knowledge_gate`, `llm_gate`, `llm_gate_stub`, `passive_gate`, `regex_gate`, `workflow_gate`, `engine registry`. `ast_gate.py` exists at two paths — a backward-compat shim re-exports from the modularized package.
- `mind/governance/` — 24 files.
- `mind/enforcement/` — 2 files.

### 5.2 Body — execution (167 files)

- `body/services/` — 38 files. Includes `blackboard_service.py` (659 lines), `worker_registry_service.py`, `intent_schema_validator.py`, crawl service.
- `body/self_healing/` — 27 files. Test-context analysis subsystem.
- `body/introspection/` — 21 files.
- `body/atomic/` — 15 files. Contains the atomic-action registry. Registered action handlers: `fix.atomic_actions`, `fix.docstrings`, `fix.duplicate_ids`, `fix.format`, `fix.headers`, `fix.ids`, `fix.imports`, `fix.logging`, `fix.modularity`, `fix.placeholders`. Support modules: `executor`, `registry`, `modularity_splitter`, `split_plan`, `file_ops`, `metadata_ops`, `sync_actions`, `check_actions`, `crate_ops`, `import_resolver`, `build_tests_action`, `remediate_cognitive_role`.
- `body/workers/` — 10 files including the `violation_remediator/` package.
- `body/maintenance/`, `body/governance/`, `body/evaluators/`, `body/analyzers/` — smaller subsystems.

### 5.3 Will — orchestration (192 files)

- `will/self_healing/` — 37 files.
- `will/agents/` — 29 files. Includes `strategic_auditor/`.
- `will/tools/` — 21 files.
- `will/test_generation/` — 20 files (Stream B infrastructure exists but is not activated).
- `will/phases/` — 20 files.
- `will/workers/` — 18 files. The 12-active / 16-paused split is expressed here plus in `body/workers/`.
- `will/commands/daemon.py` — the daemon entry point.
- `will/autonomy/proposal_executor.py` — 639 lines.

### 5.4 Shared — infrastructure and utilities (166 files)

- `shared/infrastructure/` — 89 files. The largest sub-layer in the project. Includes `context/builder.py` (743 lines) — critical because a context build is required before every Claude Code prompt — and `intent/intent_repository.py` (659 lines) — the trusted access path to `.intent/`.
- `shared/models/` — 17 files.
- `shared/utils/`, `shared/self_healing/` — 11 files each.
- `shared/protocols/` — 7 files.
- Plus roughly 20 top-level files in `shared/` (logger, config_loader, exceptions, component_primitive, atomic_action, action_types, path_resolver, etc.).

### 5.5 CLI (234 files)

`src/cli/resources/` holds the command surface — 93 files across 14 command groups:

| Group | Files |
|-------|-------|
| `code` | 17 |
| `admin` | 14 |
| `database` | 9 |
| `vectors` | 8 |
| `dev` | 8 |
| `symbols` | 7 |
| `context` | 6 |
| `proposals` | 5 |
| `constitution` | 5 |
| `workers` | 4 |
| `project` | 4 |
| `secrets` | 3 |
| `runtime` | 2 |

The remaining 141 files in `src/cli/` are plumbing: command wiring, option definitions, output formatters, CLI utilities.

### 5.6 API

`src/main.py` is a FastAPI application with a single `/healthz` endpoint. `src/api/` has 7 files. The API layer is stub-level and not load-bearing.

### 5.7 Daemon contract

`src/will/commands/daemon.py` is the canonical entry point for the autonomous loop. Its contract:

1. Scan `.intent/workers/*.yaml`.
2. For each file with `metadata.status: active`, resolve `implementation.module` and `implementation.class`.
3. Instantiate the worker with progressively simpler kwargs (full → standard → bare, each optionally with `core_context`) until one succeeds.
4. If the worker has `run_loop()`, schedule it. Otherwise wrap `start()` in a periodic loop with `max_interval` seconds.
5. Await SIGTERM/SIGINT, then cancel all tasks.

The worker set is entirely declaration-driven — no hardcoded list. Changing `status` in a YAML file is how a worker is activated or paused. This is clean.

---

## 6. Runtime contract — the autonomous loop

Reconstructed from the A3 plan and verified against the code:

```
AuditViolationSensor (×7 namespaces)
  → post finding (check_id, subject, evidence) to Blackboard
ViolationRemediator (Will)
  → if finding in remediation map → create Proposal
  → else → release back to open (let ViolationExecutor claim it)
ViolationExecutor (Will, discovery path)
  → claim UNMAPPED finding
  → delegate ceremony to body/workers/violation_remediator/ (Body)
  → surface AtomicAction candidates to Blackboard
ProposalConsumer
  → pick up APPROVED proposals → execute via ProposalExecutor
AuditViolationSensor
  → re-sense — finding either resolves or re-posts
BlackboardAuditor
  → monitor Blackboard SLA health
WorkerAuditor
  → monitor worker liveness
```

Gate order on every write:

```
ConservationGate → IntentGuard → Canary
```

The two remediation paths:

- **Proposal Path** (constitutional): finding → `auto_remediation.yaml` → proposal → atomic action
- **ViolationExecutor Path** (discovery fallback): finding → LLM → crate → candidate

---

## 7. Data contract and out-of-view state

The autonomous loop depends on a PostgreSQL database (`core` at `192.168.20.23:5432`) with at least these tables, referenced in code or the A3 plan:

- `core.blackboard_entries`
- `core.autonomous_proposals` (current)
- `core.proposals` (legacy, documented but "always truncate the correct table")
- `core.worker_registry`
- `core.audit_runs` (plan flags an unresolved write gap — `core-admin code audit` does not persist)

The live schema is referenced in the plan at `infra/sql/db_schema_live.sql`. **This file is not in the export.** Any analysis that depends on column names, indices, foreign keys, or constraints cannot be grounded against the export and will need a separate infra snapshot.

Vector collections referenced by the plan:

- `core_specs` — `.specs/` markdown (549 items, 53 files)
- `core_policies` — `.intent/` governance policies and rules
- `core-patterns` — `.intent/` architecture patterns
- `core-code` — `src/` code symbols

These live in Qdrant. Their schemas and payload structure are not in the export.

---

## 8. Observations worth attention

These are structural observations from reading the repository, not opinions about priority. They are things the architecture documents and memory do not currently record.

### 8.1 `shared/` is larger than `mind/` ✅ Resolved 2026-04-18

**Original hypothesis:** `shared/infrastructure/intent/intent_repository.py` (659 lines) "arguably closer to Body than to a layer-neutral utility."

**Resolution:** Empirical import topology analysis during shared/ boundary audit disproved this hypothesis. `intent_repository.py` has genuine multi-layer usage:
- Mind: 2 importers
- Body: 6 importers
- Will: 5 importers
- CLI: 4 importers

**Conclusion:** `intent_repository.py` correctly placed in `shared/` — serves multiple layers with no layer bias. Original concern was valid (large shared/ layer warrants audit) but the specific hypothesis about intent_repository placement was incorrect.

**Related work:** Complete shared/ boundary audit completed 2026-04-18 via ADR-002. All constitutional violations resolved through architectural moves, not rule exceptions.

### 8.2 Several large modules that the modularity sensor is not flagging

The top files by line count:

| Lines | File |
|-------|------|
| 780 | `cli/resources/runtime/health.py` |
| 743 | `shared/infrastructure/context/builder.py` |
| 659 | `shared/infrastructure/intent/intent_repository.py` |
| 659 | `body/services/blackboard_service.py` |
| 639 | `will/autonomy/proposal_executor.py` |
| 600 | `shared/self_healing/remediation_interpretation/file_role_detector.py` |
| 591 | `shared/ai/prompt_model.py` |
| 584 | `will/agents/strategic_auditor/context_gatherer.py` |
| 579 | `body/atomic/sync_actions.py` |

The plan reports 0 findings. Either these files are under the modularity threshold, are explicitly exempted, or fall into the dominant-class heuristic that treats single-responsibility classes as acceptable regardless of size. Worth confirming which.

### 8.3 No ADRs despite active architectural decision-making ✅ Partially Resolved 2026-04-18

The A3 plan lists ten significant architectural decisions made between 2026-04-15 and 2026-04-17. ADR-002 established for shared/ boundary enforcement. Decision record discipline now active.

### 8.4 No `.specs/META/` schemas

`.intent/` has ten META schemas governing its own artifacts. `.specs/` has none. Anyone authoring a paper, requirement, or plan today has no machine-checkable shape to conform to.

### 8.5 Remediation coverage is ~12% of rules

14 ACTIVE remediation mappings against 121 enforceable rules. This is an intentional state (not every rule can or should be auto-remediated) but it frames the autonomous-reach ceiling of the current system more honestly than "autonomous loop working" suggests.

### 8.6 `violation_remediator_body` paused, body package still in use ✅ Resolved 2026-04-18

**Resolution:** Two distinct workers clarified via ADR-002. `will/workers/violation_remediator.py` (active daemon Blackboard consumer) and `will/workers/violation_remediator_body/` (cognitive planning logic moved from body/ to will/ layer). Both serve different purposes and correctly coexist in Will layer.

### 8.7 No top-level `tests/` directory in the export

This could mean (a) tests exist outside the export scope, (b) tests exist under a different name, or (c) there is no test suite. The A3 plan's Stream B ("test writing") and the existence of `will/test_generation/` suggest test-writing is a capability CORE intends to *build*, not an established suite it already runs. Worth confirming — this has significant implications for what "A3 audit PASSED" means.

### 8.8 CLI surface is 28% of `src/`

234 files. The A3 plan's Phase 4 ("CLI Health") targets inventory, broken-command repair, legacy removal, and URS generation. The scale of that phase is commensurate with the surface area.

---

## 9. What this document does not tell you

- Whether the daemon is currently running — requires `systemctl --user status core-daemon`.
- Current Blackboard state — requires `core-admin workers blackboard` or a DB query.
- Current `core.worker_registry` state — requires a DB query.
- Whether the audit's "0 findings" claim holds today — requires `core-admin code audit`.
- Anything about `infra/`, `docs/`, `tests/`, or project-root packaging files.
- Git history, commit cadence, or branch state.
- Runtime performance, latency, or resource usage.

Each of these is recoverable with a single command via Claude Code. They are deliberately out of scope for *this* artifact, which is a structural snapshot of the code as it sits on disk.

---

## 10. Summary

CORE, as of 2026-04-18, is a project with:

- **A rich intent layer** — 47 papers, a charter, a north star, 3 URS documents — unusually complete for a solo project.
- **A declarative governance layer** — 121 enforceable rules, 28 workers (12 active), 14 ACTIVE + 5 PENDING remediation mappings, all driven by YAML and discoverable without code changes.
- **A large implementation layer** — 838 source files, with constitutional layer boundaries now properly enforced via ADR-002.
- **A clean daemon contract** — declaration-driven worker discovery, no hardcoded activation, graceful instantiation fallback.
- **Known out-of-view dependencies** — PostgreSQL, Qdrant, systemd, and an `infra/` directory this snapshot cannot see.

The A3 plan reports the autonomous loop PASSED end-to-end via one mapped rule (`style.formatter_required`). That is one data point of autonomy, not comprehensive autonomy. The structural facts in this document frame what "autonomy" means today: a system that can close the loop on ~12% of its own rules deterministically, with the other 88% either reporting-only, human-gated, or awaiting PENDING actions.

Whether that ratio should grow, stay, or shrink is a question for the next artifact. This one just records where things stand.
