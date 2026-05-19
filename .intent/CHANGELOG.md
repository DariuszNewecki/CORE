<!-- path: .intent/CHANGELOG.md -->

# CORE — Changelog

This changelog records **constitutional-level changes** during the modernization of CORE.

It documents *what changed and why*, not how changes were implemented.

This file is descriptive only.
It carries no authority.

---

## Versioning Model

Current versions do not follow semantic versioning.

Each version represents a **constitutional state**.

Replacement invalidates all prior constitutional authority.
Minor versions indicate clarification within the same constitutional intent.

---

## v0 — Foundational Constitution

**Status:** Initial constitutional declaration

**Description:**

* Introduced CORE as a legal system, not a framework
* Declared four irreducible primitives:

  * Document
  * Rule
  * Phase
  * Authority
* Established explicit phase discipline:

  * Load
  * Parse
  * Interpret
  * Audit
  * Execution
* Required all rules to declare governing artifacts
* Forbade silent rule emergence
* Defined enforcement strengths:

  * advisory
  * required
  * blocking
* Defined Authority hierarchy:

  * Constitutional
  * Policy
* Required dual-key amendment for the Constitution
* Set non-goals explicitly:

  * Not a framework
  * Not configuration
  * Not a runtime system
  * Not workflow logic
* Forbade emergent rule creation by Workers, Phases, or LLM components
* Required every rule and decision to be traceable to declared intent

**Constitutional Documents:**

* `constitution/CORE-CONSTITUTION.md`
* Foundational papers under `papers/`
* `CORE-CHARTER.md`

---

## v0.1 — Governance Semantics Hardening

**Status:** Clarifying amendment (non-primitive)

**Intent:**

This version hardens CORE against known governance failure modes identified during external constitutional review.

No primitives were added.
No scope expansion occurred.

### Added

* **Rule Conflict Semantics**

  * Defined handling of conflicts between rules of equal Authority and Phase
  * Classified such conflicts as governance errors
  * Explicitly forbade precedence, ordering, and interpretation
  * Artifact: `papers/CORE-Rule-Conflict-Semantics.md`

* **Amendment by Replacement Only**

  * Made explicit that the Constitution may be amended only via replacement
  * Forbade in-place modification

* **Evidence as Input Semantics**

  * Defined evidence as evaluation input, not law
  * Bound evidence to phases
  * Required reproducibility
  * Clarified indeterminate outcomes
  * Artifact: `papers/CORE-Evidence-as-Input.md`

* **Emergency and Exception Stance**

  * Explicitly rejected emergency sovereignty and exception mechanisms
  * Forbade break-glass logic
  * Required replacement, not override, when law is insufficient
  * Artifact: `papers/CORE-Emergency-and-Exception-Stance.md`

### Changed

* Article IV — Evaluation Model

  * Added explicit reference to rule conflict semantics

* Article VII — Change Discipline

  * Clarified amendment mechanism as replacement-only

### Not Changed

* Primitive set
* Authority hierarchy
* Phase definitions
* Enforcement strengths
* Non-goals and scope boundaries

---

## v0.2 — ShopManager Class Reservation

**Status:** Clarifying amendment (non-primitive)

**Intent:**

This version closes the constitutional coherence finding F-11 surfaced by
the 2026-04-28 audit. The ShopManager paper was Canonical but had drifted
from its implementation: workers fulfilling the supervisory mandate were
named `*_auditor` and declared `class: governance`, neither of which the
paper recognized. This amendment aligns code to the paper rather than the
paper to the code.

No primitives were added.
No scope expansion occurred.

### Added

* **`identity.class: supervision` reservation**

  * Reserved the `supervision` worker class exclusively for ShopManagers
  * Distinguishes ShopManagers from sensing, acting, and governance workers
  * No worker outside the ShopManager paper's scope may declare this class
  * Artifact: `papers/CORE-ShopManager.md` §2

* **§3a Implementation Status table in CORE-ShopManager.md**

  * Authoritative implementation map for the three supervisory responsibilities
  * Each row pairs a responsibility with its implementing worker and current status
  * Drift between this table and `.intent/workers/` is itself an audit finding

* **Deferral discipline for Proposal Pipeline Health**

  * §3 responsibility 3 marked "Not Yet Implemented" with reference to issue #170
  * Same deferral discipline already applied to OptimizerWorker
  * Implementation seed identified at `src/cli/resources/runtime/health.py:439-448`

### Changed

* **Worker rename: `*_auditor` → `*_shop_manager`**

  * `worker_auditor` → `worker_shop_manager`
  * `blackboard_auditor` → `blackboard_shop_manager`
  * Worker UUIDs preserved (constitutional identity per ADR-011)
  * Database `worker_registry` rows migrated; FK integrity intact

* **`CORE-OptimizerWorker.md` §3 currency** (finding F-12)

  * Removed claim that "ViolationExecutor is not yet implemented"
  * VE is implemented and active; the OptimizerWorker's deferral is now
    correctly grounded in the absence of accumulated discovery data, not
    the absence of VE

### Not Changed

* Primitive set
* Authority hierarchy
* Phase definitions
* Enforcement strengths
* Non-goals and scope boundaries

### Tracked Follow-Ups

* Issue #170 — Implement proposal-pipeline-health ShopManager (§3.3 deferred work)

---

## v0.3 — Vocabulary Governance Enforcement Triangle

**Status:** Clarifying amendment (non-primitive)

**Intent:**

This version closes the constitutional coherence findings N-01 and N-02
surfaced by the 2026-05-08 audit. ADR-023 (Vocabulary Canonical Store)
authored six vocabulary governance rule_ids across two rule files but did
not ship the corresponding enforcement mappings. The rules were declared
law but had no enforcement path — an incomplete triangle. This amendment
completes the triangle by delivering both mapping files.

No primitives were added.
No scope expansion occurred.

### Added

