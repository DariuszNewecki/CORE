---
kind: planning
title: CORE Autonomy Mission-Runner Reconnaissance
status: draft
---

# CORE Autonomy Mission-Runner Reconnaissance

**Status:** Draft — for Governor review. Reconnaissance and formal gap recording only.

## Scope and non-actions

This document traces every registered API, CLI, worker, and orchestration entry point in the
pinned trees that accepts or could propagate a goal, an external target, an investigation plan, a
findings/unavailable-evidence outcome, or a blackboard record — to determine, completely, whether
CORE currently exposes an executable mission-runner interface matching what
`.specs/attestations/adr-159-blind-author-raw-claude-opus-5-20260910.md`'s Document A §A6 / Document
B §B6 assume:

```
target + broad goal → autonomous investigation plan → governed outcomes → blackboard evidence → export
```

**This unit does not:** implement runtime code; change `.intent/` (beyond the single mechanical
namespace-manifest registration this document itself requires); alter ADR-159; rebaseline either
runner; execute either pinned runner against any target; access the ITAM Governance Library; open
the sealed benchmark; inspect anything under `work/`; accept or reject any ADR on the Governor's
behalf; or begin any implementation. **Trial 0 and Trial 1 remain paused.** The frozen runners have
not run either trial and are not described here as having failed one.

## Pins and inspection method

Git object reads only (`git show`, `git grep`, `git ls-tree`) against three refs — no checkout, no
execution:

| Ref | Commit |
|---|---|
| Trial 0 runner | `27160a0a8768cf72bbe2a8fecc3d9169db758efc` |
| Trial 1 runner | `b57423dc85c11c6650a9515c136bab49b02107ec` |
| Current HEAD (this unit) | `bb1c19c5b7f5539e401bdb0d36e63128969bdb04` |

