<!-- path: .specs/decisions/ADR-021-scoped-autonomous-git-operations.md -->

# ADR-021 — Scoped autonomous git operations

**Status:** Accepted
**Date:** 2026-05-02
**Author:** Darek (Dariusz Newecki)
**Closes:** #167
**Supersedes:** nothing
**Related:** ADR-011 (workers own blackboard attribution), ADR-014 (development-phase priority: loop liveness > productivity > quality), ADR-019 (Edge 5 git-boundary attribution posture)

---

## Context

The autonomous remediation pipeline performs two repo-wide git operations
inside `ProposalExecutor` (`src/will/autonomy/proposal_executor.py`):

1. **On failure**, `execute()` calls
   `git_service._run_command(["checkout", "--", "."])`. This reverts every
   tracked file with working-tree modifications — not just the files declared
   in `proposal.scope.files`. Unrelated edits the architect has in flight
   are silently scrubbed. (#167.)
2. **On success**, `git_service.commit(...)` calls `add -A` before
   committing. This stages every change in the working tree, not just the
   proposal's scope. Unrelated architect edits get committed under an
   autonomous proposal's commit message and pushed to history. (Not
   surfaced in #167's body; identified during the investigation that
   produced this ADR.)
3. **`execute_batch()` has no rollback at all.** Failure path calls
   `mark_failed` and returns; the working tree retains the proposal's
   partial writes. Asymmetry with the single-execute path. (Sibling
   concern to #167; not previously tracked.)

Acceptance criterion in #167: *"A working tree with in-flight architectural
work co-exists safely with the daemon."* Scoping the rollback alone does
not meet that bar — the success-path `add -A` re-creates the same hazard
on a different surface.

The underlying policy question is *"what does the daemon do when the
architect has unstaged work?"*, which is currently undefined. This ADR
decides it.

**Phase context (per ADR-014):** CORE is in its development phase. Loop
liveness ranks above productivity, which ranks above quality. A policy that
halts autonomous remediation on any dirty working tree would zero out
liveness whenever the architect is editing — which is most of the time. A
policy that yields *only when the daemon's scope and the architect's scope
collide* preserves liveness while eliminating the data-loss hazard.

---

## Decisions

### D1 — Two new `GitService` primitives: `restore_paths` and `commit_paths`

`src/shared/infrastructure/git_service.py` gains two public methods:

- `restore_paths(paths: list[str]) -> None` — runs
  `git checkout -- {paths}` on the intersection of `paths` and the
  currently tracked set. Untracked entries in `paths` are silently skipped
  (consistent with checkout's pathspec semantics). Empty input is a no-op.
- `commit_paths(paths: list[str], message: str) -> None` — runs
  `git add {paths}` then `git commit -m {message}`, preserving the existing
  pre-commit-hook retry pattern from `commit()`. Empty input raises
  `ValueError`; an autonomous proposal that resolved to no files is a
  malformed proposal, not a commitable no-op.

These primitives are the constitutional surface for autonomous git
operations. Direct use of `_run_command` for git operations from outside
`GitService` is forbidden going forward (it was already a private-method
leak; D2 closes the only autonomous call site).

The existing `add_all()`, `add()`, and `commit()` methods retain for
non-autonomous callers (CLI tooling, manual sync). A separate sweep to
audit and migrate or retire those call sites is out of scope for this
ADR.

### D2 — `execute()` rollback uses `restore_paths(proposal.scope.files)`

The failure branch of `ProposalExecutor.execute()` replaces the
`_run_command(["checkout", "--", "."])` call with
`git_service.restore_paths(proposal.scope.files)`. The captured
`pre_execution_sha` is retained for the log line — but the misleading
"Rolled back working tree to pre-execution state (%s)" formatting is
amended to "Reverted scope files to pre-execution state (count=%d, sha=%s)"
to reflect what the operation actually does.

### D3 — Commit on success uses `commit_paths(proposal.scope.files, message)`

Both `execute()` and `execute_batch()` success branches replace
`git_service.commit(message)` with
`git_service.commit_paths(proposal.scope.files, message)`. The autonomous
daemon physically cannot stage paths outside the proposal's declared scope.

### D4 — Batch rollback symmetry

`execute_batch()` failure branch gains the same scoped rollback that
`execute()` has under D2. Per-proposal in the loop: on `not all_ok`, after
`mark_failed`, call `restore_paths(proposal.scope.files)` if
`pre_execution_sha is not None`. Behavior parity with `execute()`.

### D5 — Pre-execution scope-collision check (intersection-only)

`ProposalExecutor.execute()` and `execute_batch()` each gain a pre-flight
check, **before** the `claim.proposal` step. The placement matters: per
ADR-017 D2 the claim transition is forward-only — `mark_executing` was
removed from `ProposalStateManager` and there is no sanctioned `unclaim`
primitive. A check that runs after the claim would strand a yielded
proposal in `executing` with no path back to `approved`. Yielding
pre-claim avoids the need for an unclaim mechanism entirely.

The check sequence:

1. After loading the proposal and validating its `APPROVED` status, but
   before the `claim.proposal` action invocation: read
   `git_service.status_porcelain()` and parse the modified-path set.
2. Compute the intersection with `proposal.scope.files`.
3. **If the intersection is non-empty:** return a structured yield
   result without claiming and without modifying any files:
   ```
   {
     "ok": False,
     "yielded": True,
     "yield_reason": "scope_collision",
     "colliding_paths": [...],
     "proposal_id": ...,
   }
   ```
   The proposal stays in `approved` status and naturally re-queues on
   the next worker cycle. No state mutation, no rollback required.
4. **If the intersection is empty:** proceed normally — claim, then
   execute the action loop. The architect's dirty tree is disjoint from
   the proposal's scope and therefore safe.

The check applies `mode: intersection_only` from a new policy file:
`.intent/enforcement/config/autonomy_dirty_tree.yaml`. The loader mirrors
the ADR-005 `audit_verdict.py` pattern; it lives at
`src/shared/infrastructure/intent/autonomy_dirty_tree.py`.

Per ADR-011, the *worker* — not `ProposalExecutor` — posts the finding.
`ProposalConsumerWorker` inspects the yield result and, on
`yielded=True`, posts a `BlackboardEntry` with subject
`autonomy.yielded.scope_collision::{proposal_id}` and payload carrying
`colliding_paths`, `proposal_id`, and `yielded_at`. The finding is
informational, not a violation.

### D6 — Forward path to "any dirty halts" (full C, post-stabilization)

When CORE matures past its development phase, the policy in
`.intent/enforcement/config/autonomy_dirty_tree.yaml` flips from
`mode: intersection_only` to `mode: any_dirty`. The worker's check then
treats any non-empty `status_porcelain()` output as cause to yield. No
code change is required.

The transition itself is governance, not engineering: a future ADR
declares CORE has exited the development phase and amends the YAML.
ADR-014's revisit triggers ("measured hallucination rate, signal
contamination, deployment-phase change") are the same conditions that
qualify CORE for that transition.

---

## Consequences

**Lands in this change-set:**

- `GitService.restore_paths` and `GitService.commit_paths` (D1).
- Single-execute rollback scoped (D2); single-execute commit scoped (D3).
- Batch-execute rollback added and scoped (D4).
- Batch-execute commit scoped (D3 applied symmetrically).
- Scope-collision check in both execute paths (D5, executor side).
- `.intent/enforcement/config/autonomy_dirty_tree.yaml` with
  `mode: intersection_only` (D5, policy side).
- `src/shared/infrastructure/intent/autonomy_dirty_tree.py` loader (D5).
- `ProposalConsumerWorker` reads yield result and posts
  `autonomy.yielded.scope_collision::*` finding (D5, worker side).

**Not in scope:**

- Audit and migration of non-autonomous `git_service.commit()` /
  `add_all()` / `_run_command` callers. Tracked separately; #167 closure
  does not depend on it.
- Validation that `proposal.scope.files` is non-empty for executable
  proposals. Existing validation surface; this ADR assumes scope is
  populated for any proposal that reaches `execute()`. If empty scope is
  reaching execution, that is a separate validation bug.
- Behavior when an action writes to a path *outside* `proposal.scope.files`.
  Such a write is a contract violation between proposal and action and is
  not addressed here.

**Convergence implication:** the loop becomes safe to leave running
during architectural sessions, on the condition that the architect's
edits do not collide with paths the daemon is concurrently remediating.
In the current state — where audit findings concentrate on
`ModularitySplitter` and a small set of files — collisions will be rare.
G2 measurability improves accordingly.

---

## Alternatives considered

**Stance A only (scope rollback and commit; no dirty-tree check).**
Rejected. If the architect happens to have a working-tree edit on a path
the proposal's actions are also writing, the action's write overwrites
the architect's edit before any rollback could occur. Stance A handles
post-failure cleanup; D5 handles the pre-execution collision case that
Stance A alone cannot.

**Stance B only (halt on any dirty tree).** Rejected for development
phase. Per ADR-014, loop liveness must be observable for G2 to be
measurable. Stance B suspends the loop whenever the architect is
editing, which is the typical state. Reserved as the post-stabilization
policy via D6.

**Hardcode `mode: intersection_only` as a constant in the worker.**
Rejected. Per the standing principle "policy in `.intent/`, mechanism in
`src/`" (ADR-002), the threshold/mode is governance data, not
implementation. The transition from C-light to full C should be a YAML
edit, not a code change.

**Use `git stash` instead of `checkout --`.** Rejected. `git stash`
preserves work but introduces stash-stack management as a new failure
surface (stashes leak, conflict, accumulate). The architect's edits to
files outside proposal scope are protected by D2/D3 (they are not
touched at all); the architect's edits inside proposal scope are
protected by D5 (the proposal yields rather than running). No need for
stash semantics.
