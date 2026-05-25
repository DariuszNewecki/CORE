# Worktree Sandbox Implementation Plan — ADR-071 D2.2 / Issue #444

**Status:** Active — planned, both blockers cleared, ready to start Phase 1
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-05-25
**Tracks:** [#444](https://github.com/DariuszNewecki/CORE/issues/444) (worktree sandbox), [#451](https://github.com/DariuszNewecki/CORE/issues/451) (deletion-rule prerequisite)
**Authority:** ADR-071 D2.2 (architectural fix for the b11f4dba race class)

---

## What this closes

The two-developer one-working-tree collision class surfaced by incident `b11f4dba` / `f78b5c64` / `81631145` on 2026-05-24. ADR-021's scope-binding bounds *which files* the autonomous worker may touch; it does not bound *what content within those files* the worker commits. A file legitimately in scope at pre-claim can carry contamination from concurrent human edits, parallel workers, or editor auto-saves between pre-claim and commit.

The architectural fix is **hermetic action execution via `git worktree`**: the executor runs write-bearing actions against an isolated worktree at `pre_execution_sha`, captures the diff, applies it to the main working tree under ADR-021's existing scope-binding. CORE-worker never touches the main working tree during execution. The two-developer collision is architecturally impossible.

D2.1 (operational stop/start protocol) bridges until D2.2 lands.

---

## Key architectural insight

The issue body of #444 says "Action API accepts `working_dir` parameter; all write-bearing actions run against it." That framing is half a deprecation cycle behind the code.

Atomic actions **do not take `repo_root` as a parameter today** — they pull it from `core_context.git_service.repo_path` (see `src/body/atomic/build_tests_action.py:160`, `src/body/atomic/fix_actions.py:234, 296, 1026`).

So the cleanest implementation is **swap `core_context.git_service` for a sandbox-rooted scoped service** for the duration of `ActionExecutor.execute()`. One injection point, zero per-action signature surgery. ~20 atomic-action call sites need no edits.

---

## Resolved blockers

### Blocker 1 — `pre_execution_sha` threading (was Design Question #1)

**Status: Resolved 2026-05-25.**

`pre_execution_sha` is captured at the correct moment in `src/will/autonomy/proposal_executor.py:220` — AFTER `claim.proposal` succeeds, BEFORE the action loop begins. It is a first-class field on the `Proposal` Pydantic model (`src/will/autonomy/proposal.py:569`) and persisted to the consequence chain (`src/body/services/consequence_log_service.py:42`) per ADR-015.

It is **NOT** currently threaded into `ActionExecutor.execute()` — the call at `proposal_executor.py:264` passes only `action_id`, `write`, and `**params`.

**Phase 2 scope-expansion:** add `pre_execution_sha: str | None = None` parameter to `ActionExecutor.execute()`; pass it from `proposal_executor.py:264`. One parameter + one call-site change. CLI direct invocations leave `pre_execution_sha=None` and pass through (no sandbox; operational protocol D2.1 covers concurrent-human cases for those).

### Blocker 2 — Deletion-rule governance (was Reservation #2)

**Status: Filed as [#451](https://github.com/DariuszNewecki/CORE/issues/451), 2026-05-25.**

The copy-back step of the worktree sandbox does not propagate deletions. Encoding "atomic actions cannot delete files" as a constitutional rule (rather than an inline assumption) prevents silent drift the moment a delete-bearing action is added.

#451 specifies: rule `atomic_actions.no_file_deletion` (naming open) enforced at audit time via `ast_gate`, forbidding `os.remove` / `os.unlink` / `Path.unlink` / `shutil.rmtree` / `git rm` subprocess calls inside `@atomic_action` function bodies with `WRITE_CODE` or `WRITE_METADATA` impact. Future-proofing path: a hypothetical `ActionImpact.DELETE_CODE` tier with a separately-sandboxed apply step.

**Must land alongside #444 Phase 2/3, or immediately before.**

---

## Phased plan

### Phase 1 — Worktree primitive in `GitService` (~1 session)

Mechanically isolated. No callers, no behaviour change.

- Add `GitService.create_worktree(sha: str) -> ScopedGitService` — creates `/tmp/core-action-sandbox-<uuid>/`, checks out `sha`, returns a `GitService` rooted at the sandbox.
- Add `ScopedGitService.cleanup()` → `git worktree remove --force`.
- UUID per worktree so parallel actions cannot collide.
- Startup sweep: on daemon boot, `git worktree list | grep core-action-sandbox-` → remove orphans. Prevents disk leakage from crash-during-execute.
- Unit tests for the lifecycle in isolation: create / write inside / cleanup / re-create with same SHA.

**Closes when:** `pytest tests/shared/infrastructure/test_git_service_worktree.py` passes. Standalone PR — no integration with the executor yet.

### Phase 2 + Phase 3 — Executor sandboxing + race-reproducer test (single PR, ~1-2 sessions)

These must land together. Phase 2 without Phase 3 leaves the race-shape unverified.

**Phase 2 — Sandboxed execution in `ActionExecutor`:**

- In `src/body/atomic/executor.py:140` `execute()`, before step 5 (execute action):
  - Add parameter `pre_execution_sha: str | None = None`.
  - If `pre_execution_sha is not None` AND `definition.impact_level` ∈ {`WRITE_CODE`, `WRITE_METADATA`}: create scoped worktree at `pre_execution_sha`; build a scoped `CoreContext` whose `git_service` points at the sandbox; pass it to the action.
  - Else (CLI direct invocation, `READ_ONLY`, `SYNC`, etc.): pass-through, no sandbox.
- After action returns:
  - Enumerate changed files in the sandbox (`git status --porcelain` from the worktree path).
  - Copy each changed file back to the main tree at the same relative path. (File copy, not `git apply`; simpler, binary-safe, deterministic.)
  - Cleanup worktree.
- Thread `pre_execution_sha` through `proposal_executor.py:264` (the autonomous call site). CLI direct invocations leave it `None`.
- ADR-021 scope-binding in `src/will/autonomy/proposal_execution_pipeline.py:233` (`commit_proposal_changes`) is **unchanged** — still calls `commit_paths(scope_files ∪ files_produced)` against the main tree. The worktree changes *what content* is in those paths; the existing code bounds *which paths* get staged.

**Phase 3 — Race-reproducer unit test:**

- Test setup: clone the `b11f4dba` shape — concurrent governor edit to a scope file + autonomous fix on the same file.
- **Without sandbox:** worker commit contains governor's lines (the contamination).
- **With sandbox:** worker commit contains only the action's diff; governor's lines remain as uncommitted local changes on the main tree, or surface as a `commit_paths` failure if the governor's edit is on the same scope file — loud failure rather than silent contamination.
- Test lives at `tests/body/atomic/test_executor_worktree_isolation.py`.

**Closes when:**
- Phase 3 test passes; the historic race shape is provably impossible.
- Existing autonomous fix flows still pass.
- `executed_today` metric resumes normal cadence after the PR lands.
- No atomic action signature changed.
- #451's deletion rule is in place and audit shows zero violations.

### Phase 4 — Status flip + memory + close (~½ session)

Paperwork.

- Update ADR-071 D2.2 status: `deferred to future band` → `Implemented YYYY-MM-DD commit <sha>`.
- Comment on #444 with implementation commits, close.
- Update `feedback_autonomous_remediation_race.md` memory: the race class becomes "closed architecturally; D2.1 protocol is now belt-and-suspenders, not the only defence."
- ADR-021 D5 pre-claim `scope_collision` check **stays** as defence-in-depth per ADR-071 alternatives §2.

---

## Settled design decisions

1. **`pre_execution_sha` source:** proposal-time SHA captured at `proposal_executor.py:220`, threaded as parameter. NOT `git rev-parse HEAD` at sandbox-create time — that would be a TOCTOU shadow of the exact bug being fixed.

2. **`var/` runtime writes are NOT in sandbox scope.** `var/` is non-repo runtime state, not constitutional content. Only sandbox writes that touch repo-tracked paths. `FileHandler.write_runtime_text` calls pass through.

3. **Read-only and sync actions pass through.** `READ_ONLY` and `SYNC` impact tiers do not sandbox — no race window to close.

4. **CLI direct invocations pass through.** Sandbox is opt-in by `pre_execution_sha` parameter. CLI users are not racing themselves; operational protocol D2.1 handles concurrent-daemon cases.

5. **Concurrent action execution under `FlowExecutor`:** each step gets its own UUID-rooted worktree. Within one proposal, steps are sequential, so worktrees never run truly concurrent. Optional belt-and-suspenders: `asyncio.Lock()` around the copy-back phase if a parallel-flow case ever surfaces.

6. **No file deletions allowed in write-bearing atomic actions** (#451). Enforced via `ast_gate` audit rule. Future delete-bearing actions get a new `ActionImpact.DELETE_CODE` tier with a separately-spec'd apply step.

---

## Risks named

- **Disk space leakage on crash** — addressed by Phase 1 startup sweep.
- **Git config divergence between worktree and main** — worktrees share `.git` config but have own HEAD. Unlikely to matter for one-shot actions; flag if `commit_paths` behaves oddly.
- **Symlinks in copy-back step** — needs explicit handling. Add to Phase 1 unit tests.
- **Worktree creation cost** — ~50-150ms create + remove per write-bearing action. Acceptable; write-bearing actions are not high-frequency.

---

## PR sequencing

1. **PR 1: Phase 1.** GitService worktree primitive + unit tests. Standalone. No behaviour change to executor or any caller. Safe to merge in isolation.
2. **PR 2: #451's deletion rule.** Constitutional rule + audit check. Lands before or with PR 3.
3. **PR 3: Phase 2 + Phase 3 (combined).** Executor sandboxing + race-reproducer test. Must merge together — Phase 2 alone is unverified.
4. **PR 4 (or commit on main): Phase 4 paperwork.** ADR-071 status flip, #444 close, memory update.

---

## Verification checklist for "done"

- [ ] `pytest tests/shared/infrastructure/test_git_service_worktree.py` passes.
- [ ] `pytest tests/body/atomic/test_executor_worktree_isolation.py` passes — race-shape provably impossible.
- [ ] `core-admin code audit` reports zero violations of the new deletion rule across `src/body/atomic/`.
- [ ] Existing autonomous fix flows still pass end-to-end (`build.tests` flow, `fix.format`, `fix.modularity`).
- [ ] Daemon `executed_today` metric resumes normal cadence after PR 3 lands.
- [ ] ADR-071 D2.2 status updated.
- [ ] #444 closed with commit references.
- [ ] `feedback_autonomous_remediation_race.md` memory updated.

---

## References

- ADR-071 — Action Diff Coherence Enforcement (D2.2 is this plan's authority)
- ADR-021 — Scoped Autonomous Git Operations (scope-binding retained unchanged)
- ADR-015 — Consequence chain attribution (`pre_execution_sha` provenance)
- ADR-008 — `ActionImpact` governance (`WRITE_CODE` / `WRITE_METADATA` are the sandboxed tiers)
- ADR-066 — Unmapped-rules invariant (#451's new rule will need a `DELEGATE` entry)
- Issue #444 — implementation tracker
- Issue #451 — deletion-rule prerequisite
- Incident commits: `b11f4dba` (race), `f78b5c64` (governance hardening), `81631145` (audit-trail honesty correction)
- Source file references:
  - `src/will/autonomy/proposal_executor.py:200-268` — claim, pre-sha capture, action loop
  - `src/will/autonomy/proposal.py:569` — `pre_execution_sha` field on Proposal
  - `src/will/autonomy/proposal_execution_pipeline.py:233` — `commit_paths` scope-binding site (unchanged)
  - `src/body/atomic/executor.py:140` — `ActionExecutor.execute()` (Phase 2 modification point)
  - `src/shared/infrastructure/git_service.py:193` — `commit_paths` definition
