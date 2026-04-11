# CORE — A3 Governed Autonomy Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-11
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

## Current State (2026-04-11)

| Item | Status |
|------|--------|
| Audit | PASSED — 4 findings (1 WARNING, 3 INFO), 0 blocking |
| Active workers | 4 sensors active — all audit sensors running |
| RemediationMap | 13 ACTIVE, 5 PENDING entries |
| Constitutional papers | Complete — all 42+ findings closed |
| MetaValidator | Operational — 70 documents clean |
| Knowledge graph | 2132 symbols — updated after monolith deletion |
| ViolationExecutor | Declared, not implemented |
| OptimizerWorker | Not yet designed |

**Current sensor coverage (47 rules, 0 findings):**
- `audit_sensor_purity` — 9 rules ✅
- `audit_sensor_architecture` — 33 rules ✅
- `audit_sensor_logic` — 2 rules ✅
- `audit_sensor_modularity` — 3 rules ✅

**Current warnings:**
- `governance.dangerous_execution_primitives` — 1 occurrence (`subprocess.run` in `ceremony.py`) — unmapped

**Phase 0/1/2 learnings:**
- `core.proposals` is the legacy file-proposal table — NOT the autonomous proposals table
- `core.autonomous_proposals` is the correct table to wipe for A3 clean slate
- Pre-commit hook two-pass retry now handled in `GitService.commit()` — fixed
- `violation_remediator/` submodule is the correct target architecture — monolith deleted
- Remediator releasing unmappable findings is correct behaviour, not a bug
- Phase 1 convergence achieved via human architectural decision, not autonomous remediation — this is valid
- Codebase is constitutionally clean across all four audit domains

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

**What we proved (session 2026-04-11):**
- Sensor link ✅ — purity findings posted correctly
- Remediator link ✅ — correctly releases unmappable findings (honest, not broken)
- Consumer link ✅ — executes proposals, consequence logging confirmed working
- Git commit two-pass retry ✅ — fixed in `GitService.commit()`
- Purity loop converged — 0 findings, Blackboard clean
- `violation_remediator/` submodule wired correctly — monolith deleted

**Success signal:** ✅ Purity sensor finds 0 actionable violations. Blackboard empty.

---

### Phase 2 — Expand Sensors ✅
**Goal:** All four audit sensors running, loop still converging.

**Activated in order:**
1. `audit_sensor_architecture` — 33/33 rules, 0 findings ✅
2. `audit_sensor_logic` — 2/2 rules, 0 findings ✅
3. `audit_sensor_modularity` — 3/3 rules, 0 findings ✅

**Success signal:** ✅ All four sensors active. 47 rules executed. 0 findings. Blackboard empty.

---

### Phase 3 — Capability Gaps
**Goal:** Findings that can't be auto-remediated get correctly delegated.

**Next step:** Activate remediator + consumer alongside all four sensors. The full loop needs
real findings to converge on. This requires introducing work — either by temporarily
relaxing a rule to surface violations, or by moving to a file that has known issues.

**Three workstreams:**

**A — Orphan classifier (92 findings)**
Dedicated triage session. Read each orphan file before recommending action.
Cluster by cluster: auto-fix, delegate to human, or suppress with justification.

**B — Test writing**
Wire test-writing AtomicAction. When audit finds missing test coverage:
- Daemon proposes test scaffolding
- Human approves first N proposals
- Auto-approve once pattern is proven sound

**C — Human delegation protocol**
For findings requiring `.intent/` edits or architectural decisions:
- Daemon marks finding `indeterminate` on Blackboard
- Log entry states exactly what human decision is needed
- Human resolves, marks finding `open` to re-enter loop

**Log format for delegation:**
```
[DELEGATE] modularity.needs_refactor → HUMAN REQUIRED
           File: src/body/workers/foo.py
           Decision needed: where should responsibility X move?
           Update .intent/ then run: core-admin workers remediate --finding <id>
```

**Success signal:** No orphaned findings, test coverage growing, human delegation path working.

---

### Phase 4 — CLI Health
**Goal:** All commands working, legacy removed.

**Command surface:** `src/cli/resources/` — 93 files across 14 directories.

**Steps:**
1. Inventory — Claude Code reads every command file, categorises as: working / broken / legacy
2. For each broken command — daemon proposes fix, human approves
3. For each legacy command — human decides keep/remove, daemon executes
4. Smoke test: `core-admin --help` — every command listed runs without error

