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

## Notes

* This changelog intentionally avoids implementation detail
* No legacy compatibility is implied
* Silence on future versions is intentional
