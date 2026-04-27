<!-- path: .specs/planning/BAND-B-consequence-chain-plan.md -->

# CORE — Band B: Consequence Chain Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-27 (#146 + #165 closed end-to-end; four children remain)
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
| 2. Proposal → Approval | **yes (forward path)** ✅ | **yes (forward path)** ✅ | **yes (forward path)** ✅ |
| 3. Approval → Execution claim | partial (status only) | no (no claimer attribution) | no |
| 4. Execution → AtomicAction dispatch | yes (in-row jsonb) | partial (per-row, not cross-row) | yes per proposal; no cross-proposal |
| 5. Execution → File changes | yes | yes (freeform commit-message + DB) | yes (brittle: orphan commits, prefix-only) |
| 6. File changes → New findings | yes (finding row) | **no** | **no** |

**Edge 2 update (2026-04-27):** closed for the forward path by #146 + #165 landing. Approval attribution (`approved_by`, `approved_at`, `approval_authority`) is now non-omittable on every newly-approved proposal, enforced at both the application write-path (ProposalStateManager.approve raises ValueError on falsy/unknown authority) and the structural layer (DB CHECK constraint). The 159 historical pre-2026-04-27 rows remain NULL on these columns per ADR-015 D7 (ALCOA "Complete" — no synthesized backfill).

Two cross-cutting patterns dominate the remaining open edges: asymmetric attribution (link on one side only) and schema-without-population (columns exist but aren't written by the autonomous path).

---

## 3. Existing milestone state

**Milestone 14 — Band B — Consequence Chain.** Five issues open as of 2026-04-27 (down from seven; #146 and #165 closed today).

| Issue | Edge | Title | Notes |
|---|---|---|---|
| #110 | epic | Consequence chain not materialized (two-log problem) | Strategic container. Closure criteria in body. |
| #145 | 1 | Populate finding_ids on autonomously-drafted proposals | Closes proposal-side asymmetry; unblocks `proposal_consequences.findings_resolved`. |
| ~~#146~~ | ~~2~~ | ~~Route autonomous approval through ProposalStateManager~~ | **Closed 2026-04-27.** Verification artifact: proposal_id `ac118b56-a47e-4839-9812-7834d6f18feb` on core. |
| #147 | 3 | Record claimed_by worker_uuid on autonomous_proposals execution claim | Mirrors blackboard `claimed_by` pattern onto proposals. |
| #148 | 6 | Sensor cause attribution — thread proposal/commit context onto new findings | Closes the weakest edge end-to-end. |
| #164 | 1 | Subsume-path findings resolve without attribution to subsuming proposal | Required by URS NFR.4 (ALCOA+ "Complete" / WHO TRS 1033 §11.11). |
| ~~#165~~ | ~~2~~ | ~~Record approval_authority on autonomous_proposals; enforce non-omittable at write path~~ | **Closed 2026-04-27.** Verification artifact: same proposal_id; Q2.A returns `risk_classification.safe_auto_approval`. |

The four remaining children cover edges **1, 3, 6**. Edge 4 ("yes per proposal; no cross-proposal") is an analytical convenience, not a chain integrity gap, and is not load-bearing for G3. Edge 5 brittleness is partially tracked outside Band B at issue #124 (autonomous commit-message fidelity).

---

## 4. Planning gap analysis

What the existing milestone does **not** cover, and which of those gaps need new artifacts before implementation begins versus which can be opened as issues during implementation.

### 4.1 Required before implementation

**A. URS for the chain.** ✅ **Committed 2026-04-27** at `.specs/requirements/URS-consequence-chain.md`. Adopts industry defaults (Part 11 §11.50, ALCOA+ Complete) for two scope decisions that surfaced during drafting; those decisions produced #164 and #165.

**B. ADR for the chain design.** ✅ **Committed 2026-04-27** at `.specs/decisions/ADR-015-consequence-chain-attribution.md`. Decides write paths and storage shapes for the six children as seven coordinated sub-decisions (D1–D7). Forward-only enforcement; historical rows preserved per ALCOA "Complete." Implementation work for each child is now scoped against specific Change sites named in the ADR.

### 4.2 Required by URS — opened 2026-04-27

These two issues are Band B blockers, not optional adjuncts. They are listed here separately because they entered the milestone after URS revision, not as part of the original four children.

- **#164 — Subsume-path attribution.** Required by URS NFR.4. Findings resolved on the dedup/subsume path must carry the subsuming proposal's `proposal_id` in their payload. Closure criteria on issue body.
- ~~#165 — Approval authority.~~ **Closed 2026-04-27.** See §3 row.

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

Strict ordering for the gating artifacts; the remaining four children may run in parallel.
