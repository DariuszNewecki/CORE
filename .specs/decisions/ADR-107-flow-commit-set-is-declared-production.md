---
kind: adr
id: ADR-107
title: ADR-107 — A flow's commit set is its steps' declared production, not the sandbox worktree diff
status: accepted
---

<!-- path: .specs/decisions/ADR-107-flow-commit-set-is-declared-production.md -->

# ADR-107 — A flow's commit set is its steps' declared production, not the sandbox worktree diff

**Date:** 2026-06-13
**Governing paper:** `.specs/papers/CORE-Flow.md`
**Status:** Accepted — D1–D4 ratified by the governor on 2026-06-13 ("Approve ADR, commit it, then implement it"). Drafted under the governor's "start #630 → draft an ADR for your review, then implement" direction. Implementation lands as one governor-reviewed change-set.
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-13). The success-path half of #629, split out as #630 when ADR-106 landed the failure-path fix.

**Grounding decisions:**
- **ADR-106** — flow proposals now run in one hermetic worktree; on success `SandboxLifecycle.propagate_changes` copies the worktree's modified/untracked files back to the main tree and stamps them as the production set. ADR-106 explicitly deferred the *success-path* blast radius: an incidental `fix.format` that reformats the whole worktree tree would still propagate ~26 unrelated files alongside the one generated test. This ADR closes that.
- **ADR-101 D2** — a commit's set derives from the action's *production*, not the proposal's permission scope (`scope.files`). This ADR sharpens "production" for flows: it is what the steps *declared* they produced, not everything that incidentally changed in the sandbox. The 26 reformatted files are sandbox churn, not the proposal's product.
- **#297 / `fix.modularity`** — established the `files_produced` result key: an action explicitly declaring paths it authored (used because that fix writes new package files outside any pre-declared scope). `compute_production_set` already unions `files_produced` with `_sandbox_target_paths`. This ADR makes `files_produced` the *authoritative* signal for flows rather than one of two sources.

**Related:**
- #630 — the issue this resolves. Acceptance: a successful `flow.build_tests` run commits exactly the generated test file and nothing else.
- #629 / ADR-106 — the failure-path fix this completes.
- `src/body/atomic/sandbox_lifecycle.py` — `propagate_changes` (gains an allowlist).
- `src/will/autonomy/proposal_executor.py` — the flow branch (derives the allowlist from step results).
- `src/body/atomic/build_tests_action.py` — `build.tests` (declares `files_produced`).
- `src/will/autonomy/proposal_execution_pipeline.py` — `compute_production_set` (already reads `files_produced`).
- Memory `[[feedback_flow_proposals_skip_sandbox]]` — the ADR-106 lesson this builds on.
- Memory `[[feedback_universal_sink_beats_per_site]]` — the design instinct here: bound production once at the propagate sink, not by chasing every fixer's scope.

---

## Context

### Where ADR-106 left it

ADR-106 made flow proposals sandbox in a worktree, which fixed the *failure* path completely
(a failed flow discards the worktree → main tree untouched). On the *success* path,
`propagate_changes` walks `git status_porcelain()` of the worktree and copies back **every**
modified or untracked file. For `flow.build_tests` the worktree contains:

- `tests/.../test_generated.py` — the legitimate output (untracked).
- ~26 reformatted hand-written test files — `fix.format` runs repo-wide (path unset →
  `["src","tests"]`) and reformats the whole tree inside the worktree.
- possibly `src/` files reordered by `fix.imports`.

So a *passing* generation would commit all of them — the success-path blast radius #630 tracks.
It survives today only because every observed run *failed* the gate (so propagation never ran),
and because the pilot scope is parked at one file.

### Why "everything the worktree changed" is the wrong production signal

ADR-101 D2 says commit = production. The current implementation reads "production" as "the
worktree's git diff". But the formatter reformatting unrelated files is a **tool side-effect**,
not the proposal's product. The proposal's job is to author one test file; `fix.*` reformatting
the rest of the tree is incidental churn that happens to live in the sandbox. Committing it is
the same authorship violation ADR-101 D1 forbids, just laundered through the sandbox.

The fix is not to chase every fixer's scope (fragile, per-site, and `fix.*` are general-purpose
actions used elsewhere). It is to bound what counts as production at the single propagate sink:
**a flow commits what its steps declared they produced.**