* **`mappings/governance/vocabulary_canonical_store.yaml`** (ADR-023, finding N-01)

  * Closes the enforcement triangle for four rule_ids:
    `governance.vocabulary.projection_must_match_canonical`,
    `governance.vocabulary.canonical_format_must_validate`,
    `governance.vocabulary.authoritative_source_must_be_paper`,
    `governance.vocabulary.no_direct_json_import`
  * Rules 1-3 use `artifact_gate` engine with vocabulary-specific check_types;
    engine implementation is pending ADR-023 Part 3/4 delivery
  * Rule 4 (`no_direct_json_import`) is immediately enforceable via `regex_gate`
    on `src/`, excluding the sanctioned loader

* **`mappings/governance/vocabulary_registers.yaml`** (finding N-02)

  * Closes the enforcement triangle for two rule_ids:
    `governance.vocabulary_registers.operational_fields_must_be_lowercase`,
    `governance.vocabulary_registers.diagnostic_fields_must_be_uppercase`
  * Both rules use `python_runtime` engine with `register_casing_validation`
    check_type; structured YAML/JSON field parsing required
  * Scope: all `.intent/` YAML and JSON files, excluding `.intent/META/`

### Not Changed

* Primitive set
* Authority hierarchy
* Phase definitions
* Enforcement strengths
* Non-goals and scope boundaries

### Tracked Follow-Ups

* ADR-023 Part 3/4 — implement `artifact_gate` vocabulary check_types to
  activate enforcement for rules 1-3 of vocabulary_canonical_store
* `python_runtime` `register_casing_validation` check_type implementation
  required to activate vocabulary_registers enforcement

---

## v0.4 — Autonomous Loop Integrity

**Status:** Clarifying amendment (non-primitive)

**Intent:**

This version hardens the autonomous loop across five ADRs landed between
2026-05-01 and 2026-05-05. Together they replace the deprecated indexing
worker, establish heartbeat as the sole liveness authority, scope git
operations to declared proposal files, and add two sensing workers that
make loop failures observable. Each change closes a known gap between what
the loop claims to do and what it can be verified to have done.

No primitives were added.
No scope expansion occurred.

### Added

* **`repo_crawler` + `repo_embedder` as the canonical autonomous indexing path** (ADR-018)

  * `vector_sync_worker` deprecated and removed; superseded by the crawler/embedder pair
  * `core.repo_artifacts.chunk_count` declared the inter-worker queue contract:
    0 = needs embedding, -1 = permanently empty, >0 = embedded
  * `sync.vectors.code` atomic action preserved for CLI-driven sync
  * Worker declarations updated: `repo_crawler.yaml`, `repo_embedder.yaml` (active);
    `vector_sync_worker.yaml` removed

* **`CommitReachabilityAuditor` worker and Edge 5 attribution posture** (ADR-019)

  * New worker declaration: `.intent/workers/commit_reachability_auditor.yaml`
  * Detects orphan `post_execution_sha` values and posts findings without modifying state
  * New Blackboard subject namespace: `governance.edge5.orphan_sha::*`
  * `post_execution_sha` declared the authoritative Edge 5 link in the consequence chain
  * Autonomous commit prefix widened from 8 to 16 characters (forward-only change)

* **Heartbeat-only liveness contract** (ADR-020)

  * `core.worker_registry.status` column dropped; three-state machine retired
  * `last_heartbeat` against per-worker `max_interval` + `glide_off` is the sole
    sanctioned liveness signal
  * Predicate centralized in `WorkerRegistryService`
  * Per-worker interval thresholds remain declared in `.intent/workers/*.yaml`

* **Scoped autonomous git operations** (ADR-021)

  * New enforcement policy: `.intent/enforcement/config/autonomy_dirty_tree.yaml`
    (mode: `intersection_only`)
  * Autonomous commit and rollback operate only on `proposal.scope.files`;
    no collateral writes permitted
  * Pre-claim scope-collision check yields the proposal when the architect's working
    tree intersects declared scope
  * New Blackboard subject namespace: `autonomy.yielded.scope_collision::*`

* **`CoherenceSensorWorker` and sensor-fixer coherence detection** (ADR-027)

  * New worker declaration: `.intent/workers/coherence_sensor.yaml` (active, 10-min cycle)
  * Queries `proposal_consequences` ⨝ `blackboard_entries` to detect re-posted findings
    after their fixer's `recorded_at`
  * Identity: `check_id` + `file_path` pair; deduplicates against open coherence findings
  * New threshold-config key: `coherence.lookback_seconds` in `.intent/cim/thresholds.yaml`
  * New Blackboard subject namespace: `coherence.incoherence::*`
  * Explicitly DELEGATE-class: no autonomous remediation; requires human architectural judgment

### Not Changed

* Primitive set
* Authority hierarchy
* Phase definitions
* Enforcement strengths
* Non-goals and scope boundaries

---

## v0.5 — Governance Authoring Discipline

**Status:** Clarifying amendment (non-primitive)

**Intent:**

This version establishes four meta-governance rules: how cognitive role
assignments must be qualified before deployment, how rule documentation
must be written to avoid false positives, how non-automatable rules must
be explicitly mapped, and what posture the daemon takes when its own
source code has drifted from what is loaded. Together these close the gap
between governance artifacts that declare intent and governance artifacts
that enforce it reliably.

No primitives were added.
No scope expansion occurred.

### Added

* **Governed evaluation for local LLM cognitive role assignments** (ADR-024)

  * `scripts/eval_ollama.py` declared a governed artifact; scorer changes require
    ADR amendment
  * Role-to-model assignments must be derived from evidentiary qualification,
    not parameter-count assumption
  * Development assignments on aaiMac derived from qualification run:
    `qwen2.5-coder:3b` for LocalCoder/Architect/LocalReasoner/Planner;
    `qwen2.5:7b` for DocstringWriter; `phi4:14b` retained as spare
  * Production assignments deferred until qualification against production hardware

