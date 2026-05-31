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

## ADR-056 Wave 1 — 2026-05-19 (ConstitutionalViolationPayload)

ConstitutionalViolationPayload frozen dataclass added to
src/mind/governance/violation_report.py. Governs the JSON-safe
serialization envelope produced by ConstitutionalViolationError.to_dict()
for persistence into proposal.execution_results. Fields: error (legacy
flat-string preserving backward compatibility), blocked_by, violation_count,
violations (list of ViolationReport primitives). to_dict() updated to build
via dataclasses.asdict() rather than a manual dict literal.
ConstitutionalViolationPayload.json data contract added to
.intent/enforcement/contracts/. Rule
data.contracts.constitutional_violation_payload_conforms added to
rules/data/governance.json and enforcement mapping
mappings/data/governance.yaml. governed_classes: ["ConstitutionalViolationPayload"].
Files: src/mind/governance/violation_report.py,
.intent/enforcement/contracts/ConstitutionalViolationPayload.json.

---

## ADR-056 Wave 1 — 2026-05-19 (WorkerDeclaration)

WorkerDeclaration frozen dataclass added to src/shared/workers/base.py
alongside the Worker base class that consumes worker declarations.
Re-exported via src/shared/workers/__init__.py. Governs the runtime
shape of `.intent/workers/*.yaml` declarations as returned by
IntentRepository.load_worker() and consumed by Worker.__init__ as
self._declaration. Source-of-truth schema remains
`.intent/META/worker.schema.json` for YAML validation; the dataclass
crystallises the same shape on the Python side so the AST gate has a
declared surface to reason about. Fields: kind, metadata, identity,
mandate, implementation, config (optional). Nested object fields are
kept as dicts; further nesting would add no enforcement power beyond
META/worker.schema.json on the YAML side. Class lives in base.py
(not a new file) following the established Wave 1 pattern
(ProposalConsequence in proposal.py, ConstitutionalViolationPayload in
violation_report.py) — avoids the orphan-file finding that a new
governance-only file would otherwise produce.

WorkerDeclaration.json data contract added to
.intent/enforcement/contracts/. Rule
data.contracts.worker_declaration_conforms added to
rules/data/governance.json and enforcement mapping in
mappings/data/governance.yaml. governed_classes: ["WorkerDeclaration"].

Closes the last deferred Wave 1 dataclass+contract item; ADR-056 Wave 1
deferral list (ProposalConsequence, ConstitutionalViolationPayload,
WorkerDeclaration) is now fully landed. AgentDecision.options_considered
remains a contract-level acknowledged JSONB sub-shape gap with no
writer in src/, not workable as Wave 1 dataclass work.

Files: src/shared/workers/base.py, src/shared/workers/__init__.py,
.intent/enforcement/contracts/WorkerDeclaration.json.

---

## ADR-061 — 2026-05-19

Composition-root sanctuary for `api/main.py` lifespan import. Codifies
the existing `architecture.api.no_body_bypass` exemption at
`layer_separation.yaml:237` (landed 2026-04-19, commit `f634e521`) as
the permanent answer. D1: `src/api/main.py` is exempt from the rule
for **exactly one import** — `body.infrastructure.lifespan.core_lifespan`,
required by FastAPI's `lifespan=` constructor argument at app creation
time. Relocation alternatives ruled out: `src/api/` destination would
require half a dozen new bypass imports (worse, not better); `src/will/`
is a semantic mismatch (Will is the cognitive layer, not infrastructure
ignition). D2: existing sanctuary scope verified correct (single-file,
per-rule, no glob, rationale comment in place at lines 233–237). D3:
revisit triggers — FastAPI lifespan contract changes, a second Body
import needed in `api/main.py`, or `core_lifespan`'s Body-residence
challenged. Permanent (not transitional); the FastAPI lifespan
contract is stable upstream. Closes #157.

Files: `.specs/decisions/ADR-061-composition-root-sanctuary-api-main.md`.

---

## ADR-062 — 2026-05-19

`proposal_lifecycle_actions.py` body→will closure. Closure ADR for the
`architecture.layers.no_body_to_will` exclude on
`src/body/atomic/proposal_lifecycle_actions.py`, which imports
`ProposalStatus` from `will.autonomy.proposal` to enforce the
`approved → executing` transition in the `claim.proposal` atomic action
(ADR-017). Two viable refactor paths named — Option A (preferred) move
`ProposalStatus` to `src/shared/lifecycles/proposal.py` matching
ADR-049's "shared as pure contracts" long-horizon direction; Option B
pass enum values as strings with Will-side validation. Deadline
2026-09-16 (120 days; matches ADR-051). The "TBD" deadline marker in
`layer_separation.yaml` is replaced with `2026-09-16` + back-reference
to this ADR. Closes first bullet of #313.

