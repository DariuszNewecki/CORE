# CORE — A3 Governed Autonomy Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-12
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

## Current State (2026-04-12)

| Item | Status |
|------|--------|
| Audit | PASSED — 3 INFO findings, 0 warnings, 0 blocking, 0 unmapped |
| Coverage | 100% declared, 98% effective (2 passive_gate rules — correct) |
| Active workers | 4 sensors + ViolationExecutor + ViolationRemediatorWorker + ProposalConsumerWorker |
| RemediationMap | 13 ACTIVE, 5 PENDING entries |
| Constitutional papers | Complete — all 42+ findings closed |
| MetaValidator | Operational — 70 documents clean |
| Knowledge graph | 2138 symbols |
| ViolationExecutor | ✅ Implemented, active in daemon (Will layer, `src/will/workers/violation_executor.py`) |
| OptimizerWorker | Not yet designed |

**Current sensor coverage (47 rules, 0 findings):**
- `audit_sensor_purity` — 9 rules ✅
- `audit_sensor_architecture` — 33 rules ✅
- `audit_sensor_logic` — 2 rules ✅
- `audit_sensor_modularity` — 3 rules ✅

**Session 2026-04-12 (previous) fixes applied:**
- Stream C delegation infrastructure complete — `mark_indeterminate()` wired in BlackboardService
- `fix.modularity` class-methods gap closed
- Orphan classifier dissolved — 0 real orphans confirmed, 92 findings were false positives
- Orphan check metric bug fixed (783/685 → 685/685)
- RemediationMap loader `status` field fix

**Session 2026-04-12 (this session) fixes applied:**
- `ViolationExecutorWorker` implemented — `src/will/workers/violation_executor.py`
- `BlackboardService.claim_unmapped_violation_findings()` + `abandon_entries()` added
- `ViolationRemediator.declaration_name` corrected to `violation_remediator_body`
- `ViolationRemediator.process_file()` public entry point added (Will → Body delegation interface)
- `violation_executor.yaml` updated to point to Will-layer worker
- `violation_remediator_body.yaml` authored for CLI-path Body worker
- `_load_mapped_rule_ids` fixed to use `PathResolver` + `_load_remediation_map` (constitutional path)
- Smoke test confirmed: 13 mapped rules loaded, daemon cycling clean
- **Standing workflow rule established:** every Claude Code prompt that touches `src/` requires `core-admin context build` first — no exceptions

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

**Status:** ViolationExecutor implemented and live. Stream C wired. Stream A is the remaining active work.

**Three workstreams:**

**A — Orphan classifier** ← NEXT
Previously believed to have 92 findings — dissolved last session (all were false positives).
Phase 3 Stream A now means: introduce real unmapped-rule findings to prove ViolationExecutor
claims them, runs the LLM ceremony, and surfaces AtomicAction candidates to the Blackboard.
This is the live end-to-end test of the ViolationExecutor path.

**C — Human delegation protocol** ✅ Infrastructure complete
For findings requiring `.intent/` edits or architectural decisions:
- Daemon marks finding `indeterminate` on Blackboard via `BlackboardService.mark_indeterminate()`
- Log entry states exactly what human decision is needed
- Human resolves, marks finding `open` to re-enter loop

**Log format for delegation:**
```
[DELEGATE] modularity.needs_refactor → HUMAN REQUIRED
           File: src/body/workers/foo.py
           Decision needed: where should responsibility X move?
           Update .intent/ then run: core-admin workers remediate --finding <id>
```

**B — Test writing** ← depends on stable delegation path
Wire test-writing AtomicAction. When audit finds missing test coverage:
- Daemon proposes test scaffolding
- Human approves first N proposals
- Auto-approve once pattern is proven sound

**Success signal:** ViolationExecutor processes a real unmapped finding end-to-end, surfaces
a candidate, no orphaned findings, test coverage growing, human delegation path exercised.

---

### Phase 4 — CLI Health
**Goal:** All commands working, legacy removed.

**Command surface:** `src/cli/resources/` — 93 files across 14 directories.

**Steps:**
1. Inventory — Claude Code reads every command file, categorises as: working / broken / legacy
2. For each broken command — daemon proposes fix, human approves
3. For each legacy command — human decides keep/remove, daemon executes
4. Smoke test: `core-admin --help` — every command listed runs without error

