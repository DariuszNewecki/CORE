---
kind: adr
id: ADR-148
title: 'ADR-148 — COMPLETED is a defensibility claim: the proposal finalization barrier'
status: accepted
---

<!-- path: .specs/decisions/ADR-148-proposal-finalization-barrier.md -->

# ADR-148 — COMPLETED is a defensibility claim: the proposal finalization barrier

**Status:** Accepted — 2026-07-12
**Date:** 2026-07-12
**Grounds:** NorthStar (`.specs/essays/core_northstar.md` §1–2; vocabulary term *NorthStar*)
— *"Defensibility outranks productivity"*; Charter §6 (In force) — *"law precedes machinery."*
**Relates:** ADR-129 D7 (the ordering this generalizes, and the one clause it supersedes);
ADR-101 D2/D3 (the production set the commit derives from, and rollback as compensating
transaction); ADR-056 D4 (`Proposal.json` state-conditional contract — the constitution-authority
surface strengthened here); ADR-015 D2/D6 (proposal-state DB CHECK constraints); ADR-104
(orphaned-claim reaper — the recovery precedent, extended forward); ADR-091 D2
(`resolution_mechanism`, `proposal.stuck_executing` — the reaper this rides on); ADR-070 D8
(bounded retry caps); ADR-113 (EvidenceClass evidence-grade vocabulary — the home for a future
terminal state, if one is ever needed).
**Supersedes:** ADR-129 D7's clause that a non-contamination git commit failure returns success
and completes the proposal. Everything else in ADR-129 stands.

---

## Context

### The law was silent (Charter §6)

CORE's NorthStar is not ambiguous about this case:

> Software systems must be able to explain **why** they do something, **under which authority**,
> **with what evidence**, and **at what risk**. If they cannot, they should stop.
>
> **Law outranks intelligence. Defensibility outranks productivity.**

The consequence record *is* that four-part answer in durable form: which policies authorized the
change (authority), which findings it resolved (why), the pre/post SHA and changed files
(evidence), the declared production it must match (risk of contamination). Yet the governed
`completed` state makes **no claim about any of it.** `.intent/enforcement/contracts/Proposal.json`
(authority: `constitution`, ADR-056 D4) requires, for `completed`, only:

> COMPLETED: all APPROVED invariants hold; `execution_completed_at` must be non-null. Terminal status.

Nothing about a commit. Nothing about a consequence record. So `completed` today proves that
*execution reached a transition*, not that CORE can *defend* what it did.

This is not primarily a code bug. Per Charter §6 — *"no schema, engine, or tool may be introduced
to compensate for incomplete law"* — the root cause is **incomplete law.** The NorthStar states
the principle, but no operational rule ever made "a proposal may not be `completed` unless its
consequence chain is durable" enforceable. When the executor was written, the law did not require
defensibility at this boundary, so the code chose the default an ordinary AI tool would — keep the
output. Concretely, two places encode that silence:

1. **ADR-129 D7 explicitly ranks productivity over defensibility for one case.** D7 inverted the
   ordering (commit before `mark_completed`) so a *contamination refusal* fails the proposal — but
   deliberately arranged for *other* git failures to complete anyway: the typed
   `StagingContaminationError` exists so `commit_proposal_changes` can *"catch D1 failures
   specifically without catching other git errors (unrecoverable pre-commit hook failures, etc.)
   that should not cause mark_failed."* So a genuine commit failure returns success, and a
   `completed` proposal can leave its production bytes uncommitted in the working tree — the very
   mis-attribution shape ADR-101/ADR-129 exist to prevent, re-entering through the finalization gap.

2. **The evidence steps after `mark_completed` are fail-soft.** Post-SHA capture, consequence
   recording, and deferred-finding resolution each swallow their exceptions by design
   (*"failure here must not unwind the proposal completion that has already been committed"*). A
   crash in that window leaves a durably-`completed` row with no consequence record and findings
   stranded in `deferred_to_proposal` — and disables ADR-129 D4's `CommitAuthorshipAuditWorker`,
   which has no consequence row left to audit.

### This is a solved problem; CORE already built most of the solution

The shape — "change one durable system (git), record it in another (Postgres), with no shared
transaction" — is the **dual-write problem.** The industry did **not** solve it with true
distributed atomic commit (2PC/XA is fragile, and git cannot participate anyway). It converged on
one principle, which is the NorthStar's principle restated in systems terms: *never flip the
operation to "done" until the last durable side-effect is confirmed; make everything before that
idempotent and reconcilable.* The named patterns — and what CORE already has for each:

