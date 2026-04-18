# CORE — A3 Governed Autonomy Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-18
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

## Current State (2026-04-18)

| Item | Status |
|------|--------|
| Audit | PASSED — 3 findings (all INFO), 0 blocking, 0 unmapped |
| Coverage | 121 declared, 121 executed, 100% effective |
| Active workers | 15 (7 sensors + ViolationExecutor + ViolationRemediator + ProposalConsumer + BlackboardAuditor + WorkerAuditor + TestCoverageSensor + TestRunnerSensor + TestRemediatorWorker) |
| RemediationMap | 14 ACTIVE, 5 PENDING entries |
| Stream B (test writing) | ✅ Complete — TestCoverageSensor + TestRunnerSensor + TestRemediatorWorker + `build.tests` wired. First autonomous test committed. |
| `build.tests` context gap | 🔄 CoderAgent generates without source context — ContextBuilder wiring pending |
| Worker registry | Clean — 12 active, 23 abandoned |
| Blackboard | Converging — 2 open legitimate findings, system healthy |
| Constitutional boundaries | ✅ Clean — shared/ boundary audit complete via ADR-002 |
| Governor dashboard | ✅ Redesigned — two-column layout, full-width Convergence row |
| `.specs/` layer | ✅ Established and fully wired into vector layer |
| Context build layer constraints | ✅ Implemented — layer-specific, noise-filtered |
| Vector layer | ✅ `core_specs` collection live — 549 items from 53 documents |
| Semantic search | ✅ All three collections queryable — `core_policies`, `core-patterns`, `core_specs` |
| Context build evidence | ✅ Pulls from all three collections — papers surface alongside rules |
| Functional requirements | ✅ First system-level document authored — `CORE-What-It-Does.md` |
| Proposal Path | ✅ Fully daemonized — ViolationRemediator + ProposalConsumer active |
| Worker heartbeat | ✅ Fixed — registry last_heartbeat updates on every post_heartbeat() call |
| Documentation | ✅ All docs updated — README, 7 docs pages, CONTRIBUTING.md, vocabulary.md |
| `style.formatter_required` | ✅ Fully wired — sensor detects, Remediator proposes, Consumer executes, git commits |

**Current sensor coverage (52 rules, 0 findings on clean codebase):**
- `audit_sensor_purity` — 9 rules ✅
- `audit_sensor_architecture` — 33 rules ✅
- `audit_sensor_logic` — 2 rules ✅
- `audit_sensor_modularity` — 3 rules ✅
- `audit_sensor_layout` — 1 rule ✅
- `audit_sensor_style` — 2 rules ✅
- `audit_sensor_linkage` — 2 rules ✅

**Session 2026-04-18 changes:**

*Shared/ boundary cleanup (architectural discipline):*
- Complete boundary audit against three-criterion admission test (layer-independent, serves multiple layers, no governance logic)
- **Constitutional violations resolved architecturally, not through rule exceptions:**
  - CLI utilities moved: `shared/cli_utils/` → `cli/utils/` (113/114 single-layer usage)
  - Remediation planning moved: `shared/self_healing/remediation_interpretation/` → `will/` (cognitive work)
  - Workers consolidated: `body/workers/violation_remediator/` → `will/workers/violation_remediator_body/` (resolved obs-8.6)
  - Governance constants extracted: `ai/constitutional_envelope.py` hardcoded constants → `.intent/enforcement/constitutional_envelope.yaml`
  - Subprocess governance: `ceremony.py` raw `subprocess.run` → constitutional `subprocess_utils.run_command_async()`
- **Empirical verification:** `intent_repository.py` placement confirmed correct (mind=2, body=6, will=5, cli=4 importers)
- **System health maintained:** Audit PASSED throughout, findings reduced 6 → 3 (all INFO), daemon healthy
- **Decision record:** ADR-002 created documenting all architectural decisions

**Session 2026-04-17 changes:**

*Morning (documentation + activation):*
- All documentation updated to reflect current state:
  - `README.md` — A3 current, `.specs/` layer, rule counts, dashboard link
  - `docs/autonomy-ladder.md` — A3 marked ✅ ← current
  - `docs/how-it-works.md` — `.specs/` layer added, rule counts corrected
  - `docs/getting-started.md` — vector sync step, dashboard command added
  - `docs/cli-reference.md` — dashboard, vectors query, workers blackboard added
  - `docs/index.md` — CORE-What-It-Does.md as first read
  - `docs/contributing.md` — `.specs/` added, A3 status corrected
  - `docs/vocabulary.md` — 42 dead `.intent/papers/` links fixed → `.specs/papers/`
  - `CONTRIBUTING.md` — `.specs/` added alongside `.intent/`
