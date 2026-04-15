# CORE — A3 Governed Autonomy Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-15
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

## Current State (2026-04-15)

| Item | Status |
|------|--------|
| Audit | PASSED — 3 INFO findings, 0 blocking, 1 unmapped (style.formatter_required — deferred) |
| Coverage | 121 declared, 120 executed, 99% effective |
| Active workers | 8 (7 sensors + ViolationExecutor) |
| RemediationMap | 13 ACTIVE, 5 PENDING entries |
| Worker registry | Clean — 23 ghost entries marked abandoned |
| Blackboard | 2 open entries, clean |
| Governor dashboard | ✅ Implemented — `core-admin runtime dashboard` |
| `.specs/` layer | ✅ Established — charter, papers, northstar, requirements, decisions, planning |

**Current sensor coverage (52 rules, 0 findings):**
- `audit_sensor_purity` — 9 rules ✅
- `audit_sensor_architecture` — 33 rules ✅
- `audit_sensor_logic` — 2 rules ✅
- `audit_sensor_modularity` — 3 rules ✅
- `audit_sensor_layout` — 1 rule ✅
- `audit_sensor_style` — 2 rules ✅
- `audit_sensor_linkage` — 2 rules ✅

**Session 2026-04-15 changes:**
- `.specs/` layer established — charter, papers, northstar moved out of `.intent/`
- `.intent/` is now purely operational governance
- First URS authored: `CORE-Governor-Dashboard-URS.md` → `.specs/requirements/`
- A3 plan moved to `.specs/planning/`
- Ghost worker registry entries (23) marked abandoned via SQL
- `core-admin runtime dashboard` implemented and committed — five panels:
  - Convergence Direction (Panel 1)
  - Governor Inbox (Panel 2)
  - Loop Running (Panel 3)
  - Pipeline Moving (Panel 4)
  - Autonomous Reach (Panel 5 — replaces legacy governance coverage panel)
- Dashboard first run surfaced: 20 abandoned findings (same rule, same file, April 12)
  and 1 dry-run graduation candidate
- Abandoned findings purged — sensor has not re-posted (violation may be resolved)
- Docstring references updated from `.intent/papers/` to `.specs/papers/`

**Known open items from dashboard first run:**
- `architecture.mind.no_body_invocation` — 20 abandoned findings purged; sensor not
  re-posting yet; violation status unknown (purged before full subject was captured)
- Blackboard deduplication bug — sensor re-posts findings for already-abandoned items;
  fix belongs in `BlackboardService.post_finding()` contract, not in sensor logic
- `core-admin check rule` cannot find `architecture.mind.no_body_invocation` despite
  rule existing in `.intent/rules/` — Phase 4 CLI bug

---

## A3 Phases

### Phase 0 — Clean Slate ✅
**Goal:** Known-good starting point before activating anything.

**Steps:**
1. Stop daemon: `systemctl --user stop core-daemon`
2. Wipe Blackboard and proposals (SQL below)
3. Run `core-admin code audit` — confirm PASSED baseline
4. Commit checkpoint to git

**SQL — wipe Blackboard and proposals:**
```sql
-- Run on lira: psql -U core_db -d core -h 192.168.20.23
TRUNCATE core.blackboard_entries RESTART IDENTITY CASCADE;
TRUNCATE core.autonomous_proposals RESTART IDENTITY CASCADE;
```

> ⚠️ `core.proposals` is the legacy table (file-level proposals). The autonomous loop
> uses `core.autonomous_proposals`. Always truncate the correct table.

**Success signal:** Daemon stopped, DB clean, audit passes.

---

### Phase 1 — Single Loop, Proven Convergence ✅
**Goal:** One sensor + one remediator running end to end, findings resolving.

**Success signal:** ✅ Purity sensor finds 0 actionable violations. Blackboard empty.

---

### Phase 2 — Expand Sensors ✅
**Goal:** All audit sensors running, loop still converging.

**Activated in order:**
1. `audit_sensor_architecture` — 33/33 rules ✅
2. `audit_sensor_logic` — 2/2 rules ✅
3. `audit_sensor_modularity` — 3/3 rules ✅
4. `audit_sensor_layout` — 1/1 rules ✅
5. `audit_sensor_style` — 2/2 rules ✅
6. `audit_sensor_linkage` — 2/2 rules ✅

**Success signal:** ✅ All seven sensors active. 52 rules executed. 0 findings. Blackboard clean.

---

### Phase 3 — Capability Gaps
**Goal:** Findings that can't be auto-remediated get correctly delegated.

