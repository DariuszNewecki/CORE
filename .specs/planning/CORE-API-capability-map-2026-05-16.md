# CORE API Capability Map — 2026-05-16

Operator-capability map of every `.py` file under `src/cli/commands/`, with proposed `api/*` endpoint clustering. Produced as the supporting artifact for ADR-053 (CORE API as Resource-Oriented Governance Interface) following the ADR-050 audit that established the CLI as an external operator client.

Files are grouped by their immediate subdirectory of `src/cli/commands/`. Each line lists: filename | one-line operator capability | CORE subsystems the file reaches directly (after `cli.logic/*` carve-outs, but before ADR-053 routing through `api/*`).

---

```
GROUP: (root)
  audit_reporter.py | Structured reporter helper for audit runs (header/phase/checks/summary) | mind, shared
  check_atomic_actions.py | Check and list atomic actions pattern compliance across codebase | body, shared
  components.py | List/inspect V2 architectural components (interpreters, analyzers, evaluators, etc.) | shared
  daemon.py | Start the background worker daemon (autonomous worker lifecycle) | shared (also body/will inside function bodies)
  develop.py | Trigger an autonomous refactoring cycle from a goal or file path | shared, will
  dev_sync.py | Run the fix-then-sync workflow (heal code, then sync DB and vectors) | body, shared
  diagnostics.py | Register legacy diagnostic shims (policy-coverage, manifest-hygiene, cli-registry, legacy-tags) | (cli.logic only)
  fix_governed.py | Fix docstrings on files only after per-file governance pre-check | body, shared
  fix_logging.py | Deprecated re-export shim for body logging fixer | body
  governance.py | Show constitutional enforcement coverage; run a 5-gate validate-request preview | mind, shared, will (inside fn body)
  guard.py | Run capability-drift analysis (manifest vs code) and emit JSON evidence | body, mind
  __init__.py | Package marker | —
  interactive_test.py | Interactive step-by-step test generation with operator approval | shared
  mind.py | Validate .intent documents against the GLOBAL-DOCUMENT-META-SCHEMA | mind, shared (inside fn body)
  refactor.py | Analyze/suggest/score modularity refactoring candidates | shared (delegates to refactor_support which imports mind)
  repo_census.py | Run CIM-0 mechanical repo census; write JSON artifact | body, shared
  run.py | Vectorize codebase artifacts via the worker pipeline (sync.vectors.code) | shared
  search.py | Semantic search for capabilities and fuzzy CLI command lookup | shared
  status.py | Consolidated drift entry (guard/symbol/vector/all); delegates to inspect | mind, shared
  submit.py | Deprecated shim pointing to 'proposals integrate' | —

GROUP: check
  __init__.py | Wires the check_app Typer group registrations | —
  audit.py | Run the full constitutional self-audit and persist findings to DB | mind, shared
  converters.py | Helper: convert raw engine findings to AuditFinding models | shared
  diagnostics_commands.py | Run policy-coverage diagnostic and Body-UI contract check | shared (cli.logic)
  formatters.py | Helper: render audit findings tables, summaries, AI-workflow hints | shared
  imports.py | Verify import statements resolve and have no stale namespaces | body
  quality_gates.py | Run the six industry quality gates (ruff/mypy/pytest/pip-audit/radon/vulture) | shared
  quality.py | Run lint, run pytest, and run the system-wide health bundle | mind, shared
  rule.py | Run filtered audit scoped by rule/policy/pattern/files | mind, shared
  utils.py | Helper: iterate Python target files under a path | —

GROUP: coverage
  __init__.py | Registers coverage subcommands | —
  analysis_commands.py | Show coverage history and compare legacy vs adaptive methods | shared
  check_commands.py | Check coverage compliance; render reports; show targets and gaps | shared
  generation_commands.py | Adaptive test generation for one file or a prioritised batch | body, will
  services/__init__.py | Re-exports service classes | —
  services/coverage_checker.py | Service: audit coverage rules via filtered audit | mind, shared
  services/coverage_reporter.py | Service: run coverage.py text/HTML report subprocesses | shared
  services/gaps_analyzer.py | Service: compute low-coverage module gaps and priorities | body, shared

GROUP: fix
  __init__.py | Define fix_app Typer group, COMMAND_CONFIG, dynamic submodule imports | shared
  all_commands.py | Run the curated 'fix all' sequence of self-healing steps | body, shared, will
  atomic_actions.py | Fix atomic-action pattern violations via ActionExecutor | body, shared
  audit.py | Autonomously remediate audit findings (safe/medium/all modes) with validation | body, shared, will
  body_ui.py | Use LLM to rewrite Body-layer modules violating UI/env contracts | shared (cli.logic)
  code_style.py | Fix file-header compliance via header service atomic action | body, shared
  db_tools.py | Sync the CLI command tree and vectors to PostgreSQL/Qdrant | body, shared
  fix_ir.py | Bootstrap IR triage and incident-response log YAML files | shared
  handler_discovery.py | List all registered atomic actions from the registry | body
  imports.py | Sort/group imports per PEP 8 via ruff's I rules | shared
  list_commands.py | Render a table of all 'fix' subcommands and their flags | —
  metadata.py | Metadata fixers: purge legacy tags, policy-ids, capability tags, duplicate-ids, placeholders, dead-code | body, shared, will
  modularity.py | Autonomously modularize architectural offenders via A3 loop | shared, will
  settings_access.py | Refactor settings imports to DI via CoreContext | body, shared

GROUP: inspect
  __init__.py | Mounts all inspect subcommand groups | —
  _helpers.py | Helpers: render session/recent/pattern traces, statistics | body (TYPE_CHECKING only)
  analysis.py | Inspect semantic clusters, code duplication, and consolidation opportunities | shared (cli.logic)
  decisions.py | Inspect autonomous decision traces (recent, by session, by agent, by pattern, stats) | body, shared
  diagnostics.py | Inspect CLI command-tree and SIMPLE/COMPLEX test-target classification | body, shared
  drift.py | Inspect symbol drift and vector drift (PG vs Qdrant); register guard commands | mind, shared (cli.logic)
  patterns.py | Analyze pattern classification and violations across decision traces | shared
  refusals.py | List/filter constitutional refusal records (by type, session, stats) | shared (cli.logic)
  repo_census.py | Run CIM census with snapshot/baseline/diff support | body, shared
  status.py | Show database connection and migration status | shared (cli.logic)

GROUP: refactor_support
  __init__.py | Package marker | —
  analyzer.py | Helper: compute modularity scores per file/codebase | mind
  config.py | Helper: load modularity threshold from constitution; enumerate source files | mind, shared
  display.py | Helper: Rich rendering for refactor analyses | —
  recommendations.py | Helper: emit refactoring recommendation strings from breakdown | shared


CANDIDATE API ENDPOINTS

# Constitutional audit
POST /audit/runs                    Full constitutional self-audit; persist to core.audit_findings — covers: check/audit.py, audit_reporter.py
POST /audit/runs:filtered           Audit scoped by rule_ids/policy_ids/patterns/files — covers: check/rule.py, coverage/services/coverage_checker.py
GET  /audit/findings                Latest findings with severity/check filters — covers: check/converters.py, check/formatters.py
POST /audit/remediations            Autonomously remediate findings (mode=safe|medium|all, write) — covers: fix/audit.py
GET  /audit/coverage                Constitutional rule enforcement coverage — covers: governance.py, check/diagnostics_commands.py, diagnostics.py

# Pre-flight validation
POST /governance/validations        5-gate pre-flight validation of a request — covers: governance.py (validate-request)
GET  /meta/validation               Validate .intent docs against META-SCHEMA — covers: mind.py

# Code quality / lint / test infra
POST /quality/lint                  Ruff/Black lint check — covers: check/quality.py, fix/imports.py
POST /quality/tests                 Run pytest — covers: check/quality.py
POST /quality/system                Lint + tests + audit bundle — covers: check/quality.py
POST /quality/gates                 Six industry quality gates — covers: check/quality_gates.py
POST /quality/imports               Verify imports resolve — covers: check/imports.py
POST /quality/body-ui               Body-layer UI/env contract check — covers: check/diagnostics_commands.py

# Self-healing fixes
GET  /fix/commands                  List fix commands and their config — covers: fix/list_commands.py, fix/__init__.py
POST /fix/run/{fix_id}              Generic dispatch (headers/ids/docstrings/atomic-actions/placeholders/duplicate-ids/body-ui/settings-di/dead-code/imports) — covers: fix/code_style.py, fix/atomic_actions.py, fix/metadata.py, fix/body_ui.py, fix/settings_access.py, fix_governed.py, fix_logging.py
POST /fix/all                       Curated sequence — covers: fix/all_commands.py
POST /fix/modularity                A3-loop autonomous modularity remediation — covers: fix/modularity.py
POST /fix/ir/{triage|log}           Bootstrap IR triage/incident logs — covers: fix/fix_ir.py

# Atomic actions
GET  /actions                       List registered atomic actions — covers: fix/handler_discovery.py
GET  /actions/audit                 Atomic-action pattern compliance — covers: check_atomic_actions.py

# Components & search
GET  /components                    Discover V2 components by package — covers: components.py
GET  /search/capabilities           Semantic search over capability vectors — covers: search.py
GET  /search/commands               Fuzzy CLI registry search — covers: search.py

# Sync (DB and vectors)
POST /sync/db-registry              CLI command tree → PostgreSQL — covers: fix/db_tools.py
POST /sync/vectors                  Bidirectional PG↔Qdrant — covers: fix/db_tools.py
POST /sync/code-vectors             Vectorize via worker pipeline — covers: run.py
POST /sync/dev-sync                 Fix + DB + vector workflow — covers: dev_sync.py

# Daemon / workers
POST /daemon/start | /daemon/stop   Background worker daemon lifecycle — covers: daemon.py

# Coverage (test)
GET  /coverage/check                Compliance vs constitutional rules — covers: coverage/check_commands.py, coverage/services/coverage_checker.py
GET  /coverage/report               Text/HTML coverage report — covers: coverage/check_commands.py, coverage/services/coverage_reporter.py
GET  /coverage/targets              Constitutional coverage targets — covers: coverage/check_commands.py
GET  /coverage/gaps                 Low-coverage modules ranked — covers: coverage/check_commands.py, coverage/services/gaps_analyzer.py
GET  /coverage/history              Coverage trends — covers: coverage/analysis_commands.py
GET  /coverage/methods              Legacy vs adaptive comparison — covers: coverage/analysis_commands.py
POST /coverage/generate             Adaptive test generation, single file — covers: coverage/generation_commands.py
POST /coverage/generate:batch       Prioritised batch — covers: coverage/generation_commands.py
POST /tests/interactive             Interactive step-by-step session — covers: interactive_test.py

# Refactor / modularity (read-only)
GET  /refactor/score?file=...       Per-file modularity score — covers: refactor.py, refactor_support/analyzer.py, refactor_support/display.py, refactor_support/recommendations.py
GET  /refactor/candidates           Files exceeding threshold — covers: refactor.py
GET  /refactor/stats                Aggregate modularity distribution — covers: refactor.py
GET  /refactor/threshold            Threshold from constitution — covers: refactor_support/config.py
POST /refactor/autonomous           Trigger autonomous refactor cycle — covers: develop.py

# Inspection / status / drift / traces / decisions
GET  /status/db                     DB connection + migrations — covers: inspect/status.py
GET  /status/drift?scope=...        Consolidated drift report — covers: status.py, inspect/drift.py, guard.py
GET  /decisions                     Decision traces (recent/session/agent/pattern/stats) — covers: inspect/decisions.py, inspect/_helpers.py
GET  /decisions/patterns            Pattern-classification stats — covers: inspect/patterns.py
GET  /refusals                      Constitutional refusal listings — covers: inspect/refusals.py
GET  /analysis/clusters             Semantic capability clusters — covers: inspect/analysis.py
GET  /analysis/duplicates           Semantic code duplication — covers: inspect/analysis.py
GET  /analysis/common-knowledge     DRY-violation candidates — covers: inspect/analysis.py
GET  /analysis/command-tree         Hierarchical CLI tree — covers: inspect/diagnostics.py
GET  /analysis/test-targets         SIMPLE/COMPLEX classification — covers: inspect/diagnostics.py

# Repository census (CIM-0)
POST /census/runs                   Mechanical repo census; optional snapshot — covers: repo_census.py, inspect/repo_census.py
POST /census/baselines/{name}       Create/list census baselines — covers: inspect/repo_census.py
GET  /census/diff?baseline=...      Diff against baseline — covers: inspect/repo_census.py

# Deprecated / shims (do not surface)
submit.py, fix_logging.py, diagnostics.py — keep as CLI compatibility shims pointing to canonical endpoints above.
```

