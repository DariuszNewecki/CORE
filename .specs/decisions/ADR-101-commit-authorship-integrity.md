---
kind: adr
id: ADR-101
title: 'ADR-101 — Commit authorship integrity: every commit''s diff contains only
  work its author produced'
status: accepted
---

<!-- path: .specs/decisions/ADR-101-commit-authorship-integrity.md -->

# ADR-101 — Commit authorship integrity: every commit's diff contains only work its author produced

**Date:** 2026-06-09
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-09 — drafted under explicit "write to disk, suppress the old faulty ADR" authorization at the close of the #594 reframe discussion. The discussion started as "fix the content-scope leak in the autonomous commit step" and inverted under governor pushback into "what are we actually solving — is the co-tenancy assumption itself faulty?" The governor articulated the principle: *CORE should be committing only its own work. Actually that counts for me too AND for you too. Actually that counts ALWAYS.* This ADR pins it.)
**Closes:** #594 (autonomous remediator absorbed unrelated working-tree edit under fix.format attribution — ADR-021 D3 regression of #124)
**Supersedes:** ADR-021 D3 (commit-set choice), ADR-021 D5 (pre-claim collision check, retired as vestigial), ADR-021 D2/D4 (rollback target — see D3 below)
**Reaffirms and generalizes:** ADR-071 D1 (action diff coherence as constitutional requirement, scoped there to atomic actions with WRITE impact)
**Related:**
- ADR-021 (the superseded artifact; its D1 `commit_paths` / `restore_paths` primitives survive and are reused)
- ADR-071 (hermetic worktree sandbox — the structural mechanism that makes D1 of this ADR enforceable for the daemon)
- ADR-014 (development-phase priority: loop liveness > productivity > quality — the cost reasoning that motivated ADR-021 D5's `intersection_only` mode; this ADR revisits it)
- ADR-026 (proposal.scope.files non-emptiness validation — independent of this ADR; preserved)
- ADR-097 (unified FileHandler.write channel — sandbox propagation routes here)
- #124 (April 2026 incident — first surfacing; closed by ADR-021, regressed)
- #594 (June 2026 incident — second surfacing; closed by this ADR)
- Memory: `[[feedback_two_surface_requires_two_structures]]` — *path scope* and *production scope* are two surfaces that ADR-021 unified into one (`scope.files`). The unification was the bug.

---

## Context

### What we kept calling "the autonomous git problem"

Twice in two months an autonomous proposal has committed bytes its action did not author:

- **April 2026 — #124 / commit `c8b51ca5`.** `fix.format` commit message described a format-only fix; the actual diff swept four architect-authored source files. Closed 2026-05-02 by ADR-021.
- **June 2026 — #594 / commit `e7a591be`.** `fix.format` proposal scoped to one file (`shadow_materializer.py`); the action produced zero sandbox changes; `commit_paths(["shadow_materializer.py"])` staged the architect's uncommitted symlink refactor from the working tree and landed it under the proposal's attribution. HEAD was briefly broken (referenced a method that only existed in the architect's other uncommitted file) and required a corrective human commit minutes later.

Each time, the remediating ADR closed the visible symptom and left an architectural assumption in place. ADR-021 closed the success-path `git add -A` and the failure-path `checkout -- .`; ADR-071 added a hermetic worktree sandbox so action *execution* could not contaminate the main tree. Each closure was internally consistent, met its acceptance criterion, and didn't close the class.

What kept slipping through: **the unstated assumption that path scope (which files the action is allowed to touch) and production scope (which bytes the action actually wrote) are the same set.** They are not. ADR-021 D3 chose path scope as the commit set. ADR-071 D2.2 wired a hermetic sandbox but explicitly preserved that choice — D2.2's body states: *"ADR-021's scope-binding in `commit_proposal_changes` is unchanged — still calls `commit_paths(scope_files ∪ files_produced)` against the main tree. The worktree changes what content is in those paths; the existing code bounds which paths get staged."*

That preservation is the gap. For an action that produces *non-empty* sandbox changes, ADR-071 D2.2's propagation step overwrites the main tree's bytes for those paths with the sandbox's bytes, the conflict check catches concurrent governor edits on those same paths, and the assumption holds. For an action that produces *empty* sandbox changes — an idempotent `fix.format` against an already-formatted file, a `fix.ids` against fully-tagged source — `propagate_changes` returns at its empty-target early exit, the conflict check never runs, and `commit_paths` against the main tree stages whatever bytes the architect happened to have in the working copy of the scope path. That is `e7a591be`.

### ADR-071 D1 already named the property

ADR-071 D1 reads:

> *For every atomic action bearing `ActionImpact.WRITE_CODE` or `ActionImpact.WRITE_METADATA`, the diff committed under the proposal's attribution MUST contain only content the action was authorized to produce. A commit containing content from any other source (concurrent human edit, parallel worker, editor auto-save) is a constitutional violation regardless of whether scope-binding was respected.*

That is the right property, scoped narrowly to autonomous WRITE-impact actions. The principle is correct as far as it reaches. What `e7a591be` and the reframe discussion exposed is that the property is not action-shaped — it is **committer-shaped**, and it holds for *every* author who attaches a name to a diff: the architect, the daemon, a future AI agent, a contributor applying someone else's patch. Path scope is a permission concept (what an actor may touch); authorship is a production concept (what an actor actually wrote). They are two surfaces and must be tracked as two structures, not unified.

### Why the framings split

Three coherent ways to respond to #594 surfaced in discussion:

1. **Patch the commit-set arithmetic in `commit_proposal_changes`.** Drop `scope_files` from the union; commit only the production set. Local code change; co-tenancy remains.
2. **Retire co-tenancy.** Promote `autonomy_dirty_tree.yaml` from `intersection_only` to `any_dirty` permanently (already in force as the #594 mitigation). The daemon yields whenever the architect has unsaved work; commit-set leak becomes unreachable.
3. **Daemon commits in its own hermetic space.** Sandbox commits never touch the main tree as a working copy at all; merging is an explicit human act.

Each closes #594. None of them, alone, states the underlying property — they are mechanisms. The principle below states the property; the decisions then pick the mechanism mix that enforces it.

---

## Decisions

### D1 — The principle: commit authorship integrity (constitutional)

**Every commit attributes a diff to an author. The diff MUST contain only bytes that author produced.** This holds for:

- The human architect committing manually.
- Claude Code (and any other AI agent) committing on behalf of a session.
- Autonomous CORE components (`ProposalExecutor` and any future autonomous writer) committing via the action loop.
- Any future actor that authenticates to git and creates a commit object in this repository.

"Bytes that author produced" is defined as: bytes the actor either authored directly (typed, generated, transformed via a tool the actor invoked under its own identity) or explicitly accepted authorship of (e.g., applying a contributor's patch under the contributor's name; co-authorship via trailers preserves the chain). The actor's pre-commit tooling (formatter hooks, linters the actor invoked) counts as the actor's work. A second actor's concurrent edits in the working tree do *not* count, regardless of whether path-shaped permissions would have allowed the actor to write those paths.

A commit whose diff contains bytes from a different actor than the recorded author is a **constitutional violation** — independent of whether path scope, intersection checks, or any other path-shaped guard was respected. Path scope is a permission boundary; this principle is a production boundary. The two must be tracked separately.

This generalizes ADR-071 D1 from "atomic actions with WRITE impact" to "every committer, every commit, always." ADR-071 D1 remains in force as the autonomous-action specialization of this principle.

### D2 — Commit set is derived from the production set, not the permission set

`proposal_execution_pipeline.commit_proposal_changes` MUST build `paths_to_commit` from the action's actual production, not from `proposal.scope.files`. The production set is the union of:

- `sandbox_target_paths` — paths the action mutated inside the hermetic worktree per ADR-071 D2.2, as observed by `SandboxLifecycle.propagate_changes` via the sandbox's `status_porcelain`.
- `files_produced` — paths the action explicitly declared in `ActionResult.data['files_produced']`, for the case where the action writes files outside the sandbox (the `fix.modularity` pattern, issue #297).

`proposal.scope.files` ceases to participate in the commit-set calculation. It remains a permission boundary: actions remain forbidden from writing outside it, and the rollback path (D3 below) still uses it. It just stops being treated as a production postcondition.

**Implementation contract:**

- `SandboxLifecycle.propagate_changes` returns its `target_paths` set to the caller. `ActionExecutor` stamps it into the returned `ActionResult` as `data['_sandbox_target_paths']` (underscore-prefixed to mark it as runtime-injected, not declared by the action).
- For non-sandboxed code paths (CLI direct invocation, `write=False` dry-runs), `_sandbox_target_paths` is absent and the commit step uses `files_produced` alone.
- `commit_proposal_changes` computes `paths_to_commit = sandbox_target_paths_union ∪ files_produced_union`. Empty result raises the `ValueError` from `git_service.commit_paths`, surfacing as a logged "proposal completed, no commit emitted" — the correct outcome for an idempotent action against already-correct input. The proposal row is marked completed; consequence-log recording proceeds with `changed_files=[]`; no commit object is created.

### D3 — Rollback target is the action's touched set, not the permission scope

`proposal_execution_pipeline.rollback_proposal` MUST restore the same set that would have been committed on the success path — the sandbox-touched paths. Restoring `scope.files` (ADR-021 D2/D4 behavior) clobbers concurrent architect edits on scope paths the action did not modify, which is the symmetric violation of D1: the rollback "speaks for" bytes the action did not author.

**Implementation contract:** rollback receives the same `_sandbox_target_paths` snapshot the commit path would have used. If the failure occurred before propagation completed, the snapshot is `target_paths` as known at the moment of failure; if the failure occurred during propagation itself (the loud-failure conflict-check raise), no propagation has reached the main tree and no rollback is required.

### D4 — ADR-021 D5 pre-claim check and `autonomy_dirty_tree.yaml` modes are retired

Under D2's production-set commit calculation, content scope is enforced by construction: any byte staged for commit comes from the sandbox, period. The pre-claim collision check (ADR-021 D5) was a TOCTOU-shaped path-scope guard whose only purpose was reducing the size of the leak window that D2 now structurally closes. It contributed no remaining safety property and is retired.

The `autonomy_dirty_tree.yaml` policy file and its loader (`shared.infrastructure.intent.autonomy_dirty_tree`) are retired alongside the check. `ProposalExecutor._check_scope_collision` is removed.

**Interim posture:** until D2 is implemented and verified in code, `autonomy_dirty_tree.yaml` remains at `mode: any_dirty` (live since 2026-06-09 per the #594 mitigation). The mitigation is the production-grade safety net during the implementation window. D4's retirement of the file happens with the implementation commit that lands D2, not with this ADR's acceptance.

### D5 — `intersection_only` mode is not "post-stabilization" anything

ADR-021 D6 framed `any_dirty` as a future posture for "after CORE matures past the development phase." That framing presumed `intersection_only` was the correct development-phase posture and `any_dirty` was a stricter graduation. Two incidents establish that `intersection_only` was never safe under the path-shaped commit set it was built on. The framing is reversed: under D2's production-set commit, mode selection becomes a *liveness* policy question (does the daemon run during architect sessions?), not a *safety* policy question. Safety is constitutional and lives in D1; no YAML knob can weaken it.

After D2 lands, whether the daemon yields on a dirty tree is a separate decision answerable by ADR-014's liveness criteria. It is not part of D1's authorship-integrity guarantee.

### D6 — `commit_authorship_integrity` constitutional rule

A new rule under `.intent/rules/governance/` makes D1 enforceable as a constitutional invariant rather than ADR text alone. The rule's exact name, schema, and check mechanism are deferred to its authoring issue (filed under "Implementation" below) because authoring a constitutional rule requires per-file governor confirmation per CLAUDE.md, and the right mechanism (post-commit audit hook? pre-push gate? CI verification of `git log --format` against a per-author production-claim ledger?) needs separate design.

What this ADR commits to: the rule exists, sits in `.intent/rules/governance/`, and references this ADR as its grounding paper.

### D7 — The principle applies to humans and AI agents too

The decisions above are scoped to the autonomous-component side because that is where the structural mechanism lives (the sandbox + commit pipeline). The principle in D1 binds humans and AI agents symmetrically; the *enforcement* for those actors is behavioral, not mechanical:

- **Human architect:** standard git discipline (stage specific files, never `git add -A` when other authors' WIP is in tree, never `git commit --amend` over work that wasn't yours, never `git checkout .` while concurrent edits exist). This is largely how the architect already works; D7 just names it as constitutional, not stylistic.
- **Claude Code (and any future AI agent):** the existing `CLAUDE.md` guidance ("stage specific files, not git add -A", "never run destructive git commands unless explicitly requested", "create new commits rather than amending") is the operational shape of D1. A near-term `CLAUDE.md` amendment will re-anchor those rules under D1 instead of presenting them as standalone safety advice. Co-authorship trailers (`Co-Authored-By:`) remain the mechanism by which an AI agent and a human jointly claim authorship of a commit; the trailer is the explicit consent that makes co-authorship not a violation of D1.

No code change is required for D7. The amendment to `CLAUDE.md` happens in a separate confirmed turn.

---

## Consequences

**Lands as part of this ADR's implementation change-set:**

- `proposal_execution_pipeline.commit_proposal_changes` rewritten to build `paths_to_commit` from `_sandbox_target_paths ∪ files_produced`, with `scope.files` dropped from the union.
- `proposal_execution_pipeline.rollback_proposal` rewritten to restore the touched set, not `scope.files`.
- `SandboxLifecycle.propagate_changes` returns `target_paths`; `ActionExecutor` stamps it onto the `ActionResult.data` under the `_sandbox_target_paths` key.
- `ProposalExecutor._check_scope_collision` removed; the pre-claim check call site (line 187) deleted; the import of `load_autonomy_dirty_tree_policy` removed.
- `.intent/enforcement/config/autonomy_dirty_tree.yaml` removed.
- `shared.infrastructure.intent.autonomy_dirty_tree` loader module removed.
- Tests under `tests/will/autonomy/` updated: the pre-claim collision tests retire, the commit-set tests change to assert production-set behavior, the existing ADR-071 D2.2 isolation suite remains unchanged (its conflict-check semantics are unaffected).

**Filed as separate follow-up issues (not in this change-set):**

- Implement the `governance.commit_authorship_integrity` rule (D6). Owner: filed alongside this ADR's acceptance.
- Amend `CLAUDE.md` to anchor the existing git-discipline rules under D1 (D7). Owner: filed alongside.
- Audit non-autonomous `GitService` callers (`add_all`, `commit`, `_run_command`) for D1 conformance — this was already explicitly out of scope for ADR-021 and remains so; D1's universal binding gives it grounding for prioritization.

**Positive:**

- The bug class behind #124 and #594 closes by construction, not by guard-stacking. There is no path-shaped predicate that has to stay true; the commit set is derived from the production set, period.
- The interim `any_dirty` mitigation becomes unnecessary and is removed. Liveness during architect sessions is restored to a policy decision rather than a safety decision.
- The principle is stated once, in committer-universal language, rather than as three differently-scoped action-side guarantees scattered across ADR-021, ADR-071, and `CLAUDE.md`.
- Misleading-attribution risk goes to zero for autonomous commits: a proposal that produces no changes produces no commit, which is the honest outcome.

**Negative / accepted costs:**

- Some idempotent autonomous proposals that previously emitted no-op commits will now mark completed without a commit at all. This is arguably more honest (no commit ↔ no production) but changes the consequence-log shape for those proposals: `changed_files=[]` rather than `changed_files=[scope_file]`. Downstream readers of the consequence log that joined on `changed_files` non-emptiness need to handle the empty case explicitly.
- The `autonomy_dirty_tree.yaml` config knob disappears. Any operational tooling or documentation that referenced `mode: intersection_only` / `mode: any_dirty` as a tunable becomes stale and needs updating. There are two such surfaces: `autonomy_dirty_tree.yaml` itself (deleted) and ADR-021 D5/D6 prose (preserved per closure-marker pattern; pointer added).
- ADR-071 D2.2's narrative text describing `commit_proposal_changes` as "unchanged" becomes superseded. The append-only Note pattern preserves it; D2.2's load-bearing mechanism (the hermetic sandbox + conflict check) is itself unchanged.

---

## Verification

D2 lands with a regression test that reproduces the #594 shape:

1. Construct a proposal with `scope.files = ["target.py"]` and action `fix.format` on `target.py`.
2. Pre-execution: `target.py` is already format-clean at the sandbox base SHA. Architect has uncommitted edits to `target.py` in the main tree that change its semantics non-trivially.
3. Run the proposal under `write=True`.
4. Assert: the proposal marks completed; `paths_to_commit` is empty; **no commit is created** on the main branch; `target.py` in the main tree retains the architect's edits byte-for-byte.

A second test covers the non-empty production case to confirm the happy path is unchanged:

1. Same proposal, but the action produces a one-line reformatting change inside the sandbox.
2. Architect's main-tree edits to `target.py` are absent or disjoint.
3. Assert: the proposal commits, the commit's diff is the one-line sandbox change, the proposal's attribution names `fix.format`.

A third test covers the rollback symmetry (D3):

1. Proposal with multi-action sequence; first action mutates `a.py` in sandbox, second action fails.
2. Architect has uncommitted edits to `b.py` (which is also in `scope.files` but no action touched it).
3. Assert: rollback restores `a.py` to its pre-execution sandbox state; `b.py` retains the architect's edits.

A fourth test covers D4 retirement:

1. With `autonomy_dirty_tree.yaml` and `_check_scope_collision` deleted, a proposal with `scope.files = ["x.py"]` executes cleanly even when `git status --porcelain` shows `x.py` as dirty in the main tree, **provided the production-set guard from D2 still produces a content-correct commit**.
2. Assert: no pre-claim yield; D2's production-set arithmetic does the actual safety work.

D1's universal binding is verified by D6's eventual rule once filed; until then D1 is enforced by ADR text + code review for D7's actors.

---

## Alternatives considered

**Framing A — keep ADR-021's path-shaped contract, fix the commit-set arithmetic in place.** Equivalent to D2 of this ADR without the principle restatement and without retiring D5. Rejected as a pure mechanism fix: it closes #594 but leaves the unstated assumption ("path scope == production scope") in the codebase, leaving the door open for a third regression along the same line. The point of an ADR is to surface and decide the assumption, not just patch the symptom.

**Framing B — promote `any_dirty` to permanent and call #594 closed.** Equivalent to D4 stopping at the interim posture without going on to D2. Rejected because `any_dirty` removes the trigger but not the bug: the path-shaped commit calculation is still there, latent behind a config knob. A future operator flipping back to `intersection_only` for liveness reasons re-opens the class. Safety properties that survive a config flip are not safety properties.

**Framing C — daemon commits to its own branch, governor merges.** Architecturally the cleanest separation — the daemon's authorship space and the architect's authorship space never share a working tree. Rejected for this ADR's scope as too large a behavioral change for a closure of #594 (introduces a merge surface, a branch-naming policy, a daemon-PR review flow, and tooling). Recorded here as a candidate future ADR: once D2 is stable and the production-set principle is enforced, the daemon-branch model becomes a natural next step rather than a forced restructuring. Not blocking #594's closure.

**Stash-based isolation.** Already rejected in ADR-071's alternatives (§ "Stash isolation"); the rejection stands.

**A coherence predicate framework declaring per-action production claims.** Already rejected in ADR-071 D2.3 in favor of the worktree sandbox; the rejection stands. D2 of this ADR makes the sandbox's `target_paths` the canonical production claim, which is what the predicate framework was trying to construct *outside* the execution model.

---

## Implementation

Tracked in a follow-up issue filed alongside this ADR's acceptance:

- **Issue title:** *ADR-101 D2/D3/D4 implementation — derive commit set from sandbox production, retire pre-claim collision check*
- **Scope:** the code changes itemized in the "Lands as part of this ADR's implementation change-set" bullet list above.
- **Closure condition:** four-test verification suite passes; `autonomy_dirty_tree.yaml` + loader + `_check_scope_collision` removed; ADR-021 closure marker references the implementation commit SHA.

A second follow-up issue covers D6 (authoring the constitutional rule). A third covers D7 (CLAUDE.md anchoring). Each is independent and unblocks separately from the D2 implementation.

---

## References

- ADR-021 — Scoped Autonomous Git Operations (superseded by D2/D3/D4 of this ADR; the `commit_paths` / `restore_paths` primitives survive)
- ADR-071 — Action Diff Coherence Enforcement (D1 reaffirmed and generalized by D1 of this ADR; D2.2 hermetic sandbox is the mechanism D2 of this ADR builds on)
- ADR-014 — Development-phase priority (the liveness/quality framing that motivated ADR-021 D5/D6; revisited by D5 of this ADR)
- ADR-026 — Proposal scope-files non-emptiness validation (independent; preserved)
- ADR-097 — Unified FileHandler.write channel (sandbox propagation routes through this; unaffected)
- Incident commits: `c8b51ca5` (April 2026, #124), `e7a591be` (June 2026, #594), `92782ef7` (the corrective human commit minutes after `e7a591be`)
- `src/will/autonomy/proposal_execution_pipeline.py:208-264` — `commit_proposal_changes` and `_files_produced_by` (the load-bearing site of D2)
- `src/will/autonomy/proposal_executor.py:64-130, 187` — `_check_scope_collision` and its call site (retired by D4)
- `src/body/atomic/sandbox_lifecycle.py:144-254` — `propagate_changes` (the target_paths source for D2)
- `.intent/enforcement/config/autonomy_dirty_tree.yaml` — retired by D4
- `shared/infrastructure/intent/autonomy_dirty_tree.py` — retired by D4
