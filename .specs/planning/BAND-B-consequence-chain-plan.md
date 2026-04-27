<!-- path: .specs/planning/BAND-B-consequence-chain-plan.md -->

# CORE — Band B: Consequence Chain Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-27 (revised after URS commit; #164 and #165 opened)
**Scope:** Materialize the Finding → Proposal → Approval → Execution → File changes → New findings causality chain as a queryable graph.
**Closes:** G3 (Phase 5).

---

## 1. Why this exists

CORE keeps records of what was *observed* (Blackboard findings) and what was *decided/executed* (proposals, audit JSON, git history). The edges between them are partial, asymmetric, or absent. Given a finding, no query answers "what happened because of you?"; given a file change, no query answers "which finding caused you?". The data largely exists; the relations do not.

This is the operational form of the "two-log problem" — the term that surfaced from two independent angles in March-April 2026:
- Daniel Nwaneri's piece on induced authorization in AI agents (action log exists, consequence log doesn't).
- A GxP-flavored risk analysis that bumped into the same gap from the regulated-environments side (audit trail must link who-did-what to which-record-changed-when).

Three downstream consequences make this a Band-defining gap rather than a quality-of-life improvement:
- **G2 cannot be measured truthfully.** Convergence rate ("resolutions exceed creations") infers resolution from timestamps, not from asserted causation.
- **G1 cannot be *proved*** without the chain even when it works. A successful round-trip is reconstructed across three tables and a git log; it is not queried.
- **A non-programmer governor cannot supervise** without reading code. Trust requires the chain.

---

## 2. Baseline (the investigation)

`.specs/state/2026-04-25-consequence-chain-mapping.md` is the authoritative baseline. Summary table from the investigation:

| Edge | Persisted? | Attributed? | Read-path? |
|---|---|---|---|
| 1. Finding → Proposal | partial | partial (asymmetric) | partial (reverse only via finding payload) |
| 2. Proposal → Approval | partial (columns exist, rarely populated) | partial (no rule/authority) | yes (when populated) |
| 3. Approval → Execution claim | partial (status only) | no (no claimer attribution) | no |
| 4. Execution → AtomicAction dispatch | yes (in-row jsonb) | partial (per-row, not cross-row) | yes per proposal; no cross-proposal |
| 5. Execution → File changes | yes | yes (freeform commit-message + DB) | yes (brittle: orphan commits, prefix-only) |
| 6. File changes → New findings | yes (finding row) | **no** | **no** |

