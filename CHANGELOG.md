# Changelog

All notable changes to this project are documented in this file.

This project follows **Keep a Changelog** and **Semantic Versioning**, but with an explicit focus on **governance maturity and autonomy progression**, not just features.

---

## [Unreleased]

---

## [2.9.1] — 2026-07-12

### 🐛 BYOR write-flow fixes (Phase 5 smoke-test follow-up)

Fixes arising from the `core-cli 1.0.1` release smoke test's Phase 5
write-flow exercise (`.specs/planning/CORE-CLI-2.9.0-Followups.md`).

- **Clean 4xx instead of a raw 500 on `onboard`/`promote` failures —
  `f17c7a8f`, `0a0d5701`.** Two distinct bugs, both server-side
  (`src/cli/logic/byor.py`, `src/api/v1/project_routes.py`): (1)
  `mkdir`/`shutil.copy2` and the pre-write `target_intent.exists()`
  overwrite-guard check could both raise a raw `OSError` (e.g. a
  permission-denied target path) that leaked straight into the HTTP
  response body as a 500; (2) `typer.Exit` is `click.exceptions.Exit` →
  `RuntimeError` in the installed Typer (0.16.1), **not** a `SystemExit`
  subclass, so `except SystemExit` in the API routes had never actually
  caught it — every known `byor.py` failure mode, not just this one, fell
  through to the generic 500 branch. Both routes now catch
  `(SystemExit, typer.Exit)`. Verified live against a restarted `core-api`.
- **F-1 (topology) closed — `8437c15e`.** `onboard`/`promote`/`scout --write`
  require the CLI and `core-api` to be co-located (ADR-054 D3: loopback-only,
  single-operator, no auth); documented in the API docstrings rather than
  built around, since a content-upload path would mean accepting writes to
  an arbitrary server-side path from an unauthenticated client.
- **`CORE_API_URL` now actually wired — `8437c15e`.** `CoreApiClient`
  (`src/api/cli/client.py`) advertised the env var everywhere but never read
  it; every call site does `CoreApiClient()` with no args, so it silently
  always used the hardcoded `127.0.0.1:8000` default. `base_url` now
  resolves explicit arg → `CORE_API_URL` → loopback default.
- **`docs/byor-quickstart.md` rewritten — `8437c15e`.** Had been broken for
  5 days (since the ADR-146 consumer/operator CLI split, `608d8f72`) —
  `onboard`/`scout` no longer exist under `core-admin`. Corrected to the
  `core-cli`/`core project` command surface and the real infra requirement
  (a reachable `core-api`; only `core-admin code audit --offline` is
  genuinely infra-free).

---

## [2.9.0] — 2026-07-12

### 🎯 OSS Runtime — Commercial Track Dissolved

Post-2.8.0 work completing the open-source extraction. CORE is now a pure,
auth-free governance runtime; authentication, multi-tenancy, and SaaS delivery
infrastructure live in `core-platform` (a separate repo).

#### OSS extraction

- **UAC extraction (ADR-124/132 successor) — `8a97e54e`.** JWT auth stack, 5-role
  model, `get_current_user`, `body.services.auth.*`, and `will.governance.auth_runner`
  moved to `core-platform`. CORE API is now unauthenticated at the runtime layer;
  auth is an operator/platform concern.
- **web/ dropped — `a349e8af` (ADR-125 successor).** SPA frontend belongs in
  `core-platform`, not the governance runtime.
- **Commercial track dissolved — `45ec53f9`.** All commercial-track references
  scrubbed from `.specs/` and `.intent/`; ADR-131/132 redacted. CORE is clean OSS.

#### Governance maturity (shipped post-2.8.0)

- **ADR-135 — Dual-mode generation.** `single_shot` and `iterative` code-generation
  modes; `IterativeCoderAgent` primitive live. `flow.build_test_for_symbol` v2.0.0.
- **ADR-139 — Type-safety at zero.** 435 → 0 mypy errors; `quality.type_safety`
  promoted to blocking.
- **ADR-140 — Cognitive-Write Separation.** Cognitive delegation and file mutation
  decoupled; governed write path enforced structurally.
- **ADR-142 — passive_gate attestation.** 7 previously unmapped passive-gate rules
  given declared attestation records.
- **ADR-090 — Cognitive roles structural enforcement.** Role taxonomy enforced at
  the AST level; stale role literals no longer pass audit.

