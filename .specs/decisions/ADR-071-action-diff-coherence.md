# ADR-071 — Action Diff Coherence Enforcement

**Date:** 2026-05-25
**Status:** Accepted (Revised 2026-05-25)
**Author:** Darek (Dariusz Newecki)
**Band:** E — Constitutional Completeness
**Closes:** Working-tree-race class surfaced by the b11f4dba / f78b5c64 / 81631145 incident
**Related:** ADR-021 (scoped autonomous git operations), ADR-069 (claim lifecycle lease semantics), ADR-070 (source–projection coherence)

---

## Context

On 2026-05-24 at 10:25:45 CEST, autonomous proposal
`46654f38-8f51-4217-8fe8-a37c6712d33e` committed `b11f4dba`. The
proposal's declared intent was `fix.format` on a single scope file
(`src/will/workers/violation_executor.py`) addressing a
`workflow.ruff_format_check` finding. The resulting commit contained
116 lines of substantive blast-bound enforcement code — the human
architect's in-progress hardening work, attributed to autonomous
`fix.format` remediation. The architect documented the incident in
commit `81631145` as an "audit-trail honesty correction."

The proposal had previously yielded five consecutive times on ADR-021
D5's pre-claim `scope_collision` check. On the sixth cycle, the
architect ran a `git stash` → commit governance files → `git stash pop`
sequence. The worker's pre-claim check fell into the brief clean-tree
window between stash and pop, observed an empty `git status --porcelain`,
and proceeded. Execution and `git add` of the scope file happened after
`git stash pop` had restored the unstaged 116 lines; `commit_paths`
stages working-tree-vs-HEAD for the declared paths, and those 116 lines
were now part of that diff.

The architect stopped the daemon at 10:28:11 to halt the race.

### Why ADR-021's promise was kept and why the gap is elsewhere

ADR-021 D2/D3 promised scope-bounded commits: `commit_proposal_changes`
stages only `proposal.scope.files ∪ files_produced`, never `git add -A`.
The b11f4dba commit was a single-file commit on the declared scope.
**Scope-binding worked. The race did not violate it.**

The gap is at a different layer. Scope-binding bounds **which files** the
autonomous worker may touch; it does not bound **what content within
those files** the worker may commit. A file legitimately in scope at
pre-claim can carry contamination from any source between pre-claim and
commit, and the executor had no mechanism to detect it.

The problem reduces to a two-developer, one-working-tree collision:
CORE-worker and the human architect both writing to the same git working
tree concurrently. ADR-021's pre-claim check is a snapshot guard at time
T; execution happens at T + ε with no isolation.

### Alternatives considered

1. **Working-tree lease.** Architect acquires a constitutional lock before
   any multi-step commit sequence; workers refuse to claim while held.
   Depends on architect discipline for every stash/commit dance. Does not
   address non-architect contamination sources. Rejected.

2. **Pre-commit re-check.** Run `_check_scope_collision` again immediately
   before `commit_paths`. TOCTOU-shaped — a stash dance during the recheck
   can still beat it. Reduces the window; does not close the class. Rejected
   as primary defence; retained as defence-in-depth (no code change needed;
   the check already exists).

3. **Stash isolation.** Worker stashes everything outside `scope.files`,
   runs action, commits, pops stash. Mutations in the shared working tree;
   stash/pop conflict risk with architect-side stash use; hidden state
   opaque to debug tooling. Rejected.

4. **Coherence predicate framework.** Post-execution, pre-commit content
   verification: assert that `working_tree_content == tool(git_show(pre_sha,
   path))`. Closes the class without changing the execution model. Adds a
   predicate declaration to every write-bearing action; requires corpus
   maintenance and async-aware verification. Evaluated but rejected — see D2.

5. **Worktree sandbox.** Executor creates a temporary `git worktree` at
   `pre_execution_sha`, runs the action in isolation, captures the diff,
   applies it to the main working tree under ADR-021's scope-binding. The
   two-developer collision is architecturally impossible: CORE-worker never
   touches the main working tree during execution. This is the established
   hermetic execution pattern used by Bazel, Buck2, and Nix. Selected as the
   correct architectural fix; see D2.