* **Rule documentation must paraphrase forbidden patterns** (ADR-028)

  * Rule statements, rationale prose, in-scope docstrings, comments, and ADRs
    must describe what is forbidden without reproducing the exact syntax the
    detection engine would match
  * Prevents string-matching engines from false-positiving on their own
    documentation and governance text
  * Applies to all new rule authoring and to existing violations as audits surface them
  * Authoring discipline added to `CORE-Rule-Authoring-Discipline.md`

* **Non-automatable rules must carry an explicit PENDING entry in RemediationMap** (ADR-029)

  * Absence from `auto_remediation.yaml` is not a valid signal that a finding
    requires human handling; absence routes findings into the LLM fallback path
  * Every non-automatable rule must declare a PENDING entry with `confidence < 0.50`
  * First application: `modularity.class_too_large` mapped with `confidence: 0.0`
  * Corrects routing semantics between ViolationRemediatorWorker and
    ViolationExecutorWorker

* **Daemon stale-code detection posture** (ADR-030)

  * On detecting drift between on-disk `src/` and loaded-module SHA, the daemon
    DEGRADEs, suspends autonomous execution, posts `governance.stale_daemon`
    Blackboard finding, and surfaces the condition on the runtime dashboard
  * Re-posts at elevated priority after a configurable escalation window (default 30 min)
  * Daemon never self-restarts after a `src/` change; governor restarts deliberately
  * New Blackboard subject: `governance.stale_daemon`
  * New finding subject and DEGRADE-mode policy declared; implementation pending

### Not Changed

* Primitive set
* Authority hierarchy
* Phase definitions
* Enforcement strengths
* Non-goals and scope boundaries

### Tracked Follow-Ups

* ADR-030 — drift-detection mechanism in the daemon not yet implemented;
  `governance.stale_daemon` finding subject and escalation policy declared ahead
  of implementation

---

## ADR-008 — 2026-05-08

Action impact classification externalized from `src/` to `.intent/`. The
field that determines whether a proposal requires human approval or
auto-approves was previously declared as a literal inside `@register_action`
decorators in `src/body/atomic/*.py` — a governance decision carried in
source code. This amendment moves it to its constitutional home.

`@register_action` no longer accepts an `impact_level` parameter. The
parameter was stripped from the decorator signature and from all 22 call
sites across 10 action files. Classification is now declared exclusively
in `.intent/enforcement/config/action_risk.yaml` (keyed by `action_id`,
values: `safe | moderate | dangerous`) and overlaid onto registered
`ActionDefinition` instances at `ActionExecutor` init time via
`ActionRegistry.apply_risk_config()`. Any `action_id` absent from the
mapping raises `ConstitutionalError` at startup, preventing silent
misconfiguration. The loader lives at
`src/shared/infrastructure/intent/action_risk.py`.

Rule `atomic_actions.impact_level_must_be_governed` enforces the
constraint: no `impact_level` literals may appear in decorator call sites
in `src/`. Verified 2026-05-10: 7/7 checks pass; `action_risk.yaml` in
perfect 1:1 parity with the registered action set (23 entries); audit
reports 0 findings on this rule. G4 gate closed.

Files: `.intent/enforcement/config/action_risk.yaml`,
`src/shared/infrastructure/intent/action_risk.py`,
`src/body/atomic/registry.py`, `src/body/atomic/executor.py`,
10 action files (22 decorator sites). Commit ae07f839.

---

## ADR-032 — 2026-05-10

Rule `architecture.path_access.no_hardcoded_runtime_dirs` regex tightened.
Removed two broad bare-string patterns (`["']reports["']`, `["']logs["']`) that
matched any string literal. Replaced with one path-construction-context pattern
(`/\s*["'](?:reports|logs)["']`) that matches only the path-division operator form.
`_RUNTIME_DIR_PATTERN` in `src/body/atomic/fix_actions.py` updated in lockstep.
False-positive count: ~35 removed. True violation count: 25 confirmed.
Files: `.intent/enforcement/mappings/architecture/path_access.yaml`,
`src/body/atomic/fix_actions.py`.

---

## [ADR-023 Part 3/4] — 2026-05-10