## Cross-cutting observations

- `body/self_healing/*` is already the de-facto self-healing surface — a single `POST /fix/run/{fix_id}` dispatcher absorbs ~12 CLI files with thin renderers.
- `mind.governance.*` is reached from `check/audit.py`, `check/quality.py`, `check/rule.py`, `coverage/services/coverage_checker.py`, `governance.py`, `mind.py`, `inspect/drift.py`, `refactor_support/{config,analyzer}.py` — all collapse to `/audit/*` and `/governance/*`.
- `body.atomic.executor.ActionExecutor` and `body.atomic.registry.action_registry` are already a service registry — promoting to `POST /actions/{id}` + `GET /actions` is mostly plumbing.
- `inspect/_helpers.py` and `check/formatters.py` are pure presentation — keep client-side after migration (CLI renders the JSON the API returns).
- `daemon.py` legitimately needs broad system access; its API form is a lifecycle wrapper, not a refactor.
- Some files already import from `cli.logic.*` (e.g. `body_ui.py`, `drift.py`, `refusals.py`, `status.py`, `analysis.py`) — that pattern is a partial ADR-050 extraction and a model for the rest.

## Numbers

- **58** `.py` files scanned
- **193** distinct forbidden import targets (per ADR-050 prefixes: `will.*`, `body.*`, `mind.*`, `shared.*` and their `src.` variants)
- **~40** proposed endpoints across **10** domain clusters (audit, governance, quality, fix, actions, sync, daemon, coverage, refactor, inspect/census)
- Largest two clusters by file count: `/fix/*` (~12 files), `/audit/*` (~8 files) — natural candidates for ADR-053 Phase 1
