# CORE — A3 Governed Autonomy Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-20
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

## Current State (2026-04-20 — reconnaissance verified)

| Item | Status |
|------|--------|
| Audit | PASS — 39 findings (37 WARNING, 2 INFO), 0 crashed, 1 unmapped (`governance.artifact_mutation.traceable`) |
| Audit finding concentration | 32 of 39 are `modularity.needs_split` — single-class concentration, not diverse violations |
| Coverage | 120 declared, 119 executed (5 stubs skipped), 100% rule execution; 99.0% effective |
| Worker registry | 15 active, 20 abandoned (Phase 4 cleanup item) |
| Daemon | **Inactive** — last Blackboard activity 2026-04-18 14:26. Autonomous loop not running at time of snapshot |
| RemediationMap | 14 ACTIVE, 5 PENDING (top-level rule entries) |
| ADR inventory | ADR-001 through ADR-004 accepted and landed |
| Stream B (test writing) | ✅ Complete — TestCoverageSensor + TestRunnerSensor + TestRemediatorWorker + `build.tests` wired |
| `build.tests` context gap | ✅ Resolved — ADR-003 + ADR-004 landed 2026-04-19 (commits `a0f68287`, `8a1556e4`) |
| Constitutional boundaries | ✅ Clean — ADR-002 shared/ boundary audit complete |
| Governor dashboard | ✅ Redesigned — two-column layout, full-width Convergence row |
| `.specs/` layer | ✅ Established and wired into vector layer |
| `.specs/META/` schemas | ❌ Absent — governance hygiene gap |
| Vector layer | ✅ `core_specs` collection live — 549 items from 53 documents |
| Semantic search | ✅ All three collections queryable — `core_policies`, `core-patterns`, `core_specs` |
| Proposal Path | ✅ Fully daemonized — ViolationRemediator + ProposalConsumer active when daemon runs |
| `style.formatter_required` | ✅ Fully wired — sensor detects, Remediator proposes, Consumer executes, git commits |

**Sensor coverage (119 executed rules, 39 findings on current codebase):**
- `audit_sensor_purity` — live (2 `purity.no_ast_duplication` findings)
- `audit_sensor_architecture` — live
- `audit_sensor_logic` — live
- `audit_sensor_modularity` — live (32 `modularity.needs_split` findings — single-class dominance)
- `audit_sensor_layout` — live
- `audit_sensor_style` — live
- `audit_sensor_linkage` — live

**Verdict semantics (unresolved):** Audit returns PASS despite 37 WARNING findings. The verdict threshold is not formally documented; current observed behaviour is that WARNING alone does not fail the verdict. Pinning this down is a prerequisite for meaningful convergence metrics.

---

## A3 Phases

### Phase 0 — Clean Slate ✅
Known-good starting point before activating anything.

### Phase 1 — Single Loop, Proven Convergence ✅
Purity sensor loop, Blackboard empty.

### Phase 2 — Expand Sensors ✅
All seven audit sensors active.

### Phase 3 — Capability Gaps 🔄
**Status:** Stream A (ViolationExecutor) complete. Stream B (test writing) complete — ADR-003 + ADR-004 closed the structural gap. Stream C (delegation) infrastructure complete.

Remaining Phase 3 work:
1. **Activate the daemon.** Currently inactive. Autonomous loop cannot converge if the loop does not run.
2. **WorkerAuditor finding resolution on recovery** — `worker.silent` findings persist after workers recover.
3. **Sensor-fixer coherence validation** — no mechanism to detect when sensor detection contradicts fixer correction for the same rule.

### Phase 4 — CLI Health ⬜
Not started.

**Command surface:** `src/cli/resources/` — 93 files across 14 command groups, 82 commands total.

**Known Phase 4 bugs:**
- `core-admin check rule` does not exist as a command (brief documentation drift — the command was never implemented or was removed without plan update)
- `core-admin workers` has no cleanup command — ghost registry entries (20 abandoned rows currently) require raw SQL
- `core-admin runtime health` shows abandoned workers — filter needed
- `core-admin vectors sync` has no `--force` flag — collection delete required when payload structure changes without content changing

### Phase 5 — Visibility ⬜
Not started.

