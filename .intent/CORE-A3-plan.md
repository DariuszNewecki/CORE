# CORE — A3 Governed Autonomy Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-10
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

## Current State (2026-04-10)

| Item | Status |
|------|--------|
| Audit | PASSED — 11 findings (8 WARNING, 3 INFO), 0 blocking |
| Active workers | 15 — all sensors, remediator, consumer active |
| RemediationMap | 13 ACTIVE, 5 PENDING entries |
| Constitutional papers | Complete — all 42+ findings closed |
| MetaValidator | Operational — 70 documents clean |
| Knowledge graph | 2134 symbols — 596 classes, 963 methods, 575 functions |
| ViolationExecutor | Declared, not implemented |
| OptimizerWorker | Not yet designed |

**Current warnings (daemon should resolve):**
- `purity.no_orphan_files` — 6 occurrences (orphan file cluster)
- `purity.no_ast_duplication` — 1 occurrence
- `governance.dangerous_execution_primitives` — 1 occurrence (subprocess.run)

---

## A3 Phases

### Phase 0 — Clean Slate
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
TRUNCATE core.proposals RESTART IDENTITY CASCADE;
```

**Success signal:** Daemon stopped, DB clean, audit passes.

---

### Phase 1 — Single Loop, Proven Convergence
**Goal:** One sensor + one remediator running end to end, findings resolving.

**Activate only:**
- `audit_sensor_purity` — status: active
- `violation_remediator` — status: active
- `proposal_consumer_worker` — status: active

**All other workers:** set to `paused` before starting daemon.

**Steps:**
1. Pause all workers except the three above
2. Start daemon: `systemctl --user start core-daemon`
3. Watch: `journalctl --user -u core-daemon -f`
4. Confirm: findings appear → proposals created → proposals executed → Blackboard empties
5. Fix any loop breaks (dry-run bug, consequence logging gap) before proceeding

**Success signal:** Purity findings autonomously resolved, Blackboard empty, no human code edits.

---

### Phase 2 — Expand Sensors
**Goal:** All four audit sensors running, loop still converging.

**Activate in order — wait for previous sensor's backlog to clear before next:**

1. `audit_sensor_architecture`
2. `audit_sensor_logic`
3. `audit_sensor_modularity` ← will surface modularization work

**Rule:** Never activate the next sensor until the previous one's findings are resolved or delegated.

**Success signal:** All four sensors active, Blackboard converging across all namespaces.

---

### Phase 3 — Capability Gaps
**Goal:** Findings that can't be auto-remediated get correctly delegated.

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
| 0 — Clean slate | Audit passes, DB clean | ⬜ Not started |
| 1 — Single loop | Purity loop runs unattended | ⬜ Not started |
| 2 — All sensors | All sensors active, converging | ⬜ Not started |
| 3 — Capability gaps | No orphaned findings, tests growing | ⬜ Not started |
| 4 — CLI health | All commands work, legacy gone | ⬜ Not started |
| 5 — Visibility | Demo-ready, `tail -f` tells the story | ⬜ Not started |

---

## Known Blockers

| Blocker | Phase | Notes |
|---------|-------|-------|
| Proposals dry-run bug | 1 | Proposals not executing — investigate before Phase 1 |
| `execute_batch` consequence logging gap | 1 | Causal chain broken for batch operations |
| `fix.modularity` class-methods gap | 2 | Methods not handled by modularity action |
| Orphan classifier (92 findings) | 3 | Largest single cluster — needs dedicated session |
| ViolationExecutor not implemented | 3+ | Unmapped rules accumulate with no handler |

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
```

---

## Architecture Reference

**The autonomous loop:**
```
AuditViolationSensor
    → posts findings to Blackboard
ViolationRemediatorWorker
    → claims findings, creates Proposals
ProposalConsumerWorker
    → executes approved Proposals
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