Rules `governance.vocabulary.projection_must_match_canonical`,
`governance.vocabulary.canonical_format_must_validate`, and
`governance.vocabulary.authoritative_source_must_be_paper` transition
from declared-only to enforcing. `artifact_gate` engine now implements
`vocabulary_projection_consistency`, `vocabulary_canonical_format`, and
`vocabulary_authoritative_paths` check_types. All three fire correctly on
known-violation fixtures. Governed-root check uses `.specs/` + `.intent/`
per the rule file statement (wider than D5's original `.specs/papers/`).

---

## ADR-033 — 2026-05-10

Flow→step parameter routing contract. `FlowStep` gains `consumes:
tuple[str, ...] | None` — None (absent from YAML) means no caller
params forwarded to this step; a tuple is an explicit whitelist of
forwarded keys. `FlowExecutor._execute_step` replaces the unconditional
caller-param merge with a filtered merge gated on `step.consumes`.
Static `step.params` always pass through regardless. `FlowRegistry._load_file`
parses the `consumes` key from YAML step declarations. `CORE-Flow.md §6`
gains a Parameter Routing subsection stating the contract.
Files: `src/body/flows/registry.py`, `src/body/flows/executor.py`,
`.specs/papers/CORE-Flow.md`, `.specs/decisions/ADR-033-flow-step-parameter-routing-contract.md`.

---

## 2026-05-10 — proposals show logger→console; workflow.ruff_format_check mapped

`src/cli/logic/autonomy/views.py`: `print_detailed_info` and
`print_execution_summary` replaced `logger.info()` with `console.print()`
throughout. Rich markup now renders correctly in terminal output. Unused
`logger` removed; import order corrected.

`.intent/enforcement/remediation/auto_remediation.yaml`: added
`workflow.ruff_format_check → fix.format` (Tier 1, confidence 0.92, risk low).
Gap surfaced when the views.py fix introduced a ruff formatting finding that
the daemon could not route autonomously — the rule ID had no map entry.
Daemon restarted to pick up the new mapping.

---

## ADR-034 — 2026-05-10

OptimizerWorker formally deferred. Constitutional coherence finding F-18
(2026-04-28 audit) closed. Deferral locked as a dated constitutional
decision rather than a paper status line. Review triggers: ≥20 VE-discovered
action candidates across ≥5 rule namespaces, or 12 months elapsed from
2026-05-10. `CORE-OptimizerWorker.md` §3 status transitions to "Formally
Deferred (ADR-034)". GitHub #115 retained as the implementation epic;
#246 closed.
Files: `.specs/decisions/ADR-034-optimizer-worker-formal-deferral.md`.

---

## ADR-035 — 2026-05-11

One finding, one proposal. `ViolationRemediatorWorker` previously grouped
findings by `action_id`, producing one proposal per action regardless of
how many files were affected. This forced the governor into all-or-nothing
approval decisions over independent findings and broke the 1:1 resolution
of the consequence chain. The grouping key is changed to `(action_id,
file_path)` so each proposal covers exactly one file. Deduplication,
the deferred_to_proposal transition, and the §7a revival contract are
preserved at per-finding resolution. The batch-safe classification for
homogeneous low-risk actions (e.g. `fix.format`) is deferred to a future
ADR. Closes #284.
Files: `src/will/workers/violation_remediator.py`. Commit 53272ce1.

---

## ADR-036 — 2026-05-11

PathResolver excluded from `modularity.needs_split`. The 2026-05-11 SRP
sweep landed six file splits (ProposalConsumerWorker, StrategicAuditor,
AtomicActionsEvaluator, ConstitutionalValidator, RequestInterpreter,
AuditViolationSensor). The seventh and final candidate, `path_resolver.py`,
analysis established as a catalog class with one responsibility — the rule
fired on volume (408 lines, 30+ trivial property getters), not on lumped
concerns. Splitting would have added a mixin for 8 lines over the limit
without improving clarity. The correct response is an exclusion, not a
split. Removal condition is documented: this exclusion is revisited when
the file acquires a second genuine concern. `modularity.needs_split`:
7 → 0 occurrences.
Files: `.intent/enforcement/mappings/code/modularity.yaml`,
`.specs/decisions/ADR-036-path-resolver-excluded-from-needs-split.md`.
Commit 0b68328c.

---

## ADR-037 — 2026-05-11

Flow refs exempt from ADR-035 per-file scoping. `ViolationRemediatorWorker.run()`
grouping loop now distinguishes flow refs from atomic action refs: flow refs
key by `(ref_id, None)`, bundling every finding that maps to the same flow into
a single proposal; atomic action refs continue to key by `(ref_id, file_path)`
per ADR-035 D1. The exception is **categorical, not a refinement**.

ADR-035's three governance properties — approval granularity at finding
resolution, consequence chain integrity, UNIX composition — hold for atomic
actions because each operates on a single file. They invert for flows like
`flow.fix_code`, which by design run many fixers across the entire `src/`
tree. A proposal scoped to "`flow.fix_code` on `src/foo.py`" lies to the
governor about what will be approved — the flow ignores per-file scope and
walks the whole codebase. ADR-037 restores truthful approval-scope alignment:
the governor approves one decision per codebase-wide operation, not N decisions
per file the operation might touch. The consequence chain stays whole at the
redefined unit (one flow proposal → N findings resolved together, §7a revival
bundled).

Companion to commit 2a77a9ba (Layer 1: file_path omitted from flow
ProposalAction parameters). Layer 3 — whether flows should be invoked from
the auto-remediation pipeline at all — remains an open governance question
tracked as issue #290.

Files: `src/will/workers/violation_remediator.py`,
`.specs/decisions/ADR-037-flow-scope-exception.md`. Commit 0941fd07.

---

## ADR-038 — 2026-05-11

Circuit-breaker on repeated proposal failures. The autonomous remediation
loop previously had no upper bound on how many times the same systematic
failure could repeat: `mark_failed` → `revive_and_report` → re-claim →
new proposal with byte-identical contents, indefinitely. The 2026-05-10
dashboard observation of 128 identical `fix.placeholders` failures on
one file is the conserved instance — per the Convergence Principle, a
loop that amplifies failures rather than resolving them cannot converge.

`ViolationRemediatorWorker.run()` now consults the failed-proposal tail
between dedup and `_create_proposal`. When the most recent N
(`threshold_n`, default 5) failed proposals for the same
`(ref_id, file_path)` carry the same canonical error signature, the
circuit trips: no new proposal is minted, the cycle's findings are
marked DELEGATE via the existing `_mark_delegated` path, and a
`governance.circuit_breaker_tripped` finding is posted to the
blackboard for governor triage (mirrors the
`governance.instrument_degraded` hazard pattern).

Identity is `(ref_id, file_path, error_signature)` — counting
`(ref_id, file_path)` alone over-trips on flaky infrastructure. The
signature is built by stripping volatile substrings (ISO timestamps,
UUIDs, duration suffixes, pids) from `failure_reason` and truncating
to `signature_window_chars` (default 200), so two failures with the
same root cause but different incidental noise compare equal.
Threshold and signature parameters live in `.intent/`, not `src/`,
honoring the precedent set by ADR-031 / #282.

Reset is implicit by the consecutive-identical rule: a successful
proposal between failures resets the count. Explicit governor override
via a `core-admin proposals reset-circuit` CLI is left as a follow-up
to be added when the breaker first trips in production. Closes #281.

Files: `.intent/enforcement/config/circuit_breaker.yaml`
(threshold_n=5, signature_window_chars=200, max_lookback=25, four
volatile-pattern regexes — iso_timestamp, uuid, duration_seconds, pid),
`src/will/workers/circuit_breaker.py`,
`src/will/workers/violation_remediator.py`,
`.specs/decisions/ADR-038-circuit-breaker-on-repeated-proposal-failures.md`.

---

## ADR-039 — 2026-05-12

Audit-input cache invalidation. `AuditorContext` previously memoised
`_file_list_cache` (the `rglob("*.py")` snapshot) and `_pattern_cache`
on first use and held them for the process lifetime; `IntentRepository`
likewise held its policy/rule index until daemon restart. Files and
rules committed after boot were invisible to the running audit-sensor
loop. The 2026-05-11 → 2026-05-12 incident is the conserved instance:
`circuit_breaker.py` landed 21:48 with a `linkage.assign_ids` violation,
and the daemon ran 54 sensor cycles over ~9 hours reporting "no
actionable violations" against a snapshot taken before the file existed.
A 07:04 restart self-healed the violation within 2 min 25 sec.

`AuditorContext.invalidate_file_cache()` clears `_file_list_cache`,
`_rel_path_map`, and `_pattern_cache`. `run_filtered_audit` and
`ConstitutionalAuditor.run_full_audit_async` call it at entry, before
any rule executes — within a single audit run the rebuilt cache is
still shared across rules. `IntentRepository.reload()` drops the
policy/rule index under `_INDEX_LOCK` and re-runs `_ensure_index()`,
re-emitting the "indexed N policies and M rules" log line so
cycle-to-cycle drift is visible in journald. `AuditViolationSensor.run`
calls both before `_resolve_rule_ids` and emits one INFO line —
`audit_sensor_<ns>: rescanned N files, M rules loaded` — so an operator
can confirm the cycle saw fresh state without reading the rest of the
log. Drift window is bounded to one sensor interval (600s per
`.intent/workers/audit_sensor_*.yaml`).

This is the data-drift counterpart to ADR-030's logic-drift posture.
ADR-030 governs loaded Python module drift and chooses DEGRADE +
governor restart over self-reload; this ADR governs audit-input data
drift (file lists scanned from `src/`, rule content loaded from
`.intent/`) where every successful proposal commit adds content the
running loop must see — treating it as code reload would halt A3
autonomous operation after every fix. Closes #298.

Files: `src/mind/governance/audit_context.py`,
`src/mind/governance/filtered_audit.py`,
`src/mind/governance/auditor.py`,
`src/shared/infrastructure/intent/intent_repository.py`,
`src/will/workers/audit_violation_sensor.py`,
`.specs/decisions/ADR-039-audit-input-cache-invalidation.md`.
Commit adf59796.

---

## ADR-040 — 2026-05-12

No hardcoded values in `src/`. Establishes the general principle that
numeric and string values controlling system behavior at runtime belong
in `.intent/enforcement/config/`, not in source code. ADR-008 and
ADR-031 applied this reactively to specific domains; ADR-040 makes it
constitutional law across the entire `src/` tree. Exclusions: enum
ordinals, loop/range literals, loader fallback defaults, `tests/**`,
`infra/**`. Migration and audit rule (`governance.no_hardcoded_values`)
follow as implementation. Closes #282 ADR step.
Files: `.specs/decisions/ADR-040-no-hardcoded-values-in-src.md`,
`.specs/planning/CORE-A3-plan.md`.

---

## ADR-040 — 2026-05-12 (implementation complete)

All 32 sections of `.intent/enforcement/config/operational_config.yaml`
wired across ~106 source files. Module-level constants, default argument
literals, and inline thresholds replaced with reads from
`load_operational_config()` following the `circuit_breaker.py` pattern.
Audit rule (`governance.no_hardcoded_values`) and remediation map entry
remain as follow-on work. Outstanding: #299 (modularity exemption for
loader), #300 (4 remaining strategy_selector weights).
Files: `.intent/enforcement/config/operational_config.yaml`,
`src/shared/infrastructure/intent/operational_config.py`,
~106 `src/` files across 13 commits.

