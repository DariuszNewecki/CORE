---
kind: adr
id: ADR-106
title: ADR-106 — Flow proposals execute in a hermetic worktree (sandboxing is per-execution, not per-action)
status: accepted
---

<!-- path: .specs/decisions/ADR-106-sandbox-flow-proposals.md -->

# ADR-106 — Flow proposals execute in a hermetic worktree (sandboxing is per-execution, not per-action)

**Date:** 2026-06-13
**Status:** Accepted — D1–D5 ratified by the governor on 2026-06-13 ("Approve and proceed"). Drafted under explicit "draft ADR first" authorization; the governor elected to anchor the extension in an ADR before implementation. Implementation landed as one governor-reviewed change-set the same session (`SandboxLifecycle.build_flow_execution_context`, the `proposal_executor` flow branch, and the `run_tests` repo-root threading that lets `test.sandbox_validate` execute inside the worktree — see D1).
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-13). Surfaced while implementing #629: the autonomous test-gen loop, once unblocked (ADR-008 risk-compute fix, commit `c7acb56f`), reformatted 26 unrelated test files and left failing generated tests in the working tree on every run. Root-cause recon traced all of it to one gap — flow proposals skip the sandbox that single-action proposals get.

**Grounding decisions:**
- **ADR-071 D2.2** — atomic actions sandbox their production in a hermetic `var/tmp/` git worktree checked out at the pre-execution SHA; mutations land inside the sandbox, propagate to the main tree only on success, and are discarded on failure. This ADR observes that D2.2 was wired **per single action** and never reached the flow-proposal path, and extends the same mechanism to cover it. The flow path is the uncovered case D2.2 always implied.
- **ADR-101 D2** — a commit's set derives from the action's *production* (what the sandbox observed modified), not the proposal's permission scope. Flows currently stamp no production set, so this derivation silently degrades to empty for flow proposals. Extending the sandbox restores the ADR-101 D2 guarantee for flows.
- **ADR-046 D1** — a flow's risk/impact is the max impact of its constituent steps. The flow-level sandbox gate (D5) reuses this resolution.

**Related:**
- #629 — the bug this ADR resolves (flow.build_tests reformatted the whole `tests/` tree; failing generated tests left on disk; no rollback). All three reported symptoms are downstream of the unsandboxed flow path.
- #630 — deferred follow-on: even sandboxed, `propagate_changes` copies *all* worktree-modified files back, so an unscoped `fix.format` still over-propagates on a *passing* run. Constraining the production set to the proposal's declared output is #630, explicitly out of scope here (D2 note).
- `src/will/autonomy/proposal_executor.py:181` — the flow branch that calls `FlowExecutor.execute()` without `pre_execution_sha`; the single site where sandboxing is skipped.
- `src/body/atomic/sandbox_lifecycle.py` — `SandboxLifecycle.build_execution_context` / `propagate_changes`; the per-action subsystem reused at flow granularity.
- `src/body/atomic/executor.py:283` — where single actions invoke the sandbox today.
- `src/will/autonomy/proposal_execution_pipeline.py` — `compute_production_set` (reads `_sandbox_target_paths`), `commit_proposal_changes`, the failure-rollback that restores the production set; all degrade to no-op for flows today.
- Memory `[[feedback_risk_compute_depends_on_executor_init]]` — the fix that unblocked the loop and exposed this gap.
- Memory `[[feedback_daemon_scoops_uncommitted]]` — the class of failure this closes for flows: autonomous execution writing the real tree outside its production boundary.

---

## Context

### The gap

`ProposalExecutor.execute` dispatches each proposal action by kind:

- **Single action** (`ref_kind == "action"`): threads `pre_execution_sha` into
  `ActionExecutor.execute`. When `write=True` and the action's impact is
  `WRITE_CODE`/`WRITE_METADATA`, `SandboxLifecycle` checks out a hermetic worktree at
  that SHA, repoints `git_service` + `file_handler` at it, runs the action there, and on
  success copies the modified/untracked files back to the main tree — stamping the observed
  set as `_sandbox_target_paths` (ADR-101 D2 production set). On failure the worktree is
  discarded and the main tree is untouched.

