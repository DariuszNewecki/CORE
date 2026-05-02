# CORE — A3 Governed Autonomy Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-05-02
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
| **G3 — Consequence chain** | Finding → Proposal → Approval → Execution → File changes → New findings is continuously materialized as a queryable causality chain. Required for regulated environments, autonomous debugging, and for a non-programmer governor to trust the system without reading code. | ✅ Closed 2026-05-01. All six edges delivered. Epic #110 closed; Band B milestone 14 closed. |
| **G4 — Governance in `.intent/`** | No enforcement logic, path mappings, policy thresholds, or governance decisions live in `src/`. All of it lives in `.intent/` (or, for human-intent documents, `.specs/`). This is the claim that makes the "non-programmer governor" role coherent. | 🔄 In progress. Known leaks: path mappings embedded in some sensor/action code; `action_executor` usage unguarded in some Body workers; `impact_level` in `@register_action` decorators (ADR-008 parked, debt in ADR-014). |

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

**Framing:** Phase 3 is the **trust-hardening phase** — the machinery producing the verdict is being qualified. G1 and portions of G3/G4 close here.

**Status:** Stream A (ViolationExecutor) complete. Stream B (test writing) structurally complete. Stream C (delegation) infrastructure complete. Band A (attribution) closed via ADR-011.

Remaining Phase 3 work tracked on GitHub under Band D — Engine Integrity:
https://github.com/DariuszNewecki/CORE/milestone/16

### Phase 4 — CLI Health ⬜
Not started. Tracked items captured as GitHub issues.

### Phase 5 — Visibility ✅
G3 closed 2026-05-01. Consequence chain materialized end-to-end. Band B milestone 14 closed.

---

## Bands

Operational work tracking lives entirely on GitHub. Bands are strategic groupings; closure criteria live on each milestone.

- **Band A — Attribution** (closed): https://github.com/DariuszNewecki/CORE/milestone/13
- **Band B — Consequence Chain** (closed): https://github.com/DariuszNewecki/CORE/milestone/14
- **Band C — Historical Debt**: https://github.com/DariuszNewecki/CORE/milestone/15
- **Band D — Engine Integrity**: https://github.com/DariuszNewecki/CORE/milestone/16
- **Band E — Outward-Facing**: https://github.com/DariuszNewecki/CORE/milestone/17

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
| ADR-008 | 2026-04-22 *(parked)* | Constitutionalize `impact_level` | `impact_level` in `@register_action` decorators is a G4 leak; migration deferred. |
| ADR-009 | 2026-04-24 | CLI-depth block transient — passive instrumentation | No rule modified; full `ConstitutionalViolationError` attribution persisted into `action_results`. |
| ADR-010 | 2026-04-24 | Wire the §7 + §7a Finding/Proposal contract | Correct terminal status, forward link, and revival implemented in one coordinated change. |
| ADR-011 | 2026-04-24 | Workers own blackboard attribution; services do not post | Every INSERT into `blackboard_entries` must originate from a Worker. Band A closed. |
| ADR-012 | 2026-04-25 | Centralize globstar matching via `pathspec` | Eight `Path.match` sites migrated to `src/shared/utils/glob_match.py` using `GitWildMatchPattern`. |
| ADR-013 | 2026-04-26 | Retire `core.proposals`; reserve name for `core.autonomous_proposals` | `core.proposals` retired (0 rows, no writers); name reserved for when "autonomous" becomes redundant. |
| ADR-014 | 2026-04-26 | Development-phase priority: loop liveness before artifact quality | Priority order: liveness > productivity > quality. First application: `build.tests` reclassified to `safe`. |
| ADR-015 | 2026-04-27 | Consequence chain attribution: write paths and storage shapes | Seven sub-decisions (D1–D7) covering finding_ids, approval_authority, claimed_by, and sensor attribution. |
| ADR-016 | 2026-04-27 | Test environment architecture | Schema authority = SQLAlchemy models; `core_test` ephemeral; isolation via `TRUNCATE CASCADE`. |
| ADR-017 | 2026-04-28 | `claim.proposal` as atomic action | approved→executing transition via constitutional action; `mark_executing` removed from state manager. |
| ADR-018 | 2026-05-01 | Decomposed crawler/embedder supersedes vector_sync_worker | Autonomous path split into `repo_crawler` + `repo_embedder`; `sync.vectors.code` kept for CLI. |
| ADR-019 | 2026-05-01 | Edge 5 git-boundary attribution posture | Orphan-commit detection via `CommitReachabilityAuditor`; prefix widened to 16 chars. |
| ADR-020 | 2026-05-02 | Worker liveness derived from heartbeat, not registry status | `status` column dropped; `last_heartbeat` + per-worker thresholds are canonical liveness. |
| ADR-021 | 2026-05-02 | Scoped autonomous git operations | `commit_paths` + `restore_paths` primitives; scope-collision yield pre-claim; C-light during dev phase. |

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
BlackboardShopManager                  ← active
    → monitors Blackboard SLA health
WorkerShopManager                      ← active
    → monitors worker liveness
CommitReachabilityAuditor              ← active (hourly)
    → detects orphan post_execution_sha commits
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