- Governor dashboard redesigned — two-column layout
- Worker re-evaluation — 4 workers activated: `blackboard_auditor`, `worker_auditor`,
  `violation_remediator`, `proposal_consumer_worker`
- Worker heartbeat fix — `_post_entry()` in `base.py` updates `worker_registry.last_heartbeat`

*Afternoon (style.formatter_required end-to-end):*
- `RuffFormatCheck` added to `workflow_gate` engine
  - `src/mind/logic/engines/workflow_gate/checks/ruff_format.py`
  - Registered in `checks/__init__.py` and `engine.py`
  - `verify_context()` fixed to emit per-file AuditFindings with real file paths
- `style.formatter_required` rule corrected — Black → ruff-format, `check` block added
- Enforcement mapping added: `.intent/enforcement/mappings/style/formatter.yaml`
- `workflow.ruff_format_check` added to remediation map → `fix.format`
- `governance_paths.yaml` map_path corrected to actual file location
- `fix.format` action fixed — now accepts `file_path` parameter
- `format_code()` in `code_style_service.py` updated — Black replaced with ruff-format
- `ViolationRemediatorWorker` fixed — `f["id"]` → `f.get("id") or f.get("entry_id")`
- **Full autonomous loop proven end-to-end:**
  Sensor detects → Blackboard → Remediator creates proposal → Consumer executes →
  `fix.format` runs → git commit authored by CORE

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

**Status:** All three streams complete. ViolationExecutor fully proven end-to-end.
Proposal Path fully daemonized. `style.formatter_required` autonomous loop proven.
Shared/ boundary cleanup complete. Stream B test-writing wired — first autonomous test
written (quality fix pending: CoderAgent needs source context before generating tests).

**Three workstreams:**

**A — ViolationExecutor end-to-end** ✅ Complete

**C — Human delegation protocol** ✅ Infrastructure complete

**B — Test writing** ✅ Complete
"Wire test-writing AtomicAction" → done. TestCoverageSensor + TestRunnerSensor +
TestRemediatorWorker + `build.tests` wired. First autonomous test written
(`tests/will/workers/blackboard_auditor/test_generated.py` — hallucinated, quality fix pending).

---

### Phase 4 — CLI Health
**Goal:** All commands working, legacy removed, URS written for each command.

**Command surface:** `src/cli/resources/` — 93 files across 14 directories.
**Full command tree:** 18 command groups, 82 commands total.

**Steps:**
1. Inventory — Claude Code reads every command file, categorises as: working / broken / legacy
2. For each broken command — daemon proposes fix, human approves
3. For each legacy command — human decides keep/remove, daemon executes
4. URS generation pass — one URS per command group
5. Smoke test: `core-admin --help` — every command listed runs without error

**Known Phase 4 bugs:**
- `core-admin check rule` cannot find rules that exist in `.intent/rules/`
- `core-admin workers` has no cleanup command — ghost registry entries require raw SQL
- `core-admin runtime health` shows abandoned workers — filter needed
- `core-admin vectors sync` has no `--force` flag — collection delete required when
  payload structure changes without content changing (dedup uses content hash only)

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
| 3 — Capability gaps | No orphaned findings, tests growing | 🔄 Active — Stream B complete, `build.tests` context gap remaining |
| 4 — CLI health | All commands work, legacy gone, URS written | ⬜ Not started |
| 5 — Visibility | Demo-ready, `tail -f` tells the story | ⬜ Not started |

---

## Known Blockers