## ADR-055 — 2026-05-17 (Phase 2 endpoint surface)

ADR-053 Phase 2 endpoint surface for the `/fix` and `/quality`
namespaces. A new resource table `core.fix_runs` carries every
governor-direct fix or quality operation (`kind` discriminator:
`atomic` | `flow` | `modularity` | `quality_check`). One table with a
discriminator avoids the duplicate-table scar `audit_runs` /
`audit_run_resources` left behind during Phase 1 (folded back together
by `20260518_consolidate_audit_runs.sql`).

The API layer reaches `body.*` exclusively through a single Will-layer
facade — `will.governance.fix_runner` — keeping `architecture.api.
no_body_bypass` satisfied without per-route bridge code. The facade
exposes (a) registry enumeration helpers for request-time validation,
(b) async runners (`run_and_persist_fix` / `_flow` / `_modularity` /
`_quality`) that share a `_update_fix_run_status` lifecycle primitive,
and (c) synchronous helpers for the inline `/quality/imports` and
`/quality/body-ui` checks. Subprocess invocation for the async
`/quality` runners routes through `shared.utils.subprocess_utils.
run_command_async` — the sanctioned primitive under
`governance.dangerous_execution_primitives`; direct `subprocess.run`
calls in the facade would fail the audit.

`/fix/modularity` is the only endpoint that diverges from the
flow-registry-backed pattern: there is no `flow.modularity` YAML, so
the route dispatches to `will.self_healing.modularity_remediation_
service.ModularityRemediationService.remediate_batch` directly. Row
carries `kind='modularity'`, `fix_id=NULL`. Async `/quality/*` `href`
fields point at `/fix/runs/{id}` — the single-table design means the
existing `/fix` resource read serves `quality_check` rows.

The CLI-side cutover (ADR-055 D6: 22 files under `src/cli/resources/
code/`, `src/cli/commands/fix/`, `src/cli/commands/check/`) is not in
this change-set and remains open on #349.

Files: `infra/scripts/migrations/20260517_create_fix_runs.sql`,
`infra/sql/db_schema_live.sql`,
`src/shared/infrastructure/database/models/governance.py`,
`src/will/governance/fix_runner.py`,
`src/api/v1/fix_routes.py`,
`src/api/v1/quality_routes.py`,
`src/api/main.py`,
`tests/api/v1/test_fix_routes.py`,
`tests/api/v1/test_quality_routes.py`,
`.specs/decisions/ADR-055-api-phase-2-fix-quality.md`.
Commits `90992bb1`, `2ced6e33`.