**Success signal:** Clean `--help` output, no dead commands, no legacy stubs.

---

### Phase 5 — Visibility
**Goal:** `tail -f` tells a story anyone can follow, including someone trying to break it.

**Structured log format (every daemon action):**
```
[SENSOR]    purity.stable_id_anchor → 3 findings posted
[PROPOSAL]  fix.ids on src/body/workers/foo.py → APPROVED (auto)
[EXECUTE]   fix.ids → RESOLVED (2 IDs injected)
[VERIFY]    purity.stable_id_anchor → 0 findings (converged)
[DELEGATE]  modularity.needs_refactor → HUMAN REQUIRED: architectural decision needed
[BLOCKED]   IntentGuard rejected write to src/will/agents/foo.py → rule: architecture.layers.no_body_to_will
```

**Demo scenario:** Run daemon, watch log, watch Blackboard empty in real time. Show a governance violation being blocked. Show a finding being delegated with a clear explanation.

**Success signal:** Any observer understands what CORE is doing without explanation.

---

## Milestone Summary

| Phase | Signal | Status |
|-------|--------|--------|
| 0 — Clean slate | Audit passes, DB clean | ✅ Complete |
| 1 — Single loop | Purity loop runs unattended | ✅ Complete — 0 findings, Blackboard empty |
| 2 — All sensors | All sensors active, converging | ✅ Complete — 47 rules, 0 findings |
| 3 — Capability gaps | No orphaned findings, tests growing | ⬜ Not started |
| 4 — CLI health | All commands work, legacy gone | ⬜ Not started |
| 5 — Visibility | Demo-ready, `tail -f` tells the story | ⬜ Not started |

---

## Known Blockers

| Blocker | Phase | Notes |
|---------|-------|-------|
| `fix.modularity` class-methods gap | 3 | Methods not handled by modularity action |
| `governance.dangerous_execution_primitives` unmapped | 3+ | `subprocess.run` in `ceremony.py` — needs AtomicAction or architectural decision |
| Orphan classifier (92 findings) | 3 | Largest single cluster — needs dedicated session |
| ViolationExecutor not implemented | 3+ | Unmapped rules accumulate with no handler |

**Resolved blockers:**
| ~~Proposals dry-run bug~~ | ~~1~~ | ✅ Fixed — `proposal_worker.yaml` `write: true` |
| ~~`execute_batch` consequence logging gap~~ | ~~1~~ | ✅ Fixed — `ConsequenceLogService.record()` wired |
| ~~`fix.modularity` git commit failure~~ | ~~1+~~ | ✅ Fixed — `GitService.commit()` two-pass retry |
| ~~`purity.no_orphan_files` + `purity.no_ast_duplication` unmapped~~ | ~~1~~ | ✅ Resolved — monolith deleted, submodule wired |

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
core-admin constitution validate

# Blackboard
core-admin workers blackboard

# Proposals
core-admin proposals list

# Sync
poetry run core-admin dev sync --write

# DB
psql -U core_db -d core -h 192.168.20.23

# Clean slate (correct tables)
# TRUNCATE core.blackboard_entries RESTART IDENTITY CASCADE;
# TRUNCATE core.autonomous_proposals RESTART IDENTITY CASCADE;
```

---

## Architecture Reference

**The autonomous loop:**
```
AuditViolationSensor
    → posts findings to Blackboard
ViolationRemediatorWorker
    → claims findings, creates Proposals
    → releases unmappable findings back to open (honest, not broken)
ProposalConsumerWorker
    → executes APPROVED proposals via ProposalExecutor
AuditViolationSensor
    → confirms finding resolved or re-posts
```

**Two remediation paths:**
- Proposal Path (constitutional): Finding → RemediationMap → Proposal → AtomicAction ← target state
- ViolationExecutor Path (fallback): Finding → LLM → Crate ← not yet implemented

**Gate order on every write:**
```
ConservationGate → IntentGuard → Canary
```

**`.intent/` is read-only to CORE.** All governance changes are human-authored.

---

## Session Handoff Template

Paste at the start of each working session:

```
Current A3 phase: [0/1/2/3/4/5]
Last session: [what was done]
Current blocker: [what is blocking progress]
Blackboard state: [clean / N open findings]
Active workers: [list or "all sensors active"]
Next step: [specific action]
```
