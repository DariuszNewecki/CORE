<!-- path: .specs/planning/BAND-B-consequence-chain-plan.md -->

# CORE — Band B: Consequence Chain Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-27
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

**Milestone 14 — Band B — Consequence Chain.** Five issues open as of 2026-04-26:

| Issue | Edge | Title | Notes |
|---|---|---|---|
| #110 | epic | Consequence chain not materialized (two-log problem) | Strategic container. Closure criteria in body. |
| #145 | 1 | Populate finding_ids on autonomously-drafted proposals | Closes proposal-side asymmetry; unblocks `proposal_consequences.findings_resolved`. |
| #146 | 2 | Route autonomous approval through ProposalStateManager | Populates `approved_by`/`approved_at` on the auto-approved path. |
| #147 | 3 | Record claimed_by worker_uuid on autonomous_proposals execution claim | Mirrors blackboard `claimed_by` pattern onto proposals. |
| #148 | 6 | Sensor cause attribution — thread proposal/commit context onto new findings | Closes the weakest edge end-to-end. |

The four children cover edges **1, 2, 3, 6**. Edge 4 ("yes per proposal; no cross-proposal") is an analytical convenience, not a chain integrity gap, and is not load-bearing for G3. Edge 5 brittleness is partially tracked outside Band B at issue #124 (autonomous commit-message fidelity).

---

## 4. Planning gap analysis

What the existing milestone does **not** cover, and which of those gaps need new artifacts before implementation begins versus which can be opened as issues during implementation.

### 4.1 Required before implementation

**A. URS for the chain.** Implementation cannot start without a written contract for what queries the chain must answer. The four children are mechanical fixes; the URS is what makes them coherent as a set rather than four independent patches. Required because two of the three downstream consequences (G2 measurement, governor supervision) are query-shaped, not write-shaped — the URS is what asserts the read path is in scope.

- **Artifact:** `.specs/requirements/URS-consequence-chain.md`
- **Owner:** governor (architect drafts).
- **Length:** short. Half a page of query specifications, one page of acceptance criteria.

**B. ADR for the chain design.** Five issues each carry a small design decision (which column, which table, which write path). One umbrella ADR captures the cross-cutting design choice: are we adding edges to existing tables, materializing a separate causality table, or both? Without this, each child issue re-decides the same question and the four implementations may be inconsistent.

- **Artifact:** `.specs/decisions/ADR-015-consequence-chain-design.md`
- **Decision required from evidence:** which write path each edge takes; whether the read paths the URS specifies can be satisfied by the existing schema's population gaps alone, or require new structure.
- **Inputs to the ADR:** the URS (artifact A), the investigation's edge table, and the live schema as inspected during ADR drafting. No pre-decided default.

### 4.2 Open as issues now (additions to Milestone 14)

**C. Backfill of historical proposal_consequences.** 22 completed proposals exist with empty `findings_resolved` and empty `authorized_by_rules`. Some are reconstructable from finding payloads (finding payload still holds `proposal_id` for the deferred-to-proposal path). Not all are recoverable. Backfill is best-effort, separate from forward fixes, and should not block #145.

- **Proposed issue:** "Backfill historical proposal_consequences from finding payloads"
- **Labels:** `type:task`, `priority:medium`, `governance-debt`, milestone 14.

**D. Subsume-path attribution.** Investigation §"Explicit unverifieds" flags `_resolve_entries` (`violation_remediator.py:544`): findings resolved on the dedup/subsume path are marked `resolved` without recording the subsuming proposal id. This is a partial Edge-1 break the four children do not address.

- **Proposed issue:** "Subsume-path findings resolve without attribution to the subsuming proposal"
- **Labels:** `type:task`, `priority:medium`, `governance-debt`, milestone 14.

**E. Edge 5 brittleness — confirmation against #124.** The investigation names two failure modes (orphan commits and 8-char prefix collisions) and references #124. Worth a one-turn check: does #124's closure criteria cover both modes, or only commit-message fidelity? If only the latter, a sibling issue is warranted.

- **Action:** read #124 body, confirm or open sibling.

### 4.3 Out of scope for Band B

- **Edge 4 cross-proposal queries.** Analytical, not load-bearing for G3.
- **`core.audit_findings` table population.** That table is empty in the autonomous path because the daemon does not invoke the CLI ingest; sensors post directly to the blackboard. Not a chain gap — a different surface.
- **Cognitive-task schema (`core.proposals`, `core.tasks`, `core.actions`).** Retired by ADR-013; `core.proposal_signatures` was not named in ADR-013 — confirm it's covered or open a follow-up.
- **Dev.to article.** Band E. Deferred until G3 closes.

---

## 5. Sequencing

Strict ordering for the gating artifacts; the four children may run in parallel after the ADR lands.

```
A. URS                           (gates everything)
   |
   v
B. ADR-015                       (gates implementation)
   |
   +---+---+---+---+
   |   |   |   |   |
   v   v   v   v   v
  #146 #147 #145 #148    (parallel; #148 has soft dependency on #145
                          for the proposal_id thread)
   |
   v
C. Backfill                      (after #145 lands, since the population
                                  shape it back-fills must be settled first)
   |
   v
D. Subsume-path                  (independent; can run any time)
   |
   v
Verification: G3 closure         (queryable causality chain end-to-end;
                                  closes epic #110)
```

E (#124 confirmation) happens at session-open as a one-turn read, not as a sequencing node.

---

## 6. Closure criteria for Band B

Band B closes (G3 cleared) when **all** of the following hold:

1. URS (artifact A) committed and reviewed.
2. ADR-015 (artifact B) accepted.
3. Issues #145, #146, #147, #148 closed with verification queries demonstrating the edge they fixed.
4. The two query patterns from the URS run end-to-end against live data:
   - Forward: "given a finding, list every consequence" — single query, no application-side joining.
   - Reverse: "given a file change at SHA X, list the finding that caused it and the rule that authorized the change" — single query.
5. A representative chain trace from a recent autonomous round-trip is captured as a verification artifact (markdown under `.specs/state/`) and referenced from the epic close.
6. A3 plan-doc updated: G3 row moved to "Demonstrated"; Band B milestone closed; Resolved Blockers row added.

Backfill (C) and subsume-path (D) are not Band B blockers — they are governance debt addressed during the band but allowed to slip past closure if needed.

---

## 7. What this plan does not do

- It does not specify the chain's schema. That is ADR-015's job.
- It does not specify query syntax. That is the URS's job.
- It does not order work inside individual child issues. Each child carries its own scope and acceptance criteria in the GitHub issue body.
- It does not address the broader two-log framing in Daniel's sense (consequence log extending to human-induced actions outside CORE's perimeter). That framing motivated the gap; closing the *internal* chain (this plan) is the prerequisite for any later work on the *external* chain.

---

## 8. Next action

Author URS (artifact A). Draft target ~one page; reviewed against the investigation's edge table and the closure criteria above before ADR-015 begins.