Every file cited below was hash-compared across all three refs; divergences are stated explicitly
where they exist. `git diff --stat` between the Trial 1 pin and HEAD, restricted to `src/` and
`.intent/`, shows only the seven files already accounted for by Units D/E (physical
symlink-containment, Ruff-runtime fixes, `var/tmp/` routing, plus the namespace-manifest entries
this session's own prior units added) — nothing touching any file discussed below changed between
the Trial 1 pin and HEAD.

## Complete candidate-entry-point inventory

Ten questions per candidate, per the brief: (1) registered/reachable, (2) accepted inputs, (3)
explicit external target, (4) self-directed investigation vs. fixed procedure, (5) reads/writes,
(6) authority/refusal boundary, (7) blackboard reach, (8) third-party export/reconstruction, (9)
termination/timeout/intervention, (10) source-code vs. document-corpus subjects.

### 1. `POST /develop/goal` and `develop_from_goal()` — **omitted from the earlier trace entirely**

`src/api/v1/development_routes.py`, `src/will/autonomy/autonomous_developer.py`. Byte-identical
across all three refs.

1. **Registered and reachable, on two independent surfaces.** API:
   `v1.include_router(development_routes.router, tags=["Development"])`
   (`src/api/main.py:175`); `ROUTER_EXPOSURE = "governor-only"`, router-level
   `dependencies=[require_governor]` (`development_routes.py:24-31`); route
   `@router.post("/develop/goal", status_code=202)` (`development_routes.py:43`). CLI:
   `core-admin dev refactor "<goal>" [--write] [--workflow ...]`
   (`src/cli/resources/dev/refactor.py:33-42`, `@app.command("refactor")`,
   `exposure=CommandExposure.GOVERNOR_ONLY`, `dangerous=True`) — calls `develop_from_goal` directly
   at `refactor.py:87`.
2. **Inputs:** `goal: str` (free text); `workflow_type`/`--workflow` — a **closed vocabulary**
   validated against `_VALID_WORKFLOW_TYPES = {"refactor_modularity", "code_modification",
   "coverage_remediation"}` (`src/will/phases/interpret_phase.py:41-47`, `:93-105` — an unknown
   value is rejected, not accepted as free text); `write: bool`.
3. **External target: no.** Neither `development_routes.py`, `autonomous_developer.py`, nor any
   phase in its call chain accepts a path or repository parameter. All operate on
   `context.git_service.repo_path` — the same process-level `REPO_PATH`/`MIND` binding already
   documented for BYOR/Scout in `CORE-Autonomy-Trial-Runner-Interface-Appendix.md` item 4.
4. **Self-directed investigation: partial, and precisely bounded.** `ParsePhase.execute()`
   (`src/will/phases/parse_phase.py:81`) calls `PlannerAgent.create_execution_plan(goal)` — a real
   LLM call (`will/agents/planner_agent.py:70-188`) that decomposes the goal into an ordered
   `list[ExecutionTask]`, chosen from the live 38-action registry
   (`action_registry.list_all()`, `planner_agent.py:100`), with constitutional RAG
   (`_fetch_constitutional_context`, policy-vector search) and QA-constraint injection. This is
   genuine plan synthesis, not fixed pattern matching — the one place in this entire trace where an
   LLM produces its own ordered step sequence. **But:** `create_execution_plan` accepts an optional
   `reconnaissance_report: str = ""` (`planner_agent.py:71`), and its one call site never supplies
   one (`parse_phase.py:81` passes only `goal`). **`ReconnaissanceAgent` does not exist anywhere in
   `src/` at any of the three refs** (`git grep -i reconnaissance` across `src/` returns zero
   matches for a class/module, only this one dangling docstring reference). The repository is never
   read or explored before the plan is produced — planning is goal-text-only. Target identification
   is a second, independent regex extractor: `InterpretPhase._extract_target_info`
   (`interpret_phase.py:217-250`) matches `\b[\w/]+\.py\b` file paths or `[a-z_]+_[a-z_]+` module
   names directly out of the goal string — the same single/few-target shape already documented for
   `NaturalLanguageInterpreter` in the prior Appendix (item 3), now confirmed as a second,
   independently-implemented instance of that same pattern.
5. **Reads/writes:** reads the goal string, the static action-registry description, and
   constitutional-policy vectors. Writes real files when `write=True`, via `ActionExecutor`
   (`src/body/atomic/executor.py`) in `ExecutionPhase`
   (`src/will/phases/execution_phase.py:86-90`, `:137-142`) — either through `ExecutionAgent`
   (general path) or a direct `refactor.apply_split` action call plus `git_service.commit_paths`
   (deterministic-split path, `execution_phase.py:121-196`). This is genuine, governed mutation
   capability, not a stub.
6. **Authority/refusal:** `require_governor` (API) / `GOVERNOR_ONLY` + `dangerous=True` (CLI);
   `ActionExecutor`'s own per-action constitutional checks; `StagingContaminationError` (ADR-129
   D1) refuses a commit whose staged set is contaminated (`execution_phase.py:165-179`).
7. **Blackboard: none, confirmed empirically.** `git grep -n "blackboard\|post_finding\|post_report\|post_heartbeat"`
   across every file in the call chain —
   `will/phases/{interpret,parse,load,runtime,audit,execution}_phase.py`,
   `will/orchestration/{workflow_orchestrator,phase_registry}.py`,
   `will/autonomy/autonomous_developer.py`, `will/agents/planner_agent.py`,
   `will/agents/execution_agent.py`, `will/agents/coder_agent.py`, and `body/atomic/executor.py`
   itself — returns **zero matches**. Progress is tracked in `core.tasks` via
   `TaskRepository` (`src/shared/infrastructure/repositories/task_repository.py`), a distinct table
   from `core.blackboard_entries`.
8. **Third-party reconstruction: no.** There is no blackboard export to reconstruct from; only
   `core.tasks` rows and process logs exist.
9. **Termination:** `WorkflowDefinition.timeout_minutes`
   (`will/orchestration/workflow_orchestrator.py:43`, from `.intent/workflows/*.yaml` or a
   configured default) — the only whole-operation timeout found anywhere in this reconnaissance or
   the prior unit's. `PlannerAgent.max_retries=3` bounds plan generation;
   `IterativeCoderAgent`'s generate/repair loop is capped by `generation_budget.yaml`. Phase
   failures halt the orchestrator per each phase's declared `failure_modes`
   (`workflow_orchestrator.py:191-209`).