---

## ADR-055 — 2026-05-18 (D6 CLI cutover complete)

The CLI-side of ADR-055 D6, deferred from the original Phase 2
landing (`90992bb1`, `2ced6e33`) and tracked on #349. 23 of the
24 in-scope CLI files under `src/cli/resources/code/`,
`src/cli/commands/fix/`, and `src/cli/commands/check/` are now thin
clients over the /v1 HTTP surface — `grep -E "from
(body|will|mind|shared)\."` returns zero hits across the set
(excluding `shared.cli.command_meta` and `shared.logger`, both
allowlisted as CLI-adjacent primitives).

The 16-commit ledger splits as: two C0 prep commits (`_poll_run`
helper on `CoreApiClient`; `shared.models.command_meta` relocated to
the new `shared.cli` neutral subpackage to avoid a body→cli inversion
in `command_sync_service`), five batch migrations (C1: 8 leaf files,
C2: 2 composite, C3: 4 commands/check/, C4: 7 commands/fix/, C5: 2
megaliths split across two commits), seven Stage B reopens that
extended the API surface as gaps surfaced per batch, and one final
chore that classified the six newly-registered actions in
`.intent/enforcement/config/action_risk.yaml` (without which
`ActionExecutor` refused to initialise — ADR-008 is hard law).

Registry delta: 22 → 28 atomic actions. The six new registrations
(`fix.body-ui`, `fix.capability_tagging`, `fix.policy_ids`,
`fix.purge_legacy_tags`, `fix.settings_access`, `fix.vulture_heal`)
each have a `@register_action` wrapper in
`src/body/atomic/fix_actions.py` over an existing body or will
service. Two service relocations accompanied: `vulture_healer.py`
moved will/ → body/ (no will deps; placement was wrong);
`body_contracts_fixer.py` (`fix.body-ui` impl) moved cli/logic/ →
body/self_healing/ for the same reason. `capability_tagging_service`
remained in will/ — it depends on `will.agents.tagger_agent` and
`will.orchestration.cognitive_service`; the body wrapper does a lazy
body→will import (precedent: `proposal_lifecycle_actions.py`).

Two governance-debt carries:

