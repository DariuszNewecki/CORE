---
kind: adr
id: ADR-129
title: ADR-129 — Commit authorship integrity enforcement (ADR-101 D6 delivery)
status: accepted
---

<!-- path: .specs/decisions/ADR-129-commit-authorship-integrity.md -->

# ADR-129 — Commit authorship integrity enforcement (ADR-101 D6 delivery)

**Date:** 2026-06-28
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-28 — drafted under governor direction)
**Closes:** #609
**Grounds:** ADR-101 D6
**Relates to:** ADR-101 D1/D2/D3, ADR-071 D2.2, ADR-019 D1

---

## Context

ADR-101 D1 establishes a constitutional invariant: a commit's diff MUST contain
only bytes its author produced. D2 operationalised the autonomous side (the
`_sandbox_target_paths` production claim), D3 the rollback shape, and D6 committed
to authoring a governance rule plus an enforcement engine.

Investigation before drafting this ADR surfaced two concrete gaps:

### Gap 1 — `commit_paths` staging contamination (a code bug)

`git_service.commit_paths(paths, message)` stages the production set with
`git add -- <paths>` then calls `git commit -m ...`. `git commit` commits the
*entire staging area*, not just the paths added in the preceding line. If a
Claude Code session or the governor has staged files before the autonomous
commit fires, those bytes ride along inside the autonomous commit — attributed
to the wrong author with no signal in the history.

The `propagate_changes` conflict check (ADR-071 D2.2) protects the *working
tree* (refusing propagation if the same target files are dirty in main), but
does not inspect the staging area. A staged file in a non-overlapping path
bypasses it silently.

### Gap 2 — declared production is not persisted

`compute_production_set` — the union of `_sandbox_target_paths` (observed by
SandboxLifecycle) and `files_produced` (explicitly declared by the action) —
drives the commit set but is discarded after use. `core.proposal_consequences`
only records `files_changed` (the actual `git diff --name-only pre_sha post_sha`),
not what the action *declared* it would produce. Without both sides, a post-commit
audit cannot detect contamination.

### Gap 3 — no enforcement rule or engine exists

ADR-101 D6 is not yet implemented. No file exists at
`.intent/rules/governance/commit_authorship_integrity.json`, and no worker
or sensor checks the authorship property on committed proposals. The invariant
is recorded in ADR-101 D1 and CLAUDE.md, but is enforced only by convention
and docstring.

### Why no existing engine fits

Every audit engine (`ast_gate`, `glob_gate`, `llm_gate`, `runtime_gate`) scans
source files at rest. "A commit's diff is a subset of its declared production"
is a property of git objects plus a database record — not of source code. The
right enforcement pattern is a blackboard worker that observes completed
proposals post-commit, analogous to `CommitReachabilityAuditor` (ADR-019 D1).

### Why reporting, not blocking