#### Engineering health

- Smoke test suite: 93 pre-existing failures unmasked and cleared; 2987 passing.
- `governance.namespace.classification_complete`: 45 unregistered `.intent/` files
  backfilled into `namespace_manifest.yaml`.
- Vocabulary projection: stale `authoritative_paper` paths (`NorthStar`,
  `OptimizerWorker`) corrected in `CORE-Vocabulary.md` and `vocabulary.json`;
  `source_hash` resynced.

---

## [2.8.0] — 2026-06-30

### 🎯 Governed Delivery

The external-adoption surface opens and the governance machinery itself becomes governed.
BYOR users can now `pip install core-runtime` and run `project onboard` without a source
checkout. A full SaaS auth stack (JWT, refresh tokens, 5-role model, SPA frontend) makes
the platform accessible to external users. And CORE's own prompts, operator roles, and
command-exposure axis each acquire a governing rule set — closing the gap between what CORE
enforces on others and what it enforces on itself.

#### BYOR delivery — pip users can onboard

- **ADR-108 D3 — machinery floor in wheel (T3 closed).** The `core-runtime` wheel now bundles
  the machinery floor with a loader fallback. A `pip install` adopter can run
  `project onboard` end-to-end without a source-tree checkout.
- **BYOR quickstart.** A seven-step guide takes a naked machine from `pip install` to a
  PASS audit verdict. Docs updated to remove stale source-tree assumptions.
- **ADR-119 — Scout.** LLM-driven rule induction + human ratification (BYOR Path 1).
  `project scout <path>` observes an external repo's conventions, proposes rules, and
  writes `scout_inducted.json` only after per-rule governor confirmation.
- **ADR-111 — `project onboard` delivers the authored starter.** The command writes a
  four-rule constitution into `<target>/.intent/` directly; the previous generator path
  is removed.
- **ADR-123 — `--stage` airlock.** `project onboard --stage` redirects writes to
  `work/staged/<name>/`; `project onboard promote <path>` completes delivery.

#### SaaS delivery — auth stack

- **ADR-124 — User Access Control foundation.** bcrypt password hashing (cost 12), JWT
  access tokens (1 hr, HS256, httpOnly cookie), opaque refresh tokens (30 d, SHA-256
  stored), 5-role model (VISITOR / ANALYST / AUDITOR / ORG_ADMIN / PLATFORM_ADMIN), org
  + org membership tables, invitation flow, API key management, audit event log. 14 REST
  endpoints under `/auth/`. Sliding-window rate limiting on login/register/password-reset.
- **ADR-125 — SPA frontend scaffold.** Vite 8, React 19, TypeScript 6, Tailwind v4,
  shadcn/ui, TanStack Router v1 (file-based routing), TanStack Query v5, Orval v8 (typed
  API client from OpenAPI). Auth screens (login / register / forgot-password / reset).
- **ADR-132 — Governor authentication boundary.** Operator-tier routes (invite, promote,
  API key management) gated with `require_operator`; governor routes with
  `require_governor`. CLI session persistence + auth commands. ROUTER_EXPOSURE /
  `require_governor` agreement enforced as a blocking audit rule.
- **CORS narrowed** from `["*"]` to `settings.CORS_ORIGINS`; all `/v1/` routes gated with
  `Depends(get_current_user)`; `/health` and `/auth/*` remain public.
- **Resend transactional email.** `core-governance.com` domain verified; invitation and
  password-reset emails delivered. Graceful dev-mode degradation (tokens returned in
  response when `RESEND_API_KEY` absent).

#### Prompt governance

- **ADR-134 — Prompt content governance.** Three new blocking/reporting rules:
  `prompt.adr_anchor` (every prompt must cite a governing ADR), `prompt.registered`
  (prompts must appear in the governed registry), `prompt.drift` (content must not drift
  from the registered hash). `PromptDriftSensor` worker posts findings on each cycle.
  Five existing prompt manifests updated to carry `adr_anchor` and hash.

#### Governance machinery

- **ADR-133 — Symbol-granular test generation.** `TestGapEvaluator` targets individual
  public symbols rather than whole files; generated tests track symbol-level coverage.
- **ADR-131 — Governance Application Data Model.** Typed data model for governance
  applications built on CORE's finding + proposal surfaces.
