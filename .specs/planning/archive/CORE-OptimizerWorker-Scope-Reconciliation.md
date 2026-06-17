# OptimizerWorker — Scope Reconciliation (#115)

**Status:** Ratified 2026-06-16 — governor accepted; #115 re-scoped per R2 (re-scope, not close)
**Created:** 2026-06-16
**Re:** GitHub issue #115 ("OptimizerWorker — design and implement")
**Supersedes the premise of:** the handoff note that framed #115 as a ready-to-design task

---

## 0. Why this note exists

The #115 handoff was "draft the OptimizerWorker design ADR." Reconnaissance found
the task rests on **three conflicting/stale premises**. Designing a component on
top of them would design the wrong thing. This note reconciles them and
recommends a disposition; it makes no design decision itself.

---

## 1. Findings

### F1 — The stated driver is closed.
`CORE-A3-plan.md` is `Status: Closed (Historical) — A3 milestone fully achieved
2026-05-12` (archived 2026-06-07). #115's rationale is "Known Blocker on
CORE-A3-plan.md Phase 3+." A3 is not pending, so the blocker framing is moot.
The issue body itself concedes manual candidate selection "is sustainable at
current scale."

### F2 — "OptimizerWorker" names two different components.
| Source | Conception | State |
|---|---|---|
| Issue #115 (OPEN) | **Candidate selection** for remediation campaigns — automate which parked items the governor picks | the subject of this note |
| `CORE-OptimizerWorker.md` + **ADR-034** | **Pattern graduation** — codify ViolationExecutor-discovered fixes into AtomicActions | formally deferred until VE accumulates ≥20 candidates across ≥5 rule namespaces |

These are materially different workers (selection vs codification) sharing one
name. Per `feedback_two_surface_requires_two_structures`, the collision — not a
missing design — is the bug.

### F3 — The candidate-selection role is largely already built.
`src/will/agents/strategic_auditor/` (`StrategicAuditor`) already:
- clusters audit findings into `RootCauseCluster`s,
- assembles a `StrategicCampaign`,
- persists a parent Task + one child Task per cluster (`effects.persist_campaign`),
- executes clusters flagged autonomous, leaving the rest for governor pick
  (`effects.execute_autonomous_tasks`, `execute_autonomous` flags).

That is substantially the "candidate selection for remediation campaigns under
governor oversight" #115 describes. #115 is therefore **not greenfield**; the
real residual is narrow (see §3).

---

## 2. Recommendations

### R1 — "OptimizerWorker" stays with the ADR-034-deferred pattern-graduation component.
It holds the paper (`CORE-OptimizerWorker.md`) and an accepted ADR (ADR-034)
under that name. Reusing the name for candidate-selection would re-create the
collision. ADR-034's deferral is untouched by this note — the graduation worker
remains parked on its VE-data threshold.

### R2 — Re-scope #115 away from "design+build a new worker."
The campaign/candidate machinery exists in `StrategicAuditor`. #115 should be
re-pointed at the **concrete residual gap vs StrategicAuditor**, not a fresh
component. Candidate residuals to confirm by gap-analysis:
- the **calibration check** the issue explicitly names — an observable signal of
  StrategicAuditor's picks vs what the governor would have picked;
- any **governor-oversight gating** missing from the autonomous-cluster path.

If gap-analysis finds no real residual, #115 closes as **substantially delivered
by StrategicAuditor** (consistent with the standing lesson that "build X" tasks
partly dissolve once verified against the current tree).

### R3 — Do not author an OptimizerWorker design ADR now.
Neither conception warrants it at this moment: the graduation worker is
ADR-034-deferred; the selection worker substantially exists. The next step is a
**focused StrategicAuditor-vs-#115 gap-analysis**, not a speculative design.

---

## 3. Proposed disposition (governor to ratify)

1. **Confirm R1** — name ownership stays with the deferred graduation worker.
2. **Re-scope #115** to "calibration + oversight gap-analysis vs StrategicAuditor"
   — or close it as substantially-delivered if no residual survives the analysis.
3. On your word, I update issue #115 to reflect (2) and, if you want name
   ownership formalized, append a short clarifying section to ADR-034 (R1).

No code, `.intent/`, or issue change is made until you ratify this note.

---

## 4. References
- Issue #115 — "OptimizerWorker — design and implement"
- ADR-034 — OptimizerWorker formal deferral (pattern-graduation conception)
- `.specs/papers/CORE-OptimizerWorker.md` — reserves the name for graduation
- `.specs/planning/archive/CORE-A3-plan.md` — closed A3 record (the stale driver)
- `src/will/agents/strategic_auditor/` — extant campaign/candidate machinery
