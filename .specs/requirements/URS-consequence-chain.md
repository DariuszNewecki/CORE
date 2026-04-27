<!-- path: .specs/requirements/URS-consequence-chain.md -->

# URS — Consequence Chain

**Status:** Draft (industry defaults adopted 2026-04-27; awaiting governor review for finalization)
**Authority:** Requirements
**Scope:** Band B (Milestone 14) — closes G3.
**Baseline:** `.specs/state/2026-04-25-consequence-chain-mapping.md`
**Plan:** `.specs/planning/BAND-B-consequence-chain-plan.md`
**Schema basis:** Live schema as inspected 2026-04-27 (`core.blackboard_entries`, `core.autonomous_proposals`, `core.proposal_consequences`, `core.audit_findings`).
**Regulatory basis:** 21 CFR Part 11 §§11.10, 11.50, 11.70; WHO TRS 1033 Annex 4; ALCOA+ (Attributable, Complete, Traceable). See §7.

---

## 1. Purpose

The CORE consequence chain — Finding → Proposal → Approval → Execution → File changes → New findings — must be queryable as a single causality graph. This document specifies, in query-shaped form, what the chain must answer when Band B closes.

A query is in this URS only if a stakeholder needs the answer. SQL syntax is the contract: each requirement is the literal query template that must execute against live data and return correct results when Band B is complete.

The target audience for the chain is a governance professional in a regulated environment. Industry conventions for audit trails (Part 11 / ALCOA+) are treated as the default specification rather than as choices.

---

## 2. Stakeholders and questions

| Stakeholder | Needs to ask |
|---|---|
| **Governor (Darek)** | "What did CORE just do, and why?" — supervision without reading code. |
| **Convergence measurement (G2)** | "Are findings resolving faster than they're created?" — truthful resolution count, not timestamp inference. |
| **GxP-style external auditor** | "Show me the full authorization chain for change X." — every link from rule to file change, including under what authority each approval was granted. |
| **Autonomous debugging** | "This finding regressed — what introduced it?" — backward causation from new findings. |

---

## 3. Functional requirements

Each requirement specifies: the question, the SQL template, current state, and post-implementation expectation. Columns or jsonb keys marked `(POST)` do not exist or are not populated today; their addition or population is the work of the named issue. Field names in `(POST)` markers are illustrative; ADR-015 decides exact names and storage shape (column vs. jsonb key).

### Edge 1 — Finding ↔ Proposal

**Q1.F — Given a finding, which proposal resolved it?**

```sql
SELECT payload->>'proposal_id' AS resolving_proposal_id
FROM core.blackboard_entries
WHERE id = $1;
```

- *Current:* works for findings resolved on the deferred-to-proposal path; returns NULL for findings resolved on the subsume/dedup path (investigation §"Explicit unverifieds").
- *Post-impl:* both resolution paths populate `payload->>'proposal_id'`. Subsume-path attribution is required (see §7 — ALCOA+ "Complete" / WHO Annex 4 §11.11 — superseded records must not be obscured).

**Q1.R — Given a proposal, which findings did it resolve?**

```sql
SELECT (constitutional_constraints->'finding_ids')::jsonb AS finding_ids   -- (POST: #145)
FROM core.autonomous_proposals
WHERE proposal_id = $1;
```

