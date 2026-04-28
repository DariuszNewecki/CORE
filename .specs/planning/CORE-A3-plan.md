# CORE — A3 Governed Autonomy Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-28
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
| **G2 — Convergence** | Sustained state where rate of finding resolution exceeds rate of finding creation. Per the Convergence Principle, this is the fundamental operational metric — it is what makes "governed autonomy" truthful rather than aspirational. | ⚠️ Not yet measurable. Queue stagnation (not failure) was the prior state; reclassification under ADR-014 unblocked the queue, making G2 rate observable in principle. `resolved_at` hygiene confirmed 2026-04-27 (#135 closed) — the temporal column CONV.1 depends on is now reliable. Sustained measurement pending. |
| **G3 — Consequence chain** | Finding → Proposal → Approval → Execution → File changes → New findings is continuously materialized as a queryable causality chain. Required for regulated environments, autonomous debugging, and for a non-programmer governor to trust the system without reading code. | 🔄 In progress. Strategic arc decomposed via URS + ADR-015 + ADR-017. Edges 1, 2 (forward-path), and 3 closed across 2026-04-27 / 2026-04-28 — approval attribution (Edge 2) non-omittable at write path; finding↔proposal linkage (Edge 1) populated on both deferred and subsume paths; claim attribution (Edge 3) populated via `claim.proposal` atomic action with `claimed_by` column on every claim (autonomous workers thread `self.worker_uuid`; CLI threads `CLI_CLAIMER_UUID` sentinel). URS Q1.F, Q1.R, Q2.A, Q2.F, Q3.F, Q3.R demonstrable end-to-end on live data. Edge 5 sibling opened 2026-04-27 covering orphan-commit and 8-char prefix-collision brittleness (Band B); #124 retained for commit-message fidelity (Band D). Remaining edges (5-sibling, 6) queued under Band B on GitHub. |
| **G4 — Governance in `.intent/`** | No enforcement logic, path mappings, policy thresholds, or governance decisions live in `src/`. All of it lives in `.intent/` (or, for human-intent documents, `.specs/`). This is the claim that makes the "non-programmer governor" role coherent. | 🔄 In progress. ADR-004 (task_type phase map) and ADR-005 (audit verdict policy) were direct advances. Known leaks: path mappings embedded in some sensor/action code; `action_executor` usage unguarded in some Body workers; `impact_level` in `@register_action` decorators (ADR-008 parked, debt acknowledged in ADR-014). |

**Gate coupling:** G1 cannot be *proved* without G3 (you can't demonstrate the loop closed without the chain). G2 cannot be *measured* without G1 (no resolution rate without autonomous resolution). G4 is orthogonal but load-bearing: it is the reason a non-programmer can operate the system, and without it the other three gates describe a system that still requires its author.

---

## A3 Phases

### Phase 0 — Clean Slate ✅
Known-good starting point before activating anything.

### Phase 1 — Single Loop, Proven Convergence ✅
Purity sensor loop, Blackboard empty.

### Phase 2 — Expand Sensors ✅
All seven audit sensors active.

### Phase 3 — Capability Gaps 🔄

**Framing:** Phase 3 is the **trust-hardening phase** — the machinery producing the verdict is being qualified. It is not yet autonomy-operation. See "A3 Gates" above for what closing Phase 3 means in concrete terms: G1 and portions of G3/G4 close here.

**Status:** Stream A (ViolationExecutor) complete. Stream B (test writing) structurally complete. Stream C (delegation) infrastructure complete. Band A (attribution) closed via ADR-011.

Remaining Phase 3 work tracked on GitHub under Band D — Engine Integrity:
https://github.com/DariuszNewecki/CORE/milestone/16

### Phase 4 — CLI Health ⬜
Not started. Tracked items captured as GitHub issues.

### Phase 5 — Visibility 🔄
Started 2026-04-27. **G3 closes here** — consequence chain materialization is a Phase 5 artifact. Tracked on GitHub under Band B — Consequence Chain:
https://github.com/DariuszNewecki/CORE/milestone/14

---

## Bands

Operational work tracking lives entirely on GitHub. Bands are strategic groupings; closure criteria live on each milestone.

- **Band A — Attribution** (closed): https://github.com/DariuszNewecki/CORE/milestone/13
- **Band B — Consequence Chain**: https://github.com/DariuszNewecki/CORE/milestone/14
- **Band C — Historical Debt**: https://github.com/DariuszNewecki/CORE/milestone/15
- **Band D — Engine Integrity**: https://github.com/DariuszNewecki/CORE/milestone/16
- **Band E — Outward-Facing**: https://github.com/DariuszNewecki/CORE/milestone/17

All issues opened under SESSION-PROTOCOL.md §6 template. `priority:high` labels mark items blocking a band from closing. Resolution dates and verification artifacts live on the closing comment of each issue, not in this document.

---

## Architectural Decisions Made

This section is the only place in this plan-doc that enumerates work-products, because ADRs are the durable rationale layer — issues come and go, ADRs are the reasoning we commit to.

### ADR-001 (2026-04-15) — `.specs/` layer established
Non-operational documents move out of `.intent/` into `.specs/`.

### ADR-002 (2026-04-18) — Shared layer boundary enforcement
All shared/ boundary violations resolved through architectural moves, not rule exceptions. Established "Policy in `.intent/`, mechanism in `src/`" principle.

### ADR-003 (2026-04-19) — `task_type` as first-class field on `ExecutionTask`
Test generation correctly routes through `audit` phase rather than `execution`. `build_tests_action` sets `task_type="test_generation"`; `CodeGenerator._build_context_package` passes it through.

### ADR-004 (2026-04-19) — Govern task_type → phase mapping in `.intent/`
Three-way drift (service, CLI, vestigial file) collapsed to single source at `.intent/enforcement/config/task_type_phases.yaml`. Vestigial `src/shared/infrastructure/context/cli.py` retired in same change-set.

### ADR-005 (2026-04-20) — Govern audit verdict policy in `.intent/`
Severity→verdict mapping, carve-out list, and DEGRADED preconditions codified as data at `.intent/enforcement/config/audit_verdict.yaml`. Governed loader at `src/shared/infrastructure/intent/audit_verdict.py` mirrors the ADR-004 `task_type_phases.py` pattern.

### ADR-006 (2026-04-20) — Align `modularity.needs_split` implementation with its statement
Rule statement is law, implementation is mechanism; when they disagree, the mechanism is corrected. `_identify_concerns(imports)` replaced with `_detect_responsibilities(...)` so the check measures "single coherent responsibility" (content-pattern-based) rather than "narrow external domain-library exposure" (import-based proxy).

### ADR-007 (2026-04-21) — `modularity.class_too_large` rule split from `modularity.needs_split`
`modularity.class_too_large` introduced as a distinct rule. Sensor layer routes via a deterministic structural test using two sensor methods, matching the 1-rule-to-1-method pattern. Separates the automatable module-redistribution case from the non-automatable dominant-class case.

### ADR-008 (2026-04-22, parked) — Constitutionalize `impact_level`
Documents the governance-in-code inversion where `impact_level` (auto-approve vs. requires-human) is declared in `@register_action` decorators rather than in `.intent/`. Parked — not session-scale. ADR-014 makes a `src/`-side reclassification under this debt; the `safe` value migrates with the rest when ADR-008 is unparked.

### ADR-009 (2026-04-24) — CLI-depth block transient — passive instrumentation over active probe
No `cli.*` rule or YAML mapping modified; no active reproduction of the transient attempted. Passive instrumentation in place persists full `ConstitutionalViolationError.to_dict()` attribution into `action_results.violations[]`, capturing any recurrence — `rule_name`, `path`, `source_policy` — without live introspection.

### ADR-010 (2026-04-24) — Wire the §7 + §7a Finding/Proposal contract
All three gaps closed in one coordinated change: correct terminal status (`deferred_to_proposal`), forward link added (`proposal_id` in finding payload), revival implemented on proposal failure. `BlackboardService` gains `defer_entries_to_proposal`; worker resolve path fixed; `ProposalStateManager` implements the §7a revival query.

### ADR-011 (2026-04-24) — Workers own blackboard attribution; services do not post
Every INSERT into `core.blackboard_entries` must originate from a registered Worker via base-class `post_finding` / `post_report` / `post_heartbeat` / `_post_entry`. Services may UPDATE (state transitions) but never INSERT. Architectural cut: INSERT creates attribution (Worker-only); UPDATE transitions pre-attributed rows (anyone). Enforcement rule `architecture.blackboard.worker_only_inserts` active at blocking severity. Band A closed.

### ADR-012 (2026-04-25) — Centralize globstar pattern matching via `pathspec`
Eight `Path.match` call sites carried Python 3.12's `**`-as-single-segment quirk; three were silent under-enforcement at security-sensitive sites (redactor, FileNavigator). Adopted `pathspec`'s `GitWildMatchPattern` as the standard primitive; introduced `src/shared/utils/glob_match.py` as the single entry point; migrated raw call sites and rewrote forbid-pattern strings to gitignore semantics.

### ADR-013 (2026-04-26) — Retire core.proposals; reserve name for core.autonomous_proposals
`core.proposals` (constitutional file-replacement table with cryptographic signing) retired. Never provisioned in production — 0 rows, no active writers, signing infrastructure never created. All proposal activity runs through `core.autonomous_proposals`. Table name `core.proposals` reserved: when "autonomous" becomes redundant (all proposals are autonomous), `core.autonomous_proposals` renames to `core.proposals`.

### ADR-014 (2026-04-26) — Development-phase priority: loop liveness before artifact quality
Establishes the priority order during CORE's development phase: loop liveness > productivity > quality (sequential, not parallel). A loop that produces zero outputs has zero resolution rate; quality is observable only on a moving system. First application: reclassifies `build.tests` from `impact_level="moderate"` to `impact_level="safe"`. Diagnostic finding: the pre-generation approval gate that the moderate classification triggered had no artifact to inspect — LLM generation happens at `executing`, not `draft`. Three commit-time gates (Conservation, IntentGuard, Canary) and TestRunnerSensor remain. Revisit triggers concrete (measured hallucination rate, signal contamination, deployment-phase change, ADR-008 unpark). G4 leak via ADR-008 acknowledged as known debt.

### ADR-015 (2026-04-27) — Consequence chain attribution: write paths and storage shapes
Decides write paths and storage shapes for the Band B consequence-chain work as seven coordinated sub-decisions (D1–D7). D1: `finding_ids` as jsonb key in `constitutional_constraints`. D2: `approval_authority` as new column with forward-only CHECK. D3: `claimed_by uuid` as new column on proposals. D4: subsume-path writes `proposal_id` into payload. D5: sensor cause attribution heuristic via `proposal_consequences` lookup at post time. D6: `ProposalStateManager.approve()` signature carries `approval_authority`. D7: forward-only enforcement; no historical backfill (ALCOA "Complete" preserves originals). Each sub-decision names its Change sites with file:line references. Authored against the URS (industry defaults from 21 CFR Part 11 §§11.10/11.50 and ALCOA+). D1, D2, D4, D6, D7 implemented end-to-end 2026-04-27.

### ADR-016 (2026-04-27) — Test environment architecture
Designs CORE's test environment as four coordinated sub-decisions: schema authority is the SQLAlchemy model registry (D1); `core_test` is ephemeral per pytest session via drop+create+`create_all` (D2); per-test isolation via `TRUNCATE CASCADE` — transactional rollback rejected as structurally impossible because workers commit in their own sessions (D3); CI uses GitHub Actions Postgres service container (D4). Retires the stale `db_schema_live.sql` dump, the broken `reset_test_db.sh`, and the `_ensure_blackboard_table` workaround. Forces but does not answer the production-migration story (separate ADR required). Recon baseline: `.specs/state/2026-04-27-test-environment-recon.md`.

### ADR-017 (2026-04-28) — `claim.proposal` as atomic action
Decides that proposal claim (the approved → executing transition) is performed by a constitutional atomic action rather than a service method, satisfying URS Q3.F (forward) and Q3.R (reverse). Five sub-decisions: D1 — `claim.proposal` action with `category=STATE`, `policies=["rules/will/autonomy"]` (transitional ref to be replaced by a dedicated `proposal_lifecycle.json` policy per #169); D2 — `ProposalStateManager.mark_executing` and the `ProposalService.mark_executing` wrapper removed; bounded inconsistency with the remaining mark_completed/mark_failed/approve/reject methods documented; D3 — `ProposalExecutor.execute()` and `execute_batch()` invoke `claim.proposal` via `ActionExecutor`, threading `claimed_by: UUID`; D4 — CLI sentinel UUID `00000000-0000-0000-0000-000000000001` (`CLI_CLAIMER_UUID`) identifies CLI-class claims as distinct from autonomous worker claims, mirroring the ADR-015 D6 / NFR.5 `approval_authority='human.cli_operator'` pattern at the claim layer; D5 — preserves ADR-015 D3's `claimed_by uuid` column shape; write-path wording amended to "atomic action sets the column" rather than "state manager sets the column." Implementation 2026-04-28 in commits 6ee9c7c5 + 2136ffb6.

---

## Intent Layer Hygiene — proposed (not executed)

`.specs/` has grown organically. Proposal captured here for a later session.

**Proposed reorganization:**
- `state/` keeps only periodic state snapshots (`CORE-state-YYYY-MM-DD.md`)
- `state/investigations/` holds dated one-off analyses
- `state/handoffs/` holds the handoff archive
- `whitepapers/` (new) holds external-facing positioning documents
- `META/` gains minimum-viable schemas for: paper, ADR, URS, handoff, plan, state snapshot, investigation, whitepaper
- Naming convention: `kebab-case` for multi-word filenames; date prefix `YYYY-MM-DD-` for dated artifacts; no spaces anywhere

**Execution cost:** one session.

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

# Context (REQUIRED before every Claude Code prompt that touches src/)
core-admin context build --file <target_file> --task code_modification --goal "<goal>" --no-cache

# Proposals
core-admin proposals list
core-admin proposals list --full-ids

# Vectors
core-admin vectors sync --write
core-admin vectors query "<query>" --collection policies|patterns|specs --limit <n>

# Sync
poetry run core-admin dev sync --write

# DB (only when no core-admin command covers the need)
# Connection requires PGPASSWORD env var or ~/.pgpass.
PGPASSWORD=core_db psql -U core_db -d core -h 192.168.20.23
```

---

## Standing Workflow Rule — Claude Code Prompts

**Every Claude Code prompt that modifies or creates a `src/` file requires a context build first.**

```
Before writing any code, run this command and read the output:

core-admin context build \
  --file <target_file> \
  --task code_modification \
  --goal "<what this change does>" \
  --no-cache

Then read <target_file> in full.
Then [implementation instruction].
Return the complete corrected file.
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
BlackboardAuditor                      ← active
    → monitors Blackboard SLA health
WorkerAuditor                          ← active
    → monitors worker liveness
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