Files: `.specs/decisions/ADR-062-proposal-lifecycle-actions-body-will-closure.md`.

---

## ADR-063 — 2026-05-19

`bootstrap.py` `will.tools` body→will closure. Closure ADR for the
three lazy `will.tools.*` imports at
`src/body/infrastructure/bootstrap.py:60–64`
(`ArchitecturalContextBuilder`, `ModuleAnchorGenerator`,
`PolicyVectorizer`), all caught under the expanded ADR-049 D1
bare-prefix `forbidden:` list (commit `6edec08d`). Two paths —
Option A (preferred) re-home the three tools to
`src/shared/cognitive_tools/` since they are stateless protocol-based
builders fitting ADR-049's "shared as pure contracts" direction;
Option B invert ownership so Body owns the factory and Will instances
are injected via `CoreContext`. Deadline 2026-09-16. Closes
second/third/fourth bullets of #313.

Files: `.specs/decisions/ADR-063-bootstrap-will-tools-body-will-closure.md`.

---

## ADR-064 — 2026-05-19

`fix_actions.py` `capability_tagging` body→will closure. Closure ADR
for the `src/body/atomic/fix_actions.py:666` lazy import of
`will.self_healing.capability_tagging_service.main_async`, added under
the ADR-049 exclude in commit `5201b3b6`. The action is a thin Body
dispatch wrapper around a Will-resident agent that uses
cognitive/knowledge services. Two paths — Option A (preferred)
Body-layer dispatch facade with injected callable
(`CapabilityTaggingService` in `src/body/services/`, wired at lifespan
composition); Option B move `main_async` to Body, keep
`CapabilityTaggerAgent` as a Will-internal helper. Precedent:
`BrainServicesProvider` protocol injection (commit `c9332d73`).
Deadline 2026-09-16. Closes fix-actions bullet of #313.

Files: `.specs/decisions/ADR-064-fix-actions-capability-tagging-body-will-closure.md`.

---

## ADR-065 — 2026-05-20

Documentation layer separation: `.specs/` vs `docs/`. Declares
constitutional law for the two human-readable directories. D1:
`.specs/` is the **governance layer** (authoritative artifacts,
internal audience, governor-only); `docs/` is the **communication
layer** (external audience, reader-facing, no constitutional
authority). D2: authority and derivation are one-way: `docs/` →
`.specs/`, never the reverse. D3: explicit placement rules per
audience and authority. D4: specific placements confirmed —
`CORE-Features.md` and `CORE-Product-Tiers.md` in `.specs/papers/`;
ADRs in `.specs/decisions/`; URS in `.specs/urs/`; usage guides and
tutorials in `docs/`. D5: GitHub Feature issues link to `.specs/`,
not `docs/`. No automated rule; verification is governor
responsibility. Closes Track 10 placement ambiguity.

Files: `.specs/decisions/ADR-065-documentation-layer-separation.md`.

---

## ADR-066 — 2026-05-21

Unmapped-rules invariant — every active rule must have an
`auto_remediation.yaml` entry. Closes the silent abandoned-finding
re-emission loop where an active rule with no remediation map entry
produced **8,539 abandoned findings across four rules in 48 hours**
(`architecture.cli.api_only` 4,282; `purity.no_orphan_files` 1,691;
`architecture.channels.logger_not_presentation` 1,558;
`architecture.layers.no_body_to_will` 8). Invariant: every rule that
is `active` in the audit rule registry and capable of producing
findings MUST have a corresponding entry in
`.intent/enforcement/remediation/auto_remediation.yaml`. A
minimum-valid `DELEGATE` entry (confidence 0.40, below MIN_CONFIDENCE
0.80) is sufficient — it requires no automatable fixer, no action ID,
no implementation work. Its sole purpose is to close the loop:
`ViolationRemediatorWorker` recognises the entry, routes the finding
to the governor inbox, and the finding does not re-accumulate. New
blocking audit rule `governance.remediation.all_rules_mapped` enforces
the invariant at each audit cycle (severity HIGH; emits FAIL on
unmapped active rules). Self-referential: the new rule must itself
be mapped (DELEGATE). Implementation tracked as #418.