---

## Milestone Summary

| Phase | Signal | Status |
|-------|--------|--------|
| 0 — Clean slate | Audit passes, DB clean | ✅ Complete |
| 1 — Single loop | Purity loop runs unattended | ✅ Complete |
| 2 — All sensors | All sensors active, converging | ✅ Complete — 7 sensors, 119 rules executed |
| 3 — Capability gaps | No orphaned findings, daemon live | 🔄 Stream B closed via ADR-003/004; daemon inactive |
| 4 — CLI health | All commands work, legacy gone, URS written | ⬜ Not started |
| 5 — Visibility | Demo-ready, `tail -f` tells the story | ⬜ Not started |

---

## Known Blockers

| Blocker | Phase | Notes |
|---------|-------|-------|
| Daemon inactive | 3 | Reconnaissance 2026-04-20 shows last Blackboard activity 2026-04-18 14:26. Autonomous loop not observably converging. Cause not diagnosed — could be deliberate stop, crashed worker, systemd state, or missing `systemctl --user start core-daemon`. Resolution prerequisite for all other Phase 3 work |
| Verdict-threshold documentation | 3+ | `PASS` is returned with 37 WARNINGs. Threshold semantics not written down. Blocks honest convergence reporting |
| `modularity.needs_split` single-class concentration | 3+ | 32 of 39 findings are one check_id with identical shape ("File has N lines with only 2 concern(s)"). Either the check is producing systematic false positives, the threshold (400 lines) is miscalibrated, or there is genuine modularity debt. Needs diagnosis before remediation |
| `audit_runs` DB write gap | 4+ | `core-admin code audit` does not persist results to DB — dashboard Panel 4 shows "never"; manual audit and daemon audit are separate systems |
| WorkerAuditor does not resolve findings on recovery | 3+ | `worker.silent` findings persist after workers recover |
| Sensor-fixer coherence validation | 3+ | No mechanism to detect when sensor detection contradicts fixer correction for the same rule |
| OptimizerWorker | 3+ | Not yet designed — manual candidate review until then |
| `.specs/META/` schemas absent | Hygiene | `.intent/META/` has 10 schemas. `.specs/` has zero. No machine-checkable shape for papers, URS, ADRs, handoffs, plans, investigations |

**Open remediation items (2026-04-20 audit):**

| Severity | Check | Count | Class |
|----------|-------|-------|-------|
| WARNING | `modularity.needs_split` | 32 | Single-class concentration — diagnose before remediate |
| WARNING | `autonomy.tracing.mandatory` | 2 | `self_healing_agent.py`, `tagger_agent.py` — sensing workers that may legitimately not need tracer; selector design question |
| WARNING | `purity.no_ast_duplication` | 2 | `IntentRepository.resolve_rel` ↔ `SpecsRepository.resolve_rel` — pre-existing structural |
| WARNING | `governance.dangerous_execution_primitives` | 1 | `src/body/services/cim/scanners.py:55` (`subprocess.check_output`) — governor decision pending |
| WARNING | `workflow.mypy_check` | 1 | Not previously tracked |
| WARNING | `workflow.security_check` | 1 | Not previously tracked |
| INFO | (various) | 2 | — |

**Resolved blockers:**