**Status:** ViolationExecutor fully proven end-to-end. Stream A and C complete.
Next: Stream B (test writing).

**Three workstreams:**

**A — ViolationExecutor end-to-end** ✅ Complete

**C — Human delegation protocol** ✅ Infrastructure complete

**B — Test writing** ← NEXT
Wire test-writing AtomicAction. When audit finds missing test coverage:
- Daemon proposes test scaffolding
- Human approves first N proposals
- Auto-approve once pattern is proven sound

---

### Phase 4 — CLI Health
**Goal:** All commands working, legacy removed, URS written for each command.

**Command surface:** `src/cli/resources/` — 93 files across 14 directories.
**Full command tree:** 18 command groups, 82 commands total.

**New scope (added 2026-04-15):**
Every command gets a URS document in `.specs/requirements/` — generated from
existing implementation by Claude Code + Claude.ai, reviewed and approved by governor.
This closes the requirements layer gap identified in session 2026-04-15.

**Steps:**
1. Inventory — Claude Code reads every command file, categorises as: working / broken / legacy
2. For each broken command — daemon proposes fix, human approves
3. For each legacy command — human decides keep/remove, daemon executes
4. URS generation pass — one URS per command group
5. Smoke test: `core-admin --help` — every command listed runs without error

**Known Phase 4 bugs (from dashboard session):**
- `core-admin check rule` cannot find rules that exist in `.intent/rules/`
- `core-admin workers` has no cleanup command — ghost registry entries require raw SQL
- `core-admin runtime health` shows abandoned workers — filter needed

**Success signal:** Clean `--help` output, no dead commands, no legacy stubs, URS for every command group.

---

### Phase 5 — Visibility
**Goal:** `tail -f` tells a story anyone can follow.

**Success signal:** Any observer understands what CORE is doing without explanation.

---

## Milestone Summary

| Phase | Signal | Status |
|-------|--------|--------|
| 0 — Clean slate | Audit passes, DB clean | ✅ Complete |
| 1 — Single loop | Purity loop runs unattended | ✅ Complete |
| 2 — All sensors | All sensors active, converging | ✅ Complete — 52 rules, 7 sensors, 0 findings |
| 3 — Capability gaps | No orphaned findings, tests growing | 🔄 Stream B (tests) next |
| 4 — CLI health | All commands work, legacy gone, URS written | ⬜ Not started |
| 5 — Visibility | Demo-ready, `tail -f` tells the story | ⬜ Not started |

---

## Known Blockers

| Blocker | Phase | Notes |
|---------|-------|-------|
| Blackboard deduplication bug | 3+ | Sensor re-posts findings for already-abandoned items. Fix: `BlackboardService.post_finding()` must check for existing abandoned findings with same subject before posting |
| `architecture.mind.no_body_invocation` status unknown | 3 | 20 abandoned findings purged; sensor has not re-posted; file unknown (subject truncated, purged before full capture) |
| Sensor-fixer coherence validation | 3+ | No mechanism to detect when sensor detection contradicts fixer correction for the same rule |
| OptimizerWorker | 3+ | Not yet designed — manual candidate review until then |
| Stream B (test writing) | 3 | Next active workstream |
| `core-admin check rule` lookup bug | 4 | Cannot find rules that exist in `.intent/rules/` |
| `core-admin workers` missing cleanup command | 4 | Ghost registry entries require raw SQL |
| `core-admin runtime health` worker filter | 4 | Shows abandoned workers — needs status filter |
| `style.formatter_required` | 3+ | Declared but no engine check — deferred |
| `.specs/META/` | — | Schema for `.specs/` artifacts not yet authored |
| `audit_runs` write gap | 4+ | `core-admin code audit` does not persist results to DB — dashboard Panel 4 shows "never" for consequence log; manual audit and daemon audit are separate systems |

**Resolved blockers:**

| Blocker | Notes |
|---------|-------|
| ~~Ghost worker registry entries (23)~~ | ✅ Marked abandoned via SQL — 2026-04-15 |
| ~~`.intent/` contains non-operational documents~~ | ✅ `.specs/` layer established — charter, papers, northstar moved out |
| ~~No requirements layer~~ | ✅ `.specs/requirements/` established, first URS authored |
| ~~Sensor coverage gaps~~ | ✅ layout, style, linkage sensors added |
| ~~`purity.forbidden_placeholders` naming mismatch~~ | ✅ Fixed |
| ~~`check_import_order` relative import bug~~ | ✅ Fixed |
| ~~ViolationExecutor dry_run result posting~~ | ✅ Fixed |
| ~~ViolationExecutor end-to-end live test~~ | ✅ Proven |
| ~~Stream C delegation transition missing~~ | ✅ Resolved |
| ~~`fix.modularity` class-methods gap~~ | ✅ Resolved |
| ~~Orphan classifier (92 findings)~~ | ✅ Dissolved — 0 real orphans |
| ~~Proposals dry-run bug~~ | ✅ Fixed |
| ~~`execute_batch` consequence logging gap~~ | ✅ Fixed |