Blocking enforcement requires intercepting the commit before it lands —
a pre-push hook (option b from the #609 design questions). That hook is not
yet implemented. A post-commit audit worker catches violations within the
next sensor cycle (max_interval: 3600s) and posts to the blackboard where
ViolationRemediatorWorker can drive governor response. Per the ramp-arc
pattern (ship reporting → resolve drifts → promote blocking), shipping at
`reporting` now, then promoting to `blocking` when a pre-push hook lands,
is the correct progression.

### Claude Code and governor-direct commits

This ADR covers the autonomous commit path only. Claude Code commits carry
a `Co-Authored-By: Claude Sonnet X.Y <noreply@anthropic.com>` trailer by
convention; there is no claim ledger for purely governor-direct commits. Both
remain open problems. A claim ledger design belongs in a follow-on ADR.

---

## Decisions

### D1 — Fix `commit_paths` staging contamination

`git_service.commit_paths` gains a pre-flight staging check before any
`git add` call. The check runs `git diff --cached --name-only` and compares
the result against the production set. If any staged paths fall outside the
production set, the method raises immediately:

```
RuntimeError: ADR-129 D1: staging area contains N path(s) outside the
declared production set — refusing autonomous commit to prevent authorship
contamination. Commit or restore staged work first: [...]
```

This closes the write-side race at the point of commit, not after the fact.
The check runs before the first `git add --`; the two-pass pre-commit-hook
retry loop is not affected (both passes re-stage only the production set).

### D2 — Persist declared production in consequence log

`core.proposal_consequences` gains a `declared_production jsonb DEFAULT '[]'::jsonb
NOT NULL` column. `ConsequenceLogService.record()` accepts a `declared_production:
list[str]` parameter and persists it alongside `files_changed`. The pipeline
function `record_consequence()` receives the value from `compute_production_set(
action_results)` — the same derivation that drives the commit set — and
forwards it to the service.

The ON CONFLICT DO UPDATE clause includes `declared_production` so retries
are idempotent.

### D3 — Rule: `governance.commit_authorship_integrity`

`.intent/rules/governance/commit_authorship_integrity.json` declares the
invariant from ADR-101 D1 as an enforceable rule. A single rule in the file:

- **id**: `governance.commit_authorship_integrity`
- **enforcement**: `reporting` (see rationale above)
- **authority**: `constitution` (grounds in ADR-101 D1)
- **phase**: `audit`

### D4 — Worker: `CommitAuthorshipAuditWorker`

A new worker in `src/will/workers/commit_authorship_audit_worker.py`, declared
in `.intent/workers/commit_authorship_audit_worker.yaml`. Scheduled hourly
(`max_interval: 3600`).

On each cycle:

1. Queries `core.proposal_consequences` for entries with `post_execution_sha IS NOT NULL`
   and `recorded_at > now() - 7 days`.
2. Fetches existing open `governance.commit_authorship_integrity::*` findings
   from the blackboard to avoid re-posting duplicates.
3. For each unverified entry, runs `git diff --name-only pre_sha post_sha` to
   obtain the actual commit diff.
4. Compares against `declared_production`. If the actual diff is not a subset,
   posts a finding with subject `governance.commit_authorship_integrity::{proposal_id}`.
5. Posts a completion report and heartbeat.

The worker uses `governance.dangerous_execution_primitives` (subprocess git)
in the Body validation sanctuary pattern: git shell-outs are already used by
`CommitReachabilityAuditor` and `compute_changed_files`.

### D5 — Remediation map: PENDING

`governance.commit_authorship_integrity` is added to
`.intent/enforcement/remediation/auto_remediation.yaml` with `status: PENDING`.
No autonomous remediation action exists for a contaminated commit (the fix
requires governor investigation — git history rewrite with proper attribution,
or acceptance of the contamination as a documented exception). The PENDING entry
satisfies `governance.remediation.all_rules_mapped` and prevents the abandoned-
finding re-emission loop (ADR-066).

### D7 — Executor ordering: commit before mark_completed

Prior to this decision, `ProposalExecutor` called `mark_completed` then
`commit_proposal_changes`. When D1 fired and refused the commit, the proposal
row was already `completed` in the DB — execution had succeeded but the git
record was absent. The consequence log would record `post_sha == pre_sha`
(no new commit), making the row indistinguishable from a no-op proposal.

D7 inverts the ordering: `commit_proposal_changes` is called first and returns
`bool` — `True` on a successful commit or an empty production set (nothing to
commit), `False` when `StagingContaminationError` blocks the commit. On `False`,
the executor calls `rollback_proposal` (same as the action-failure path) then
`mark_failed` with the D1 reason. `mark_completed` and consequence recording
proceed only on `True`.

`StagingContaminationError(RuntimeError)` is introduced in `git_service.py`
as a typed exception distinct from generic `RuntimeError`, so `commit_proposal_
changes` can catch D1 failures specifically without catching other git errors
(unrecoverable pre-commit hook failures, etc.) that should not cause `mark_failed`.

The net result: a D1 refusal now produces `status=failed` with
`failure_reason="ADR-129 D1: staging contamination detected"`, which is
honest about why the proposal did not land a commit.

### D6 — Claude Code and governor-direct paths: explicitly deferred

This ADR closes the autonomous-path enforcement gap. The human/AI-agent paths
(Co-Authored-By convention for Claude Code; no mechanism for governor-direct
commits) remain open. A claim ledger design is a follow-on ADR.

---

## Consequences

**Positive:**

- The staging contamination race is closed at the point of commit (D1). Any
  autonomous commit attempt while a session has staged work aborts loudly
  rather than sweeping in unrelated bytes.
- The consequence log now carries both sides of the authorship equation:
  `files_changed` (actual) and `declared_production` (claimed). A future
  pre-push enforcement path can use the same data.
- `governance.commit_authorship_integrity` findings appear in the blackboard
  within one sensor cycle of a violation, giving the governor a signal to
  investigate and remediate.

**Negative:**

- The D1 pre-flight check will abort autonomous commits if a session leaves
  staged work overnight. Operators must not stage work without committing
  before autonomous cycles run. This is the correct contract; the check
  surfaces an invariant violation that already existed silently.
- Reporting (not blocking) enforcement means a contaminated commit can still
  land. Promotion to blocking requires a pre-push hook as a separate work item.

**Neutral:**

- `declared_production` will be `[]` for consequence log entries written before
  this migration. The worker treats an empty `declared_production` alongside a
  non-empty `files_changed` as unverifiable (not a violation) and skips the
  entry rather than false-positiving on pre-ADR-129 history.
- Schema-as-truth: `infra/sql/db_schema_live.sql` is the canonical schema;
  the `ALTER TABLE` migration lands in the numbered ledger
  (`20260628_adr129_add_declared_production_to_proposal_consequences.sql`).

---

## References

- ADR-101 D1 — the constitutional invariant this ADR enforces
- ADR-101 D2 — `_sandbox_target_paths` / `files_produced` (the production claim)
- ADR-101 D3 — rollback derives from the same production set
- ADR-101 D6 — committed to this rule + engine
- ADR-071 D2.2 — sandbox lifecycle and propagate_changes conflict check
- ADR-019 D1 — CommitReachabilityAuditor pattern (the worker template)
- ADR-066 — remediation map completeness invariant
- #609 — issue tracking this ADR