| Blocker | Phase | Notes |
|---------|-------|-------|
| build.tests context gap | 3 | CoderAgent generates tests without source context — hallucinated API. Fix: call ContextBuilder (`RemediationInterpretationService.build_reasoning_brief_dict`) before CoderAgent in `build_tests_action.py`. Same pattern as `ViolationRemediator._plan_file()`. This is an intelligence gap, not a constitutional violation — belongs here, not in `.intent/rules/`. |
| End-to-end Proposal Path verification | 3 | Loop proven with `fix.format`; needs verification across all mapped rules |
| WorkerAuditor does not resolve findings on recovery | 3+ | `worker.silent` findings persist after workers recover — needs fix |
| Sensor-fixer coherence validation | 3+ | No mechanism to detect when sensor detection contradicts fixer correction for the same rule |
| OptimizerWorker | 3+ | Not yet designed — manual candidate review until then |
| `core-admin check rule` lookup bug | 4 | Cannot find rules that exist in `.intent/rules/` |
| `core-admin workers` missing cleanup command | 4 | Ghost registry entries require raw SQL |
| `core-admin runtime health` worker filter | 4 | Shows abandoned workers — needs status filter |
| `core-admin vectors sync` missing `--force` flag | 4 | Collection delete required to force payload re-index when content hash unchanged |
| `.specs/META/` | — | Schema for `.specs/` artifacts not yet authored |
| `audit_runs` write gap | 4+ | `core-admin code audit` does not persist results to DB — dashboard Panel 4 shows "never"; manual audit and daemon audit are separate systems |

**Resolved blockers:**

| Blocker | Notes |
|---------|-------|
| ~~ViolationExecutor ceremony `'id'` bug~~ | ✅ Fixed 2026-04-18 — BlackboardService contract enforced (`finding["id"]` everywhere). `entry_id` was a local variable name confused with dict key. |
| ~~Stream B test-writing not wired~~ | ✅ Complete 2026-04-18 — TestCoverageSensor + TestRunnerSensor + TestRemediatorWorker + `build.tests`. First autonomous test committed. |
| ~~Shared/ boundary violations~~ | ✅ Resolved 2026-04-18 — ADR-002: constitutional moves (CLI utilities → cli/, remediation planning → will/, workers consolidation, subprocess governance, constitutional constants extraction) |
| ~~`style.formatter_required` — deferred, no engine check~~ | ✅ Fully wired 2026-04-17 — RuffFormatCheck, enforcement mapping, remediation map, fix.format fixed, autonomous loop proven end-to-end |
| ~~Proposal Path workers not daemonized~~ | ✅ Fixed 2026-04-17 — violation_remediator + proposal_consumer_worker activated |
| ~~Worker heartbeat not updating registry~~ | ✅ Fixed 2026-04-17 — base.py _post_entry() updates worker_registry on heartbeat |
| ~~BlackboardAuditor and WorkerAuditor not active~~ | ✅ Fixed 2026-04-17 — both activated |
| ~~Documentation stale — A2 marked current, .specs/ absent~~ | ✅ Fixed 2026-04-17 — all docs updated |
| ~~Blackboard hygiene bug (2 failure modes)~~ | ✅ Fixed 2026-04-16 |
| ~~`.specs/` invisible to vector layer~~ | ✅ Fixed 2026-04-16 |
| ~~Context build evidence missing constitutional papers~~ | ✅ Fixed 2026-04-16 |
| ~~`intent_alignment.py` northstar broken~~ | ✅ Fixed 2026-04-16 |
| ~~Context build layer constraints noise~~ | ✅ Fixed 2026-04-16 |
| ~~`core-admin vectors query` missing specs collection~~ | ✅ Fixed 2026-04-16 |
| ~~Rich Panel rendering bug in build.py~~ | ✅ Fixed 2026-04-16 |
| ~~Context build missing constitutional layer constraints~~ | ✅ Fixed 2026-04-16 |
| ~~`architecture.mind.no_body_invocation` status unknown~~ | ✅ Resolved 2026-04-16 |
| ~~Stale Blackboard entries (2)~~ | ✅ Purged 2026-04-16 |
| ~~No functional requirements document~~ | ✅ `CORE-What-It-Does.md` authored 2026-04-16 |
| ~~Ghost worker registry entries (23)~~ | ✅ Marked abandoned via SQL — 2026-04-15 |
| ~~`.intent/` contains non-operational documents~~ | ✅ `.specs/` layer established — 2026-04-15 |
| ~~No requirements layer~~ | ✅ `.specs/requirements/` established — 2026-04-15 |
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

## Architectural Decisions Made

