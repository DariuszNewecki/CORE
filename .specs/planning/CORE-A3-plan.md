# CORE — A3 Governed Autonomy Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-14
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

## Current State (2026-04-14)

| Item | Status |
|------|--------|
| Audit | PASSED — 0 findings, 0 blocking, 1 unmapped (style.formatter_required — deferred) |
| Coverage | 100% declared, 99% effective |
| Active workers | 7 sensors + ViolationExecutor |
| RemediationMap | 13 ACTIVE, 5 PENDING entries |
| Constitutional papers | Complete — all 42+ findings closed |
| MetaValidator | Operational — 70 documents clean |
| Knowledge graph | 2138 symbols |
| ViolationExecutor | ✅ Fully proven end-to-end — sensor → claim → LLM → Canary → dry_run posted |
| OptimizerWorker | Not yet designed |

**Current sensor coverage (52 rules, 0 findings):**
- `audit_sensor_purity` — 9 rules ✅
- `audit_sensor_architecture` — 33 rules ✅
- `audit_sensor_logic` — 2 rules ✅
- `audit_sensor_modularity` — 3 rules ✅
- `audit_sensor_layout` — 1 rule ✅ (added 2026-04-14)
- `audit_sensor_style` — 2 rules ✅ (added 2026-04-14)
- `audit_sensor_linkage` — 2 rules ✅ (added 2026-04-14)

**Session 2026-04-11 fixes applied:**
- Stream C delegation infrastructure complete — `mark_indeterminate()` wired in BlackboardService
- `fix.modularity` class-methods gap closed
- Orphan classifier dissolved — 0 real orphans confirmed, 92 findings were false positives
- Orphan check metric bug fixed (783/685 → 685/685)
- RemediationMap loader `status` field fix

**Session 2026-04-12 fixes applied:**
- `ViolationExecutorWorker` implemented — `src/will/workers/violation_executor.py`
- `BlackboardService.claim_unmapped_violation_findings()` + `abandon_entries()` added
- `ViolationRemediator.declaration_name` corrected to `violation_remediator_body`
- `ViolationRemediator.process_file()` public entry point added (Will → Body delegation interface)
- `violation_executor.yaml` updated to point to Will-layer worker
- `violation_remediator_body.yaml` authored for CLI-path Body worker
- `_load_mapped_rule_ids` fixed to use `PathResolver` + `_load_remediation_map` (constitutional path)
- `ModularitySplitter` dominant-class detection fixed — selection metric and threshold gate
- `action_executor` monkey-patch guard added in `ViolationExecutorWorker._process_file()`
- `caller_uuid` param added to `ViolationRemediator.__init__()` — ViolationExecutor passes its own UUID to prevent FK violation on Blackboard posts
- **ViolationExecutor end-to-end proven:** sensor → claim → LLM (DeepSeek) → Canary pass → `audit.remediation.dry_run` posted successfully by ViolationExecutor UUID
- **Standing workflow rule established:** every Claude Code prompt that touches `src/` requires `core-admin context build` first — no exceptions

**Session 2026-04-14 fixes applied:**
- Sensor coverage gap analysis completed — full matrix built (dev sync vs sensors vs remediation map)
- `audit_sensor_layout` added — `layout.src_module_header` now detected by daemon ✅
- `audit_sensor_style` added — `style.import_order` now detected by daemon ✅
- `audit_sensor_linkage` added — `linkage.assign_ids` + `linkage.duplicate_ids` now detected ✅
- `purity.no_todo_placeholders` naming mismatch fixed in `auto_remediation.yaml` ✅
- `check_import_order` bug fixed — relative imports now classified as `local` (idx=4) ✅
- `style.yaml` enforcement mapping `internal_roots` aligned with ruff `known-first-party` ✅
- `core-admin workers blackboard purge` command added — filter by status, rule, age ✅
- Stale Blackboard entries cleared (152 pre-fix `style.import_order` findings purged)
- Daemon now running 8 workers: 7 sensors + ViolationExecutor

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
**Goal:** All audit sensors running, loop still converging.

**Activated in order:**
1. `audit_sensor_architecture` — 33/33 rules, 0 findings ✅
2. `audit_sensor_logic` — 2/2 rules, 0 findings ✅
3. `audit_sensor_modularity` — 3/3 rules, 0 findings ✅
4. `audit_sensor_layout` — 1/1 rules, 0 findings ✅ (2026-04-14)
5. `audit_sensor_style` — 2/2 rules, 0 findings ✅ (2026-04-14)
6. `audit_sensor_linkage` — 2/2 rules, 0 findings ✅ (2026-04-14)

**Success signal:** ✅ All seven sensors active. 52 rules executed. 0 findings. Blackboard clean.

---

### Phase 3 — Capability Gaps
**Goal:** Findings that can't be auto-remediated get correctly delegated.

**Status:** ViolationExecutor fully proven end-to-end. Stream A and C complete.
Next: Stream B (test writing) or run ViolationExecutor in write=True mode on existing dry_run candidate.

**Three workstreams:**

**A — ViolationExecutor end-to-end** ✅ Complete
Full path proven in live test (session 2026-04-12):
- Sensor detects violation → ViolationExecutor claims → LLM produces fix → Canary passes
- `audit.remediation.dry_run` posted to Blackboard by ViolationExecutor UUID
- AtomicAction candidate surfacing wired and ready
- Graduation path (ViolationExecutor → RemediatorWorker) operational

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

**B — Test writing** ← NEXT
Wire test-writing AtomicAction. When audit finds missing test coverage:
- Daemon proposes test scaffolding
- Human approves first N proposals
- Auto-approve once pattern is proven sound

