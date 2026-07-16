---
kind: adr
id: ADR-150
title: 'ADR-150 — The finalizing roll-forward is bounded: cap, escalation, and the terminal that stays earned'
status: accepted
---

<!-- path: .specs/decisions/ADR-150-finalizing-redrive-cap.md -->

# ADR-150 — The finalizing roll-forward is bounded: cap, escalation, and the terminal that stays earned

**Status:** Accepted — 2026-07-16
**Date:** 2026-07-16
**Grounds:** NorthStar — *"Defensibility outranks productivity"*; ADR-148 D4 (the bound this
implements) and D6 (the deferral this preserves); ADR-104 D3/D9 (the abandon-at-cap rail this
extends to a third loop).
**Relates:** ADR-148 (finalization barrier — this closes its one declared-but-unimplemented
clause); ADR-104 D3 (`reclaim_cap_n`) and D9 (`remediation_cap_n`) — the two existing
instances of the rail; ADR-091 D2 (`resolution_mechanism` vocabulary); the blocking rule
`architecture.blackboard.indeterminate_requires_human_mechanism` (the escalation shape this
rides on). Tracking: #802 (external review 2026-07-16, finding T1; epic #799).
**Supersedes:** nothing. One citation in ADR-148 D4 is corrected via append-only note (see D4
below); the decision itself stands.

---

## Context

### A declared bound that was never built

ADR-148 D4 states the `stuck_finalizing` roll-forward is *"Bounded per the ADR-070 D8 cap."*
Verified against source (2026-07-16, `af5d7549`): **no such bound exists on that path.**

- `ProposalPipelineShopManager._roll_forward_finalizing` is fail-soft by design — *"any step
  failing leaves the proposal finalizing and the finding open; the next cycle retries"* — with
  no attempt counter, no cap check, and no escalation beyond the standing finding.
- `ProposalSupervisionService.fetch_stuck_finalizing` selects purely on
  `status='finalizing' AND execution_completed_at < :cutoff` — a permanently failing proposal
  is re-selected every cycle, forever.
- `WorkerProposalPipelineShopConfig` carries no cap field for this loop (contrast
  `remediation_cap_n: int = 3`).
- The one cap that does exist in this pipeline (`remediation_cap_n`, ADR-104 D9) fires on the
  failure-side **revival** path — a path the roll-forward, which by design never fails the
  proposal, cannot reach.

So a single poison proposal — e.g. `record_consequence` failing durably for a data reason —
sits in `finalizing` indefinitely, redriven every cycle, re-flagged every cycle by its own
`proposal.stuck_finalizing` finding, with no governed disposition. (Note
`governance.proposal_finalization_integrity` does **not** see it — that rule fires only on
`completed` rows missing a consequence record; the standing finding is the sole signal.) An
unresolvable governed state is itself undefensible; the bound ADR-148 D4 promised is the
missing rail.

### The citation was also wrong

ADR-148 D4 cites *"the ADR-070 D8 cap."* ADR-070 D8 is the `repo_artifacts ↔ filesystem`
projection delivery — it contains no retry cap. The rail D4 plainly meant is **ADR-104's
abandon-at-cap principle**: D3 caps the orphaned-claim loop (`reclaim_cap_n`), and D9 — with
the governor's own words, *"ADR-104's rail covers any finding that loops on failure, not just
orphaned claims"* — extends it to the remediation-failure loop (`remediation_cap_n`). The
finalizing redrive loop is the third loop of exactly that family. This ADR implements it as
such and corrects the citation trail.

### What the evidence does — and does not — support

Queried live (2026-07-16): **zero** proposals in `finalizing`, **zero** `stuck_finalizing`
findings ever posted, **zero** post-barrier `completed` rows missing
`consequence_recorded_at`. Permanent finalization failure has never been observed.

That cuts both ways, and the decision below honors both edges:

- The **bound** is required by analysis, not incident: unbounded retry is a structural gap
  regardless of whether it has fired yet (the same reasoning that shipped D3 and D9 before
  their loops spun in production).
- The **terminal state** stays deferred: ADR-148 D6's bar — *"build the state when the
  evidence for it exists, not before"* — is still unmet. Zero observed permanent failures is
  zero evidence for a terminal's shape. Minting `finalization_failed` today would be exactly
  the speculative state D6 refused.

---

## Decisions