Two cross-cutting patterns dominate: asymmetric attribution (link on one side only) and schema-without-population (columns exist but aren't written by the autonomous path).

---

## 3. Existing milestone state

**Milestone 14 — Band B — Consequence Chain.** Seven issues open as of 2026-04-27:

| Issue | Edge | Title | Notes |
|---|---|---|---|
| #110 | epic | Consequence chain not materialized (two-log problem) | Strategic container. Closure criteria in body. |
| #145 | 1 | Populate finding_ids on autonomously-drafted proposals | Closes proposal-side asymmetry; unblocks `proposal_consequences.findings_resolved`. |
| #146 | 2 | Route autonomous approval through ProposalStateManager | Populates `approved_by`/`approved_at` on the auto-approved path. |
| #147 | 3 | Record claimed_by worker_uuid on autonomous_proposals execution claim | Mirrors blackboard `claimed_by` pattern onto proposals. |
| #148 | 6 | Sensor cause attribution — thread proposal/commit context onto new findings | Closes the weakest edge end-to-end. |
| #164 | 1 | Subsume-path findings resolve without attribution to subsuming proposal | Required by URS NFR.4 (ALCOA+ "Complete" / WHO TRS 1033 §11.11). |
| #165 | 2 | Record approval_authority on autonomous_proposals; enforce non-omittable at write path | Required by URS Q2.A and NFR.5 (Part 11 §11.50 + §11.10(g)). |

The six children cover edges **1, 2, 3, 6**. Edge 4 ("yes per proposal; no cross-proposal") is an analytical convenience, not a chain integrity gap, and is not load-bearing for G3. Edge 5 brittleness is partially tracked outside Band B at issue #124 (autonomous commit-message fidelity).

---

## 4. Planning gap analysis

What the existing milestone does **not** cover, and which of those gaps need new artifacts before implementation begins versus which can be opened as issues during implementation.

### 4.1 Required before implementation

**A. URS for the chain.** ✅ **Committed 2026-04-27** at `.specs/requirements/URS-consequence-chain.md`. Adopts industry defaults (Part 11 §11.50, ALCOA+ Complete) for two scope decisions that surfaced during drafting; those decisions produced #164 and #165.

**B. ADR for the chain design.** Six issues each carry a small design decision (which column, which table, which write path). One umbrella ADR captures the cross-cutting design choice: are we adding edges to existing tables, materializing a separate causality table, or both? Without this, each child issue re-decides the same question and the six implementations may be inconsistent.

- **Artifact:** `.specs/decisions/ADR-015-consequence-chain-design.md`
- **Decision required from evidence:** which write path each edge takes; whether the read paths the URS specifies can be satisfied by the existing schema's population gaps alone, or require new structure.
- **Inputs to the ADR:** the URS (artifact A), the investigation's edge table, and the live schema as inspected during ADR drafting. No pre-decided default.

### 4.2 Required by URS — opened 2026-04-27

These two issues are Band B blockers, not optional adjuncts. They are listed here separately because they entered the milestone after URS revision, not as part of the original four children.

- **#164 — Subsume-path attribution.** Required by URS NFR.4. Findings resolved on the dedup/subsume path must carry the subsuming proposal's `proposal_id` in their payload. Closure criteria on issue body.
- **#165 — Approval authority.** Required by URS Q2.A and NFR.5. Every approved proposal carries an `approval_authority` value, write-path enforced. Closure criteria on issue body.

### 4.3 Proposed but not yet opened

- **C. Backfill of historical proposal_consequences.** 22 completed proposals exist with empty `findings_resolved` and empty `authorized_by_rules`. Some are reconstructable from finding payloads. Backfill is best-effort, separate from forward fixes, and should not block #145.
  - Proposed title: "Backfill historical proposal_consequences from finding payloads"
  - Proposed labels: `type:task`, `priority:medium`, `governance-debt`, milestone 14.
  - Sequencing: opens after #145 lands (the population shape it back-fills must be settled first).

- **E. Edge 5 brittleness — confirmation against #124.** The investigation names two failure modes (orphan commits and 8-char prefix collisions) and references #124. Worth a one-turn check: does #124's closure criteria cover both modes, or only commit-message fidelity? If only the latter, a sibling issue is warranted.
  - Action: read #124 body, confirm or open sibling.

### 4.4 Out of scope for Band B

- **Edge 4 cross-proposal queries.** Analytical, not load-bearing for G3.
- **`core.audit_findings` table population.** That table is empty in the autonomous path because the daemon does not invoke the CLI ingest; sensors post directly to the blackboard. Not a chain gap — a different surface.
- **Cognitive-task schema (`core.proposals`, `core.tasks`, `core.actions`).** Retired by ADR-013; `core.proposal_signatures` was not named in ADR-013 — confirm it's covered or open a follow-up.
- **Non-proposal resolution causes** (file deleted, rule retired, scope changed). Captured in URS §6 as a follow-up after Band B closes if CONV.1 shows distortion.
- **Dev.to article.** Band E. Deferred until G3 closes.

---

## 5. Sequencing

Strict ordering for the gating artifacts; the six children may run in parallel after the ADR lands.

```
A. URS                           ✅ committed 2026-04-27
   |
   v
B. ADR-015                       (gates implementation)
   |
   +---+---+---+---+---+---+
   |   |   |   |   |   |   |
   v   v   v   v   v   v   v
  #145 #146 #147 #148 #164 #165   (parallel; #148 has soft dependency on #145
                                    for the proposal_id thread)
   |
   v
C. Backfill                      (after #145 lands, since the population
                                  shape it back-fills must be settled first)
   |
   v
Verification: G3 closure         (queryable causality chain end-to-end;
                                  closes epic #110)
```

E (#124 confirmation) happens at session-open as a one-turn read, not as a sequencing node.

---

## 6. Closure criteria for Band B

Band B closes (G3 cleared) when **all** of the following hold:

1. URS (artifact A) committed and reviewed. ✅
2. ADR-015 (artifact B) accepted.
3. Issues #145, #146, #147, #148, #164, #165 closed with verification queries demonstrating the edge they fixed.
4. The URS query patterns run end-to-end against live data — specifically Q1.F, Q1.R, Q2.F, Q2.R, Q2.A, Q3.F, Q3.R, Q5.F, Q5.R, Q6.F, Q6.R, E2E.F, E2E.R as defined in `.specs/requirements/URS-consequence-chain.md` §3.
5. CONV.1 returns a sustained resolution_ratio ≥ 1.0 over a representative window (URS §3 CONV.1, §5 acceptance criterion 3).
6. NFR.5 enforcement verified: write-path rejects `status='approved'` without `approval_authority` (URS §5 acceptance criterion 4).
7. A representative chain trace from a recent autonomous round-trip is captured as a verification artifact (markdown under `.specs/state/`) and referenced from the epic close (URS NFR.3).
8. A3 plan-doc updated: G3 row moved to "Demonstrated"; Band B milestone closed; Resolved Blockers row added.

Backfill (C) is not a Band B blocker — it is governance debt addressed during the band but allowed to slip past closure if needed.

---

## 7. What this plan does not do

- It does not specify the chain's schema. That is ADR-015's job.
- It does not specify query syntax. That is the URS's job.
- It does not order work inside individual child issues. Each child carries its own scope and acceptance criteria in the GitHub issue body.
- It does not address the broader two-log framing in Daniel's sense (consequence log extending to human-induced actions outside CORE's perimeter). That framing motivated the gap; closing the *internal* chain (this plan) is the prerequisite for any later work on the *external* chain.

---

## 8. Next action

Author ADR-015 (artifact B). Inputs: the committed URS, the investigation edge table, and the live schema as inspected during ADR drafting. Decides write paths and storage shapes for the six children's combined effect. No pre-decided default; evidence-driven.