---

## Decisions

### D1 — Action diff coherence is a constitutional requirement

For every atomic action bearing `ActionImpact.WRITE_CODE` or
`ActionImpact.WRITE_METADATA`, the diff committed under the proposal's
attribution MUST contain only content the action was authorized to
produce. A commit containing content from any other source (concurrent
human edit, parallel worker, editor auto-save) is a constitutional
violation regardless of whether scope-binding was respected.

This decision establishes the property. D2 specifies how it is enforced.

### D2 — Two-phase enforcement: operational protocol now, worktree sandbox later

#### D2.1 — Immediate: operational stop/start protocol

The daemon is stopped before any architect coding session and restarted
after the session ends. This eliminates the two-developer collision by
construction for the period it is active.

This is discipline-dependent and accepted as a deliberate temporary
measure. Its limitation — it relies on the architect remembering the
protocol — is known and accepted. It is not the architectural answer;
it is the bridge.

**The daemon may restart immediately under this protocol.**

#### D2.2 — Architectural fix: worktree sandbox (deferred to future band)

The correct fix is hermetic action execution via `git worktree`:

```
git worktree add /tmp/core-action-sandbox <pre_execution_sha>
# action runs against sandbox path, not main working tree
# executor captures diff between sandbox output and pre_execution_sha
# applies diff to main working tree under ADR-021 scope-binding
git worktree remove /tmp/core-action-sandbox
```

The action never touches the main working tree. The commit content is
the sandbox diff — unambiguous, uncontaminatable, deterministic. ADR-021's
scope-binding applies at the staging step unchanged.

Implementation requires threading a `working_dir` parameter through the
action API and adding worktree lifecycle to the executor. This is a
one-time cost; no per-action declarations or corpus maintenance follow.
A GitHub issue tracks the implementation work.

#### D2.3 — Predicate framework rejected

The coherence predicate framework (CoherencePredicate,
ReproducibilityPredicate, StructuralPredicate, per-action declarations,
idempotence corpora, CLI gate) was evaluated and rejected. It solves
the right problem at the wrong layer — adding verification complexity
on top of an in-place execution model that the worktree sandbox
eliminates entirely. Every new write-bearing action would require
predicate authoring, corpus maintenance, and async-aware verification
in perpetuity. The worktree sandbox makes this overhead unnecessary.
GitHub issue #443 is closed.

---

## Consequences

**Positive:**
- Daemon restarts today. No code changes required.
- The race class is operationally closed pending the worktree sandbox.
- Zero predicate complexity introduced into the codebase.
- The worktree sandbox, when implemented, closes the class
  architecturally with no ongoing per-action cost.

**Negative:**
- Autonomous remediation is unavailable during architect coding sessions
  under D2.1. This is the known cost of the operational protocol.
- D2.1 is discipline-dependent. Failure to stop the daemon before a
  coding session re-opens the race window.
- D2.2 implementation requires changes to the action API and executor.
  Until it lands, D2.1 is the only defence.

---

## Verification

D2.1: Daemon starts cleanly after a coding session ends. No predicate
or coherence infrastructure required. Verified by daemon restart.

D2.2: Verified at implementation time. The b11f4dba race shape
reproduced in a unit test against the worktree executor confirms
contamination is impossible.

---

## References

- ADR-021 — Scoped Autonomous Git Operations: D2/D3 scope-binding
  retained unchanged; D5 pre-claim check retained as defence-in-depth.
- ADR-070 — Source–Projection Coherence: the (proposal, commit) pair
  joins the coherence inventory; enforcement is the worktree sandbox.
- Incident commits: b11f4dba (race), f78b5c64 (governance hardening),
  81631145 (audit-trail honesty correction).
- GitHub issue #443 — closed as superseded by D2.3.
- GitHub issue #444 — tracks D2.2 worktree sandbox implementation.

---

*Revised 2026-05-25: Original decisions (D1–D8 predicate framework)
replaced. The predicate framework was rejected in favour of an
operational stop/start protocol (immediate) and a worktree sandbox
(architectural). The incident context and gap analysis are preserved
unchanged as they remain the accurate historical record.*
