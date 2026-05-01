<!-- path: .specs/decisions/ADR-019-edge5-git-boundary-attribution-posture.md -->

# ADR-019 — Edge 5 git-boundary attribution posture

**Status:** Accepted
**Date:** 2026-05-01
**Author:** Darek (Dariusz Newecki)
**Closes:** #166
**Supersedes:** nothing
**Related:** ADR-015 (consequence chain attribution), #124 (commit-message fidelity, Band D)

---

## Context

Edge 5 of the consequence chain (Execution → File changes) carries two
attribution artefacts:

1. `core.proposal_consequences.post_execution_sha` — a structured DB column
   recording the git HEAD after execution. Written by `ProposalExecutor` via
   `ConsequenceLogService.record()`.
2. A commit-message prefix `fix({proposal_id[:8]}):` — a freeform convention
   written into the git commit message at execution time. Used as a reverse-lookup
   aid (`git log --grep` + a LIKE against `core.autonomous_proposals`).

The investigation at `.specs/state/2026-04-25-consequence-chain-mapping.md`
named two failure modes that break the scheme silently. #166 captures both.
This ADR decides the posture for each.

**Scale at decision time:** 188 proposals, 28 consequence rows, all with
`post_execution_sha` populated.

---

## Failure mode 1 — orphan commits

A `post_execution_sha` may point to a commit that exists in the git object
database but is not reachable from any branch (`git branch --contains` returns
empty). The commit is GC-eligible. The DB link survives but the commit is
effectively a dangling pointer.

**Confirmed instance:** proposal `0b359369`, `post_execution_sha = 211c2dd2`.
Verified unreachable on 2026-05-01.

## Failure mode 2 — 8-char prefix collisions

The commit-message prefix carries only `proposal_id[:8]` — 32 bits of
distinguishability. Birthday collision probability grows with corpus size:

| Proposals | Approx. collision probability |
|-----------|-------------------------------|
| 188 (now) | ~0.0004% |
| 1,000     | ~0.01% |
| 10,000    | ~1% |
| 100,000   | ~55% |

At current scale, collisions are negligible. At production scale, they become
a silent correctness hazard.

---

## Decisions

### D1 — Orphan detection: sense, surface, preserve

A governance sensor (`CommitReachabilityAuditor`) periodically reads
`post_execution_sha` values from `core.proposal_consequences` and verifies
reachability via `git branch --contains`. On detecting an orphan:

- A blackboard finding is posted with subject
  `governance.edge5.orphan_sha::{proposal_id}` and payload carrying
  `proposal_id`, `orphan_sha`, and `detected_at`.
- The `post_execution_sha` value in `core.proposal_consequences` is **not
  modified** — ALCOA "Original" principle; the DB record preserves what was
  written at execution time.
- No automatic remediation. Orphan resolution (re-tagging, gc-protection, or
  explicit documentation) is a governor action.

The confirmed orphan (`0b359369` → `211c2dd2`) is preserved as-is in the DB.
It is documented here as a known instance; no backfill or invalidation.

### D2 — Prefix widening: 16 chars on new commits, forward-only

The commit-message prefix is widened from `proposal_id[:8]` to
`proposal_id[:16]` (64 bits) for all new executions. At any realistic corpus
size, 64 bits renders birthday collisions astronomically unlikely.

**Change site:** `src/will/autonomy/proposal_executor.py` — both the
single-execute path (line 219) and the batch-execute path (line 469) format
the commit message string `f"fix({proposal.proposal_id[:8]}): {proposal.goal}"`.

Historical commits are immutable (git history). The 28 existing consequence
rows carry their original 8-char prefixes in git history and are not
re-written. Forward-only; no migration.

### D3 — `post_execution_sha` is the authoritative Edge 5 link

`core.proposal_consequences.post_execution_sha` is the canonical,
machine-readable Edge 5 attribution. Queries that traverse the consequence
chain (URS Q5.F, Q5.R) must use this column as the primary join key.

The commit-message prefix (`fix({proposal_id[:16]}):`) is a human-readable
convenience for `git log --grep` and is not the authoritative link. Any query
that relies solely on the commit-message prefix for chain traversal is brittle
by design. #124 (Band D) governs the fidelity of the commit message content;
this ADR governs the structural link.

---

## Consequences

**Immediate implementation required (closes #166):**

1. **D1 sensor** — new worker YAML + sensor class for commit reachability
   auditing. Posts `governance.edge5.orphan_sha::*` findings.
2. **D2 prefix widening** — two-line change at the commit-message formatting
   sites. No schema change. No migration.

**Not in scope for this ADR:**
- Moving the commit-message prefix to a structured column (supersedes the
  prefix convention entirely; Band D/E scope).
- Automatic orphan remediation (governor action).
- #124 commit-message fidelity (separate issue, separate band).

---

## Alternatives considered

**Widen to 12 chars.** Reduces collision probability substantially but leaves
a residual tail at very large scale. 16 chars (UUID hex) costs nothing
additional and eliminates the problem at any practical corpus size. 16 chosen.

**Invalidate orphan SHAs in the DB.** Rejected. Violates ALCOA "Original" —
the DB should preserve what was recorded, not synthesize a corrected value.
Detection + surfacing is the correct response; remediation is governor-owned.

**Move immediately to a structured column for the proposal→commit link.**
Out of scope for Band B. The column already exists (`post_execution_sha`);
the commit-message prefix is already secondary per D3. The structured-column
migration belongs in Band D alongside #124.