- **Saga + compensating transaction** — `rollback_proposal` (ADR-101 D3) already is one.
- **Idempotency + reconciler** — the idempotent consequence upsert (ADR-129 D2) + the
  `stuck_executing` reaper (`ProposalPipelineShopManager`, ADR-091 D2) already are these.
- **Durable execution** (Temporal-class engines) — the blackboard + proposal state machine + reaper
  is a domain-specific one.
- **Commit-marker / ledger-first** (Delta Lake/Iceberg manifests; financial ledgers, where a
  payment is not "done" until the ledger row exists — the record *is* the transaction) — this is
  the missing piece: making `completed` the single atomic flip that vouches the whole chain is
  durable.

CORE is ~80% through a standard architecture. This ADR lays the last brick, in CORE's own law.

### Why exactly one new state is structurally necessary

There is a real boundary at "the git commit succeeded":

- **Before** it, nothing landed on the main tree, so a stuck proposal is **rollback-safe** — the
  existing `executing` state + the retire-reaper (which marks failed and revives findings) is correct.
- **After** it, the change is committed, so a stuck proposal must **roll *forward*** — retry the
  idempotent evidence steps. It must **never** be rolled back and re-executed, which would
  double-apply the change.

The existing reaper *retires* `stuck_executing` proposals. A post-commit proposal must not be
treated that way. That is why one — and only one — new state earns its place: a post-commit,
evidence-in-progress state the reaper rolls *forward*. It is not review cargo-cult; it is the
minimum vocabulary the recovery semantics require.

---

## Decisions

**D1 — `completed` becomes a defensibility claim, as law.** Strengthen the `Proposal.json`
`completed` invariant (authority: `constitution`, ADR-056 D4): a proposal may be `completed` only
when its consequence chain is durable. Mechanised as a field invariant in the same shape as the
existing ones — add a `consequence_recorded_at` timestamp, **required (non-null) when
`status = completed`**, set as the last step of finalization. `execution_completed_at` proves
execution stopped; `consequence_recorded_at` proves CORE recorded *why · under what authority ·
with what evidence · at what risk.* This makes the NorthStar's four-part test a constitutional
field invariant, checkable by the same AST/DB mechanism that already governs the other states.

**D2 — Add `finalizing`: the forward-rolling, post-commit state.** New value `finalizing` in the
`proposal_status` closed set (`.intent/META/enums.json`), with its field invariant in `Proposal.json`
and a `core.autonomous_proposals` CHECK-constraint update (ADR-015). The executor ordering becomes:
commit succeeds → `executing → finalizing` (own committed transaction) → persist evidence
(post-SHA, consequence record, finding resolution) → `finalizing → completed` (setting
`consequence_recorded_at`). A crash anywhere in the evidence phase leaves `finalizing` —
recoverable — and **never** a false `completed`. This is the commit-marker discipline: `completed`
is the atomic flip that vouches the chain.