- **ADR-130 — Constitutional artifact staging.** Governor-applied draft pattern:
  `var/drafts/` as a staging area before intent artifacts land in `.intent/`.
- **ADR-129 — Commit authorship integrity (D1/D2/D4/D5/D6).** All async git operations
  centralised in `GitService` sanctuary; staging-contamination detection; commit set
  derives from declared production output, not worktree diff.
- **ADR-128 — CoreContext DI typing.** Git, knowledge, and file-handler services promoted
  from `Optional` to mandatory DI fields; `CoreContext` construction now fails fast on
  missing services rather than silently deferring.
- **CommandExposure axis (#671).** Every CLI command and API endpoint carries an `exposure`
  field; accessibility overview generated from the registry.
- **Write-safety rails on directed AI-mutation path (#672).** `ExecutionPhase._execute_deterministic_split`
  propagates `write=False` correctly; non-interactive mutation paths gated.

#### Performance and infrastructure

- **Evaluation-level cache in `rule_executor` (#720, ADR-039 Option F).** Rule results
  are cached per `(rule_id, file_path)` within an audit cycle; redundant re-evaluation
  eliminated.
- **Keyset pagination (#699).** `proposals`, `decisions`, and `audit-runs` list endpoints
  switch from offset to keyset pagination; stable under concurrent writes.
- **Systemd watchdog pinger.** Reads `WATCHDOG_USEC`, pings `sd_notify(WATCHDOG=1)` at
  half the watchdog interval; prevents the 120-second SIGABRT restart cycle on loaded
  instances.
- **ToolRunner sanctuary + AuthRunner Will facade (#718/#719).** Subprocess and auth
  operations isolated into dedicated sanctuary modules in Will.

#### Security and bug fixes

- **`SECURITY.md` added.** Supported versions, vulnerability reporting process, disclosure
  contact, and known security boundaries documented at repo root.
- asyncpg cast fixes: `::jsonb` binding (`_log_event`), `:count` cast in `to_jsonb()`,
  `bindparam` replacement for `_query_recent_symbol_failures` (#721).
- `Depends` double-wrap fix on `require_governor` — `require_role()` returns a `Depends`
  already; unwrapping prevented a FastAPI startup crash.
- Rule evaluation failures now surface as `HIGH` findings on the blackboard rather than
  being swallowed silently.
- `parents[4]` replaced with `get_intent_repository().root.parent` in GRC services
  (fragile path arithmetic removed).

## Closes

- ADR-119, ADR-123, ADR-124, ADR-125, ADR-128, ADR-129, ADR-130, ADR-131, ADR-132,
  ADR-133, ADR-134
- #670 (CLI auth gap), #671 (CommandExposure axis), #672 (write-safety rails),
  #674 (ADR-108 D3 wheel packaging), #699 (keyset pagination), #718, #719, #720, #721

PyPI `core-runtime==2.8.0`; Docker `ghcr.io/dariusznewecki/core-engine:2.8.0`;
classifier `Development Status :: 4 - Beta`.

---

## [2.7.0] — 2026-06-14

### 🎯 Bounded Autonomy

The autonomous remediation loop becomes real *and* safe. CORE's daemon finds constitutional violations in its own codebase, proposes fixes, and executes approved ones — this release puts hard bounds around that capability so it can run unattended without escaping its lane.

#### Autonomy, bounded

- **ADR-106 — Sandboxed flow proposals.** Autonomous flow proposals execute in a hermetic git worktree; a failed remediation rolls back instead of reflowing the working tree. Closes the gap where flows skipped the per-action sandbox single actions already had (ADR-071).
- **ADR-107 — Declared-production commit set.** A flow commits only the files its steps declared as produced, not whatever the worktree diff happens to contain.
- **ADR-104 — Orphaned-claim reaper.** Claim lifecycle is process-scoped; a dead worker's claims are reclaimed under a lease (D8), so slow *live* workers are never reaped mid-run.
- **Remediation-attempt cap (#637).** A proposal that fails repeatedly is abandoned with attestations rather than retried forever (ADR-104 D9).
- **Test-generation loop unblocked end-to-end.** Risk compute reads governed `action_risk` instead of an executor-init overlay, and every generated test is sandbox-validated before it counts.

#### ADR-101 — Commit authorship integrity

A commit's diff must contain only bytes its author produced — constitutional, applied to every committer. Supersedes ADR-021's path-shaped guards: the commit set derives from production, not permission scope.

#### ADR-105 — `.specs/` document model

`.specs/` gains a typed, fail-closed document model with a forked vocabulary (`doctrine_tier`, distinct from `.intent`'s operational `authority`). 181 documents migrated to machine-readable headers; a structural validator enforces them.

#### Outward-facing — the open on-ramp

- **ADR-108 — Minimal starter-intent** for external adoption (a 4-rule authored starter vs the full 248-artifact `.intent`).
- One-command on-ramp (`install-core.sh`) plus a reviewer-reproducible consequence-chain demo.

#### Packaging & distribution

- **PEP 621 migration (#543).** `pyproject.toml` moves to the standard `[project]` table; license declared as the SPDX expression `MIT`.
- **Semver policy (#541).** An authoritative versioning contract (`.specs/planning/CORE-Semver-Policy.md`) anchored on ADR-086 D7 + ADR-088 D5.
- **`core-engine` Docker image (#539).** The Solo+ runtime image publishes to GHCR on every tag — `core-engine:X.Y.Z` exists if and only if `core-runtime X.Y.Z` is on PyPI (ADR-086 D7 iff invariant now satisfied).

#### Engineering health

Type-safety drain: mypy errors 756 → 547, including a DI construction-guarantee pass (#643) making `CoreContext`'s git/knowledge/file-handler services mandatory rather than Optional.

PyPI `core-runtime==2.7.0`; Docker `ghcr.io/dariusznewecki/core-engine:2.7.0`; classifier `Development Status :: 4 - Beta`.

## Closes

- #539 (core-engine Docker image + GHCR workflow), #541 (semver policy doc), #543 (PEP 621 migration)
- ADR-101, ADR-104, ADR-105, ADR-106, ADR-107, ADR-108

---

## [2.6.0] — 2026-06-02

### 🎯 Declared Surface

First release on the aligned PyPI/GitHub version track (ADR-088). The `core-runtime` package now publishes from a declared `__all__` rather than the unbounded source tree, and the runtime chokepoint that authorizes filesystem writes is observable per capability and per mode.

#### F-48.4 — Public Python API surface (#540)

The first explicit declaration of CORE's published Python contract per ADR-084 D4. `__all__` is declared in every top-level package; forks pin against this contract, and every symbol outside it is internal. Public surface: 6 symbols across 6 packages (`shared`'s `@atomic_action` extension contract plus `mind.run_stateless_audit`); `api`/`body`/`cli`/`will` export nothing until promoted via ADR.

#### ADR-079 D10 Stage 2 — Capability-scoped chokepoint at blocking

`governance.taxonomy.operational_capabilities_decorator_backing` promotes from reporting to blocking: every capability id in `.intent/taxonomies/operational_capabilities.yaml` must be backed by exactly one `@atomic_action`. Stages 3–5 (per-capability denial, `.intent`/`.specs` atomic swap, legacy `FileService` retirement) carry forward.

#### ADR-088 — Aligned PyPI/GitHub version track

`pyproject.toml`'s version and GitHub's release track agree from this release forward. The `v0.1.0`–`v0.1.6` PyPI tags were F-48 publish-bootstrap iterations — honest history, not a parallel `0.x` track, and no future `0.x` tags are created. The `v2.x` track is continued, not reset; the Beta classifier surfaces the residual SemVer concession (ADR-088 D2).

PyPI `core-runtime==2.6.0`; classifier `Development Status :: 4 - Beta`.

## Closes

- #540 (F-48.4 — public-vs-internal API distinction)
- ADR-079 D10 Stage 2, ADR-088

---

## [2.5.0] — 2026-05-12

### 🎯 Engine Integrity

Band D closed. CORE's governance engine is now constitutionally coherent: no enforcement logic lives in `src/`, no impact classification lives in decorators, no operational threshold lives as a hardcoded literal. The rules that govern autonomous behaviour are declared in `.intent/` and enforced from there.

This release closes the gap between a system that *behaves* constitutionally and one that *is auditable as* constitutional.

#### G4 — Governance in `.intent/` (closed)

**ADR-008 — `impact_level` constitutionalization.**
The field that determines whether a proposal auto-executes or requires human approval was declared in `@register_action()` Python decorators — governance logic in `src/`. Externalized to `.intent/enforcement/config/action_risk.yaml`, keyed by `action_id`. A loader at `shared.infrastructure.intent.action_risk` overlays the mapping at `ActionExecutor` init time. Any `action_id` absent from the mapping raises `ConstitutionalError` at startup. 23 actions registered; 22 decorator literals removed.

**ADR-040 — Operational config wiring campaign.**
32 categories of operational thresholds and scoring weights moved from hardcoded `src/` literals to `.intent/enforcement/config/operational_config.yaml`. 23 commits, 122 files touched, 113 `src/` files now importing `load_operational_config`, 48 typed frozen dataclasses backing every section. Enum ordinals, loop bounds, and loader fallback defaults explicitly exempted per ADR-040 exclusion list. Audit verdict held PASS throughout the campaign.

#### G2 — Convergence (closed)

**ADR-038 — Circuit-breaker on repeated proposal failures (#281).**
The autonomous loop previously had no protection against a systematic error producing unbounded proposal churn. The circuit-breaker trips on repeated failures against the same `(action_id, file)` signature within a configurable lookback window. Thresholds governed via `.intent/`; fallback constants are the fail-safe path only.

#### Path governance

**ADR-031 — No hardcoded runtime directory paths.**
A blocking `regex_gate` rule prevents any `src/` file from declaring raw `var/` path strings. All runtime path resolution routes through `PathResolver`. The 40 pre-existing findings surfaced by ADR-031 served as the training corpus for autonomous remediation; all resolved.

#### Autonomous loop integrity

- **ADR-033** — Flow→step parameter routing contract. Routing behaviour auditable from YAML without reading Python source.
- **ADR-035** — One proposal per `(action, file)` at a time. Eliminates parallel-proposal races on the same target.
- **ADR-036** — PathResolver exclusion from modularity enforcement.
- **ADR-037** — Flow refs exempt from per-file scoping rules.
- **ADR-039** — Per-cycle audit-input cache invalidation. Eliminates stale findings surviving across cycles.

#### Gate state after this release

| Gate | Meaning | Status |
|------|---------|--------|
| G1 — Loop closure | Round-trip autonomous fix demonstrated | ✅ |
| G2 — Convergence | Circuit-breaker; resolution rate > creation rate | ✅ closed |
| G3 — Consequence chain | Causality queryable end-to-end | ✅ |
| G4 — Governance in `.intent/` | No enforcement logic or thresholds in `src/` | ✅ closed |

Closes milestone 16 (Band D — Engine Integrity), 107 issues.

---

## [2.4.0] — 2026-05-01

### 🎯 Consequence Chain

Band B closed. CORE's autonomous-operation gate G3 (Consequence Chain) is materialized. The Finding → Proposal → Approval → Execution → File changes → New findings causality chain is now queryable end-to-end.

This release closes the operational form of the two-log problem — the gap between what was decided (action log) and what changed because of it (consequence log). Without that chain, autonomous operation cannot be audited, debugged, or trusted in regulated environments.

#### G3 — Consequence Chain (closed)

All six edges of the chain delivered:

- **Edge 1** — Finding ↔ Proposal linkage (`finding_ids` jsonb on `constitutional_constraints`).
- **Edge 2** — Approval attribution. `approved_by`, `approved_at`, `approval_authority` non-omittable; DB CHECK constraint enforced.
- **Edge 3** — Claim attribution via `claim.proposal` atomic action (ADR-017). CLI sentinel UUID distinguishes human-driven claims from autonomous worker claims.
- **Edge 5** — Execution → file changes. Orphan-commit detection via new `CommitReachabilityAuditor`; commit-message proposal-id prefix widened from 8 to 16 chars (ADR-019).
- **Edge 6** — File changes → new findings. `AuditViolationSensor` threads `causing_proposal_id`, `causing_commit_sha`, `cause_attribution` into every new finding payload.

Hygiene fix: `BlackboardService.update_entry_status` corrected as the fifth terminal-state write site (#135).

#### Decomposed crawler/embedder (ADR-018)

The autonomous repository-to-vectors path moves from a single composite worker to a decomposed pair: `repo_crawler` writes structural facts and enqueues work by zeroing `chunk_count`; `repo_embedder` dequeues, chunks, embeds, and upserts. The manual `core-admin dev sync --write` CLI path is preserved unchanged. ~1,640 artifacts embedded across six Qdrant collections post-activation.

#### Dashboard truthfulness (#173)

`core-admin runtime health` now renders workers with stale heartbeats as `stale`, not `active`. Previously the `_worker_colour` function graded by heartbeat age but the cell text was the raw status column, masking staleness in pipes and screenshots.

#### Gate state after this release

| Gate | Meaning | Status |
|------|---------|--------|
| G1 — Loop closure | Round-trip autonomous fix demonstrated | ✅ |
| G2 — Convergence | Resolution rate > creation rate, sustained | parked |
| G3 — Consequence chain | Causality queryable end-to-end | ✅ closed |
| G4 — Governance in `.intent/` | No enforcement logic in `src/` | 🔄 in progress |

Closes epic #110, milestone 14 (Band B — Consequence Chain).

---

## [2.3.0] — 2026-04-17

### 🎯 Governed Attribution

Intermediate release during the Band B campaign. Established the attribution write-path contracts and schema foundations that the consequence chain (v2.4.0) completed. ADR-015 coordination plan landed; sub-issue attribution edges (D1–D7) scoped and tracked.

---

## [2.2.2] — 2026-02-28

### 🎯 Self-Compliance & Hygiene Edition

**Historic milestone**: CORE successfully governed its own major refactoring cycle with **zero constitutional violations** maintained throughout.

#### Changed
- Completed deep modularity refactoring (4 big files → 17 focused single-responsibility modules)
- Hardened Mind/Will/Body separation (fixed layer leaks, tracing exclusions, race conditions)
- Switched planning to deterministic `passive_gate` (no more unnecessary LLM calls)
- Unified `IntentGuard.check_transaction` API for cleaner constitutional validation
- Major repository hygiene cleanup (removed `.archive/`, binary/temp files, updated `.gitignore`)

#### Removed
- Legacy `.archive/` directory
- Temporary refactor cast files (`core-refactor.cast`)
- Any leftover sensitive or unnecessary files

#### Notes
- Real self-governance in action: the constitutional runtime actively flagged issues during development
- Technical debt reduced further, codebase now even cleaner and more maintainable
- Ready for next leap toward A3 strategic autonomy

---

## [2.2.1] — 2026-01-26

### 🎯 Modularity Refactoring — Constitutional Debt Elimination

This release achieves **zero constitutional violations** through systematic modularity refactoring and establishes **DRY-by-design** infrastructure for validation and path operations.

### Fixed

#### Constitutional Compliance

* **Zero Violations Achieved** (2026-01-26)
  - Eliminated last modularity violation (proposal_repository: 63.6 → compliant)
  - 100% compliance with modularity.refactor_score_threshold (all files < 60)
  - Technical debt reduction: 46% (13 warnings → 7 warnings)
  - Refactored 4 high-complexity files into 17 focused modules

#### Modularity Refactoring

* **proposal_repository.py** → 4 modules (63.6 → <35 per module)
  - `proposal_repository.py`: Pure CRUD operations (130 lines)
  - `proposal_mapper.py`: Domain/DB conversion (150 lines)
  - `proposal_state_manager.py`: Lifecycle transitions (160 lines)
  - `proposal_service.py`: High-level facade (120 lines)

* **validate.py** → 3 modules (51.6 → <25 per module)
  - `intent_schema_validator.py`: Pure validation logic (180 lines)
  - `policy_expression_evaluator.py`: Safe expression evaluation (120 lines)
  - `validate.py`: Thin CLI layer (70 lines)

* **intent_guard.py** → 4 modules (55.8 → <30 per module)
  - `rule_conflict_detector.py`: Constitutional conflict detection (120 lines)
  - `path_validator.py`: Path-level validation (180 lines)
  - `code_validator.py`: Generated code validation (90 lines)
  - `intent_guard.py`: Thin coordinator (150 lines)

* **complexity_service.py** → 4 modules (50.3 → <25 per module)
  - `capability_parser.py`: Capability tag extraction (60 lines)
  - `refactoring_proposal_writer.py`: Constitutional proposal creation (90 lines)
  - `capability_reconciliation_service.py`: AI-powered reconciliation (100 lines)
  - `complexity_service.py`: Thin orchestrator (140 lines)

### Added

#### DRY Infrastructure

* **constitutional_validation.py** - Standardized validation result models
* **path_utils.py** - Reusable file discovery and pattern matching
* **policy_resolver.py** - Constitutional path compliance

### Changed

* Single Responsibility Principle enforced across all refactored modules
* Separation of Concerns: clear boundaries between CRUD, validation, coordination, and execution

### Performance & Metrics

| Metric | Before | After |
|--------|--------|-------|
| Constitutional violations | 1 | 0 ✅ |
| Technical debt warnings | 13 | 7 (−46%) |
| Avg responsibilities/file | 4–5 | 1–2 |
| Total new modules | — | 17 |

---

## [2.2.0] — 2026-01-08

### 🎯 Universal Workflow Pattern — The Operating System

This release establishes the **foundational architecture for autonomous operations at scale**. CORE now has a universal orchestration model that closes all loops, enables self-correction everywhere, and provides the substrate for fully autonomous conversational operation.

### Added

#### Constitutional Architecture

* **INTERPRET Phase — 6th Constitutional Phase**
* **Dynamic Phase Registry** — phase discovery from constitutional definitions, not hardcoded imports
* **Universal Workflow Pattern** (`INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE`)

#### Component Types Formalized

* Interpreters, Analyzers, Evaluators, Strategists, Orchestrators — all defined with constitutional phase boundaries
* `ComponentResult` contract — universal return structure with confidence scoring

### Changed

* `core` CLI positioned as primary conversational interface
* `core-admin` CLI positioned as developer tooling
* Component phases given strict constitutional boundaries

---

## [2.1.0] — 2025-01

### 🎯 Consolidation Release — Governance First

Stabilisation, credibility, and enforcement depth. Transition from capability discovery to governance consolidation.

### Added

* Enforcement coverage tracking as first-class governance signal
* Explicit distinction between declared vs enforced constitutional rules
* Formalisation of A2 Governed Autonomy (coverage-bounded)

### Changed

* Reframed A2 status from "achieved" to "governed and bounded"
* Tightened language around autonomy, authority, and responsibility

---

## [2.0.0] — 2024-11-28

### 🎯 Major Milestone: A2 Governed Code Generation (Foundational)

First operational realization of A2 autonomy: the ability to autonomously generate new code under constitutional governance, with semantic awareness and enforced constraints.

### Added

* **CoderAgent v1** — context-aware autonomous code generation (70–80% success)
* **Semantic Infrastructure** — 500+ symbols vectorized, 60+ module anchors
* **Constitutional Audit System** — continuous validation with violation tracking
* **Micro-Proposal Loop** — autonomous remediation proposals (governed)
* **PostgreSQL Knowledge Graph** — symbols and relations as SSOT
* **Vector Store Integration** — semantic search over code and policies

---

## [1.0.0] — 2024-10-01

### 🎯 Major Milestone: A1 Self-Healing Autonomy

Initial public release establishing governed self-healing as a first-class capability.

### Added

* Autonomous docstring generation, header and metadata compliance, import organisation
* Mind–Body–Will architecture
* Constitutional governance via `.intent/`
* `core-admin` CLI with constitutional audit commands

---

## Autonomy Levels (Reference)

* **A0 — Self-Awareness**: Knowledge graph, symbol discovery ✅
* **A1 — Self-Healing**: Autonomous compliance and drift repair ✅
* **A2 — Governed Generation**: Code generation under enforced rules ✅
* **A3 — Governed Autonomy**: Daemon finds, proposes, and fixes violations unattended ✅ current
* **A4 — Self-Replication**: CORE generates CORE.NG from its own understanding of itself 🔮

---

[Unreleased]: https://github.com/DariuszNewecki/CORE/compare/v2.8.0...HEAD
[2.8.0]: https://github.com/DariuszNewecki/CORE/compare/v2.7.0...v2.8.0
[2.7.0]: https://github.com/DariuszNewecki/CORE/compare/v2.6.0...v2.7.0
[2.6.0]: https://github.com/DariuszNewecki/CORE/compare/v2.5.0...v2.6.0
[2.5.0]: https://github.com/DariuszNewecki/CORE/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/DariuszNewecki/CORE/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/DariuszNewecki/CORE/compare/v2.2.2...v2.3.0
[2.2.2]: https://github.com/DariuszNewecki/CORE/compare/v2.2.1...v2.2.2
[2.2.1]: https://github.com/DariuszNewecki/CORE/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/DariuszNewecki/CORE/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/DariuszNewecki/CORE/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/DariuszNewecki/CORE/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/DariuszNewecki/CORE/releases/tag/v1.0.0