---

## Decision

### D1 — A flow's production set is the union of its steps' declared outputs (ratify)

On flow success, the set propagated to the main tree (and stamped as the ADR-101 D2 commit set)
is the union over the flow's steps of their **declared** production — the `files_produced` result
key — **not** the worktree's full git diff. Files the sandbox changed incidentally (a formatter
reformatting unrelated files, an importer reordering `src/`) are sandbox-local: they are
discarded with the worktree, never propagated, never committed. This is ADR-101 D2 read
precisely for flows: production is what a step *authored and declared*, not ambient churn.

### D2 — `build.tests` declares its output (ratify)

`build.tests` adds `files_produced: [test_file]` to its success `ActionResult.data` (it already
computes `test_file` and writes exactly that one file). This is the single source the flow's
propagate step reads. No new path-derivation logic — the action that wrote the file names it.

### D3 — `propagate_changes` gains an allowlist; the flow branch supplies it (ratify)

`SandboxLifecycle.propagate_changes(scoped_git, only_paths=None)` — when `only_paths` is given,
the copy-back is restricted to that set (intersected with what the worktree actually changed, so
a declared-but-unwritten path is a no-op, not a failure). The conflict-check / loud-failure /
no-deletion contract is unchanged. `proposal_executor`'s flow branch derives `only_paths` from
the flow result's steps (`∪ step.data["files_produced"]`) and passes it. The propagated file is
the worktree copy — i.e. *after* any `fix.*` formatting ran on it — so the committed test is the
healed version, just without the collateral.

### D4 — Fallback keeps un-migrated flows on current behavior (ratify)

If a flow's steps declare **no** `files_produced`, the flow branch falls back to the full
worktree diff (today's behavior). Only flows whose steps opt in (via `files_produced`) get the
bounded commit set. This makes the change incrementally safe: `flow.build_tests` opts in through
D2; no other flow's behavior changes until its actions declare production.

### Corollary — fix.format / fix.imports (tracked, not ratified)

With D1, the committed test is whatever `fix.*` left it as in the worktree. Two non-blocking
cleanups, scoped to the implementation, not core decisions:

- `fix.format` is currently broken on the daemon (`run_poetry_command` needs `poetry` on PATH,
  which it lacks), so the propagated test is **unformatted** — a cosmetic nit under D1 (the test
  still runs and commits; a later format sweep catches it). The fix is to run the formatter via
  the venv directly. Scope it to the `fix.format` action, not `format_code` (7 callers), to keep
  blast radius small — or defer if it grows.
- `fix.imports` / `fix.headers` in `flow.build_tests` hardcode `src/` and are no-ops for a
  `tests/` output. Trimming them from the flow is an optional simplification (one less
  worktree-churn source), not required by D1.

---

## Consequences

**Positive**
- A successful `flow.build_tests` run commits exactly the generated test file (#630 acceptance).
- Closes the success-path blast radius at the single propagate sink — robust to which `fix.*`
  steps a flow uses and to their internal scope.
- Reuses the existing `files_produced` convention and the `compute_production_set` reader; no new
  parallel mechanism.
- Unblocks reopening the autonomous test-gen pilot beyond one file, and lets the
  `fix.*`/pytest-in-worktree **success** path get its first live verification (every run so far
  failed before reaching it).

**Negative / watch**
- A flow step that authors a file but forgets to declare it in `files_produced` would have that
  file silently dropped from the commit (declared-production is now load-bearing). Mitigation: D4
  fallback only triggers when *no* step declares anything; a partially-declaring flow trusts the
  declarations. For `flow.build_tests` the only writer is `build.tests`, which D2 makes declare.
- The committed test is unformatted until the `fix.format` corollary lands.

**Verification**
- Unit: `propagate_changes(only_paths=...)` copies only the allowlist ∩ worktree-changes; a
  worktree with the test file + extra reformatted files propagates only the test file.
- Live (post-deploy, scope re-opened): a `flow.build_tests` proposal that **passes** the
  `test.sandbox_validate` gate commits exactly one file (the generated test); `git show --stat`
  on the autonomous commit shows the test file and nothing else.