- *Current:* `constitutional_constraints` does not contain `finding_ids`; reverse query requires JSONB scan over `blackboard_entries.payload`, asymmetric and unindexed.
- *Post-impl (#145):* direct, single-row read. Set must include findings resolved on both the deferred-to-proposal path and the subsume path.

### Edge 2 — Proposal ↔ Approval

**Q2.F — Given a proposal, who approved it and when?**

```sql
SELECT approved_by, approved_at
FROM core.autonomous_proposals
WHERE proposal_id = $1;
```

- *Current:* populated for 2 of 159 rows; autonomous self-promote path (`risk=safe`) bypasses `ProposalStateManager.approve()` and never writes these columns.
- *Post-impl (#146):* populated for every proposal that reaches `approved` state, including the autonomous path.

**Q2.R — Given an approver, what did they approve?**

```sql
SELECT proposal_id, goal, approved_at
FROM core.autonomous_proposals
WHERE approved_by = $1
ORDER BY approved_at DESC;
```

- *Current:* answerable only for the 2 populated rows.
- *Post-impl (#146):* answerable for all approved proposals.

**Q2.A — Given a proposal, under what authority was approval granted?**

```sql
SELECT approved_by,
       approved_at,
       approval_authority   -- (POST: new issue covering authority field)
FROM core.autonomous_proposals
WHERE proposal_id = $1;
```

- *Current:* not answerable. The schema does not record a meaning/authority for approval. For autonomous self-promotion, the rule that classified the proposal as auto-approvable is known to `.intent/` but is not propagated onto the proposal record.
- *Post-impl:* populated for every approved proposal. Value is a structured reference to the rule or policy that authorized approval (e.g., `risk_classification.safe_auto_approval` for autonomous self-promote; the human approver's role/scope for human approvals).
- *Regulatory basis:* 21 CFR Part 11 §11.50 requires every signed record to indicate the meaning of the signature (review, approval, authorship) in addition to who signed and when. §11.10 requires authority checks. ALCOA+ "Attributable" extends "who" to include role/authority. See §7.

### Edge 3 — Approval → Execution claim

**Q3.F — Given a proposal, which worker claimed it for execution?**

```sql
SELECT claimed_by, execution_started_at   -- (POST: #147 adds claimed_by)
FROM core.autonomous_proposals
WHERE proposal_id = $1;
```

- *Current:* `claimed_by` does not exist on `autonomous_proposals`. Inferable only from daemon-log scan correlated to `execution_started_at` ± window. Not queryable.
- *Post-impl (#147):* direct.

**Q3.R — Given a worker UUID, which proposals did it execute?**

```sql
SELECT proposal_id, status, execution_completed_at
FROM core.autonomous_proposals
WHERE claimed_by = $1   -- (POST: #147)
ORDER BY execution_started_at DESC;
```

- *Current:* not answerable.
- *Post-impl (#147):* direct.

### Edge 5 — Execution → File changes

In scope for the URS as a read-path requirement; commit-fidelity brittleness (orphan commits, 8-char prefix) tracked at #124 outside Band B.

**Q5.F — Given a proposal, which files changed and at which commit?**

```sql
SELECT files_changed, pre_execution_sha, post_execution_sha
FROM core.proposal_consequences
WHERE proposal_id = $1;
```

- *Current:* works for the 22 rows in `proposal_consequences`.
- *Post-impl:* unchanged. URS asserts as no-regression.

**Q5.R — Given a commit SHA, which proposal produced it?**

```sql
SELECT proposal_id, recorded_at
FROM core.proposal_consequences
WHERE post_execution_sha = $1;
```

- *Current:* works.
- *Post-impl:* unchanged.

### Edge 6 — File changes → New findings

**Q6.F — Given a new finding (potentially a regression), which prior proposal or commit caused it?**

```sql
SELECT payload->>'causing_proposal_id'  AS causing_proposal_id,   -- (POST: #148)
       payload->>'causing_commit_sha'   AS causing_commit_sha     -- (POST: #148)
FROM core.blackboard_entries
WHERE id = $1;
```

- *Current:* not answerable. Finding payload carries no back-reference. The lone counter-example (`test.run_required` postings by `ProposalConsumerWorker`, investigation §Edge 6) does not generalize to `audit.violation::*` findings.
- *Post-impl (#148):* sensors thread proposal/commit context into the payload of new findings posted in proximity to a recent execution.

**Q6.R — Given a proposal or commit, what new findings did it introduce?**

```sql
SELECT id, subject, created_at
FROM core.blackboard_entries
WHERE payload->>'causing_proposal_id' = $1   -- (POST: #148)
   OR payload->>'causing_commit_sha'   = $2; -- (POST: #148)
```

- *Current:* not answerable.
- *Post-impl (#148):* direct.

### End-to-end chain queries

These are the two queries that justify Band B as a band. If either fails to run end-to-end against live data after the four children land, Band B has not closed.

**E2E.F — Walk a finding forward through every consequence.**

```sql
SELECT
  bb.id                                AS finding_id,
  bb.subject                           AS finding_subject,
  ap.proposal_id                       AS proposal_id,
  ap.goal                              AS proposal_goal,
  ap.approved_by                       AS approved_by,
  ap.approved_at                       AS approved_at,
  ap.approval_authority                AS approval_authority,    -- (POST: Q2.A issue)
  ap.claimed_by                        AS claimed_by,            -- (POST: #147)
  ap.execution_started_at              AS executed_at,
  pc.files_changed                     AS files_changed,
  pc.post_execution_sha                AS commit_sha,
  COALESCE(
    (SELECT jsonb_agg(jsonb_build_object('id', child.id, 'subject', child.subject))
     FROM core.blackboard_entries child
     WHERE child.payload->>'causing_proposal_id' = ap.proposal_id),  -- (POST: #148)
    '[]'::jsonb
  )                                    AS new_findings_caused
FROM core.blackboard_entries bb
LEFT JOIN core.autonomous_proposals ap
  ON ap.proposal_id = bb.payload->>'proposal_id'
LEFT JOIN core.proposal_consequences pc
  ON pc.proposal_id = ap.proposal_id
WHERE bb.id = $1;
```

- *Current:* runs but returns NULLs for `approved_by` (most rows), `approval_authority` (column missing), `claimed_by` (column missing), and `new_findings_caused` (always empty).
- *Post-impl:* returns a populated row per the children's combined effect.

**E2E.R — Walk a commit backward to its findings, approver, authority, and worker.**

```sql
SELECT
  pc.proposal_id,
  ap.goal,
  ap.approved_by,
  ap.approval_authority,                                                 -- (POST: Q2.A issue)
  ap.claimed_by,                                                         -- (POST: #147)
  COALESCE(ap.constitutional_constraints->'finding_ids', '[]'::jsonb)    -- (POST: #145)
                                       AS finding_ids,
  pc.files_changed
FROM core.proposal_consequences pc
JOIN core.autonomous_proposals ap
  ON ap.proposal_id = pc.proposal_id
WHERE pc.post_execution_sha = $1;
```

- *Current:* runs but `approval_authority` and `claimed_by` error (columns missing) and `finding_ids` returns `[]`.
- *Post-impl:* returns a populated row.

### Convergence — G2 measurement

**CONV.1 — Resolution rate vs creation rate over a window.**

```sql
WITH window_bounds AS (
  SELECT $1::timestamptz AS lo, $2::timestamptz AS hi
),
created AS (
  SELECT COUNT(*) AS n
  FROM core.blackboard_entries, window_bounds
  WHERE entry_type = 'audit.violation'
    AND created_at >= window_bounds.lo
    AND created_at <  window_bounds.hi
),
resolved AS (
  SELECT COUNT(*) AS n
  FROM core.blackboard_entries bb, window_bounds
  WHERE bb.entry_type = 'audit.violation'
    AND bb.status = 'resolved'
    AND bb.resolved_at >= window_bounds.lo
    AND bb.resolved_at <  window_bounds.hi
    AND EXISTS (
      SELECT 1 FROM core.autonomous_proposals ap
      WHERE ap.proposal_id = bb.payload->>'proposal_id'
        AND ap.status = 'completed'
    )
)
SELECT created.n AS findings_created,
       resolved.n AS findings_resolved_by_completed_proposal,
       (resolved.n::float / NULLIF(created.n, 0)) AS resolution_ratio
FROM created, resolved;
```

- *Current:* runs. `resolved` count under-reports because subsume-path resolutions lose the `proposal_id` link.
- *Post-impl:* same query; under-reporting eliminated once subsume-path attribution lands (see §3 Q1.F post-impl). The numerator counts only proposal-attributed resolutions; non-proposal resolution causes (file deleted, rule retired, scope changed) are out of Band B scope and addressed in §6.

A resolution ratio ≥ 1.0 sustained over a representative window is the operational definition of G2 cleared.

---

## 4. Non-functional requirements

**NFR.1 — Read-path complexity.** Q1–Q6 single-table or single-FK-join queries. E2E queries acceptable as 3–4 JOINs. No application-side joining required.

**NFR.2 — Index coverage.** Existing indexes (`autonomous_proposals_proposal_id_key`, `proposal_consequences_pkey`) cover Q1–Q5 and the E2E queries' join conditions. Q6 reverse query (`payload->>'causing_proposal_id'`) requires a GIN or expression index on `blackboard_entries.payload` if performance becomes a concern; not a v1 requirement, opened as a follow-up only on observed query latency.

**NFR.3 — Verification artifact.** A representative chain trace from a recent post-Band-B autonomous round-trip is captured as a markdown document under `.specs/state/`, includes the actual output of E2E.F and E2E.R for the chosen proposal, and is referenced from the closure of issue #110.

**NFR.4 — Complete attribution of resolved findings.** Every resolved `audit.violation` finding must be attributable to a queryable cause. For proposal-caused resolutions — both the deferred-to-proposal path and the subsume/dedup path — the cause is the resolving proposal's `proposal_id`, recorded in the finding's payload by the worker that performed the resolution. Silent resolution (status flipped to `resolved` without payload attribution) is not acceptable. Non-proposal resolution causes are out of Band B scope; see §6.

**NFR.5 — Authority of approval is non-omittable.** Every approved proposal carries an `approval_authority` value. The system MUST refuse to mark a proposal `approved` without it (validation at the write path, not after the fact). This serves Part 11 §11.10 "authority checks" and §11.50 "meaning of signature."

---

## 5. Acceptance criteria

Band B closes when all of the following are demonstrated against live data:

1. Q1.F, Q1.R, Q2.F, Q2.R, Q2.A, Q3.F, Q3.R, Q5.F, Q5.R, Q6.F, Q6.R execute and return non-default values for at least one recent autonomous round-trip.
2. E2E.F and E2E.R execute end-to-end and return all populated columns for the verification proposal — including `approval_authority`, `claimed_by`, `finding_ids`, and `new_findings_caused`.
3. CONV.1 returns a resolution_ratio ≥ 1.0 sustained over a representative measurement window. The window is itself a Band B artifact, not specified here — defined when daemon liveness has produced enough data.
4. NFR.5 enforcement verified: an attempt to write `status='approved'` without `approval_authority` is rejected at the write path.
5. The verification artifact (NFR.3) exists and is referenced from issue #110's closing comment.

---

## 6. Out of scope

- **Edge 4 cross-proposal queries** ("all executions of action X"). Analytical, not load-bearing for the chain.
- **Commit-message fidelity / orphan-commit defense.** Tracked at #124 outside Band B.
- **`core.audit_findings` table integration with the autonomous chain.** Empty in autonomous path; populated only by CLI ingest.
- **Legacy `core.proposals`, `core.proposal_signatures`, `core.tasks`, `core.actions`.** Retired per ADR-013; `proposal_signatures` confirmation pending.
- **Non-proposal resolution causes** (file deleted, rule retired, scope changed). The truthfulness of CONV.1's denominator depends on these being either attributed or excluded with a recorded reason. Out of Band B scope; opens as a follow-up after Band B closes if the resolution_ratio shows distortion.
- **External (post-CORE-perimeter) consequence chain.** Daniel's broader two-log framing covers consequences of CORE's *output* on humans and external systems. v1 scope is the *internal* chain only.

---

## 7. Regulatory basis

The URS adopts industry-default audit-trail conventions for the consequence chain because the target audience is governance professionals in regulated environments. The conventions are not invented; the citations below name where each requirement comes from.

**21 CFR Part 11 §11.50 — Signature manifestations.** Every signed electronic record must indicate (1) the printed name of the signer, (2) the date and time when the signature was executed, and (3) the meaning of the signature (such as review, approval, responsibility, or authorship). Q2.A and NFR.5 implement this for autonomous-path approvals: `approved_by` (1), `approved_at` (2), `approval_authority` (3).

**21 CFR Part 11 §11.10(g) — Authority checks.** Systems must use authority checks to ensure that only authorized individuals can use the system, electronically sign a record, access the operation or computer system input or output device, alter a record, or perform the operation at hand. NFR.5's write-path enforcement implements this: a proposal cannot transition to `approved` without recording the authority under which the transition was made.

**21 CFR Part 11 §11.70 — Signature/record linking.** Electronic signatures executed to electronic records shall be linked to their respective electronic records to ensure that the signatures cannot be excised, copied, or otherwise transferred to falsify an electronic record by ordinary means. Q1.R, Q5.F, and the E2E queries demonstrate this linkage by binding finding identity, proposal identity, approval, execution, and commit into a single queryable chain.

**WHO TRS 1033 Annex 4 §11.11 — Audit trail completeness.** An audit trail provides for secure recording of life-cycle details such as creation, additions, deletions or alterations of information in a record, either paper or electronic, without obscuring or overwriting the original record. NFR.4 implements this for the subsume/dedup path: a subsumed finding is not a deleted finding; it is a superseded finding whose superseder must be recorded.

**ALCOA+ — Attributable, Complete, Traceable.** The chain as a whole satisfies these three attributes when the Band B acceptance criteria are met. "Attributable" is satisfied edge-by-edge (Q1–Q6). "Complete" is satisfied by NFR.4 (no silent resolutions). "Traceable" is satisfied by E2E.F and E2E.R (end-to-end walkability).

---

## 8. References

- Investigation: `.specs/state/2026-04-25-consequence-chain-mapping.md`
- Plan: `.specs/planning/BAND-B-consequence-chain-plan.md`
- Issues: #110 (epic), #145, #146, #147, #148; #124 (related, outside Band B). Two new milestone-14 issues required by this URS — see §9.
- ADRs: ADR-011 (worker-only INSERTs — attribution principle), ADR-013 (legacy table retirement)
- Regulatory: 21 CFR Part 11 (eCFR title 21 part 11); WHO TRS 1033 Annex 4 (Guideline on data integrity); ALCOA+ as defined in WHO TRS 996 Annex 5

---

## 9. Plan-doc consequences

This URS revision changes two items previously listed as "proposed" in the plan-doc §4.2 into Band B requirements:

- **Subsume-path attribution** (formerly proposed issue D) is now required by NFR.4. Open as a milestone-14 issue with closure criteria tied to NFR.4.
- **Approval authority** (formerly D1 open decision) is now required by Q2.A and NFR.5. Open as a new milestone-14 issue with closure criteria tied to those requirements.

The plan-doc §4.2 should be updated to reflect this — moving D from "proposed" to "open issue against milestone 14", and adding the new approval-authority issue to the same list. This URS does not edit the plan-doc; that is a separate file change.