Files: `.specs/decisions/ADR-066-unmapped-rules-invariant.md`.

---

## ADR-067 — 2026-05-21

Constitutional Coherence Checker — storage, CLI, LLM invocation,
scheduling. Implementation decisions for the CCC instrument defined
in `.specs/papers/CORE-ConstitutionalCoherenceChecker.md`. D1: two new
tables `core.coherence_runs` and `core.coherence_candidates` (no FK
entanglement with `autonomous_proposals` / blackboard / findings —
CCC candidates are a separate governance artifact). D2: three CLI
subcommands `core-admin coherence check [--full] | report [RUN_ID]
| triage CANDIDATE_ID DECISION [--note TEXT]`. D3: dedicated
`constitutional_coherence_analysis` cognitive role (analysis-only,
read-only; produces no proposals, no blackboard entries, no file
writes); R1/R2/R3/R4 batching strategy; all failure modes non-fatal
(LLM/parse/schema/file failures → `skipped` with reason; >20% skip
emits WARNING; advisory threshold). D4: CCC is CLI-only, not a daemon
worker; trigger detection (`adr_added`, `northstar_changed`, `manual`)
computed at invocation time; automated daemon triggering deferred.
D5: advisory `Constitutional Coherence: …` line appended to
`core-admin code audit` output (does not affect PASS/FAIL verdict).
Closes #374 acceptance criteria.

Files: `.specs/decisions/ADR-067-constitutional-coherence-checker.md`.

---

## ADR-068 — 2026-05-22

Principal Role Taxonomy. Establishes CORE's constitutional role model
in three layers — Layer 1 taxonomy in `.intent/` (constitutional;
governor-amendment only); Layer 2 principal-to-role binding at
deployment (not part of the constitution); Layer 3 action-to-role
requirement in enforcement rules. D1: three-layer separation is
constitutional; roles are permanently flat (no inheritance, no
Layer-1 resource scoping — irrevocable). Mirrors NIST RBAC Core
(ANSI/INCITS 359-2004). D2: four declared roles —
`principal.governor`, `principal.operator`, `principal.auditor`,
`principal.system`. D3: SoD constraint — a Governor may not sign the
audit-verification record for an action they approved (declared now,
enforcement deferred to multi-operator tier). D4: Single-Governor
Local deployment posture defined as a constitutionally recognized
topology; authentication deferred when the only access path is
localhost. D5: `proposal_approval_authority` enum value
`human.cli_operator` retired and replaced by `principal.governor`
(migration backfills existing `autonomous_proposals` rows). D6:
canonical replacement template for founder-sovereignty language in
Tier A documents — resolves Track 10 with a derivable substitution
rather than editorial judgment. Satisfies 21 CFR Part 11 §11.50 and
EU AI Act Article 17(1)(m) at the constitutional level. Implementation
deferred (`.intent/governance/principal_roles.yaml`, `enums.json`
update, DB CHECK constraint update, `ProposalStateManager` call site,
backfill migration).

Files: `.specs/decisions/ADR-068-principal-role-taxonomy.md`.

---

## ADR-069 — 2026-05-23

Claim lifecycle: lease semantics. Closes the structural orphan-claim
gap (154 stuck `audit.violation` claims found 2026-05-23 across
2026-05-13 → 2026-05-19; ~26 fresh per daemon restart measured; orphan
rate is structural, not historical). D1: a `claimed` row's ownership
is bounded by a declared `lease_expires_at`; expiry is intrinsic to
the row, not asserted by surveillance — same posture as ADR-016
(confidence floor) extended to the ownership-lifecycle dimension.
D2: schema adds nullable `lease_expires_at TIMESTAMPTZ` to
`core.blackboard_entries`; terminal transitions set it to NULL;
`claimed_at` preserved as forensic record. D3: every worker
(daemon-run or CLI-triggered) MUST declare
`mandate.schedule.lease_seconds`; no runtime fallback;
`intent_validator.py` refuses workers omitting it. Migration values:
`violation_executor` 3600 s; `proposal_consumer_worker` and
`violation_remediator_body` 1800 s; all others 2× `max_interval`.
D4: `BlackboardService.renew_lease(entry_ids, claimed_by,
additional_seconds)` per-batch API; partial loss treated as full
batch loss; `LeaseExpiredError` raised and caught at `Worker.start()`;
`_on_lease_lost` hook for rollback. D5: terminal transitions release
the lease. D6: re-claim on expiry uses the same query path
(`status='claimed' AND lease_expires_at < now()` recognised as
re-claimable); partial index on `(lease_expires_at) WHERE
status='claimed'`. D7: migration backfills existing claimed rows at
`claimed_at + 600 s`; `release_claimed_entries` retained as
governor-override utility. Implementation deferred. Closes #439.

