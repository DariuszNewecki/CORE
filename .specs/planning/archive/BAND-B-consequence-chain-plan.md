<!-- path: .specs/planning/BAND-B-consequence-chain-plan.md -->

# CORE — Band B: Consequence Chain Plan

**Status:** Closed
**Owner:** Darek (Dariusz Newecki)
**Last updated:** 2026-05-01 (Band B closed — #148 and #166 closed; ADR-019 shipped; Edges 5 and 6 closed; epic #110 closed)
**Scope:** Materialize the Finding → Proposal → Approval → Execution → File changes → New findings causality chain as a queryable graph.
**Closes:** G3 (Phase 5). ✅

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

`.specs/state/2026-04-25-consequence-chain-mapping.md` is the authoritative baseline. Summary table from the investigation, updated to final state:

| Edge | Persisted? | Attributed? | Read-path? |
|---|---|---|---|
| 1. Finding → Proposal | **yes** ✅ | **yes** ✅ | **yes** ✅ |
| 2. Proposal → Approval | **yes (forward path)** ✅ | **yes (forward path)** ✅ | **yes (forward path)** ✅ |
| 3. Approval → Execution claim | **yes** ✅ | **yes** ✅ | **yes** ✅ |
| 4. Execution → AtomicAction dispatch | yes (in-row jsonb) | partial (per-row, not cross-row) | yes per proposal; no cross-proposal |
| 5. Execution → File changes | yes | yes ✅ | yes ✅ (ADR-019: orphan detection + prefix widened to 16 chars) |
| 6. File changes → New findings | yes ✅ | **yes** ✅ | **yes** ✅ |

**Edge 2 update (2026-04-27):** closed for the forward path by #146 + #165 landing. Approval attribution (`approved_by`, `approved_at`, `approval_authority`) is now non-omittable on every newly-approved proposal, enforced at both the application write-path (ProposalStateManager.approve raises ValueError on falsy/unknown authority) and the structural layer (DB CHECK constraint). The 159 historical pre-2026-04-27 rows remain NULL on these columns per ADR-015 D7 (ALCOA "Complete" — no synthesized backfill).

**Edge 3 update (2026-04-28):** closed by #147 + ADR-017 (commits 6ee9c7c5 + 2136ffb6). Approval→execution claim attribution is now non-omittable on every newly-claimed proposal, populated via the `claim.proposal` atomic action. Autonomous workers thread `self.worker_uuid`; CLI claims thread `CLI_CLAIMER_UUID = '00000000-0000-0000-0000-000000000001'` per ADR-017 D4.

**Edge 5 update (2026-05-01):** closed by #166 + ADR-019 (commit 61f9671b). Orphan-commit detection via `CommitReachabilityAuditor` (new sensing worker); prefix widened from `proposal_id[:8]` to `proposal_id[:16]` at both execute sites in `src/will/autonomy/proposal_executor.py`. `post_execution_sha` declared authoritative Edge 5 link per ADR-019 D3.

**Edge 6 update (2026-05-01):** closed by #148 (commit 0aeb7e90). `AuditViolationSensor` now consults `ConsequenceLogService.find_cause_for_file()` per violation and threads `causing_proposal_id`, `causing_commit_sha`, `cause_attribution` into every new finding payload. URS Q6.F and Q6.R read paths implemented. ADR-015 D5.

**Hygiene fix (2026-04-27, #135):** `BlackboardService.update_entry_status` was the fifth terminal-state write site, missed by commit `59ff25be`. Fix landed; verified post-restart on 1,516 resolved transitions. Upstream of Band B query correctness.

---

## 3. Existing milestone state

Operational issue tracking lives on GitHub: https://github.com/DariuszNewecki/CORE/milestone/14

**Summary as of 2026-05-01:** Band B closed. Epic #110 closed 2026-05-01. All child edges delivered. Milestone 14 closed on GitHub.

---

## 4. Planning gap analysis

### 4.1 Gating artifacts

**A. URS for the chain.** ✅ Committed at `.specs/requirements/URS-consequence-chain.md`.

**B. ADR-015 for the chain design.** ✅ Committed at `.specs/decisions/ADR-015-consequence-chain-attribution.md`. All seven sub-decisions (D1–D7) implemented.

**C. ADR-019 for Edge 5 posture.** ✅ Committed at `.specs/decisions/ADR-019-edge5-git-boundary-attribution-posture.md`. Orphan detection and prefix widening delivered.

### 4.2 Governance debt carried forward

- **Backfill of historical proposal_consequences.** 22 completed proposals exist with empty `findings_resolved` and empty `authorized_by_rules`. Tracked as governance debt; not a Band B blocker per original closure criteria. Re-evaluate under Band C.

### 4.3 Out of scope for Band B (unchanged)

- Edge 4 cross-proposal queries. Analytical, not load-bearing for G3.
- `core.audit_findings` table population. Different surface.
- Non-proposal resolution causes. URS §6 follow-up.
- Dev.to article. Band E.

---

## 5. Sequencing

All edges closed.

```
A. URS                           ✅ committed 2026-04-27
B. ADR-015                       ✅ committed 2026-04-27
   |
   Edge 1                        ✅ closed 2026-04-27
   Edge 2 (forward)              ✅ closed 2026-04-27
   Edge 3                        ✅ closed 2026-04-28 (ADR-017)
   Edge 5 (sibling)              ✅ closed 2026-05-01 (ADR-019, commit 61f9671b)
   Edge 6                        ✅ closed 2026-05-01 (commit 0aeb7e90)
   |
C. Backfill                      governance debt — Band C candidate
   |
G3 closure                       ✅ 2026-05-01 — epic #110 closed
```

---

## 6. Closure criteria for Band B

Band B closed 2026-05-01. All criteria met:

1. URS (artifact A) committed and reviewed. ✅
2. ADR-015 (artifact B) accepted. ✅
3. All Band B child issues on milestone 14 closed. ✅
4. URS query patterns Q1.F, Q1.R, Q2.F, Q2.R, Q2.A, Q3.F, Q3.R, Q6.F, Q6.R implemented. ✅ Q5.F, Q5.R, E2E.F, E2E.R demonstrable via the structured columns now populated.
5. CONV.1 sustained measurement pending — observation criterion; daemon running with all children landed. `resolved_at` hygiene confirmed via #135.
6. NFR.5 enforcement verified. ✅
7. Representative chain traces in closing comments of each child issue. ✅
8. A3 plan-doc updated: G3 row updated to ✅. Band B milestone closed on GitHub. ✅

---

## 7. What this plan does not do

- It does not specify the chain's schema. That is ADR-015's job.
- It does not specify query syntax. That is the URS's job.
- It does not enumerate live issue state. GitHub milestone 14 is the authoritative surface.
- It does not address the broader two-log framing in Daniel's sense. Closing the internal chain (this plan) is the prerequisite for any later work on the external chain.