---

## Architectural Decisions Made (2026-04-15)

### `.specs/` layer established
**Decision:** Non-operational documents move out of `.intent/` into `.specs/`.
**Test:** Does CORE read this file at runtime to make a governance decision? If no → `.specs/`.
**Structure:**
```
.specs/
├── CORE-CHARTER.md       ← founding declaration
├── META/                 ← schema for .specs/ itself
├── northstar/            ← why CORE exists
├── papers/               ← architectural reasoning
├── requirements/         ← URS documents
├── decisions/            ← ADRs
└── planning/             ← roadmaps, operational plans
```

### Dashboard reads daemon state only
**Decision:** `core-admin runtime dashboard` reads the autonomous loop's DB state.
Manual audit output (`core-admin code audit`) is irrelevant to the dashboard.
The daemon's sensors are the continuous audit. The dashboard reads their output.

### Panel 5 is Autonomous Reach, not governance coverage
**Decision:** Panel 5 answers "how much can the daemon fix without human help?"
not "did the last manual audit pass?" Sources: Blackboard abandoned findings,
dry-run candidates, ViolationExecutor in-flight claims.

---

## Key Commands

```bash
# Daemon
systemctl --user start core-daemon
systemctl --user stop core-daemon
systemctl --user restart core-daemon
journalctl --user -u core-daemon -f

# Audit
core-admin code audit
core-admin check rule --rule <rule_id> --verbose
core-admin constitution validate

# Blackboard
core-admin workers blackboard
core-admin workers blackboard --status open
core-admin workers blackboard --filter "audit.violation"
core-admin workers purge --status <status> --rule <subject_prefix> --before <hours> --write

# Runtime (plumbing view)
core-admin runtime health

# Governor dashboard (five-panel state view)
core-admin runtime dashboard
core-admin runtime dashboard --plain
watch -n 30 core-admin runtime dashboard

# Workers
core-admin workers run <declaration_name>

# Context (REQUIRED before every Claude Code prompt that touches src/)
core-admin context build --file <target_file> --task code_modification --goal "<goal>" --no-cache

# Proposals
core-admin proposals list

# Sync
poetry run core-admin dev sync --write

# DB (only when no core-admin command covers the need)
psql -U core_db -d core -h 192.168.20.23

# Ghost worker cleanup (no core-admin command yet — Phase 4 item)
# UPDATE core.worker_registry SET status = 'abandoned'
# WHERE status = 'active' AND last_heartbeat < NOW() - INTERVAL '24 hours';
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
ViolationRemediatorWorker (Will)
    → claims MAPPED findings, creates Proposals
    → releases unmapped findings back to open
ViolationExecutorWorker (Will)         ← active, fully proven
    → claims UNMAPPED findings
    → delegates ceremony to ViolationRemediator (Body)
    → surfaces AtomicAction candidates to Blackboard
ProposalConsumerWorker
    → executes APPROVED proposals via ProposalExecutor
AuditViolationSensor
    → confirms finding resolved or re-posts
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
.specs/     ← human intent layer (charter, papers, URS, ADRs, plans)
.intent/    ← operational governance (constitution, rules, enforcement, workers)
src/        ← implementation
infra/      ← infrastructure (DB migrations, SQL schema)
```

---

## Session Handoff Template

```
Current A3 phase: [0/1/2/3/4/5]
Last session: [what was done]
Current blocker: [what is blocking progress]
Blackboard state: [clean / N open findings]
Active workers: [list or "all sensors active"]
Next step: [specific action]
```

---

Current A3 phase: 3
Last session: .specs/ layer established. Dashboard implemented and committed.
  Ghost workers cleaned up. First URS authored. 20 abandoned findings purged.
Current blocker: None blocking. Stream B (test writing) is next.
  Blackboard deduplication bug noted — dedicated session needed.
Blackboard state: 2 open (nature unknown — sensor cycle pending)
Active workers: 7 sensors + ViolationExecutor (8 total)
Next step: Stream B — wire test-writing AtomicAction.
  Or: investigate architecture.mind.no_body_invocation if sensor re-posts.