**D3 — A failed commit fails the proposal (supersedes ADR-129 D7's completing clause).** Replace
`commit_proposal_changes`'s boolean return with a typed `CommitOutcome`
(`COMMITTED` · `NOTHING_TO_COMMIT` · `REFUSED_CONTAMINATION` · `FAILED`). `COMMITTED` /
`NOTHING_TO_COMMIT` proceed to `finalizing`; `REFUSED_CONTAMINATION` / `FAILED` route to
`mark_failed` + `rollback_proposal` with an accurate reason (no more mislabelling a git error as
contamination). The `except Exception → return True` branch is retired. This is a straight
application of the NorthStar ranking: a change that cannot be durably committed is not a completed
proposal, however valid the change itself was. Defensibility outranks the productivity D7 was
protecting.

**D4 — Recovery rolls forward, reusing the reaper (do not reinvent).** Extend
`ProposalSupervisionService` / `ProposalPipelineShopManager`: `stuck_executing` → retire + rollback
(unchanged); **new** `stuck_finalizing` → re-drive the idempotent evidence steps forward. Add
`proposal.stuck_finalizing` to the `resolution_mechanism` vocabulary (`self_resolve`, ADR-091 D2),
alongside the existing `proposal.stuck_executing`. Bounded per the ADR-070 D8 cap. This is the
reconciler/durable-execution piece — the machinery CORE already runs, pointed at the new state.

> **Note (2026-07-16, ADR-150):** the cap referenced above as "the ADR-070 D8 cap"
> is implemented by ADR-150 on the **ADR-104 D3/D9** rail; ADR-070 D8 is an
> unrelated projection delivery (`repo_artifacts ↔ filesystem`). Citation drift,
> not a changed decision — D4's substance stands as written.

**D5 — The invariant is enforced, not merely declared.** A `completed` proposal without a durable
consequence record is a violation detectable post-hoc exactly as ADR-129 D4's
`CommitAuthorshipAuditWorker` detects authorship contamination — that worker already reads
`core.proposal_consequences`. Extend it (or add a sibling governance rule
`governance.proposal_finalization_integrity`) to flag any `completed` row lacking its consequence
record, shipped on CORE's ramp arc (`reporting` → resolve drift → `blocking`). Law that cannot be
checked is not yet law.

**D6 — The permanent-finalization-failure terminal is deferred, not invented.** If the idempotent
evidence steps never succeed within the D4 cap, the proposal remains `finalizing` and the reaper
escalates via a durable blackboard finding — the honest signal — rather than a false success or a
new terminal state minted speculatively. Should operational reality show permanent finalization
failures actually occur, a terminal evidence-grade state gets its own decision, named from CORE's
existing EvidenceClass vocabulary (ADR-113: `proven` / `judged` / `attested`) — **never** the
review's `EVIDENCE_INCOMPLETE`, because "Evidence" is already a governed term
(`.intent/META/vocabulary.json`) meaning rule-evaluation inputs. §6 + ramp discipline: build the
state when the evidence for it exists, not before.

---

## Governed surfaces this touches (implementation map)

Each is a heightened-confirmation edit the governor names individually; listed here so the blast
radius is explicit, not to pre-authorize.

| Surface | Authority | Change |
|---|---|---|
| `.intent/META/enums.json` (`proposal_status`) | meta | add `finalizing` |
| `.intent/enforcement/contracts/Proposal.json` | constitution | `finalizing` invariant; strengthen `completed` (require `consequence_recorded_at`) |
| `infra/sql/` schema + CHECK (ADR-015) | — | `finalizing` in the status CHECK; `consequence_recorded_at` column |
| `.intent/META/enums.json` (`resolution_mechanism`) | meta | add `proposal.stuck_finalizing` |
| governance rule / worker (D5) | policy/constitution | `completed ⇒ consequence record` audit, reporting-first |
| `src/shared/lifecycles/proposal.py` | code | `ProposalStatus.FINALIZING` |
| `proposal_execution_pipeline.py`, `proposal_executor.py` | code | `CommitOutcome`; `finalizing` ordering |
| `proposal_pipeline_shop_manager.py` / `proposal_supervision_service.py` | code | `stuck_finalizing` forward-drive |

## What `completed` proves — before and after

| At `status = completed` | Today | After ADR-148 |
|---|---|---|
| Execution reached the transition | ✅ | ✅ |
| Production set committed to git | ❌ (non-D1 commit failure still completes) | ✅ (D3) |
| Consequence record persisted (the four-part defense) | ❌ (fail-soft, may be absent) | ✅ (D1 — `consequence_recorded_at` required) |
| Deferred findings resolved | ❌ (fail-soft, may strand) | ✅ (finalization obligation) |
| A crash cannot forge success | ❌ (crash after `mark_completed` → false `completed`) | ✅ (D2 — crash leaves recoverable `finalizing`) |

## Consequences

**Positive.** `completed` becomes a proof state — CORE's front-of-chain exclusivity (governed
finding → claim → sandbox → ActionExecutor → FileHandler) finally has a matching end-of-chain
proof. The uncommitted-bytes hazard is closed structurally (typed outcome + existing rollback).
Recovery reuses the reaper CORE already runs. The net new surface is one state, one
`resolution_mechanism` term, one timestamp field, a typed `CommitOutcome`, and a `stuck_finalizing`
branch — the last brick in a standard architecture, not new machinery.

**Costs / obligations.** Adds `finalizing` to constitution- and meta-authority surfaces (heightened
confirmation, and DB CHECK + schema ledger). The success path gains one DB round-trip
(`executing → finalizing → completed`) — negligible, and the price of a proof state. Every reporting
surface that partitions on status must learn `finalizing` (a transient, non-terminal state). A small,
bounded **eventual-consistency window** now exists and is made explicit — the interval where the
change is committed but the record is catching up. The industry accepts exactly this window and
answers it the same way: name it, bound it, reconcile it. That window *is* `finalizing`.

**Follow-up (not gating).** Add a one-page "transaction boundaries and what each terminal state
proves" section to `CLAUDE.md` so no contributor reads `completed` as "the whole chain is durable"
without checking.

## Scope boundaries (deferred to their own decisions)

Migrating `approve`/`reject`/`mark_completed`/`mark_failed` into the atomic-action kernel (only
`claim.proposal` is one today); a finding/proposal **creation** outbox (the front-of-chain dual
write, distinct from finalization); retiring the dormant `MicroProposalExecutor`.