Files: `.specs/decisions/ADR-069-claim-lifecycle-lease-semantics.md`.

---

## ADR-070 — 2026-05-24

Source–projection coherence as bounded drift. Establishes representation
coherence as a constitutional property across the five-surface model
(`src/` + `.intent/` + `.specs/` as on-disk sources of truth; PostgreSQL
and Qdrant as derived projections). The property is **bounded drift,
not identity** — every projection's divergence from its source is
observable through audit/finding/remediation channels and bounded by a
constitutional value declared in `.intent/`, not inferred by
surveillance.

D1: representation coherence is constitutional. D2:
`.intent/governance/projections.yaml` inventory (governor-authored;
completeness is governor obligation — no automated discovery, since
no projection registry exists to enumerate against). D3: three bound
shapes (lease-style, hash-equality, reference-set). D4: coherence
sensors emit findings under `coherence.*` namespace; two permitted
patterns — independent sensor (`remediation.mode: proposal`, default)
and writer-as-sensor (`remediation.mode: inline`, reference-set pairs
only). The `logger.warning` anti-pattern (current state in
`RepoEmbedderWorker`) is constitutionally retired. D5: meta-rule
`governance.coherence.all_pairs_sensed` enforces declared-but-unsensed.
D6: composite "Representation Coherence" advisory line on
`core-admin code audit` output (parallel to ADR-067 D5's CCC line;
advisory only, does not affect PASS/FAIL verdict). D7: existing
partial mechanisms (ADR-030, ADR-039/060, `DbSyncWorker`,
`core-admin inspect drift`, `CommitReachabilityAuditor`) remain —
each documented as the sensor for its pair; no retrofit. D8: first
incremental delivery — `repo_artifacts ↔ filesystem` reframes #441 as
the framework's first pair (writer-as-sensor on `RepoCrawlerWorker`;
reap is one extra SQL operation in the existing walk pass). D9:
subsequent pairs sequenced by silent-blast-radius.

Cognate with ADR-016 (confidence floor), ADR-066 (unmapped-rules
invariant), and ADR-069 (claim lifecycle lease) — same pattern
(validity declared on the artifact, not inferred by surveillance)
extended to the representation layer. Implementation deferred; D8
implementation is the next step and closes #441.

Files: `.specs/decisions/ADR-070-source-projection-coherence.md`.

---

## ADR-075 — 2026-05-28

Framework/project namespace split. Formalizes Governance-Topology §8 from
declared principle into an enforced classification: every governance artifact
under `.intent/` and `.specs/` belongs to exactly one governance namespace —
`framework` (ships with CORE, applies to any governed project) or
`project::<name>` (specific to a named repo; CORE's own codebase is
`project::core`, a BYOR repo is `project::<external>`). The split is the
prerequisite for the governance-application data model, which cannot reason
over a surface that conflates framework and project ownership.

D1: the namespace model is constitutional. D2: namespace is declared in an
external path-to-namespace manifest, not per-file frontmatter — `.intent/`
artifacts are heterogeneous YAML/JSON with no shared frontmatter convention,
and stamping every file is a big-bang touch against the Topology §11
backfill-on-touch posture. D3: the key is `governance_namespace`, never bare
`namespace`, to avoid collision with the three existing senses (`rule_namespace`
sensor scope, blackboard subject namespace, API domain namespace). D4: two
artifacts realize the model — a vocabulary register
(`.intent/taxonomies/governance_namespaces.yaml`) and a classification manifest
(`.intent/governance/namespace_manifest.yaml`), following the ADR-068
register-plus-enforcement shape. D5: classification authority is per-artifact;
file type is a non-authoritative default heuristic only, because a rule, ADR, or
paper may be framework-general or CORE-specific regardless of type. D6: the
manifest is per-layer — the framework ships its own, each project carries its
own — which gives the separability #457 requires and the mechanism
`src/cli/logic/byor.py` will eventually consume. D7: a reporting rule
`governance.namespace.classification_complete` fails on any unclassified
`.intent/`/`.specs/` file, maintaining the invariant. D8: initial population is
a one-shot full classification (a bounded exception to §11, since partial
classification cannot unblock the data model), maintained thereafter by D7.