### 2026-04-15 — `.specs/` layer established
**Decision:** Non-operational documents move out of `.intent/` into `.specs/`.
**Test:** Does CORE read this file at runtime to make a governance decision? If no → `.specs/`.
**Structure:**
```
.specs/
├── CORE-CHARTER.md       ← founding declaration
├── META/                 ← schema for .specs/ itself
├── northstar/            ← why CORE exists (including CORE-What-It-Does.md)
├── papers/               ← architectural reasoning
├── requirements/         ← URS documents
├── decisions/            ← ADRs
└── planning/             ← roadmaps, operational plans
```

### 2026-04-15 — Dashboard reads daemon state only
**Decision:** `core-admin runtime dashboard` reads the autonomous loop's DB state.
Manual audit output is irrelevant. The daemon's sensors are the continuous audit.

### 2026-04-15 — Panel 5 is Autonomous Reach, not governance coverage
**Decision:** Panel 5 answers "how much can the daemon fix without human help?"
Sources: Blackboard abandoned findings, dry-run candidates, ViolationExecutor in-flight.

### 2026-04-16 — Context build emits layer constraints from path, not role inference
**Decision:** Constitutional layer derived from file path alone (`src/mind/` → mind).
Deterministic and authoritative. Layer constraints appear before all other sections.

### 2026-04-16 — `.specs/` is a first-class vector collection
**Decision:** `.specs/` documents vectorized into `core_specs`, queried by context build
alongside `core_policies` and `core-patterns`. Reasoning layer must be semantically searchable.

### 2026-04-16 — Functional requirements layer established
**Decision:** `CORE-What-It-Does.md` is the entry point for new readers before architecture.

### 2026-04-17 — Dashboard two-column layout
**Decision:** Convergence Direction full-width (primary signal), remaining panels in
two-column rows. Scales naturally when new panels are added.

### 2026-04-17 — Worker heartbeat updates registry in base class
**Decision:** `_post_entry()` in `base.py` updates `worker_registry.last_heartbeat`
when `entry_type == 'heartbeat'`. Single fix point — all workers benefit automatically.

### 2026-04-17 — ruff-format is the formatting authority, not Black
**Decision:** `style.formatter_required` enforces ruff-format (commit-gate hook in
`.pre-commit-config.yaml`). Black is `stages: [manual]` only and is not the authority.
`fix.format` action and `format_code()` updated to invoke ruff-format.

### 2026-04-17 — workflow.ruff_format_check is the Blackboard check_id for formatting
**Decision:** The check_id posted to the Blackboard by `workflow_gate` engine is
`workflow.ruff_format_check`. The remediation map must key on this, not `style.formatter_required`.
Both keys map to `fix.format` for forward compatibility.

### 2026-04-18 — Shared layer boundary enforcement (ADR-002)
**Decision:** All shared/ boundary violations resolved through architectural moves, not rule exceptions. Constitutional violations require constitutional fixes.
**Key moves:** CLI utilities to cli/ layer, remediation planning to will/ layer, governance constants extracted to .intent/, subprocess routing through constitutional infrastructure.
**Verification:** Empirical import analysis, obs-8.6 resolution (two-worker separation pattern), audit health maintained throughout.
**Rationale:** "Governance mappings live in .intent/, never hardcoded in src/" — policy decisions belong in constitutional layer, mechanisms belong in implementation layer.

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

# Vectors
core-admin vectors sync --write
core-admin vectors query "<query>" --collection policies|patterns|specs --limit <n>
# Force re-index when payload changed without content change (no --force flag yet):
# python3 -c "import asyncio; from shared.infrastructure.clients.qdrant_client import QdrantService; asyncio.run(QdrantService().client.delete_collection('core_specs'))" 2>/dev/null
# core-admin vectors sync --write

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

**Vector collections:**
```
core_specs      ← .specs/ markdown documents (549 items, 53 files)
core_policies   ← .intent/ governance policies and rules
core-patterns   ← .intent/ architecture patterns
core-code       ← src/ code symbols
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
Last session: 2026-04-18 (end of day). Stream B complete. First autonomous test
  written. ViolationExecutor `'id'` bug fixed. `action_executor` guard added to
  `build_tests_action.py`. `proposals list --full-ids` added. Two governance rules
  added then correctly removed (intelligence gap, not constitutional violation).
Current blocker: `build.tests` context gap — CoderAgent needs source context before
  generating tests.
Blackboard state: converging — Stream B loop active, `test.missing` findings cycling
Active workers: 15
Next step: Wire ContextBuilder into `build_tests_action.py` before CoderAgent invocation.