- **Flow** (`ref_kind == "flow"`): calls `FlowExecutor.execute(flow_id, write, **params)`
  with **no `pre_execution_sha`**. Every step runs `ActionExecutor.execute` with
  `pre_execution_sha=None`, so the sandbox gate short-circuits and each step mutates the
  **real working tree** directly. No production set is stamped; on failure nothing is rolled
  back.

This asymmetry is invisible until a flow proposal runs. It is why the 2026-06-10 single-action
`violation_remediator` proposals never polluted the tree, while the 2026-06-13 *flow*
`build.tests` proposals did.

### What it caused (#629)

A single `flow.build_tests` run for one source file:

1. **Reformatted 26 unrelated hand-written test files** — the `fix.format` step (path
   unset → whole repo) reformatted the real `tests/` tree.
2. **Left the generated test on disk after the gate rejected it** — `build.tests` wrote the
   file; `test.sandbox_validate` then failed (the test didn't pass); the flow halted; nothing
   rolled the write back.
3. Both survived only because the gate blocked the *commit* (`commit_proposal_changes` runs
   only on `all_ok`). HEAD never moved — but the working tree was polluted, and a *passing*
   run would have swept the 26 files into the commit (ADR-101 D2 breach).

### Why per-flow, not per-step

A flow's steps build on each other: `build.tests` writes the file, `fix.*` edit that same
file, `test.sandbox_validate` executes it. A per-step sandbox (each step its own worktree,
discarded after) would lose the generated file before the next step could see it. The flow
must run in **one** worktree shared across all steps — the unit of isolation is the flow
execution, not the individual action. This is the core insight: **sandboxing is a property of
a proposal's execution, not of a single atomic action.**

---

## Decision

### D1 — Flow proposals execute in one hermetic worktree (ratify)

When `ProposalExecutor` runs a flow-kind action with `write=True` and the flow qualifies under
the D5 gate, it builds a single `ScopedGitService` worktree at `pre_execution_sha` and a scoped
`CoreContext` (with `git_service` and `file_handler` repointed at the worktree), then runs the
**entire** `FlowExecutor.execute` against that scoped context. All steps share the one worktree
and see each other's writes. The worktree is cleaned up in a `finally` block.

Reuse — not reimplement — the `SandboxLifecycle` worktree-creation and copy-back primitives;
the flow path needs a flow-granularity entry point alongside the existing per-action one
(`build_execution_context` is keyed on a single `ActionDefinition` and cannot be called as-is
for a flow — see D5 for the gate it is replaced by).

**Implementation note — validation must run *inside* the worktree.** `test.sandbox_validate`
executes the generated test via `run_tests`, which was globally pinned to `settings.REPO_PATH`
(the main tree). In a sandboxed flow the generated test exists only in the worktree, so
`run_tests` gains an optional `repo_root` override and `test.sandbox_validate` receives the
scoped `core_context` and threads `git_service.repo_path` through — pytest then runs against the
worktree where the file actually is. Unsandboxed/direct callers leave `repo_root=None` and fall
back to `settings.REPO_PATH`, so the full-suite `test.execute` path is unchanged. This coupling
(a globally-pinned test runner) is non-obvious and is the one piece of D1 that is more than a
straight reuse of the per-action sandbox.

### D2 — Production set + commit/rollback derive from the flow sandbox (ratify)

On flow **success** (`FlowResult.ok`), `propagate_changes` copies the worktree's
modified/untracked files back to the main tree and returns the observed set. That set is stamped
onto the flow's `action_results` entry as `_sandbox_target_paths`, so the existing
`compute_production_set` → `commit_proposal_changes` derivation (ADR-101 D2) and the
existing production-set failure-rollback both light up for flows with no further change.

**Out of scope (→ #630):** until the production set is constrained to the proposal's declared
output, this stamped set is *everything the flow touched in the sandbox* — including any
`fix.*` churn. So a *passing* flow still over-propagates. Phase 1 (this ADR) delivers
failure-isolation + rollback, which covers 100% of the pollution observed in #629 (every run
failed). The success-path production-set constraint is #630 and ships separately.

### D3 — Failure discards the sandbox (ratify)

On flow **failure** (any required step fails, or an exception escapes), `propagate_changes` is
**not** called: the worktree is cleaned up and the main tree is left exactly as it was at
`pre_execution_sha`. This is the rollback. It supersedes today's behavior where a halted flow
left every write on disk. No reliance on `fix.*` self-cleanup or explicit `unlink`.

### D4 — Steps must not nested-sandbox (ratify)

Inside the flow, `FlowExecutor` constructs each step's `ActionExecutor` from the **scoped**
context and calls `execute(..., pre_execution_sha=None)`. The per-action sandbox gate
(`pre_execution_sha is None`) therefore returns the scoped context unchanged — steps mutate the
shared worktree directly, with no second-level worktree. The implementation MUST NOT thread
`pre_execution_sha` into individual steps; doing so would fork each step into its own throwaway
worktree and break the chain (D1's rationale). A regression test asserts a multi-step write
flow produces a single worktree and a non-empty production set.

### D5 — Flow sandbox gate = write ∧ (max step impact ∈ {WRITE_CODE, WRITE_METADATA}) (ratify)

A flow proposal is sandboxed when `write=True` **and** at least one constituent action
(transitively, through nested flows) declares impact `WRITE_CODE` or `WRITE_METADATA` — the same
impact set D2.2 gates single actions on, resolved over the flow per ADR-046 D1. A flow with no
write-bearing step (pure read/validate, or `WRITE_DATA`-only targeting external systems) is not
sandboxed, matching the per-action carve-out. `flow.build_tests` qualifies (`build.tests` =
WRITE_CODE).

### Corollary — fix.format formatter availability (re-homed to #630)

`fix.format` / `fix.imports` shell out via `run_poetry_command`; on the daemon `poetry` is not
on `PATH`, so `fix.format` fails (`"poetry command failed"`). It is `required=false`, so it does
not fail the flow, but it never formats. **Under this ADR the breakage is no longer a pollution
source** — the sandbox discards it on failure, and the success-path production set is bounded by
#630 — so it degrades to a quality nit (the generated file is not auto-formatted). Because the
`fix.*` steps are exactly what #630 reworks (scoping them to the generated file), the poetry-PATH
fix is re-homed there rather than bundled into this sandboxing change-set, keeping ADR-106's
change focused on D1–D5. Tracked in #630.

---

## Consequences

**Positive**
- Flow proposals gain the same hermetic isolation single actions have had since ADR-071 D2.2:
  failed runs leave the real tree untouched; ADR-101 D2 commit-set derivation works for flows.
- Closes #629's rollback + real-tree-pollution symptoms at the root, for *all* flows, not just
  `flow.build_tests`.
- The autonomous test-gen loop can re-open scope beyond one file (the `test_coverage.yaml`
  narrowing in `5c72cfef`) once this + #630 land.

**Negative / watch**
- A *passing* flow still over-propagates until #630 constrains the production set — this ADR
  does not claim to fix the success-path blast. The narrowed pilot scope (1 file) stays until
  #630 lands, so the window is closed operationally in the meantime.
- `propagate_changes`' conflict check refuses to propagate when the main tree is dirty on a
  target path (loud failure). For the autonomous daemon the tree should be committed; a governor
  with concurrent WIP on a sandbox target path will see a refused proposal rather than a clobber
  — the intended ADR-071 D2.2 safety, now also covering flows.
- Worktree creation cost (one per write-bearing flow proposal) is paid once per flow, same
  order as the per-action cost today.

**Verification**
- Regression test: a multi-step write flow (`flow.build_tests` shape) run with `write=True` (a)
  produces a non-empty `_sandbox_target_paths`, (b) leaves the main tree clean on a forced
  step-failure, (c) mutates only the worktree mid-flight.
- Post-deploy: a live `flow.build_tests` proposal that fails the `test.sandbox_validate` gate
  leaves `git status` clean (no reformatted tests, no leftover `test_generated.py`).