10. **Subjects:** source code only. All three valid `workflow_type` values and the underlying
    38-action registry are code-shaped; no document-corpus workflow exists.

**Classification: present and usable** (two independent, live entry points) **for a narrow,
single/few-target, code-only, self-repo-only goal** — categorically different from, not a
degraded version of, Documents A/B's assumption.

### 2. `core-admin dev strategic-audit [--write] [--execute]`

`src/cli/resources/dev/strategic_audit.py`, `src/will/agents/strategic_auditor/{agent,
context_gatherer,effects,models,reasoning}.py`. Byte-identical across all three refs. Also omitted
from the earlier trace.

1. **Registered and reachable.** `@app.command("strategic-audit")`
   (`strategic_audit.py:34`); instantiates `StrategicAuditor(context=context,
   cognitive_service=cognitive_service)` (`strategic_audit.py:97`).
2. **Inputs:** `--write`, `--execute` booleans only — **no goal, no target of any kind.**
3. **External target: no, structurally.** `StrategicAuditor.__init__(self, context: CoreContext,
   cognitive_service)` (`agent.py:61`) and `SystemContextGatherer` take no path/repo argument
   anywhere in their signatures. `SystemContextGatherer` reads six dimensions of **CORE's own**
   state — constitutional_health (AST + `.intent/`), semantic_landscape (Qdrant), knowledge_gaps,
   structural_health (DB symbols), change_context (git), intent_drift
   (`context_gatherer.py:4-14`) — all bound to `context`, the same process-level repo/DB/vector
   binding as everywhere else in this trace.
4. **Self-directed investigation: the most genuine found in this reconnaissance, but entirely
   self-referential.** Reads broad system state across six dimensions (not a single/few-target
   regex extraction), then LLM-synthesizes a prioritized, multi-cluster remediation campaign
   (`reasoning.synthesize_campaign`, `agent.py:26`) — this is real investigation-and-plan
   synthesis, closer in shape to what Trial 0/1 assume than anything else traced. It never touches
   `.intent/` (hard invariant, `agent.py:15,55`) and flags any `.intent/`-relevant finding as an
   escalation requiring governor approval rather than acting on it.
5. **Reads/writes:** reads audit output, DB, `.intent/`, git, vectors; writes only through
   `develop_from_goal` (`effects.execute_approved_clusters`, imported at `agent.py:26`) — and only
   for clusters the governor has already approved via the per-cluster review surface (ADR-110 D4,
   `agent.py:74-77`) — a fresh campaign therefore executes nothing on its first run.
6. **Authority/refusal:** per-cluster governor acceptance gate; the `.intent/`-write hard
   invariant above.
7. **Blackboard: none** (`git grep -n "blackboard\|post_finding\|post_report"` across
   `will/agents/strategic_auditor/**` — zero matches).
8. **Third-party reconstruction:** campaign persisted to `core.tasks`/related tables (via
   `effects.persist_campaign`), not the blackboard.
9. **Termination:** one bounded audit cycle; no goal-driven or open-ended exploration loop.
10. **Subjects:** CORE itself only — cannot address an external target of either modality, by
    construction, not by a closable gap.

**Classification: present and usable, but categorically self-referential** — cannot serve Trial
1's unfamiliar-external-corpus requirement regardless of how it is invoked.

### 3. `ConversationalAgent` — re-confirmed, unchanged

`src/will/agents/conversational/agent.py`. Byte-identical across all three refs (no `src/` change
between the Trial 1 pin and HEAD touches this file, per the diff check above). The prior Appendix's
item 1 finding stands without modification: its own docstring states "Phase 1 (Current): Read-only
information retrieval... **NO proposals, NO execution**"; Phase 2 (proposal generation) and Phase 3
(full autonomous execution) are explicitly marked future/not-yet-implemented.

**Classification: present but disconnected** from any planning or execution capability.

### 4. `core-admin governance validate-request` / `NaturalLanguageInterpreter` — re-confirmed, plus one addition