Grounded in `papers/CORE-Governance-Topology.md` §8 (row 2). Implementation
deferred: the register, manifest, and rule do not exist at acceptance; per
Topology row 4 strict the ADR D-text names each. Satisfies #457
close-condition 1; #457 remains open pending the manifest (close-2) and the
governance-application data-model follow-on issue (close-3).

Files: `.specs/decisions/ADR-075-framework-project-namespace-split.md`.

---

## ADR-075 — 2026-05-29 (implementation complete)

Framework/project namespace classification surface authored. The five
artifacts named in the ADR's D-text now exist on disk:

* `.intent/taxonomies/governance_namespaces.yaml` — vocabulary register
  (D3, D4). Declares the closed value space (`framework`,
  `project::<name>`) with `project::core` as the reserved self-name.
* `.intent/governance/namespace_manifest.yaml` — classification manifest
  (D4, D6, D8). One-shot full pass: every path under `.intent/` and
  `.specs/` (402 files) plus the four new artifacts (4 self-references)
  classified, 406 entries total — 152 `framework`, 254 `project::core`.
* `.intent/rules/governance/namespace.json` — rule
  `governance.namespace.classification_complete` (D7, reporting).
  Surfaces any `.intent/`/`.specs/` file with no manifest entry.
* `.intent/enforcement/mappings/governance/namespace.yaml` — enforcement
  mapping. `python_runtime` check_type
  `namespace_manifest_completeness`; severity WARNING.
* `.intent/enforcement/remediation/auto_remediation.yaml` — DELEGATE
  entry for the new rule, satisfying the ADR-066 unmapped-rules
  invariant. Inserted in TIER 3a adjacent to
  `governance.remediation.all_rules_mapped` and
  `governance.quarantine.namespace_has_drainer`.

The manifest is itself classified `project::core` — CORE's classification
data is project-layer, per D6. The register, rule, and mapping are
classified `framework` — they are the mechanism, inherited by any
deployment that adopts CORE.