**Note:** Any place in the workflow where raw `psql` is the natural reach is a place where
a `core-admin` command is missing or incomplete. These are Phase 4 audit items.

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
| 3 — Capability gaps | No orphaned findings, tests growing | 🔄 ViolationExecutor live — Stream A live test next |
| 4 — CLI health | All commands work, legacy gone | ⬜ Not started |
| 5 — Visibility | Demo-ready, `tail -f` tells the story | ⬜ Not started |

---

## Known Blockers

| Blocker | Phase | Notes |
|---------|-------|-------|
| `fix.modularity` class-methods gap | 3 | Methods not handled by modularity action |
| ViolationExecutor end-to-end live test | 3 | Implementation done — needs real unmapped finding to prove full path |
| OptimizerWorker | 3+ | Not yet designed — manual candidate review until then |
| Stream B (test writing) | 3 | Depends on stable delegation path first |

**Resolved blockers:**
| ~~ViolationExecutor not implemented~~ | ~~3+~~ | ✅ Resolved — Will-layer worker implemented, active in daemon, 13 mapped rules loaded |
| ~~Stream C delegation transition missing~~ | ~~3~~ | ✅ Resolved — `mark_indeterminate()` wired in BlackboardService |
| ~~`governance.dangerous_execution_primitives` unmapped~~ | ~~3+~~ | ✅ Resolved — `ceremony.py` exclude path corrected |
| ~~Unmapped rules (2)~~ | ~~3~~ | ✅ Resolved — `passive_gate` entries added |
| ~~Orphan classifier (92 findings)~~ | ~~3~~ | ✅ Dissolved — 0 real orphans, all were false positives |
| ~~Proposals dry-run bug~~ | ~~1~~ | ✅ Fixed — `proposal_worker.yaml` `write: true` |
| ~~`execute_batch` consequence logging gap~~ | ~~1~~ | ✅ Fixed — `ConsequenceLogService.record()` wired |
| ~~`fix.modularity` git commit failure~~ | ~~1+~~ | ✅ Fixed — `GitService.commit()` two-pass retry |
| ~~`purity.no_orphan_files` + `purity.no_ast_duplication` unmapped~~ | ~~1~~ | ✅ Resolved — monolith deleted, submodule wired |
| ~~RemediationMap `status` field missing~~ | ~~3~~ | ✅ Fixed — loader now carries status field |
| ~~`fix.modularity` class-methods gap~~ | ~~3~~ | ✅ Closed last session |

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
core-admin workers blackboard --filter "violation_executor"

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

# Clean slate (correct tables)
# TRUNCATE core.blackboard_entries RESTART IDENTITY CASCADE;
# TRUNCATE core.autonomous_proposals RESTART IDENTITY CASCADE;
```

---

## Standing Workflow Rule — Claude Code Prompts

**Every Claude Code prompt that modifies or creates a `src/` file requires a context build first.**

```bash
# Step 1 — ground the prompt in repo reality
core-admin context build \
  --file <target_file> \
  --task code_modification \
  --goal "<what this change does>" \
  --no-cache

# Step 2 — construct the Claude Code prompt
[paste context build output]
---
[implementation instruction]
```

This rule exists because AI code generation from memory produces code that is syntactically
correct and constitutionally wrong in ways that only show up at runtime. The context package
is not optional scaffolding — it is the grounding step that makes AI output trustworthy.
Skipping it is accepting ungoverned AI output into CORE's own `src/`.

---

## Architecture Reference

**The autonomous loop:**
```
AuditViolationSensor (×4 namespaces)
    → posts findings to Blackboard
ViolationRemediatorWorker (Will)
    → claims MAPPED findings, creates Proposals
    → releases unmapped findings back to open
ViolationExecutorWorker (Will)         ← NEW — active
    → claims UNMAPPED findings
    → delegates ceremony to ViolationRemediator (Body)
    → surfaces AtomicAction candidates to Blackboard
ProposalConsumerWorker
    → executes APPROVED proposals via ProposalExecutor
AuditViolationSensor
    → confirms finding resolved or re-posts
```

**Two remediation paths:**
- Proposal Path (constitutional): Finding → RemediationMap → Proposal → AtomicAction ← target state
- ViolationExecutor Path (discovery fallback): Finding → LLM → Crate → AtomicAction candidate ✅ implemented

**Graduation path (rule promotion):**
```
ViolationExecutor surfaces candidate
    → human observes pattern on Blackboard
    → human authors AtomicAction + RemediationMap entry
    → rule graduates to RemediatorWorker
    → ViolationExecutor never touches that rule again
(OptimizerWorker will automate observation step — not yet designed)
```

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