| Blocker | Notes |
|---------|-------|
| ~~`build.tests` context gap — CoderAgent generates without source context~~ | ✅ Resolved 2026-04-19 — commits `a0f68287` (Gap 2+3 change-set) and `8a1556e4` (ADR-003 task_type field + ADR-004 phase map in `.intent/`). Verified: dry-run against `src/shared/time.py` produces tests with real symbols |
| ~~`src/shared/infrastructure/context/cli.py` vestigial CLI~~ | ✅ Deleted 2026-04-19 in same change-set as ADR-004 |
| ~~Phase map hardcoded in `src/` (three-way drift)~~ | ✅ Governed in `.intent/enforcement/config/task_type_phases.yaml` per ADR-004 |
| ~~fnmatch include-pattern asymmetry in `AuditorContext.get_files`~~ | ✅ Compensated via `_include_matches` helper, commit `8e9325fb` (2026-04-18). Live verification 2026-04-20: top-level files under `src/will/agents/` now matched by `src/will/agents/**/*.py` scope |
| ~~`_expr_is_intent_related` missing `Call` handling~~ | ✅ `ast.Call` branch present in current code with both `Path(tainted)` wrapping and attribute-chain propagation. Commit SHA not recovered; shape verified live |
| ~~`autonomy.tracing.mandatory` silent non-firing~~ | ✅ Premise falsified by `state/tracing_mandatory_diagnostic_2026-04-20.md`. Rule fires, produces 2 findings today. The handoffs carrying this claim are superseded |
| ~~ViolationExecutor `'id'`/`entry_id` bug~~ | ✅ Fixed 2026-04-18 |
| ~~Stream B test-writing not wired~~ | ✅ Complete 2026-04-18 |
| ~~Shared/ boundary violations~~ | ✅ Resolved 2026-04-18 — ADR-002 |
| ~~`style.formatter_required` — deferred, no engine check~~ | ✅ Fully wired 2026-04-17 |
| ~~Proposal Path workers not daemonized~~ | ✅ Fixed 2026-04-17 |
| ~~Worker heartbeat not updating registry~~ | ✅ Fixed 2026-04-17 |
| ~~BlackboardAuditor and WorkerAuditor not active~~ | ✅ Fixed 2026-04-17 |
| ~~Documentation stale — A2 marked current, .specs/ absent~~ | ✅ Fixed 2026-04-17 |
| ~~Blackboard hygiene bug (2 failure modes)~~ | ✅ Fixed 2026-04-16 |
| ~~`.specs/` invisible to vector layer~~ | ✅ Fixed 2026-04-16 |
| ~~Context build evidence missing constitutional papers~~ | ✅ Fixed 2026-04-16 |
| ~~`intent_alignment.py` northstar broken~~ | ✅ Fixed 2026-04-16 |
| ~~Context build layer constraints noise~~ | ✅ Fixed 2026-04-16 |
| ~~`core-admin vectors query` missing specs collection~~ | ✅ Fixed 2026-04-16 |
| ~~Rich Panel rendering bug in build.py~~ | ✅ Fixed 2026-04-16 |
| ~~Stale Blackboard entries (2)~~ | ✅ Purged 2026-04-16 |
| ~~No functional requirements document~~ | ✅ `CORE-What-It-Does.md` authored 2026-04-16 |
| ~~Ghost worker registry entries (23)~~ | ✅ Marked abandoned via SQL — 2026-04-15. Note: 20 abandoned rows present today, accumulating since |
| ~~`.intent/` contains non-operational documents~~ | ✅ `.specs/` layer established — 2026-04-15 |
| ~~Orphan classifier (92 findings)~~ | ✅ Dissolved — 0 real orphans |

---

## Architectural Decisions Made

### ADR-001 (2026-04-15) — `.specs/` layer established
Non-operational documents move out of `.intent/` into `.specs/`.

### ADR-002 (2026-04-18) — Shared layer boundary enforcement
All shared/ boundary violations resolved through architectural moves, not rule exceptions. Established "Policy in `.intent/`, mechanism in `src/`" principle.

### ADR-003 (2026-04-19) — `task_type` as first-class field on `ExecutionTask`
Test generation correctly routes through `audit` phase rather than `execution`. `build_tests_action` sets `task_type="test_generation"`; `CodeGenerator._build_context_package` passes it through.

### ADR-004 (2026-04-19) — Govern task_type → phase mapping in `.intent/`
Three-way drift (service, CLI, vestigial file) collapsed to single source at `.intent/enforcement/config/task_type_phases.yaml`. Vestigial `src/shared/infrastructure/context/cli.py` retired in same change-set.

### Undocumented-as-ADR decisions (backfill candidates)
The following decisions were made in code and in session handoffs but not captured as ADRs. Each is a candidate for retrospective ADR authoring:

- 2026-04-15 — Dashboard reads daemon state only
- 2026-04-15 — Panel 5 is Autonomous Reach, not governance coverage
- 2026-04-16 — Context build emits layer constraints from path, not role inference
- 2026-04-16 — `.specs/` is a first-class vector collection
- 2026-04-17 — Dashboard two-column layout
- 2026-04-17 — Worker heartbeat updates registry in base class
- 2026-04-17 — ruff-format is the formatting authority, not Black
- 2026-04-17 — `workflow.ruff_format_check` is the Blackboard check_id for formatting

---

## Intent Layer Hygiene — proposed (not executed this session)

`.specs/` has grown organically over five weeks and its layout no longer reflects clean genre separation. Proposal captured here for a later session.

**Current state of `.specs/`:**
- `META/` exists but is empty (0 schemas)
- `state/` mixes three genres: periodic snapshots (`CORE-state-2026-04-18.md`), dated investigations (`nested_scope_audit_2026-04-19.md`, `tracing_mandatory_diagnostic_2026-04-20.md`, `reconnaissance_2026-04-20.md`), and external-facing whitepapers (`Prior Art and the End-to-End Gap.md`)
- Naming is inconsistent: `northstar/CORE - What It Does.md` (spaces, hyphens), `northstar/core_northstar.md` (snake_case lowercase), `state/Prior Art and the End-to-End Gap.md` (spaces, title case, no date), `state/CORE-state-2026-04-18.md` (hyphen date), `state/nested_scope_audit_2026-04-19.md` (underscore date)

**Proposed reorganization:**
- `state/` keeps only periodic state snapshots (`CORE-state-YYYY-MM-DD.md`)
- `state/investigations/` holds dated one-off analyses (nested-scope audit, tracing diagnostic, reconnaissance)
- `whitepapers/` (new) holds external-facing positioning documents (Prior Art whitepaper, any future competitive framing)
- `META/` gains minimum-viable schemas for: paper, ADR, URS, handoff, plan, state snapshot, investigation, whitepaper (eight schemas)
- Naming convention: `kebab-case` for multi-word filenames; date prefix `YYYY-MM-DD-` for dated artifacts; no spaces anywhere

**Execution cost:** one session. Moves are `git mv`; schemas are authored per minimum-viable shape. The current session's citations at `state/tracing_mandatory_diagnostic_2026-04-20.md` and `state/reconnaissance_2026-04-20.md` become `state/investigations/2026-04-20-tracing-mandatory-diagnostic.md` and `state/investigations/2026-04-20-reconnaissance.md` — one find-replace edit in this plan when the reorg runs.

**Not executed this session.** Captured here so the idea does not drift out of context.

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
# NOTE: 'core-admin check rule --rule X --verbose' is documented in prior plans but
# does not exist in the current CLI. Command name may have been removed without
# plan update. Treated as Phase 4 documentation-drift item.

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
# Connection requires PGPASSWORD env var or ~/.pgpass; no-password invocation fails.
PGPASSWORD=core_db psql -U core_db -d core -h 192.168.20.23

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

**Module path notes:**
- `AuditorContext` lives at `src/mind/governance/audit_context.py`, not `src/mind/logic/engines/ast_gate/base.py`. Several prior documents cite the wrong path; they are superseded.

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
Audit state: [verdict, total findings, distribution by check_id]
Daemon state: [active/inactive, last Blackboard activity]
Active workers: [count]
Next step: [specific action]
```

---

Current A3 phase: 3
Last session: 2026-04-20 — Engine-integrity triad investigation concluded. Three of four named engine issues falsified (fnmatch, Call-handling, silent rule); one remains (existence-not-coverage in `required_calls`) but is non-blocking. `.specs/` documentation drift corrected via Block A. Reconnaissance captured in `state/reconnaissance_2026-04-20.md`.
Current blocker: Daemon inactive since 2026-04-18 14:26. No autonomous convergence has occurred in ~36 hours at time of snapshot.
Audit state: PASS, 39 findings (37 WARNING, 2 INFO). 32 of 39 are `modularity.needs_split` (single-class concentration — needs diagnosis).
Daemon state: inactive.
Active workers: 15 registered active; 20 abandoned rows in `core.worker_registry`.
Next step: (a) decide whether to activate daemon and address finding concentration, or (b) begin Block B (state/ reorganization + META schemas), or (c) diagnose verdict-threshold semantics. Open question for next session.