Satisfies #457 close-condition 2 (manifest authored with every
`.intent/`/`.specs/` path classified) and close-condition 3 (follow-on
issue #479 for the governance-application data model). Closes #457.

Files: `.intent/taxonomies/governance_namespaces.yaml`,
`.intent/governance/namespace_manifest.yaml`,
`.intent/rules/governance/namespace.json`,
`.intent/enforcement/mappings/governance/namespace.yaml`,
`.intent/enforcement/remediation/auto_remediation.yaml`.

---

## ADR-076 — 2026-05-29

Context-level dispatch as a per-check-type engine property. Audit rules dispatch
either per-file (`verify(file_path)` once per file) or context-level
(`verify_context(context)` once over the repo). The dispatch is already per-rule
(`rule_executor.py:118`), but `is_context_level` was set per-engine
(`engine in CONTEXT_LEVEL_ENGINES`) — that asymmetry is the defect. `artifact_gate`
is mixed-mode: six repo-level governance/vocabulary checks that ignore `file_path`
plus three per-file PromptModel checks that parse it. A per-engine flag cannot
enroll a mixed engine without breaking the three per-file checks, so all nine
`artifact_gate` checks produced no findings under any condition since the audit
walker was authored 2026-05-16 — including ADR-066's blocking unmapped-rules
invariant (the abandoned-finding re-emit guard) and ADR-075 D7. No prior ADR or
paper governed context-level dispatch; this ADR governs it for the first time.

D1: context-level is a per-check-type property owned by the engine. D2: the
extractor consults `engine.is_context_level_for(check_type)` instead of the
`CONTEXT_LEVEL_ENGINES` frozenset, which is retired; `workflow_gate` and
`knowledge_gate` declare their modes via the same method. D3: `artifact_gate`
becomes explicitly mixed-mode, gaining `verify_context` for its six repo-level
check_types and keeping `verify` for the three per-file ones. D4: each rule's
effective mode is surfaced in audit/inspect output — visibility under a single
source of truth, not a second declaration in `.intent/`. D5: the audit walker
admits the file set per-file rules declare, derived from active rule `scope`
declarations (the per-file half of #480, consistent with the ADR's
projection-from-declarations stance). D6: every check_type must demonstrably fire
on a planted violation — a test-time coverage gate testing the property that
matters rather than a `file_path`-usage proxy.

Grounded in `papers/CORE-Gate.md` (engine-model context; the paper does not
itself govern dispatch mode). Implementation deferred and tracked on #481; closes
#480 at land, with the ADR-066 provocation as the acceptance gate. Complements
ADR-075's implementation entry: that entry records D7 as gated by #480; this one
removes that gate for nine rules.

Files: `.specs/decisions/ADR-076-per-check-type-context-level-dispatch.md`.

---

## ADR-077 — 2026-05-30

Config-driven protected-namespace access with an introspective
filesystem-operation taxonomy. The trust claim that operational CORE
cannot mutate its own constitution was enforced only narrowly: IntentGuard
blocks `.intent/` writes as a tier-1 invariant but only for writes routed
through FileHandler; the two ast_gate backstops split the axes — one
namespace-aware but write-blind, the other write-aware but
namespace-blind — and neither was both at once. Three live bypasses
reached protected namespaces directly: variable-receiver
`write_text`/`write_bytes`, uncovered `mkdir`/`makedirs`/`touch`/
`symlink`/`link`/`chmod`, and bare-import forms of `os.{replace,rename,
remove,unlink,rmdir}`. Protected-namespace literals and operation
call-sets were hardcoded `ClassVar` frozensets, invisible to governance.
`.specs/` had no equivalent protection at all.

The ADR moves the access policy into config and the operation vocabulary
into a governed taxonomy. `.intent/taxonomies/filesystem_operations.yaml`
becomes the canonical call-name → op-class mapping for the audit-time
backstop; per-entry match mode (`leaf` vs `qualified`) closes the
variable-receiver and bare-import bypasses without false-positiving on
collision-prone names (`str.replace` etc.). An introspective completeness
check in `artifact_gate` guards the taxonomy against `pathlib.Path` drift
and a curated cross-module watched set — fail-closed against the live
stdlib. The enforcement rollout is two dials on one policy phased across
five steps: land the taxonomy, land the completeness check, promote the
blocking dial for protected markers, keep the broad-path advisory dial
advisory until the gateway's read methods exist, then converge the
~340-site migration under the advisory perimeter.

Pre-existing gaps recorded honestly rather than closed: variable-receiver
`p.replace(...)` / `p.rename(...)` / `p.open(mode)` remain detection-inert
because leaf-matching `replace`/`rename`/`open` would collide with
`str.replace`, `tarfile.open`, etc. (~143 src/ collision sites). Tracked
under #506 (Phase 2 honesty addendum) and the §6 step 3 plan.

Grounded in `papers/CORE-Enforcement-Completeness.md` (runtime↔audit
complement and completeness-against-runtime-reality principle) and
`papers/CORE-IntentGuard.md` (the runtime Gate whose reach gap motivates
the audit-time check). Closes #489 and #507 at land.

Files:
`.specs/decisions/ADR-077-protected-namespace-access.md`,
`.intent/taxonomies/filesystem_operations.yaml`,
`.intent/enforcement/mappings/architecture/governance_basics.yaml`,
`.intent/enforcement/mappings/architecture/mutation_surface.yaml`,
`src/shared/infrastructure/intent/filesystem_operations.py`,
`src/mind/logic/engines/ast_gate/checks/purity_checks.py`,
`src/mind/logic/engines/ast_gate/engine.py`,
`src/mind/logic/engines/artifact_gate.py`.
Commits 6a7f6965 (steps 1+2), 17173680 (Phase 1 prep), 047a3165 (drain),
4a1b867f (boundary fix), bf3521aa (Phase 2 — step 3 convergence).

---

## ADR-078 — 2026-05-30

Operational-Capability Taxonomy Schema. Closes bullet 2 of the
Capability-Scoped Filesystem Authority paper's §9 deferral set: the
data-model schema for `.intent/taxonomies/operational_capabilities.yaml`,
which until this ADR could not become governance because no stable schema
existed for it to land on. The forcing inventory enumerated the live
`@atomic_action` surface across nine clusters but self-declared as
"planning document, NOT governance"; this ADR provides the schema that
lets each capability declare a per-capability `fs_profile` of allowed
op-classes plus its risk classification, identity, and chokepoint
primitive binding.

Four pre-existing patterns constrain the choice space: the
`.intent/taxonomies/` precedent (ADR-068, fail-closed Python loader, no
META schema); the operation-class vocabulary declared by ADR-077;
`.intent/META/enums.json` as the canonical home for cross-document closed
vocabularies; and `.intent/enforcement/config/action_risk.yaml` as the
existing source of truth for per-action risk. The schema honours all
four: the loader is the sole sanctioned reader, the `fs_profile` keys
reference op-classes from `filesystem_operations.yaml`, the enum is
binding-validated against `enums.json`, and the risk field cross-checks
against `action_risk.yaml`. Structural deviation raises a typed
`OperationalCapabilityTaxonomyError`.

The ADR establishes a first-materialization clause for shared enums
(D5): whichever sibling ADR's implementation lands first creates the
enum entry in `enums.json`; the second no-ops. This clause was exercised
and refined by ADR-080.

Grounded in `papers/CORE-Capability-Scoped-Filesystem-Authority.md` §9
bullet 2 and `papers/CORE-Cognitive-Role-Capability-Resource-Taxonomy.md`
(parent framework for `.intent/taxonomies/`).

Files:
`.specs/decisions/ADR-078-operational-capability-taxonomy-schema.md`,
`.intent/taxonomies/operational_capabilities.yaml`,
`src/shared/infrastructure/intent/operational_capabilities.py`,
`.intent/META/enums.json`.

---

## ADR-079 — 2026-05-30

Chokepoint Implementation for Capability-Scoped Filesystem Authority.
Closes bullets 5 and 6 of the Capability-Scoped Filesystem Authority
paper's §9: the chokepoint's identity-propagation implementation and the
migration path from today's `scope.excludes`-based perimeter to
capability-keyed authorization. The runtime chokepoint becomes capability
tier-aware: each filesystem mutation transaction carries the calling
capability's identity through `FileHandler` to `IntentGuard`, which
authorizes (or refuses) against the operational-capability taxonomy's
per-capability `fs_profile` declarations.

Two-stage rollout. Stage 1 (advisory): the capability tier emits
log-only `would-deny` lines at the existing tier-1 chokepoint; raises
remain governed by the existing `scope.excludes` perimeter, so behaviour
is unchanged but every mismatched transaction is observable. Stage 2
(phantom resolution): the inventory contract is enforced — every
capability declared in `operational_capabilities.yaml` must resolve to a
live `@atomic_action` registration, and every live `@atomic_action` must
have a taxonomy entry. Drift between the two surfaces fails the
introspective completeness check at engine startup.

Three items remain explicitly deferred to their own ADRs: the mode-flag
startup mechanism and its provenance guarantees (#492), the
governor-token machinery for development-mode privileged writes, and
the full operational migration execution plan beyond the framing in D10.

Grounded in `papers/CORE-Capability-Scoped-Filesystem-Authority.md` §§4–7
(chokepoint, capability-scoped least authority, mode dimension, identity
at the chokepoint). Closes #495 (operational_capabilities phantoms) at
stage 2 land.

Files:
`.specs/decisions/ADR-079-chokepoint-implementation-for-capability-scoped-filesystem-authority.md`,
`src/shared/infrastructure/storage/file_handler.py`,
`src/body/governance/intent_guard.py`,
`src/shared/infrastructure/intent/operational_capabilities.py`.

---

## ADR-080 — 2026-05-31

Filesystem-operation-class vocabulary split. The original
`fs_operation_class` enum in `.intent/META/enums.json` conflated two
distinct meanings under one spelling: a write-axis vocabulary
(`[read, create, modify, delete]`) consumed by
`operational_capabilities.yaml`'s `fs_profile`, and a read/traverse-axis
vocabulary needed by `filesystem_operations.yaml`'s call-name
classification (`[read, traverse, parse, write, neutral]`). Both
surfaces would have used the same enum key with different values —
violating `papers/CORE-Vocabulary.md`'s discipline that one spelling
must carry one meaning.

The ADR splits the enum along the meaning boundary. `fs_operation_class`
keeps its existing `[read, create, modify, delete]` values for the
capability/write-axis surface. A new `fs_audit_op_class` enum carries
`[read, traverse, parse, write, neutral]` for the audit/read-axis
surface. Both are declared in `.intent/META/enums.json`; the loaders for
the two consumer taxonomies each cross-reference exactly one of them.
ADR-078's first-materialization clause is preserved and now applies
per-enum rather than per-spelling.

Grounded in `papers/CORE-Vocabulary.md` (one term, one definition, one
spelling — and its corollary that one spelling per meaning is the same
discipline). Unblocks ADR-077 §6 step 1 (the audit-side taxonomy could
not bind to a meaningful enum until the split landed) and transitively
unblocks #489.

Files:
`.specs/decisions/ADR-080-fs-op-class-vocabulary-split.md`,
`.intent/META/enums.json`.
Commits df6d95ca (Proposed), 3499d489 (Accepted), 3e8eefc0
(materialization).

---

### #490 — Engine check rename: `IntentAccessCheck` → `ProtectedNamespaceAccessCheck`

The literal scope of #490, deferred from ADR-077. The class was
`.intent/`-specific in name only — its constitutional intent (announced
in ADR-077) is broader: no direct access to any protected namespace
outside its sanctioned gateway. The name now matches the intent.

Renames in one atomic commit:
- Class: `IntentAccessCheck` → `ProtectedNamespaceAccessCheck` (fresh UUID)
- File: `checks/intent_access_check.py` → `checks/protected_namespace_access_check.py`
- Method: `check_direct_intent_access` → `check_protected_namespace_access`
- Engine dispatch key: `direct_intent_access` → `protected_namespace_access`
- Rule ID: `architecture.intent.non_gateway_no_direct_resolution` → `architecture.namespace.no_direct_protected_access`

Behaviour preserved verbatim. Markers (`.intent`, `intent_root`, etc.),
the gateway path (`src/shared/infrastructure/intent/`), and the
traversal/read/parse call sets all remain hardcoded to `.intent/`
semantics. Promoting these to rule-supplied parameters
(`protected_markers`, `gateway_segment`, `forbidden_classes`) is the
generalisation step ADR-077 anticipated and is intentionally separate
follow-up work — keeping the rename atomic limits the symbol-index
ripple to one bounded change.

Old rule ID kept in inline comments on the rule (`.intent/rules/architecture/intent_access.json`,
`_renamed_from` field) and on the mapping
(`.intent/enforcement/mappings/architecture/intent_access.yaml`, header
comment) for greppability. Auto-remediation map key updated.

No back-compat: the old `check_type: direct_intent_access` and the old
rule ID no longer dispatch / no longer match. Audit-log finding subjects
shift from `…architecture.intent.non_gateway_no_direct_resolution…` to
`…architecture.namespace.no_direct_protected_access…` going forward.

Files:
`src/mind/logic/engines/ast_gate/checks/protected_namespace_access_check.py` (new, replaces `intent_access_check.py`),
`src/mind/logic/engines/ast_gate/engine.py`,
`src/mind/logic/engines/ast_gate/checks/__init__.py`,
`.intent/enforcement/mappings/architecture/intent_access.yaml`,
`.intent/rules/architecture/intent_access.json`,
`.intent/enforcement/remediation/auto_remediation.yaml`,
`src/shared/governance/coherence_harvester.py` (docstring),
`src/will/governance/coverage_runner.py` (docstring),
`tests/engines/test_intent_access_check.py`,
`.specs/decisions/ADR-077-protected-namespace-access.md` (Note appended).
Closes #490.

---

### #490 — Engine check rename: `import_boundary` → `runtime_import_boundary`

Honesty cleanup, deferred from ADR-077. The `ast_gate` engine's
`import_boundary` check forbade *imports*; the rule IDs that dispatched
to it (e.g. `architecture.mind.no_body_invocation`) declared a
constitutional intent about *invocation*. The check also silently
exempted `if TYPE_CHECKING:` blocks — a convention authored in the
engine but invisible in the rule YAML, so a reader of the rule alone
could not tell whether type-level cross-layer references counted as
violations.

The check is renamed `runtime_import_boundary` so its name announces
what it actually checks (runtime imports, not all imports). The
TYPE_CHECKING exemption is promoted from a hardcoded engine convention
to a rule-visible parameter (`type_checking_exempt: true` default). The
constitutional intent — *mind knows body's surface (proprioception),
mind does not invoke body's machinery* — is now expressed at three
layers (rule ID, check name, parameter) telling the same story.

No back-compat alias: the old `import_boundary` string no longer
dispatches. Audit-log identifiers shift from `ast_gate.import_boundary`
to `ast_gate.runtime_import_boundary` going forward; historical records
are unchanged.

Files:
`src/mind/logic/engines/ast_gate/checks/runtime_import_boundary.py`
(new, replaces `import_boundary.py`),
`src/mind/logic/engines/ast_gate/engine.py`,
`.intent/enforcement/mappings/architecture/{layer_separation,async_logic,privileged_boundaries}.yaml`,
`.specs/decisions/ADR-049-doctrine-rule-parity.md` (Note appended),
`.specs/decisions/ADR-063-bootstrap-will-tools-body-will-closure.md` (Note appended).
Closes #490.

---

## Notes

* This changelog intentionally avoids implementation detail
* No legacy compatibility is implied
* Silence on future versions is intentional