**D1 — The redrive loop gets the ADR-104 rail: counter + cap, own knob — incremented in
place on the single persistent finding.** The `proposal.stuck_finalizing` finding's payload
tracks `finalization_redrive_count`, updated **in place** on that proposal's one open
finding (the shop manager already holds the handle: its `existing` subject → entry_id map)
on each roll-forward attempt that fails to advance the proposal (attempts that *succeed*
end the loop by completing the proposal). In-place is safe **here** because this finding
never renews while the proposal stays stuck — verified lifecycle: the fetch predicate
(`execution_completed_at < cutoff`) is monotonic, so a stuck proposal is re-selected every
cycle; a flagged subject is skipped by the dedup guard (`if subject in existing: continue`)
rather than re-posted; and the resolve pass only resolves subjects *not* flagged this
cycle. One finding, held open, no renewal window — so there is nothing for a renewal to
launder. This is deliberately **not** D9's counter-inheritance mechanism
(`query_max_remediation_attempt_count`): that seed-from-history exists because remediation
findings are *abandoned and renewed* across attempts; its query filters
`status = 'abandoned'`, a status a `self_resolve` `stuck_finalizing` finding never reaches
— inherited unadapted, it would read `COALESCE(…) → 0` every cycle and the cap would never
trip. The count legitimately resets to zero only when the proposal leaves the stuck set and
a fresh finding is later posted — which is exactly D3's re-arm. New governed knob
`finalizing_redrive_cap_n: int = 3` on `WorkerProposalPipelineShopConfig` — reusing D3's
"tolerate two transient failures" calibration, but its own knob per D9's precedent: a
consequence chain that cannot be recorded is a distinct phenomenon from a crashing worker
or a perpetually-failing generation, and may want independent tuning.

**D2 — At cap: stop redriving, escalate to the governor inbox; the proposal stays
`finalizing`.** When the count reaches the cap, the shop manager (a) stops selecting the
proposal for redrive, and (b) transitions the `stuck_finalizing` finding to
`status='indeterminate'` with `resolution_mechanism='human'` — the governed escalation shape
(`indeterminate_requires_human_mechanism` is already a blocking rule), which lands it in the
governor-inbox backlog that F-19's two-component clock counts. The payload carries
`proposal_id`, the final count, and the last step error. The at-cap exclusion keys on **the
open `indeterminate`/`human` `stuck_finalizing` finding for that proposal** — not a flag on
the proposal row — so D3's re-arm follows from resolving the finding alone, with no second
piece of state to clear. One load-bearing invariant is named here so it cannot be sawn off
silently: the escalation survives the shop manager's resolve pass (which auto-resolves any
`existing` finding not flagged this cycle) **only because** `_fetch_existing_findings` /
`fetch_open_findings` filters `status = 'open'` strictly — the `indeterminate` finding drops
out of `existing` at escalation. Broadening that fetch to include `indeterminate` findings
would re-expose escalations to the resolve pass and silently defeat the hand-to-human; the
D5 tests pin this by asserting the escalated finding survives subsequent manager cycles. The proposal row itself remains `finalizing`: post-commit, its
bytes are in git history, so it can be neither rolled back nor falsely completed — a
visible, bounded, human-owned pending state is the honest description of what it is. **No
new proposal status is introduced.**

**D3 — Human disposition re-arms or escalates to law.** Resolving the escalated finding
re-arms the rail: if the governor fixes the underlying cause, the next reaper cycle
re-detects `stuck_finalizing` fresh (new finding, count starts at zero) and the now-unblocked
redrive completes the proposal through the same guarded `mark_completed`. If instead the
governor judges the consequence chain genuinely unrecoverable, **that concrete case is the
evidence ADR-148 D6 was waiting for** — the terminal evidence-grade state then gets its own
decision, named from the EvidenceClass vocabulary per D6, with a real failure to shape it.
This ADR deliberately does not pre-empt that decision.

**D4 — Corrigendum to ADR-148 D4's citation (append-only).** ADR-148 receives a dated Note
under D4: *"the cap referenced as 'ADR-070 D8' is implemented by ADR-150 on the ADR-104
D3/D9 rail; ADR-070 D8 is an unrelated projection delivery — citation drift, not a changed
decision."* ADR-148's text otherwise stands verbatim per the append-only discipline
(ADR-074 D13 / ADR-080 §D5).