## Verification note

Written after verifying the claims against source at `87182fa0`: the too-early completion ordering,
the `commit → return True` path, and the fail-soft evidence helpers are confirmed in
`proposal_executor.py` / `proposal_execution_pipeline.py`; the strengthenable `completed` contract is
in `Proposal.json`. The companion review claim that *no* `EXECUTING` reaper exists was **refuted** —
`ProposalPipelineShopManager` / `proposal.stuck_executing` is present and named in governed law
(ADR-091 D2), which is why D4 extends it rather than proposing a new one.

---

## Addendum — D7: reconstructed consequence rows must be labeled and surfaced (2026-07-17, accepted)

**Status of this addendum:** Accepted (governor confirmed 2026-07-17, Path A confirmation naming
this file). This extends D4's reconstruction mechanism and D1's "consequence chain recorded"
obligation; it is not a new principle, so it is recorded as an addendum rather than a fresh ADR.

**Relates:** ADR-150 (finalizing-redrive-cap) — a sibling extension of the same D4 mechanism: ADR-150
*bounds* the roll-forward loop, this addendum *labels its output honestly*. Both operate on
`ProposalPipelineShopManager._roll_forward_finalizing`.

### The gap (issue #790)

D4's roll-forward reconstructs a missing consequence record when a `stuck_finalizing` proposal has
none:

```python
consequence_ok = await record_consequence(
    proposal_id=proposal_id,
    pre_sha=None,
    post_sha=None,
    changed_files=[],
    finding_ids=list(row.get("finding_ids") or []),
    policies=list(row.get("policies") or []),
    declared_production=declared,
)
```

