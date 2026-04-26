# CORE — A3 Governed Autonomy Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-26
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
| **G1 — Loop closure** | An autonomous fix lands end-to-end on a non-synthetic example: finding detected → proposal created → proposal approved → execution succeeded → re-audit confirms resolution. Single clean run is the minimum. | ⚠️ Not yet demonstrated on the live codebase. Stream B is structurally complete. Daemon is active (as of 2026-04-24 session 4) but an end-to-end autonomous round-trip has not yet been observed post-restart. |
| **G2 — Convergence** | Sustained state where rate of finding resolution exceeds rate of finding creation. Per the Convergence Principle, this is the fundamental operational metric — it is what makes "governed autonomy" truthful rather than aspirational. | ⚠️ Not reached. 31 findings open as of 2026-04-24. Verdict-threshold semantics undocumented (tracked as issue #108) — PASS is returned with WARNING-dominant finding sets, so the convergence signal is ambiguous at the metric layer. |
| **G3 — Consequence chain** | Finding → Proposal → Approval → Execution → File changes → New findings is continuously materialized as a queryable causality chain. Required for regulated environments, autonomous debugging, and for a non-programmer governor to trust the system without reading code. | ⚠️ Not built. Individual links exist (proposals table, Blackboard history, audit JSON, git). The chain is not materialized as a single queryable graph. This is the "two-log problem" — legal traceability, not bookkeeping. Tracked as issue #110; Band B is the strategic arc. |
| **G4 — Governance in `.intent/`** | No enforcement logic, path mappings, policy thresholds, or governance decisions live in `src/`. All of it lives in `.intent/` (or, for human-intent documents, `.specs/`). This is the claim that makes the "non-programmer governor" role coherent. | 🔄 In progress. ADR-004 (task_type phase map in YAML) and ADR-005 (audit verdict policy in YAML) were direct advances. Leaks worth naming: path mappings embedded in Stream B sensor/action code; `action_executor` usage unguarded in some Body workers. Tracked as issue #111. |

**Gate coupling:** G1 cannot be *proved* without G3 (you can't demonstrate the loop closed without the chain). G2 cannot be *measured* without G1 (no resolution rate without autonomous resolution). G4 is orthogonal but load-bearing: it is the reason a non-programmer can operate the system, and without it the other three gates describe a system that still requires its author.

---

## Current State (2026-04-24)

| Item | Status |
|------|--------|
| Audit | PASS — 31 findings, WARNING-dominant, duration 55s |
| Daemon | Active — runtime verification of restarted state underway |
| Worker registry | 15 active |
| Bands | Band A closed (attribution); Bands B, C, D, E open |
| GitHub issue migration | 47 open issues (35 from the 2026-04-24 migration #107–141, plus issues opened in subsequent sessions); Known Blockers, handoff residue, Population C all migrated |
| Autonomy status hub | Pinned issue #106 — current A2, working toward A3 |
| ADR inventory | ADR-001 through ADR-013 accepted and landed |
| Handoff archive | Moved to `.specs/state/handoffs/` per SESSION-PROTOCOL.md §2 |
| Session protocol | SESSION-PROTOCOL.md active at `.specs/planning/SESSION-PROTOCOL.md` |

**Active audit finding classes (2026-04-24 tail sample):** `modularity.needs_split`, `modularity.class_too_large`, `governance.dangerous_execution_primitives`, `autonomy.tracing.mandatory`. All WARNING; no ERROR findings observed.

**Verdict semantics:** Still unresolved at the documentation layer (issue #108). ADR-005 governs the policy *file*; ADR-005's codified behavior is what currently gates audit verdicts.

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

**Status:** Stream A (ViolationExecutor) complete. Stream B (test writing) structurally complete. Stream C (delegation) infrastructure complete. Band A (attribution) closed 2026-04-24 via ADR-011.

Remaining Phase 3 work is tracked on GitHub under Band D — Engine Integrity. Live list:
https://github.com/DariuszNewecki/CORE/milestone/16

### Phase 4 — CLI Health ⬜
Not started. Tracked items (e.g. ghost registry cleanup, `core-admin` command gaps) captured as GitHub issues.

### Phase 5 — Visibility ⬜
Not started. **G3 closes here** — consequence chain materialization is a Phase 5 artifact. Tracked on GitHub under Band B — Consequence Chain:
https://github.com/DariuszNewecki/CORE/milestone/14

---

## Milestone Summary

| Phase | Signal | Status |
|-------|--------|--------|
| 0 — Clean slate | Audit passes, DB clean | ✅ Complete |
| 1 — Single loop | Purity loop runs unattended | ✅ Complete |
| 2 — All sensors | All sensors active, converging | ✅ Complete |
| 3 — Capability gaps | Trust-hardened; G1 demonstrated; daemon live | 🔄 Daemon active; Band A closed; G1 not yet demonstrated on live codebase; remaining work tracked under Band D |
| 4 — CLI health | All commands work, legacy gone, URS written | ⬜ Not started |
| 5 — Visibility | Demo-ready, `tail -f` tells the story, G3 chain queryable | ⬜ Not started; Band B carries G3 — 5 issues open (1 epic + 4 children); decomposition committed `acf56a6b` 2026-04-25 |

---

## Known Blockers

Operational tracking moved to GitHub under band milestones as of 2026-04-24. The Known Blockers table previously held in this document is superseded by:

- **Band A — Attribution** (closed): https://github.com/DariuszNewecki/CORE/milestone/13
- **Band B — Consequence Chain**: https://github.com/DariuszNewecki/CORE/milestone/14
- **Band C — Historical Debt**: https://github.com/DariuszNewecki/CORE/milestone/15
- **Band D — Engine Integrity**: https://github.com/DariuszNewecki/CORE/milestone/16
- **Band E — Outward-Facing**: https://github.com/DariuszNewecki/CORE/milestone/17

All issues opened under SESSION-PROTOCOL.md §6 template. Closure criteria live on each issue. Priority filter: `priority:high` labels mark items blocking a band from closing.

---

## Resolved Blockers

Historical record of blockers resolved. New resolutions land here at session close per SESSION-PROTOCOL.md §5 Step 3.

| Blocker | Notes |
|---------|-------|
| ~~`core.proposals` legacy table — schema drift causing tooling confusion~~ | ✅ Resolved 2026-04-26 — ADR-013. Legacy table (0 rows, never provisioned), ORM models, file-based CLI path, and all reference strings removed. `core.autonomous_proposals` is now the sole proposal table. Table name `core.proposals` reserved for future rename. Commits 107887b9–db5d31e2. |
| ~~Daemon inactive — autonomous loop not converging~~ | ✅ Resolved 2026-04-25 — root cause identified as clean shutdown via `systemctl stop` on 2026-04-18 16:26:35 (exit 0; not a crash). Daemon restarted 2026-04-24 13:18; 24h verification confirmed 12,199 blackboard entries, 729 cycle completions, 15 active workers heartbeating. #107 closed with verification scan; G1 round-trip evidence gap split out as #144. |
| ~~Attribution principle unwired in `src/`~~ | ✅ Resolved 2026-04-24 — ADR-011 authored; two refactors closed the violations (commits `8738595d`, `794a4480`); enforcement rule `architecture.blackboard.worker_only_inserts` active at blocking severity. Band A closed. |
| ~~Finding → Proposal contract unwired (§7 + §7a)~~ | ✅ Resolved 2026-04-24 — ADR-010 authored; three-layer contract closed (commit `62a84ff7`). Runtime verification of revival path remains passive (issue #122). |
| ~~`build.tests` context gap — CoderAgent generates without source context~~ | ✅ Resolved 2026-04-19 — commits `a0f68287`, `8a1556e4` (ADR-003 + ADR-004). |
| ~~`src/shared/infrastructure/context/cli.py` vestigial CLI~~ | ✅ Deleted 2026-04-19. |
| ~~Phase map hardcoded in `src/` (three-way drift)~~ | ✅ Governed via ADR-004 in `.intent/enforcement/config/task_type_phases.yaml`. |
| ~~Audit verdict policy hardcoded in `src/`~~ | ✅ Governed 2026-04-20 via ADR-005 in `.intent/enforcement/config/audit_verdict.yaml`. |
| ~~`modularity.needs_split` implementation misaligned with statement~~ | ✅ Corrected 2026-04-20 via ADR-006 — mechanism replaced from import-based proxy to content-pattern responsibility detection. |
| ~~`_expr_is_intent_related` missing `Call` handling~~ | ✅ `ast.Call` branch present; shape verified live 2026-04-20. |
| ~~`autonomy.tracing.mandatory` silent non-firing~~ | ✅ Premise falsified 2026-04-20 — rule fires. Handoffs carrying the claim superseded. |
| ~~ViolationExecutor `'id'`/`entry_id` bug~~ | ✅ Fixed 2026-04-18. |
| ~~Stream B test-writing not wired~~ | ✅ Complete 2026-04-18. |
| ~~Shared/ boundary violations~~ | ✅ Resolved 2026-04-18 — ADR-002. |
| ~~`style.formatter_required` — deferred, no engine check~~ | ✅ Fully wired 2026-04-17. |
| ~~Proposal Path workers not daemonized~~ | ✅ Fixed 2026-04-17. |
| ~~Worker heartbeat not updating registry~~ | ✅ Fixed 2026-04-17. |
| ~~BlackboardAuditor and WorkerAuditor not active~~ | ✅ Fixed 2026-04-17. |
| ~~Documentation stale — A2 marked current, `.specs/` absent~~ | ✅ Fixed 2026-04-17. |
| ~~Blackboard hygiene bug (2 failure modes)~~ | ✅ Fixed 2026-04-16. |
| ~~`.specs/` invisible to vector layer~~ | ✅ Fixed 2026-04-16. |
| ~~Context build evidence missing constitutional papers~~ | ✅ Fixed 2026-04-16. |
| ~~`intent_alignment.py` northstar broken~~ | ✅ Fixed 2026-04-16. |
| ~~Context build layer constraints noise~~ | ✅ Fixed 2026-04-16. |
| ~~`core-admin vectors query` missing specs collection~~ | ✅ Fixed 2026-04-16. |
| ~~Rich Panel rendering bug in build.py~~ | ✅ Fixed 2026-04-16. |
| ~~Stale Blackboard entries (2)~~ | ✅ Purged 2026-04-16. |
| ~~No functional requirements document~~ | ✅ `CORE-What-It-Does.md` authored 2026-04-16. |
| ~~Ghost worker registry entries (23)~~ | ✅ Marked abandoned via SQL — 2026-04-15. |
| ~~`.intent/` contains non-operational documents~~ | ✅ `.specs/` layer established — 2026-04-15 — ADR-001. |
| ~~Orphan classifier (92 findings)~~ | ✅ Dissolved — 0 real orphans. |

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

### ADR-005 (2026-04-20) — Govern audit verdict policy in `.intent/`
Severity→verdict mapping, carve-out list, and DEGRADED preconditions codified as data at `.intent/enforcement/config/audit_verdict.yaml`. Governed loader at `src/shared/infrastructure/intent/audit_verdict.py` mirrors the ADR-004 `task_type_phases.py` pattern. `_determine_verdict` retrofitted to branch on the loaded policy.

### ADR-006 (2026-04-20) — Align `modularity.needs_split` implementation with its statement
Rule statement is law, implementation is mechanism; when they disagree, the mechanism is corrected. `_identify_concerns(imports)` replaced with `_detect_responsibilities(...)` so the check measures "single coherent responsibility" (content-pattern-based) rather than "narrow external domain-library exposure" (import-based proxy).

### ADR-007 (2026-04-21) — `modularity.class_too_large` rule split from `modularity.needs_split`
`modularity.class_too_large` introduced as a distinct rule in `.intent/rules/code/modularity.json`. Sensor layer routes via a deterministic structural test using two sensor methods, matching the 1-rule-to-1-method pattern. Separates the automatable module-redistribution case from the non-automatable dominant-class case.

### ADR-008 (2026-04-22, parked) — Constitutionalize `impact_level`
Documents the governance-in-code inversion where `impact_level` (auto-approve vs. requires-human) is declared in `@register_action` decorators rather than in `.intent/`. Parked — not session-scale. No implementation committed.

### ADR-009 (2026-04-24) — CLI-depth block transient — passive instrumentation over active probe
No `cli.*` rule or YAML mapping modified; no active reproduction of the transient attempted. Passive instrumentation already in place (commit `cf2ea63c` persists full `ConstitutionalViolationError.to_dict()` attribution into `action_results.violations[]`) captures any recurrence — `rule_name`, `path`, `source_policy` — without live introspection.

### ADR-010 (2026-04-24) — Wire the §7 + §7a Finding/Proposal contract
All three gaps closed in one coordinated change: correct terminal status (`deferred_to_proposal`), forward link added (`proposal_id` in finding payload), revival implemented on proposal failure. `BlackboardService` gains `defer_entries_to_proposal`; worker resolve path fixed; `ProposalStateManager` implements the §7a revival query.

### ADR-011 (2026-04-24) — Workers own blackboard attribution; services do not post
Every INSERT into `core.blackboard_entries` must originate from a registered Worker via base-class `post_finding` / `post_report` / `post_heartbeat` / `_post_entry`. Services may UPDATE (state transitions) but never INSERT. Architectural cut: INSERT creates attribution (Worker-only); UPDATE transitions pre-attributed rows (anyone). Enforcement rule `architecture.blackboard.worker_only_inserts` active at blocking severity. Band A closed.

### ADR-012 (2026-04-25) — Centralize globstar pattern matching via `pathspec`
Eight `Path.match` call sites across `src/` carry Python 3.12's `**`-as-single-segment quirk; three are silent under-enforcement at security-sensitive sites (redactor, FileNavigator). Adopt `pathspec`'s `GitWildMatchPattern` as the standard primitive; introduce `src/shared/utils/glob_match.py` as the single entry point; migrate seven raw call sites and rewrite forbid-pattern strings to gitignore semantics. `AuditorContext` is out of scope — its hand-rolled `_include_matches`/`_is_excluded` compensation works correctly today and migrates separately under retargeted Issue #117 (real landing SHA `f634e521`, not `8e9325fb` as the plan previously claimed).

### ADR-013 (2026-04-26) — Retire core.proposals; reserve name for core.autonomous_proposals
`core.proposals` (constitutional file-replacement table with cryptographic
signing) retired. Never provisioned in production — 0 rows, no active
writers, signing infrastructure never created. All proposal activity runs
through `core.autonomous_proposals`. Table name `core.proposals` reserved:
when "autonomous" becomes redundant (all proposals are autonomous),
`core.autonomous_proposals` renames to `core.proposals`. Eliminates the
two-table confusion that produced issue #144.

---

## Intent Layer Hygiene — proposed (not executed)

`.specs/` has grown organically. Proposal captured here for a later session.

**Proposed reorganization:**
- `state/` keeps only periodic state snapshots (`CORE-state-YYYY-MM-DD.md`)
- `state/investigations/` holds dated one-off analyses
- `state/handoffs/` holds the handoff archive (done 2026-04-24)
- `whitepapers/` (new) holds external-facing positioning documents
- `META/` gains minimum-viable schemas for: paper, ADR, URS, handoff, plan, state snapshot, investigation, whitepaper (tracked as issue #116)
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

---

## Session Handoff Template

Per SESSION-PROTOCOL.md, session handoff lives in GitHub (issues, milestones, releases, commits) rather than in long-form markdown. This template is retained for quick orientation only:

```
Current A3 phase: [0/1/2/3/4/5]
Gate status: [G1/G2/G3/G4 — any that moved this session]
Last session: [what was done]
Current band: [A closed / B/C/D/E in progress — what's queued]
Audit state: [verdict, finding count]
Daemon state: [active/inactive]
Active workers: [count]
Next step: [specific action or issue #N]
```

---

Current A3 phase: 3 (trust-hardening)
Gate status: G1 not yet demonstrated on live codebase, G2 not reached, G3 not built (Band B), G4 in progress (ADR-005 added).
Last session: 2026-04-24 — Band A closed via ADR-011 and enforcement rule; ADR-009, ADR-010, ADR-011 landed. GitHub migration: 25 labels, 5 band milestones, 35 issues opened across three batches (#107–141); autonomy status hub pinned at #106; handoff archive relocated to `.specs/state/handoffs/`; SESSION-PROTOCOL.md committed; `.gitignore` hygiene fixes.
Current band: Band A closed. Band D carries most remaining Phase 3 work. Band B carries G3 (consequence chain) — strategic arc, not yet started.
Audit state: PASS, 31 findings, WARNING-dominant.
Daemon state: active.
Active workers: 15.
Next step: Session-open at next session per SESSION-PROTOCOL.md §3 — state scan, GitHub scan, pick a lead. Candidate issues are visible under band milestones at https://github.com/DariuszNewecki/CORE/milestones.