`src/cli/commands/governance.py`, `src/will/interpreters/natural_language_interpreter.py`.
Byte-identical across all three refs. Prior Appendix items 2-3 stand: the command performs a
five-gate constitutional-validation demonstration and stops after printing a summary — it never
constructs a Proposal, never calls `ActionExecutor`, never writes to the blackboard.
`NaturalLanguageInterpreter` remains a priority-ordered, single-target regex classifier.

**Addition from this unit:** `InterpretPhase` (item 1 above) independently reimplements the same
single-target-extraction pattern for the `develop_from_goal` pipeline, via its own
`_infer_workflow_type`/`_extract_target_info` methods — a second, separately-maintained instance of
the identical narrow-classification shape, not a shared component.

**Classification: present but non-executing** (`validate-request`) / **partially suitable, narrow**
(`InterpretPhase`, which does feed real execution but only for a single/few named target).

### 5. BYOR / Scout / `core-admin code audit --offline --target` — carried forward

Full findings already filed in `CORE-Autonomy-Trial-Runner-Interface-Appendix.md`'s 2026-09-10
addendum (commit `bb1c19c5`) and not repeated in full here. Summary for this inventory: BYOR
(`src/cli/logic/byor.py`) and Scout's interactive path (`src/cli/logic/scout.py`'s `induce_rules`)
are **present but disconnected** — real production code with zero CLI registration at either pin;
BYOR is reachable only via a governor-gated API route, Scout's write path is unreachable
end-to-end even via its API route. `core-admin code audit --offline --target <path>` is **present
and usable** as a CLI command but confirmed to produce **zero blackboard record** in `--offline`
mode (`mind/governance/stateless_audit.py`'s own docstring: "No filesystem writes. No DB access...
No worker dispatch").

### 6. Proposal creation and `ProposalConsumerWorker` — re-confirmed, plus one addition

`will.autonomy.proposal_repository.ProposalRepository.create()`,
`will.autonomy.proposal_state_manager.ProposalStateManager.approve()`. Prior Appendix item 7
stands: both are direct Python/DB calls, not CLI/NL surfaces; the production creation path is
`ViolationRemediatorWorker`, from blackboard findings already present — not from an operator-
supplied goal. No CLI command at either pin creates or approves a Proposal.

**Addition from this unit:** `develop_from_goal`'s execution phase (item 1 above) writes via
direct `ActionExecutor` calls, **entirely bypassing the Proposal lifecycle** —
`ProposalRepository.create()` is never called anywhere in that chain. This is a third, independent
write path alongside the two already documented (Unit D's hand-constructed Proposal;
`ViolationRemediatorWorker`'s blackboard-driven Proposal), gated instead by the per-invocation
`require_governor`/`dangerous=True` boundary. `ProposalConsumerWorker`, as a genuine `Worker`
subclass, does post to the blackboard (confirmed via `violation_remediator_blackboard.py` and
related files in the prior unit's grep) — but it only ever consumes Proposals that already exist
and are approved; nothing in the goal-driven paths traced here ever creates one for it to consume.

### 7. Blackboard export/query surfaces — re-confirmed, unchanged

`body.services.blackboard_service.blackboard_query_service.BlackboardQueryService
.fetch_latest_report_payload(subject)`; `core-admin workers show/purge/resolve`. No single
"export everything from this run" command exists at any of the three refs (prior Appendix item 8).
Since every goal/campaign-accepting path traced in this document and the prior one —
`develop_from_goal`, `strategic-audit`, BYOR, Scout, `code audit --offline` — produces zero
blackboard rows, this export surface currently has nothing to export for any of them, independent
of whether an "export everything" command existed.

## Evidenced call/reachability map

```
POST /develop/goal ─┐
                     ├─→ develop_from_goal() ─→ WorkflowOrchestrator.execute_goal()
core-admin dev       │        (autonomous_developer.py)   (workflow_orchestrator.py)
  refactor ──────────┘                                          │
                                                                  ├─ InterpretPhase   (regex target/workflow-type extraction)
                                                                  ├─ ParsePhase       (PlannerAgent — real LLM step planning,
                                                                  │                    NO reconnaissance_report ever supplied)
                                                                  ├─ LoadPhase        (readiness gate only)
                                                                  ├─ RuntimePhase     (CodeGenerationPhase / TestGenerationPhase)
                                                                  ├─ AuditPhase       (validates candidate artifacts)
                                                                  └─ ExecutionPhase   (ActionExecutor — real governed writes;
                                                                                        NO Proposal lifecycle; NO blackboard)

core-admin dev strategic-audit ─→ StrategicAuditor.run() ─→ SystemContextGatherer (CORE's own state only)
                                                          ─→ reasoning.synthesize_campaign (LLM)
                                                          ─→ effects.persist_campaign (core.tasks, not blackboard)
                                                          ─→ effects.execute_approved_clusters ─→ develop_from_goal()
                                                                                                    (same chain as above)

ConversationalAgent ─→ (Phase 1 only: read-only Q&A; no plan, no execution, dead end)

validate-request / NaturalLanguageInterpreter ─→ (stops after printing an authority-package summary)

BYOR (initialize_repository/promote_staged) ─→ POST /project/onboard[/promote] only (no CLI wiring)

Scout induce_rules() ─→ (zero call sites — dead)
Scout API route (scout_routes.py) ─→ returns candidates only; expects a CLI ratifier that does not exist

code audit --offline --target ─→ run_stateless_audit() ─→ stdout only (no DB, no blackboard, no writes)

ViolationRemediatorWorker ─→ Proposal (blackboard-sourced findings) ─→ ProposalConsumerWorker
                                                                          (the ONLY path in this whole
                                                                           trace that both posts to
                                                                           and consumes from the blackboard —
                                                                           and it is goal-blind: it never
                                                                           accepts an operator goal at all)
```

## Capability matrix

| Path | Registered/reachable | External target | Self-directed investigation | Blackboard | Classification |
|---|---|---|---|---|---|
| `POST /develop/goal` + `core-admin dev refactor` | Yes (API + CLI) | No | Partial — real LLM step planning, no comprehension/recon step | None | Present and usable, narrow |
| `core-admin dev strategic-audit` | Yes (CLI) | No — structurally CORE-only | Yes, broadest found — but self-only | None | Present and usable, self-referential only |
| `ConversationalAgent` | Yes, but Phase 1 read-only | N/A | No | None | Present but disconnected |
| `validate-request` / `NaturalLanguageInterpreter` | Yes | N/A | No — single-target regex | None | Present but non-executing |
| BYOR | API only, governor-gated | Yes (the one path that does) | No — fixed copy | None | Present but disconnected (no CLI) |
| Scout | API returns candidates only | Yes (if reachable) | Partial — LLM proposes from AST-only digest | None | Present but disconnected (write path unreachable) |
| `code audit --offline --target` | Yes (CLI) | Yes | No — fixed declared rule set | None | Present and usable, blackboard-silent |
| `ProposalRepository`/`ProposalStateManager` | Direct Python/DB only | N/A | No | N/A | Present but no operator-facing surface |
| `ViolationRemediatorWorker` → `ProposalConsumerWorker` | Yes (worker cadence) | No — CORE-internal findings only | No — consumes pre-existing findings | **Yes, both directions** | Present and usable, but goal-blind |

**The one row with real blackboard reach (`ViolationRemediatorWorker`/`ProposalConsumerWorker`)
accepts no goal or target at all. Every row that accepts a goal has no blackboard reach. No row
has both.**

## Exact confirmed gap

No registered, reachable entry point in the pinned trees — nor in current HEAD, which is identical
to the Trial 1 pin on every file discussed above — combines all of: (a) an explicit, per-invocation
external target; (b) genuine investigation/comprehension of that target prior to planning
(reconnaissance, not narrow regex-based single-file extraction); (c) execution through the governed
Proposal lifecycle or an equivalent blackboard-writing path; and (d) applicability beyond source
code. The closest real capability, `develop_from_goal` (items 1-2 above), supplies (partial)
planning and real governed execution but fails (a), (c), and (d) outright, and fails the
"investigation" half of (b) specifically (no `ReconnaissanceAgent` exists to supply it).

## Reconciliation of the earlier finding

**The original headline — "neither pin exposes a genuine interface that accepts a free-text goal
and autonomously investigates a subject repository, producing planned findings on the blackboard"
— survives, but the earlier trace was materially incomplete, not merely under-detailed.**
`POST /develop/goal` and `develop_from_goal()` were omitted entirely from the prior item-by-item
findings. They are not a hypothetical or disconnected path: they are registered, reachable via two
independent live surfaces (API and CLI) at both trial pins and at current HEAD, and they perform
real LLM-driven step planning and real governed file mutation. This should have been found and
was not. It is corrected here plainly, not minimized.

Tracing it in full does not overturn the conclusion, because it fails on different, more specific
grounds than "does not exist":

- **Existed at each runner pin:** yes, byte-identical at `27160a0a`, `b57423dc`, and HEAD.
- **Registered:** yes — API (`require_governor`) and CLI (`GOVERNOR_ONLY`, `dangerous=True`).
- **Can receive an external target:** no — process-bound only, same constraint as BYOR/Scout.
- **Creates its own investigation plan:** partially — genuine plan synthesis over a fixed
  38-action registry, but with no investigation/comprehension step over the subject at all
  (`reconnaissance_report` is always empty; `ReconnaissanceAgent` does not exist). Not "plan its
  own investigation" in Document A §A6 / Document B §B6's sense.
- **Uses the governed proposal lifecycle:** no — bypasses `ProposalRepository`/
  `ProposalStateManager`/`ProposalConsumerWorker` entirely, writing via direct `ActionExecutor`
  calls under a per-invocation governor gate instead.
- **Records all relevant outcomes on the blackboard:** no — confirmed empirically, zero
  blackboard involvement anywhere in the call chain, including the write executor itself.
- **Satisfies any material part of the Trial 0 or Trial 1 interface:** partially. It is the
  single closest capability to genuine autonomous planning found anywhere in the pinned trees, and
  a real, working, governed execution engine — but it satisfies neither trial's blackboard-
  reconstructability requirement (Trial 0 I-4 / Trial 1 C5, both load-bearing and, for C5,
  mandatory per B9), neither trial's external-target requirement, nor the "investigate an
  unfamiliar corpus" comprehension requirement (C1/C2).

`core-admin dev strategic-audit` (item 2) was also omitted from the earlier trace. It does not
change the reconciliation above — it is the most genuinely self-directed investigation capability
found, but is structurally incapable of addressing an external target at all, which the earlier
report's external-repository-route addendum did not need to consider and does not overturn.

## Mapping to Trial 0 and Trial 1 requirements

**Trial 0 (ADR-159 D5):** still, and for the same structural reason stated in the prior addendum,
largely not applicable — Trial 0's subject is frozen CORE itself, which needs no external-target
binding. `develop_from_goal`/`strategic-audit` could in principle operate directly on CORE's own
checkout without any external-target mechanism — but neither produces a blackboard record (I-4
unsupported, confirmed directly) and neither performs the open-ended, eight-row-capable discovery
process D5's recall figure assumes (both are goal-driven or self-audit-driven, not free investigation).

**Trial 1 (ADR-159 D6):**

| Criterion | Mapping | Basis |
|---|---|---|
| C1 Comprehension | Unsupported | No traced path reads/comprehends an external, unfamiliar corpus before acting; `develop_from_goal` cannot even accept one. |
| C2 Independent planning | Partially supported, in isolation from C1 | `PlannerAgent` genuinely plans its own steps from a goal — but not from investigating the subject, and not for an external target at all. |
| C3 Boundary respect | Supported, narrowly | Real, attributable refusals exist (`require_governor`, `StagingContaminationError`, the `.intent/`-write hard invariant) — not exercised as Document B's specific C3 probes. |
| C4 Honest unavailability (mandatory) | Undetermined | Nothing traced here was executed; cannot be assessed from source alone. |
| C5 Reconstructability (mandatory) | Unsupported | Confirmed directly: zero blackboard involvement in `develop_from_goal` or `strategic-audit`, consistent with every other path traced in this and the prior unit. |
| C6 Marginal value (arms) | Not applicable | No traced path has an arm structure or is invoked comparably across arms. |

This mapping is consistent with, and extends, the prior unit's addendum — C5 remains the one
criterion no traced path in either document satisfies, and it is mandatory.

## Reusable existing components

- `PlannerAgent` / `IterativeCoderAgent` / `CoderAgent` — real LLM plan synthesis and governed,
  budget-capped generation, already production-live.
- `ActionExecutor` and the 38-action registry — a real, governed mutation surface with impact
  classification, already the single sanctioned write path across the codebase.
- `WorkflowOrchestrator` / `PhaseRegistry` / `.intent/workflows/` + `.intent/phases/` — a working,
  declarative, constitutionally-governed phase-composition engine; exactly the kind of substrate a
  mission runner would sit on rather than duplicate.
- `SystemContextGatherer`'s six-dimension read pattern — an existing template for "read broadly,
  then reason," currently scoped to CORE's own state only.
- The `Worker` base class and `post_finding`/`post_report`/`post_heartbeat` — the existing,
  constitutionally-correct blackboard-writing mechanism, simply never invoked from any
  goal-accepting path traced here.
- `external_target_binding.py` (Units A/B) — the existing, governor-authorized, already-proven
  (Units D/E) mechanism for binding a CORE process to an external repository, currently
  process-level rather than per-invocation.

## Genuinely missing primitives

- A **reconnaissance/comprehension step** that reads an unfamiliar (potentially external) corpus
  and produces its own investigation plan before code-level planning begins.
  `ReconnaissanceAgent` is named in a docstring but implemented nowhere in `src/` at any of the
  three refs checked.
- A **per-invocation external-target parameter** on any goal- or campaign-accepting entry point —
  every such path is bound to the process-level `REPO_PATH`/`MIND`, confirmed consistently across
  BYOR, Scout, `develop_from_goal`, and `strategic-audit`.
- A **blackboard-writing bridge** for any goal-accepting path — none of `develop_from_goal`,
  `strategic-audit`, BYOR, Scout, or `code audit --offline` posts a single blackboard entry; only
  `Worker` subclasses do, and no `Worker` sits in any of these chains.
- A **document-corpus-shaped workflow or action set** — `_VALID_WORKFLOW_TYPES` and the 38
  registered atomic actions are code-shaped; `document.gap_analysis` is the one action that
  touches documents, but it is a single narrow action, not an investigative framework, and nothing
  routes a free-text goal into it.
- A **governed evidence-export/bundle mechanism** matching Document A §A9/§A13 / Document B
  §B7/§B12's sealed-bundle shape — `BlackboardQueryService` reads one subject's latest report;
  nothing assembles a full trial-shaped bundle (blackboard + refusals + write inventory + egress
  log) even where blackboard rows exist.

## Architectural options (no option chosen)

1. **Add a per-invocation external-target parameter** to `develop_from_goal`/`/develop/goal`,
   reusing Units A/B's binding mechanism per-call rather than per-process.
2. **Build a genuine `ReconnaissanceAgent`** that reads and comprehends a subject before
   `PlannerAgent` runs, feeding a real `reconnaissance_report` instead of the permanently-empty
   default.
3. **Add a blackboard-writing bridge** to the existing goal-driven chain — either run the relevant
   call inside a `Worker`, or extend the existing "services and atomic actions route through
   `self.post_finding()`" pattern into this specific chain.
4. **Extend `StrategicAuditor`** to accept an external target instead of only CORE's own state,
   and extend its LLM-reasoning step to synthesize an investigation plan rather than only a
   remediation campaign.
5. **Build a new, purpose-specific mission-runner component** that composes the existing pieces —
   `PlannerAgent`-style planning, `ActionExecutor`-style governed execution, `Worker`-style
   blackboard posting, `external_target_binding`-style target scoping — rather than extending any
   one existing path.

## ADR-159 D4 consequences of each option

D4's line: acceptable adaptation = target `.intent/`, GRC catalogs, domain profiles,
configuration/resource bindings; thesis-negative = new `src/` modules, new check/rule classes,
target-specific branches, schema changes.

| Option | D4 classification | Why |
|---|---|---|
| 1. Per-call target param | Thesis-negative | Changes `develop_from_goal`'s signature and the API/CLI contract — a `src/` change to existing production code. |
| 2. `ReconnaissanceAgent` | Thesis-negative | A wholly new `src/` module/component. |
| 3. Blackboard bridge | Thesis-negative | New `src/` wiring into an existing chain, even where it reuses the existing `Worker` base class. |
| 4. Extend `StrategicAuditor` | Thesis-negative | New `src/` capability on an existing class, beyond its current self-only scope. |
| 5. New mission-runner component | Thesis-negative | By construction, a new `src/` module. |

**All five options are thesis-negative under D4 as currently worded.** This is itself a finding
for the Governor: on the evidence traced here, satisfying Documents A/B's assumed interface at all
appears to require `src/` production changes under every option considered — none of the existing
paths can be reached by target-`.intent/`/config/domain-profile adaptation alone. Whether that is
acceptable, and under what review process, is not decided here.

## Smallest credible vertical slice — target-neutral

Given D4's constraint applies regardless of which option above is chosen, the smallest slice that
would let a future trial-relevant capability be evaluated without committing to a full mission
runner:

1. One new entry point (CLI or API) accepting exactly a target binding (reusing Units A/B's
   `external_target_binding` mechanism as-is, not inventing a new one) plus a free-text goal
   string.
2. Routes to the **existing** `WorkflowOrchestrator`/`PhaseRegistry` composition, reusing
   `InterpretPhase`/`ParsePhase`/`LoadPhase`/`RuntimePhase`/`AuditPhase`/`ExecutionPhase` exactly as
   they are today — no new phase logic.
3. Adds exactly one new integration point: the orchestrator (or a thin wrapper around it) posts
   start/plan/outcome/refusal records to the blackboard via the **existing**
   `Worker.post_finding`/`post_report` pattern — reusing the existing mechanism, not inventing a
   new persistence layer.
4. No new atomic actions, no new workflow types, no document-corpus-specific logic.
5. **No ITAM-specific paths, rules, document knowledge, or benchmark information of any kind** —
   this slice is defined entirely in terms of CORE's own existing components and mechanisms.
6. Deliberately does **not** add investigation/comprehension intelligence — `ReconnaissanceAgent`
   (Option 2) stays out of scope for this slice. The slice's planning step remains exactly as
   narrow as `PlannerAgent` is today. Whether that narrowness is acceptable for a real trial is a
   separate, later Governor decision, not resolved by scoping the slice this way.

This slice stays as close to "acceptable adaptation" territory as the evidence in this document
allows, by reusing existing binding/orchestration/blackboard mechanisms rather than building new
ones — but it still touches `src/` (the new entry point itself, and the blackboard-posting
wire-up), so it too is D4-relevant. That is disclosed here, not minimized.

## Governor decisions required before implementation

1. Whether any `src/` production change is acceptable under D4 for this purpose at all, given
   every option traced here is thesis-negative as D4 is currently worded — or whether D4 itself
   needs a Governor-authored amendment or carve-out first.
2. Which architectural option (if any) to pursue — including the smallest slice above, or none of
   the above.
3. Whether Trial 0/Trial 1 should instead proceed against a deliberately narrower interface than
   Documents A/B assume (amending the blind-authored procedures) rather than building toward their
   assumption — a live alternative this reconnaissance surfaces but does not resolve or recommend.
4. Whether `develop_from_goal`/`strategic-audit`'s existing, real, governed capability
   (goal → plan → execute, no blackboard, no external target) should be exercised as-is for some
   evaluation purpose distinct from Trial 0/1, given it already works today, independent of any
   decision on the above.
5. Whether closing the blackboard gap (Option 3) should be pursued independently of the harder
   target/investigation gaps, since it is the one gap common to every goal-accepting path traced
   in this document and the prior one, and is not entangled with the investigation-planning
   question.

No implementation begins from this document. No option above is recommended over another.
