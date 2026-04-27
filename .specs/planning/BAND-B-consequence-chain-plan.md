<!-- path: .specs/planning/BAND-B-consequence-chain-plan.md -->

# CORE — Band B: Consequence Chain Plan

**Status:** Active
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-04-27 (#146 + #165 closed end-to-end; #135 closed; Edge 5 sibling opened; four Edge 1/3/6 children remain)
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

**Hygiene fix (2026-04-27, #135):** `BlackboardService.update_entry_status` was the fifth terminal-state write site, missed by commit `59ff25be`. Two workers (`ProposalConsumerWorker._mark_finding`, `ViolationRemediator._mark_finding`) routed through it and produced terminal rows with NULL `resolved_at`, distorting any query using `resolved_at` as a temporal filter (URS Q1.R / Q2.R / Q3.R / Q5.R / Q6.R / CONV.1). Fix landed; verified post-restart on 1,516 resolved transitions. Upstream of Band B query correctness.

---

## 3. Existing milestone state

Operational issue tracking lives on GitHub: https://github.com/DariuszNewecki/CORE/milestone/14

**Summary as of 2026-04-27:** seven issues at session-open; two closed earlier in the day (#146, #165 — Edge 2 forward-path attribution); one sibling opened this session for Edge 5 brittleness (orphan commits + 8-char prefix collisions); five Band B issues now remain (one epic + four children covering edges 1, 3, 6) plus the new Edge 5 sibling. Edge 4 ("yes per proposal; no cross-proposal") is an analytical convenience, not a chain integrity gap, and is not load-bearing for G3. Edge 5 brittleness is tracked across two issues: #124 (commit-message fidelity, Band D — different scope) and the new sibling on Band B (orphan commits + prefix collisions).

For the live issue list, current labels, and closing comments with verification artifacts, query GitHub directly. The milestone page is the authoritative surface; restating it here would go stale immediately.

---

## 4. Planning gap analysis

What the existing milestone does **not** cover, and which of those gaps need new artifacts before implementation begins versus which can be opened as issues during implementation.

### 4.1 Gating artifacts

**A. URS for the chain.** ✅ Committed at `.specs/requirements/URS-consequence-chain.md`. Adopts industry defaults (Part 11 §11.50, ALCOA+ Complete) for two scope decisions that surfaced during drafting.

**B. ADR for the chain design.** ✅ Committed at `.specs/decisions/ADR-015-consequence-chain-attribution.md`. Decides write paths and storage shapes for the children as seven coordinated sub-decisions (D1–D7). Forward-only enforcement; historical rows preserved per ALCOA "Complete." Implementation work for each child is scoped against specific Change sites named in the ADR. D2/D6/D7 implemented end-to-end 2026-04-27.

### 4.2 Proposed but not yet opened

- **C. Backfill of historical proposal_consequences.** 22 completed proposals exist with empty `findings_resolved` and empty `authorized_by_rules`. Some are reconstructable from finding payloads. Backfill is best-effort, separate from forward fixes, and should not block the Edge 1 children.
  - Proposed title: "Backfill historical proposal_consequences from finding payloads"
  - Proposed labels: `type:task`, `priority:medium`, `governance-debt`, milestone 14.
  - Sequencing: opens after Edge 1 lands (the population shape it back-fills must be settled first).

- **E. Edge 5 brittleness — resolved 2026-04-27.** Investigation named two failure modes (orphan commits and 8-char prefix collisions). #124 covers a third mode (commit-message fidelity), not these two. Sibling issue opened on Band B milestone covering orphan-commit detection and prefix-collision posture. #124 retains its original scope under Band D.

### 4.3 Out of scope for Band B

- **Edge 4 cross-proposal queries.** Analytical, not load-bearing for G3.
- **`core.audit_findings` table population.** That table is empty in the autonomous path because the daemon does not invoke the CLI ingest; sensors post directly to the blackboard. Not a chain gap — a different surface.
- **Cognitive-task schema (`core.proposals`, `core.tasks`, `core.actions`).** Retired by ADR-013; `core.proposal_signatures` was not named in ADR-013 — confirm it's covered or open a follow-up.
- **Non-proposal resolution causes** (file deleted, rule retired, scope changed). Captured in URS §6 as a follow-up after Band B closes if CONV.1 shows distortion.
- **Dev.to article.** Band E. Deferred until G3 closes.

---

## 5. Sequencing

Strict ordering for the gating artifacts; the remaining children may run in parallel.

```
A. URS                           ✅ committed 2026-04-27
   |
   v
B. ADR-015                       ✅ committed 2026-04-27
   |
   +---+---+---+---+---+---+
   |   |   |   |   |   |   |
   v   v   v   v   v   v   v
   Edge 1   Edge 2 (forward)   Edge 3   Edge 5 (sibling)   Edge 6
   (open)   ✅ closed 2026-04-27 (open) (open)             (open)
   |
   v
C. Backfill                      (after Edge 1 lands; scope bounded by
                                  ADR-015 D7 — findings_resolved only,
                                  authorized_by_rules permanently empty
                                  for pre-ADR rows)
   |
   v
Verification: G3 closure         (queryable causality chain end-to-end;
                                  closes epic on GitHub)
```

E (#124 confirmation) was a one-turn read at session-open and is now resolved (sibling opened); not a sequencing node.

---

## 6. Closure criteria for Band B

Band B closes (G3 cleared) when **all** of the following hold:

1. URS (artifact A) committed and reviewed. ✅
2. ADR-015 (artifact B) accepted. ✅
3. All Band B child issues on milestone 14 closed with verification queries demonstrating the edge they fixed. **Partial: Edge 2 forward-path closed 2026-04-27; Edges 1, 3, 5 (sibling), 6 remain.**
4. The URS query patterns run end-to-end against live data — specifically Q1.F, Q1.R, Q2.F, Q2.R, Q2.A, Q3.F, Q3.R, Q5.F, Q5.R, Q6.F, Q6.R, E2E.F, E2E.R as defined in `.specs/requirements/URS-consequence-chain.md` §3. **Partial: Q2.A and Q2.F demonstrable end-to-end; others depend on remaining children.**
5. CONV.1 returns a sustained resolution_ratio ≥ 1.0 over a representative window (URS §3 CONV.1, §5 acceptance criterion 3). **Pending — observation criterion; daemon must run with all remaining children landed. `resolved_at` hygiene confirmed via #135 fix on 2026-04-27.**
6. NFR.5 enforcement verified: write-path rejects `status='approved'` without `approval_authority` (URS §5 acceptance criterion 4). ✅ Verified 2026-04-27 — application layer (ValueError on falsy/unknown) and structural layer (DB CHECK) both exercised by the test surface committed in this band's work.
7. A representative chain trace from a recent autonomous round-trip is referenced from the closing comment of the relevant issue (mirrors SESSION-PROTOCOL.md's GitHub-as-record posture). ✅ Demonstrated 2026-04-27 for Edge 2 — verification artifact `proposal_id ac118b56-a47e-4839-9812-7834d6f18feb` on core, full lifecycle approved → executing → failed with attribution preserved through `mark_failed`. Each remaining child's closing comment carries its own end-to-end trace at closure.
8. A3 plan-doc updated: G3 row reflects sustained closure; Band B milestone closed on GitHub. **Pending — partial Band B progress reflected in this revision; full migration of G3 row to "Demonstrated" awaits remaining children.**

Backfill (C) is not a Band B blocker — it is governance debt addressed during the band but allowed to slip past closure if needed.

---

## 7. What this plan does not do

- It does not specify the chain's schema. That is ADR-015's job.
- It does not specify query syntax. That is the URS's job.
- It does not order work inside individual child issues. Each child carries its own scope and acceptance criteria in its GitHub issue body.
- It does not enumerate live issue state. GitHub milestone 14 is the authoritative surface.
- It does not address the broader two-log framing in Daniel's sense (consequence log extending to human-induced actions outside CORE's perimeter). That framing motivated the gap; closing the *internal* chain (this plan) is the prerequisite for any later work on the *external* chain.

---

## 8. Next action

Edges 1, 3, 6 remain (four child issues), plus the Edge 5 sibling opened 2026-04-27. The four Edge 1/3/6 children are independently scoped per their issue bodies and ADR-015's named Change sites; no further coordination binds them like ADR-015 D6 bound the Edge 2 pair. The Edge 5 sibling is governance-shaped (ADR before code) and runs in parallel. Lead selection is a session-open decision per SESSION-PROTOCOL.md §3 Step 5.