* **#353** — `cli/resources/code/integrity.py` parked from D6.
  `IntegrityService.create_baseline / verify_integrity` has no
  matching D2/D3 endpoint and no clean atomic-action wrap (DB
  session dependencies that don't fit the executor signature).
  Closes when `POST /v1/integrity/{baseline,verify}` is designed and
  the file is rewritten as a thin client.

* **#356** — `cli/commands/fix/all_commands.py` dropped the
  `db-registry` step from the curated `fix all` sequence. The body
  service (`_sync_commands_to_db` in
  `body.maintenance.command_sync_service`) has DB session plumbing
  that requires a wrapper before it can be registered as a fix.*
  action. Closes when `fix.sync_commands` is registered and added
  back to the `fix all` plan.

Two pre-existing constitutional gaps were exposed during the
migration and resolved in the same diffs (not regressions —
they were already broken):

* Several CLI commands carried decorative-only `@atomic_action`
  decorations with `action_id` values that were never registered
  (`fix.cli.atomic_actions`, `tests.cmd`, duplicate `fix.headers`,
  duplicate `fix.imports`, decorative `fix.duplicate`, decorative
  `fix.placeholders`). All dropped on touch.

* `fix.body-ui` was decorated `@atomic_action` but missing
  `@register_action`, so `POST /v1/fix/run/fix.body-ui` returned 422
  for the entire pre-migration period. Registered in `35d27a50`.

Postmortem with full per-batch detail and seven lessons for D7+
Phase 3 batches lives at `var/d6-stage-c-migration-plan.md` (the
plan was rewritten from "Draft" to "Complete" with execution
results in `85a9f8cb`).

CLI is now a typed HTTP client over `/v1/*` for the entire `/fix`
and `/quality` surface, with the two named governance-debt
exceptions above. The "CLI is a typed HTTP client; API is the
system" framing from ADR-053 D5 holds on the in-scope surface.

Files: 23 files under `src/cli/resources/code/` +
`src/cli/commands/{check,fix}/`;
`src/api/cli/client.py`;
`src/api/v1/{fix,quality}_routes.py`;
`src/will/governance/fix_runner.py`;
`src/body/atomic/{__init__,fix_actions}.py`;
`src/body/self_healing/{body_ui_fixer,vulture_healer}.py` (relocated
from cli/logic/ and will/self_healing/ respectively);
`src/shared/cli/{__init__,command_meta}.py` (relocated from
shared/models/);
`.intent/enforcement/config/action_risk.yaml`;
`.intent/enforcement/mappings/infrastructure/cli_commands.yaml`
(path-rename propagation from the command_meta relocation).
Commits `43b2adf1` (range start) through `3eea5b87` (Stage D unblock).

---

## ADR-056 — 2026-05-17 (artifact)

Runtime data contracts as first-class constitutional artifacts. Introduces
`.intent/data_contracts/` (JSON Schemas for `Finding`, `Proposal`,
`BlackboardEntry.entry_type`), renames the Pydantic `Finding` to
`CheckResult`, adds a `SchemaConformanceChecks` class to the AST gate,
and governs `entry_type` as a vocabulary enum. Artifact accepted;
implementation (D2–D6) tracked separately.
Files: `.specs/decisions/ADR-056-runtime-data-contracts.md`.

---

## ADR-056 — 2026-05-18 (broadening: D7 boundary criteria + inventory)

ADR-056 expanded from three concrete decisions to a seven-decision frame.
D7 adds the boundary-based criterion that determines when any structured
object requires a governing schema: an object must be governed when it
crosses a consequence-chain, worker, persistence, AI-invocation, vector-
store, API, phase, atomic-action, or flow boundary. Rules for the
artifact class are introduced at INFO severity; enforcement tightens as
coverage matures.

Canonical path corrected: data contracts live at
`.intent/enforcement/contracts/` (alongside existing `config/`,
`mappings/`, `remediation/`), not at a new top-level `.intent/data_contracts/`.
The 2026-05-17 entry above predates the path correction.

Implementation catalogue moved out of the ADR into
`.specs/planning/data-contracts-inventory.md`: ~70 contracts and 13 enum
additions identified from a `src/` audit against the D7 boundary
criteria, organized into three waves. Wave 1 covers the consequence
chain (Finding, Proposal sub-objects, ProposalConsequence,
BlackboardEntry payload family), the universal result family
(ActionResult, ComponentResult, FlowResult/StepResult, RefusalResult),
the violation persistence family (ViolationReport,
ConstitutionalViolationPayload, ConstitutionalValidationResult), the AI
invocation surface (PromptModelManifest, ContextPacket, EmbeddingPayload,
ExecutionTask, TaskStructure), and all 13 vocabulary enums. Wave 2 and
Wave 3 cover governance routing, self-healing, API DTOs, and
observability persistence.

Implementation tracked in #366. Commit `4aad2ee4`.

Files: `.specs/decisions/ADR-056-runtime-data-contracts.md`,
`.specs/planning/data-contracts-inventory.md`.

---

## ADR-056 — 2026-05-18 (D5 closure)

ADR-056 D5 complete. Ten enum definitions added to
`.intent/META/enums.json`: `blackboard_entry_type`, `blackboard_subject`,
`action_impact`, `action_category`, `refusal_type`, `step_kind`,
`task_type`, `audit_severity`, `risk_tier`, `approval_type`. The
existing `proposal_status` enum extended with `rejected` to reconcile
with the Python `ProposalStatus` enum (governor decision: REJECTED is
the governor-veto outcome and belongs in the constitutional vocabulary).

Four reconciliation decisions captured in enum description text:
`risk_tier` kept separate from `proposal_risk` (validator input vs
proposal self-assessment); `approval_type` kept separate from
`proposal_approval_authority` (gating mechanism vs post-fact record);
`task_type` deferred vs ADR-003 `ExecutionTask.task_type` vocabulary;
`audit_severity` deferred vs CIM Pydantic Finding BLOCK/HIGH/MEDIUM/LOW/INFO.

ADR-056 D5 prose corrected: the original draft referenced "the existing
vocabulary canonical store rule" as the enforcement mechanism. That
phrasing was inaccurate — `governance.vocabulary_canonical_store`
governs term vocabulary at `CORE-Vocabulary.md` ↔ `vocabulary.json`,
not enum vocabulary at `enums.json`. The actual enforcement pattern is
`$ref` from JSON Schemas (precedent: `phase`, `worker_status`,
`artifact_status`). Python-source enum enforcement deferred to D6
SchemaConformanceChecks + Wave 1 schema authoring.

Inventory erratum: `blackboard_entry_status` has 9 canonical values
(ADR-045 + #263), not the 4 originally listed.

Commits: `19dcbe5c` (10 enums), `b6531e41` (proposal_status += rejected),
`4e01beae` (inventory erratum), and this commit (ADR text correction +
D5 closure).

Files: `.intent/META/enums.json`,
`.specs/decisions/ADR-056-runtime-data-contracts.md`,
`.specs/planning/data-contracts-inventory.md`.

---

## ADR-057 — 2026-05-18 (artifact + Phase 3 implementation)

API Phase 3: `/coverage`, `/refactor`, `/inspect`, and deferred
`POST /audit/remediations`. Three new resource tables (`coverage_runs`,
`refactor_runs`, `audit_remediation_runs`). All `/inspect` endpoints
read-only with no new tables. `POST /refactor/autonomous` routes through
a separate `refactor_runs` record — distinct from the `autonomous_proposals`
it produces, preserving GxP request-to-output traceability. Phase 4 boundary
confirmed: `inspect/repo_census.py` and `/census` namespace excluded.

Implementation landed in same session. Two constitutional violations caught
and corrected by audit during implementation: `architecture.path_access`
(hardcoded `"reports"` literal in `coverage_runner.get_coverage_history` →
replaced with `PathResolver.reports_dir`) and
`architecture.intent.non_gateway_no_direct_resolution` (direct
`yaml.safe_load` on `.intent/` file in `coverage_runner.get_coverage_targets`
→ replaced with `IntentRepository.load_document`). Audit verdict: PASS at
44 findings (down from 55 pre-implementation). 40 tests passing.

CLI cutover complete (2026-05-18). All 22 files in
`var/adr057-phase3-imports.txt` migrated. `CoreApiClient` extended with
33 Phase 3 helper methods. Two suppress markers placed for HTML coverage
report path (tracked in issue #358). Filtered audit on Phase 3 rules:
0 findings attributable to migrated files. ADR-057 fully verified.

Files:
`.specs/decisions/ADR-057-phase3-imports.md`,
`infra/scripts/migrations/20260518_create_phase3_tables.sql`,
`infra/sql/db_schema_live.sql`,
`src/shared/infrastructure/database/models/governance.py`,
`src/will/governance/coverage_runner.py`,
`src/will/governance/refactor_runner.py`,
`src/will/governance/inspect_runner.py`,
`src/will/governance/audit_remediation_runner.py`,
`src/api/v1/coverage_routes.py`,
`src/api/v1/refactor_routes.py`,
`src/api/v1/inspect_routes.py`,
`src/api/v1/audit_routes.py` (amended),
`src/api/main.py` (amended),
`tests/api/v1/test_coverage_routes.py`,
`tests/api/v1/test_refactor_routes.py`,
`tests/api/v1/test_inspect_routes.py`,
`tests/api/v1/test_audit_remediations.py`.

---

## 2026-05-18 — audit_runner Unicode sanitization (hotfix)

`run_sync_audit` and `run_and_persist_audit` in
`src/will/governance/audit_runner.py` now sanitize the findings JSONB
payload via `_sanitize_payload` before INSERT, mirroring the
`will.autonomy.proposal_mapper` precedent. Fixes 500 on
`POST /v1/audit/runs` caused by Unicode escape sequences rejected by
the SQL_ASCII database encoding. `core-admin code audit` restored to
full operation: PASS, 45 findings, findings persisted and queryable
via `GET /v1/audit/runs/{id}`. Closes #359.
Files: `src/will/governance/audit_runner.py`.

---

## ADR-058 — 2026-05-18 (artifact + Phase 4 implementation)

API Phase 4: `/census`, `/sync`, `/daemon`. Two new resource tables
(`census_runs`, `sync_runs` with `sync_type` discriminator). Daemon
lifecycle endpoints synchronous with no resource table; `POST
/daemon/stop` fire-and-forget via FastAPI BackgroundTask. Phase 4
completion is the ADR-050 CLI extraction trigger.

Implementation landed same session. Schema + routes: 2 tables, 3
Will-layer facades, 13 endpoints, 22 tests. CLI cutover: 7 files
migrated, 15 new CoreApiClient methods. `daemon.py` carries one
documented block-level SUPPRESS — bootstrap path deliberately separate
from `POST /v1/daemon/start`. Audit verdict PASS, 49 findings, no new
findings introduced.

ADR-053 D5 trigger met: all four phases complete, all ten namespaces
have endpoints, all CLI surfaces route through `api.*`. Extraction
unblocked pending unassigned `/components` + `/search` items (tracked).

Open items: #357 (orphan detector, now 10 runners), #358 (HTML
coverage report), #360 (CoreApiClient split), #361 (force flag on
`/sync/code-vectors`), unassigned namespace issue (extraction blocker).

Files:
`.specs/decisions/ADR-058-api-phase-4-census-sync-daemon.md`,
`infra/scripts/migrations/20260518_create_phase4_tables.sql`,
`infra/sql/db_schema_live.sql`,
`src/shared/infrastructure/database/models/governance.py`,
`src/will/governance/census_runner.py`,
`src/will/governance/sync_runner.py`,
`src/will/governance/daemon_runner.py`,
`src/api/v1/census_routes.py`,
`src/api/v1/sync_routes.py`,
`src/api/v1/daemon_routes.py`,
`src/api/main.py` (amended),
`tests/api/v1/test_census_routes.py`,
`tests/api/v1/test_sync_routes.py`,
`tests/api/v1/test_daemon_routes.py`,
`src/cli/commands/inspect/repo_census.py`,
`src/cli/commands/fix/db_tools.py`,
`src/cli/resources/vectors/sync.py`,
`src/cli/resources/vectors/sync_code.py`,
`src/cli/commands/dev_sync.py`,
`src/cli/commands/daemon.py`,
`src/cli/commands/run.py`,
`src/api/cli/client.py` (amended).

---

## ADR-053 / ADR-057 — 2026-05-18 (namespace assignment for unassigned capability map items)

`components.py` and `search.py` — the two CLI files left unassigned in the
original ADR-053 D4 capability map — are formally assigned to the Inspect
namespace group. ADR-053 D4 records the assignment and eliminates the two
alternative candidates (`/audit`, `/meta`) with explicit constraint reasoning.
ADR-057 D5 adds `GET /v1/components` and `GET /v1/search/capabilities` to the
Phase 3 endpoint surface. `GET /v1/search/commands` is Phase 3b deferred
pending extraction of `hub_search_cmd` from `cli.logic.hub` — tracked as #363.
Implementation complete: 7 files touched, ruff clean, zero `shared.*` imports
remaining in either CLI file. Closes #362. Unblocks ADR-050 CLI extraction.

---

## ADR-059 — 2026-05-19

Severity vocabulary governance. Three governor decisions from ADR-056 Wave 1:
D1: retire "dangerous" from RiskAssessment.overall_risk; align to proposal_risk enum (safe/moderate/high).
D2: replace audit_severity 3-value set (info/warning/error) with 5-value finding severity scale (info/low/medium/high/block); CIM surface aligned post-migration (issue #370).
D3: five severity surfaces documented as three distinct domains (audit findings, proposal risk, validator input); no unification; translation tables defined at risk_tier→proposal_risk and audit_severity→log-level boundaries as constitutional policy.
Files: .specs/decisions/ADR-059-severity-vocabulary-governance.md.

---

## ADR-060 — 2026-05-19

Governance input staleness closure. ADR-039 companion. reload_governance()
already landed on auditor.py:88 (commit e36b42f7). D1: extend wiring to
filtered_audit.py and audit_violation_sensor.py so all three audit entry
points refresh policies and enforcement mappings each cycle, matching the
existing invalidate_file_cache() coverage. D2: CORE-IntentRepository.md
§4a amended — "restart required" contract superseded; drift window bounded
to one sensor interval on all code paths.
Files: .specs/decisions/ADR-060-governance-input-staleness-closure.md,
src/mind/governance/filtered_audit.py,
src/will/workers/audit_violation_sensor.py.

---

## ADR-056 Wave 1 — 2026-05-19 (ProposalConsequence)

ProposalConsequence Python dataclass added to src/will/autonomy/proposal.py.
Mirrors core.proposal_consequences table row (ConsequenceLogService.record()
fields: proposal_id, pre/post_execution_sha, files_changed, findings_resolved,
authorized_by_rules, recorded_at). ProposalConsequence.json data contract
added to .intent/enforcement/contracts/. Closes the last deferred Wave 1
consequence-chain contract. governed_classes: ["ProposalConsequence"].
Files: src/will/autonomy/proposal.py,
.intent/enforcement/contracts/ProposalConsequence.json.

---

## Notes

* This changelog intentionally avoids implementation detail
* No legacy compatibility is implied
* Silence on future versions is intentional
