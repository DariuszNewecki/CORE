<!-- path: .specs/papers/CORE-CommitReachabilityAuditor.md -->

# CORE — Commit Reachability Auditor

**Status:** Canonical
**Authority:** Policy
**Scope:** Edge 5 orphan-commit detection in the consequence chain

---

## 1. Purpose

This paper defines the `CommitReachabilityAuditor` — the sensing Worker
responsible for verifying that every commit produced by autonomous execution
remains reachable from a git branch.

---

## 2. Problem Statement

When the autonomous loop executes a proposal and commits the result, it records
the commit SHA as `post_execution_sha` in `core.proposal_consequences`. A commit
that cannot be reached from any branch — an orphan — means the governed change
is no longer part of the codebase history. The consequence chain records the
execution, but the code change has been silently lost: rebases, force pushes, or
branch deletions can all produce this state. Without active detection, the
governor has no signal that governed work has been severed from the repository.

---

## 3. Definition

`CommitReachabilityAuditor` is a sensing Worker. It reads every
`post_execution_sha` from `core.proposal_consequences`, verifies branch
reachability via git, and posts a Blackboard Finding for each orphan. It makes
no decisions. It writes no source files. It calls no LLM.

---

## 4. Constitutional Identity

| Field | Value |
|---|---|
| Declaration | `.intent/workers/commit_reachability_auditor.yaml` |
| Class | `sensing` |
| Phase | `audit` |
| Permitted tools | none |
| Approval required | false |
| Schedule | max_interval 3600 s (1 hour) |
| ADR | ADR-019 |

---

## 5. Detection Logic

One detection cycle:

**Step 1 — Post heartbeat**
Posted unconditionally before any I/O so a downstream failure does not
cause the supervisor to flag the worker as silent.

**Step 2 — Load existing orphan findings**
Fetches all open Blackboard subjects matching the
`governance.edge5.orphan_sha::%` prefix. Used for deduplication in Step 4.

**Step 3 — Read consequence SHAs**
Retrieves all `(proposal_id, post_execution_sha)` pairs from
`core.proposal_consequences` via `ConsequenceLogService.get_all_shas()`.

**Step 4 — Verify reachability**
For each pair, runs `git branch --contains {sha}` against the repository
working directory. A commit is reachable if the command returns at least
one branch name. A commit is an orphan if the output is empty.

**Step 5 — Post deduplicated findings**
For each orphan, computes subject `governance.edge5.orphan_sha::{proposal_id}`.
Skips subjects already present in the open set from Step 2. Posts one
Blackboard Finding per new orphan.

**Step 6 — Post completion report**
Posts `commit_reachability_auditor.run.complete` with `checked` and
`orphans_detected` counts.

---

## 6. Blackboard Contract

| Subject prefix | Entry type | Producer |
|---|---|---|
| `governance.edge5.orphan_sha::{proposal_id}` | finding | `CommitReachabilityAuditor` |
| `commit_reachability_auditor.run.complete` | report | `CommitReachabilityAuditor` |

No other worker produces `governance.edge5.orphan_sha::` findings.

---

## 7. Finding Payload

```
proposal_id:   {UUID of the proposal whose commit is unreachable}
orphan_sha:    {the unreachable commit SHA}
detected_at:   {ISO 8601 timestamp}
```

SHA prefix width is 16 characters (per ADR-019 D2).

---

## 8. Remediation Posture

Orphan-commit findings require human review. An orphan may result from an
intentional rebase, an accidental force push, or a governance process error.
Autonomous remediation is not appropriate — the correct response depends on
intent the system cannot determine. Per ADR-019 D1, this worker detects only;
it does not modify `core.proposal_consequences` records.

---

## 9. Non-Goals

This paper does not define:
- how orphan commits are recovered or re-applied
- the policy governing force-push permissions on governed branches
- what constitutes an acceptable commit-reachability SLA

---

## 10. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.