The code comment is honest that this is a best-effort substitute ("the SHAs are unavailable to the
reaper and are omitted"), but the resulting `core.proposal_consequences` row carries no marker
distinguishing it from a normal, fully-evidenced record. A `NULL` SHA cannot serve as that marker:
`capture_git_sha()` (`will/autonomy/proposal_execution_pipeline.py`) already returns `None` fail-soft
on the *normal* execution path (git service unavailable, or `get_current_commit()` raising), so
`pre_execution_sha IS NULL` already means two different things today. An explicit column is the only
disambiguation that doesn't overload an existing, already-ambiguous signal.

### Why the `DEFAULT` backfill is safe: ADR-150's verified 0/0/0

Backfilling every pre-existing row with a single default value is only honest if none of history's
existing rows are secretly reconstructed. ADR-150 already queried this exact path live
(2026-07-16) and found **zero** proposals ever in `finalizing`, **zero** `stuck_finalizing` findings
ever posted, and **zero** post-barrier `completed` rows missing a consequence record — i.e. D4's
reconstruction branch has never fired in production. Re-verified live at addendum time
(2026-07-17, corrected join on `autonomous_proposals.proposal_id`, not `.id`): still zero. So every
row in `core.proposal_consequences` today is genuinely execution-sourced, and defaulting the
backfill to `'execution'` mislabels nothing.

### D7 — `consequence_source` column, and a consumer that reads it

**Schema.** Add `consequence_source text NOT NULL DEFAULT 'execution' CHECK (consequence_source IN
('execution', 'reaper_reconstructed'))` to `core.proposal_consequences`, via a migration sibling to
`20260712_adr148_finalizing_and_consequence_recorded_at.sql`.

**Write path.** `record_consequence()` (`will/autonomy/proposal_execution_pipeline.py`) gains a
`source: str = "execution"` parameter, threaded into `ConsequenceLogService.record()`'s INSERT/
UPDATE. `record_consequence`'s existing parameters map to columns as: `pre_sha` →
`pre_execution_sha`, `post_sha` → `post_execution_sha`, `changed_files` → `files_changed` (the
parameter and column names diverge; kept explicit here so the migration and the call sites don't
drift). The only call site passing a non-default value is
`ProposalPipelineShopManager._roll_forward_finalizing`, which passes
`source="reaper_reconstructed"`.

**A label with no consumer is a labeled silent-green, not a fix.** The existing D5 integrity check
(`governance.proposal_finalization_integrity`, `CommitAuthorshipAuditWorker`) queries `NOT EXISTS
(SELECT 1 FROM core.proposal_consequences ...)` — it fires only when the row is *absent*. A
reaper-reconstructed row exists (with `consequence_source='reaper_reconstructed'`), so it
satisfies that check and passes invisibly: a proposal can be `completed`, with
`consequence_recorded_at` set, on evidence that is empty and fabricated, and nothing today would
tell a governor that happened. Labeling without surfacing repeats the pattern the last several
ADRs have been closing (ADR-151's unpopulated `state='deprecated'`; ADR-152's unvalidated
`governed_exclusions` entries) — a governed vocabulary term that nothing reads.

So D7 adds a **second, independent check** to `CommitAuthorshipAuditWorker` (same worker, same
cadence, same dedup-by-open-subject shape it already uses for two other checks — see its own
module docstring), reporting posture, new rule `governance.consequence_evidence_degraded`:

> A Proposal in `status='completed'` whose `core.proposal_consequences` row has
> `consequence_source = 'reaper_reconstructed'` MUST be surfaced — its evidence chain (pre/post SHA,
> changed files) was fabricated by the D4 roll-forward, not captured at execution time.

Posts `governance.consequence_evidence_degraded::{proposal_id}`. The query selects strictly on
`consequence_source = 'reaper_reconstructed'` — it cannot fire on a normal proposal whose
`capture_git_sha()` returned `None` fail-soft, because that proposal's row still carries
`consequence_source = 'execution'` (the column, not the SHA, is the marker; the NULL-SHA ambiguity
this addendum exists to route around never enters this check's predicate).

Per ADR-150's 0/0/0 (re-verified live at addendum time), zero `reaper_reconstructed` rows exist
today — the roll-forward's reconstruction branch has never fired in production. So
`governance.consequence_evidence_degraded` ships firing on zero rows: it is *prevention*, in the
same sense ADR-151's refined rule shipped primarily as prevention with one live catch — this
check's first real firing is the reconstruction path's first, and CORE will know the instant it
happens instead of the row sitting silently labeled-but-unread.

### Governed surfaces this touches

| Surface | Authority | Change |
|---|---|---|
| `infra/scripts/migrations/` + `infra/migrations/manifest.yaml` | — | new migration: `consequence_source` column + CHECK |
| `schema.sql` | — | reflect the new column |
| `.intent/enforcement/contracts/ProposalConsequence.json` | constitution | add `consequence_source` property |
| `.intent/rules/governance/consequence_evidence_degraded.json` | policy/constitution | new rule, reporting posture |
| `.intent/enforcement/mappings/governance/` | — | new mapping for the rule |
| `.intent/enforcement/remediation/auto_remediation.yaml` | — | `governance.consequence_evidence_degraded` → PENDING (human investigation, same as its sibling) |
| `.intent/governance/namespace_manifest.yaml` | — | classify the new rule/mapping/migration files |
| `src/body/services/consequence_log_service.py` | code | `record()` gains `source` param |
| `src/will/autonomy/proposal_execution_pipeline.py` | code | `record_consequence()` gains `source` param |
| `src/will/workers/proposal_pipeline_shop_manager.py` | code | pass `source="reaper_reconstructed"` at the one call site |
| `src/body/services/proposal_supervision_service.py` | code | new `fetch_completed_with_degraded_consequence()` query |
| `src/will/workers/commit_authorship_audit_worker.py` | code | third check, same worker |

### Out of scope (noted, not fixed here)

`ProposalConsequence.json` is also missing `declared_production` (added by the 2026-06-28 ADR-129
migration, never added to the contract) — a pre-existing gap, unrelated to this addendum's evidence-
provenance question. Flagged for a separate fix, not folded in here to keep this change's diff
legible.

**Named trajectory, not built here (D8 candidate):** a reconstructed row records empty evidence
(`changed_files=[]`, null SHAs) even though real evidence exists on disk — the proposal is
post-commit by definition (it reached `finalizing`), and `commit_proposal_changes`
(`proposal_execution_pipeline.py`) commits with message `fix({proposal_id[:16]}): {goal}`, so the
commit is discoverable by `git log --grep=<proposal_id[:16]>` under the same ADR-101 attribution
this codebase already relies on elsewhere. A future roll-forward could recover the actual
post-SHA/changed-files from that commit instead of recording empty — turning "honestly labeled as
empty" into "actually reconstructed." Not built now: D7's scope is making the existing empty
reconstruction honest and visible, not building git-recovery; the label is this addendum's floor,
not its ceiling.

### Consequences

**Positive.** Closes the silent-mislabeling gap #790 identified: a reconstructed consequence record
is now explicitly marked and, independently, surfaced to a governor the same reporting-first way
every other post-hoc integrity check in this ADR family is. The backfill is provably safe (ADR-150's
0/0/0), not merely assumed safe.

**Costs.** One more column, one more migration, one more reporting rule — consistent with D5's own
"detection only" ramp discipline. No behavior change to the normal execution path (default value
applies).