---

### Phase 4 — CLI Health
**Goal:** All commands working, legacy removed.

**Command surface:** `src/cli/resources/` — 93 files across 14 directories.
**Full command tree:** 18 command groups, 82 commands total (inventoried 2026-04-14).

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
| 2 — All sensors | All sensors active, converging | ✅ Complete — 52 rules, 7 sensors, 0 findings |
| 3 — Capability gaps | No orphaned findings, tests growing | 🔄 ViolationExecutor proven — Stream B (tests) next |
| 4 — CLI health | All commands work, legacy gone | ⬜ Not started |
| 5 — Visibility | Demo-ready, `tail -f` tells the story | ⬜ Not started |

---

## Known Blockers

| Blocker | Phase | Notes |
|---------|-------|-------|
| Sensor-fixer coherence validation | 3+ | No mechanism exists to detect when a sensor's detection logic contradicts the fixer's correction logic for the same rule. Deployed `audit_sensor_style` without validating against `fix.imports` — produced 152 false positives. Required manual diagnosis. A `governance.sensor_fixer_coherence` check is needed: for every RemediationMap entry, verify sensor findings and fixer dry-run agree on the same file set. Instrument qualification principle from GxP — a sensor must be validated before it is trusted. |
| OptimizerWorker | 3+ | Not yet designed — manual candidate review until then |
| Stream B (test writing) | 3 | Next active workstream — wire test-writing AtomicAction |
| Ghost workers in registry | 4 | 16–32d old registrations from previous daemon generations — cosmetic, not blocking |
| Observer snapshot stale | 4 | System Observer worker last ran 9d ago — needs investigation |
| `style.formatter_required` | 3+ | Declared but no engine check — per-file Black in async daemon deferred |

**Resolved blockers:**

| Blocker | Phase | Notes |
|---------|-------|-------|
| ~~Sensor coverage gaps~~ | ~~3~~ | ✅ Resolved — layout, style, linkage sensors added; all dev sync actions now have sensors |
| ~~`purity.forbidden_placeholders` naming mismatch~~ | ~~3~~ | ✅ Fixed — renamed to `purity.no_todo_placeholders` in auto_remediation.yaml |
| ~~`check_import_order` relative import bug~~ | ~~3~~ | ✅ Fixed — relative imports classified as `local` (idx=4) |
| ~~ViolationExecutor dry_run result posting~~ | ~~3~~ | ✅ Fixed — `caller_uuid` param added |
| ~~ViolationExecutor end-to-end live test~~ | ~~3~~ | ✅ Proven — full path working, dry_run posted cleanly |
| ~~ViolationExecutor not implemented~~ | ~~3+~~ | ✅ Resolved — Will-layer worker implemented, active in daemon |
| ~~Stream C delegation transition missing~~ | ~~3~~ | ✅ Resolved — `mark_indeterminate()` wired in BlackboardService |
| ~~`fix.modularity` class-methods gap~~ | ~~3~~ | ✅ Resolved — selection metric and threshold gate fixed |
| ~~`governance.dangerous_execution_primitives` unmapped~~ | ~~3+~~ | ✅ Resolved — `ceremony.py` exclude path corrected |
| ~~Unmapped rules (2)~~ | ~~3~~ | ✅ Resolved — `passive_gate` entries added |
| ~~Orphan classifier (92 findings)~~ | ~~3~~ | ✅ Dissolved — 0 real orphans, all were false positives |
| ~~Proposals dry-run bug~~ | ~~1~~ | ✅ Fixed — `proposal_worker.yaml` `write: true` |
| ~~`execute_batch` consequence logging gap~~ | ~~1~~ | ✅ Fixed — `ConsequenceLogService.record()` wired |
| ~~`fix.modularity` git commit failure~~ | ~~1+~~ | ✅ Fixed — `GitService.commit()` two-pass retry |
| ~~`purity.no_orphan_files` + `purity.no_ast_duplication` unmapped~~ | ~~1~~ | ✅ Resolved — monolith deleted, submodule wired |
| ~~RemediationMap `status` field missing~~ | ~~3~~ | ✅ Fixed — loader now carries status field |

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

# Runtime health (full view: workers, Blackboard, crawls, blast radius)
core-admin runtime health

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

**Claude Code must run the context build itself** — do not pre-build and paste. Structure every Claude Code prompt as follows:

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

This rule exists because AI code generation from memory produces code that is syntactically
correct and constitutionally wrong in ways that only show up at runtime. The context package
is not optional scaffolding — it is the grounding step that makes AI output trustworthy.
Skipping it is accepting ungoverned AI output into CORE's own `src/`.

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
- Proposal Path (constitutional): Finding → RemediationMap → Proposal → AtomicAction ← target state
- ViolationExecutor Path (discovery fallback): Finding → LLM → Crate → AtomicAction candidate ✅ fully proven

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

---

Current A3 phase: 3
Last session: Sensor coverage gaps closed. 7 sensors active, 52 rules, 0 findings.
  layout, style, linkage sensors added. Blackboard purge command added.
  Stale entries cleared. Plan updated.
Current blocker: None blocking. Stream B (test writing) is next.
Blackboard state: 2 open (1 purity.stable_id_anchor finding, 1 ViolationExecutor dry_run candidate)
Active workers: 7 sensors (architecture, layout, linkage, logic, modularity, purity, style)
  + ViolationExecutor. ViolationRemediatorWorker + ProposalConsumerWorker paused.
Next step: Stream B — wire test-writing AtomicAction, or run ViolationExecutor
  in write=True mode on the existing dry_run candidate to prove full convergence loop.