**D5 — The rail is enforced by fault injection, not declaration.** The change-set ships tests
that inject a persistently-failing evidence step and assert the properties that actually
hold in this lifecycle: the count **persists across cycles on the same open finding** (same
entry_id — the finding is not re-posted while the proposal stays finalizing); at
`finalizing_redrive_cap_n` the finding is `indeterminate`/`human` and no further redrive
occurs; the escalated finding **survives subsequent manager cycles** (the resolve pass must
not auto-clear it — the D2 invariant, pinned); the proposal remains `finalizing` and is
never `completed` nor `failed`; and the count **resets to zero only after a
resolve → re-detect** — the D3 re-arm path, exercised as its own case. This is the same tests-as-enforcement posture the ADR-148 change-set used
for the barrier itself.

---

## Implementation map (no constitutional-core surfaces)

| Surface | Authority | Change |
|---|---|---|
| operational config (`WorkerProposalPipelineShopConfig` + its `.intent` config source) | policy | add `finalizing_redrive_cap_n: int = 3` |
| `proposal_pipeline_shop_manager.py` | code | increment count on failed redrive; at-cap escalation + skip |
| `proposal_supervision_service.py` | code | exclude at-cap/escalated proposals from `fetch_stuck_finalizing` |
| blackboard finding transition (existing service surface) | code | `stuck_finalizing` finding → `indeterminate`/`human` at cap |
| `ADR-148` §D4 | specs | append-only corrigendum Note (D4 above) |
| tests (fault injection per D5) | — | new |

Deliberately **not** touched: `.intent/META/enums.json`, `Proposal.json`, the
`core.autonomous_proposals` CHECK constraint, `proposal_state_manager.py`'s guarded
transitions. The issue (#802) anticipated a `finalization_failed` terminal requiring all
four; the evidence review above is why this ADR lands smaller.

## Consequences

**Positive.** ADR-148 D4's declared bound becomes real, on the rail CORE already runs twice —
one knob, one payload counter, one escalation branch; no new state, no constitutional-core
edits. Exhaustion acquires a governed disposition (governor inbox) instead of an infinite
retry, and the F-19 backlog clock sees it instead of it hiding in worker logs. D6's
build-on-evidence bar is preserved, with the disposition path (D3) that will *produce* the
evidence if a permanent failure ever occurs.

**Costs / obligations.** A capped proposal parks in `finalizing` until a human acts — that is
the design: it is the only honest state for committed-but-unrecorded, and it is now visible
in the inbox rather than silent. The governor inbox gains a (rare) new entry class. If
permanent failures turn out to recur, the D6 follow-on decision becomes due — this ADR's D3
is the tripwire that says so.

## Verification note

Written after verifying against source at `af5d7549` and live state (2026-07-16): the
unbounded redrive, the missing cap field, the cutoff-only supervision query, and the
revival-path-only reach of `remediation_cap_n` are confirmed in
`proposal_pipeline_shop_manager.py` / `proposal_supervision_service.py` /
`operational_config.py`; the 0 / 0 / 0 live counts (finalizing rows, `stuck_finalizing`
findings, post-barrier completed-without-consequence) are from the production database. The
ADR-070 D8 mis-citation was confirmed by reading ADR-070 (its D8 is the
`repo_artifacts ↔ filesystem` delivery).

**Review passes on this draft (2026-07-16) — recorded because the counter mechanism flipped
twice, and the reason it settled matters more than the answer:**

- *Pass 1 (external review):* flagged that D9's durability comes from seed-from-history
  ("counter inheritance"), not increment-in-place, and D1 was revised to adopt it. The pass
  also added D2's explicit exclusion predicate (open `indeterminate`/`human` finding, not a
  proposal-row flag) and corrected the Context claim about
  `governance.proposal_finalization_integrity` (fires on `completed` rows only). Those two
  corrections stand.
- *Pass 2 (lifecycle read, both reviewers against source):* the inheritance revision was
  itself wrong for this loop. The `stuck_finalizing` finding does **not** renew while the
  proposal is stuck — monotonic fetch predicate, dedup guard skips re-post, resolve pass
  leaves flagged subjects open — so there is no renewal to launder an in-place count. And
  D9's seed query filters `status = 'abandoned'`, a status a `self_resolve` finding never
  reaches: inherited unadapted it reads 0 every cycle and the cap never trips, shipping the
  exact unbounded-redrive bug this ADR exists to kill, with a D5 test asserting a renewal
  that never happens. D1/D5 were reverted to in-place increment with the safety condition
  stated explicitly. The general lesson — match the counter mechanism to the finding's
  actual lifecycle (abandoned-and-renewed → inherit; held-open → increment in place) — is
  recorded for future rails.
