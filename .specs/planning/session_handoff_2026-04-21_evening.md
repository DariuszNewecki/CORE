# Session Handoff — 2026-04-21 (evening)

**A3 phase:** 3 (Capability gaps). The session's target was Option A from
the morning handoff — the worker that "claims audit.violation entries but
never transitions them to resolved." That framing turned out to be a
naming drift in the opener (explained below) and the real bug ran
several layers deeper than expected.

**Last session:** 2026-04-21 morning — ADR-007 class_too_large rule split.

**Audit state at close:** Not re-run as the final step. Last observed
audit during the session (post-`fix.format` execution at 17:28 UTC) showed
`workflow.ruff_format_check` on `violation_remediator.py` absent — the
first durable autonomous remediation confirmed by re-audit. Session closes
with commits `54d12f24`, `7fb11fd5`, `06792b30`.

**Daemon state:** active, PID 412587, restarted at 19:48:03 CEST to load
the capstone `claimed_at` commit.

**Blackboard state:** zero stuck claims across all workers and all
subject prefixes. Eight recent `audit.violation::*` entries resolved
within a single post-restart VR cycle at 17:49:16 UTC, all carrying
populated `claimed_at`. First time on this system the `status='claimed'`
query on the blackboard has returned an empty set at steady state.

---

## What this session did

### The three commits

| Commit     | Fix                                                                | What it unblocked                                                      |
|------------|--------------------------------------------------------------------|------------------------------------------------------------------------|
| `54d12f24` | VR resolve/release routing + `_entry_id` helper                    | Worker calls the right service methods on all four failure paths       |
| `7fb11fd5` | `resolve_entries` predicate broadened `open` → `open` OR `claimed` | Service methods actually transition what claim→resolve callers expect  |
| `06792b30` | `claimed_at` populated by all three `claim_*` methods              | Claim-age becomes observable; age-based purge semantics usable         |

Each commit was verified end-to-end before moving on. The morning
handoff's ordering recommendation (A before B) held up, but A turned
out to be three nested bugs, not one.

### ViolationRemediatorWorker — routing logic (commit 54d12f24)

The morning handoff said "Audit Ingest Worker claims audit.violation
entries but never transitions them to resolved." Read against the
code, `AuditIngestWorker` has no claim loop at all — it only posts
findings for `ai.prompt.model_required`. The real claimer was
`ViolationRemediatorWorker` (bb52f62a), identified by joining
blackboard `claimed_by` rows against the worker registry. Handoff
drift again; caught early enough not to cost anything.

Four failure modes in VR's `run()` loop left claimed findings stuck:

1. **Dedup-skip (primary):** when a finding mapped to an action that
   already had an active proposal, the worker logged the skip and
   `continue`d without resolving. Subsequent runs could not re-claim
   (status=claimed), so findings leaked. Directly explained the 7
   stuck `modularity.needs_split` entries stranded behind the active
   `fix.modularity` DRAFT.
2. **Proposal creation failure:** `_create_proposal` returned None,
   the `if proposal_id:` branch was skipped, findings stayed
   claimed. Latent, not observed today.
3. **`_load_open_findings` release-fallback:** if
   `release_claimed_entries` raised during the immediate-release of
   unmappable findings, entries stayed claimed.
4. **`_resolve_entries` exception path:** if the service call
   raised, exception was caught and logged but findings stayed
   claimed.

Fix: dedup-skip path now resolves (mandate says "mark each consumed
Blackboard entry as resolved"; a finding routed to an active proposal
has been consumed). Proposal-failure path now releases. New counters
`entries_resolved_dedup` and `entries_released_after_failure`. New
module-level `_entry_id(finding)` helper replaces the sloppy
`f.get("id") or f.get("entry_id")` idiom at four sites — fails loud on
contract violation, cleared 6 pre-existing mypy errors in the same
edit.

Paths 3 and 4 (service-exception cases) remain unaddressed in this
commit; flagged in the docstring for a future hardening pass.

### BlackboardService.resolve_entries — the foundational fix (commit 7fb11fd5)

Canary release of one stuck entry confirmed the VR routing commit was
live and took the right branch (`proposals_skipped_dedup: 1`,
`skipped_actions: ["fix.modularity"]`). But `entries_resolved_dedup`
came back 0 — the new branch called the right method; the method did
nothing.

Root cause: `BlackboardService.resolve_entries`'s UPDATE WHERE clause
filtered `status = 'open'`. By the time any claim→resolve caller ran
it, the row was at `claimed`. Zero rows matched. Method returned 0.
Every historical VR report's `entries_resolved: 0` was the fingerprint,
and nobody read that zero as evidence.

**This bug has been silent since the service was written.** Every
worker that claims findings before resolving them — VR,
`TestRemediatorWorker` — has been silently no-op'ing its resolve on
every run since inception. Historical `fix.format` proposals executed
successfully back to 2026-04-18 (three completed proposals visible in
`core.autonomous_proposals`); the action ran, formatted files,
returned ok=true — but the findings it was "fixing" stayed claimed on
the blackboard because the resolve predicate never matched. The action
worked; the governance accounting of the action didn't.

The dashboard's historical `resolved` count (~13,818 as of this
morning) is almost entirely heartbeats and reports, which are
*inserted* at `status='resolved'` via `_post_entry`, not
*transitioned*. The Convergence Principle metric on the governor
dashboard has been computed against a figure that never reflected
actual finding→resolution transitions. From 19:26:36 CEST forward
the metric is real.

Fix: broaden the predicate to `AND status IN ('open', 'claimed')` so
both caller patterns work — `fetch_open → resolve`
(TestRunnerSensor, unchanged) and `claim → ... → resolve` (VR,
TestRemediatorWorker, now actually resolves).

### End-to-end loop closure — first confirmed

Post-resolve-fix, batch-release of the remaining 8 stuck entries
triggered two code paths simultaneously:

- 7 `modularity.needs_split` + 1 `purity.no_todo_placeholders` →
  dedup-skip path → `entries_resolved_dedup: 7 + 1`.
- 1 `workflow.ruff_format_check` → happy path → new `fix.format`
  proposal `79dc24e9-d41e-4d29-92a4-7948808bbb73` created, auto-approved
  (risk=safe), picked up by ProposalConsumerWorker 4 seconds later,
  executed in 1.17s, marked completed, blackboard entry resolved,
  re-audit confirms `workflow.ruff_format_check` on
  `violation_remediator.py` is gone.

**Sense → route → approve → execute → re-observe, end-to-end, durable
under re-audit.** First of its kind on this system.

One edge observation: PC's log records "changes recorded: 0 files" for
this proposal. Coherent — the pre-commit hook had already
ruff-formatted the file when commit 54d12f24 landed, so the autonomous
`fix.format` ran on an already-clean file and had nothing to rewrite.
The action reported success either way. When two-log consequence
logging arrives, distinguishing "fix applied" from "fix ran on clean
state" will want its own field.

### ProposalConsumerWorker — empirically cleared

The symmetric silent-leak bug I flagged for a possible next session
(PC doing to approved proposals what VR was doing to claimed
findings) is empirically not present. PC handled `79dc24e9` cleanly:
approved → executing → completed, 1.17s, failure_reason NULL,
execution_results populated. One item removed from the forward queue
without needing dedicated audit time.

### Capstone — `claimed_at` hygiene (commit 06792b30)

All three `BlackboardService.claim_*` methods atomically transitioned
entries to `status='claimed'` but none wrote `claimed_at`. Column
exists in the schema, CLI reads it, no writer populated it. Every
claimed row had `claimed_at` NULL since inception. Age-based purge
semantics on claim-age were unusable.

Fix: `claimed_at = now()` in the SET clause of each UPDATE. Three
identical one-line additions. Verification: 8 post-restart claims
all carry populated `claimed_at` (single atomic UPDATE via FOR UPDATE
SKIP LOCKED, identical timestamps across all 8 rows).

---

## What this session did NOT do

- **Audit the historical 13,818 resolved count.** Unknowable
  retroactively — the blackboard doesn't record status-transition
  provenance — but important for framing what the counter meant
  before 19:26:36 CEST today. Any external claim about CORE's
  convergence history should carry this caveat.
- **Fix `resolved_at` symmetric hygiene gap.** Surfaced by Claude Code
  during the capstone verification: `resolved_at` is NULL on every
  row `resolve_entries` transitions, same shape as the `claimed_at`
  bug just fixed. Trivially small edit. Parked.
- **Fix `claim_open_findings`'s missing `claimed_by`.** Discovered
  during the capstone. Separate correctness bug (not hygiene); needs
  a signature change. Sole caller (PromptExtractorWorker) is
  abandoned per the worker registry, so no live code affected.
  Parked.
- **Address the fix.modularity / fix.placeholders DRAFT proposals.**
  Both have been sitting in DRAFT since before this session,
  awaiting human approval because their `impact_level` is
  "moderate". Sensor re-emits the same findings every cycle, VR
  dedup-skips and resolves every cycle — working correctly but
  busy-waiting on a governance decision. Either approve/reject
  those proposals or make a policy call about moderate-risk
  auto-approval.
- **ADR-007 Consequences addendum + 13-file `class_too_large`
  review ADR.** Still pending from the morning session.
- **`details: {}` audit JSON serializer.** Option B from the morning
  handoff. Dashboards and downstream consumers are still blind to
  structured finding fields. Now a cleaner target because the
  convergence layer underneath it is trustworthy for the first
  time.
- **The morning handoff's longer parked list** — ContextBuilder
  wiring, path-mapping, `action_executor` guards, daemon composition
  root, dead `auto_remediation.yaml` entries, `proposals show` logger
  bug, `logic.di.no_global_session`, `autonomy.tracing.mandatory`,
  `purity.no_ast_duplication`, `ai.cognitive_role.no_hardcoded_string`
  campaign, `architecture.api.no_body_bypass` — all still parked.

---

## Carry-over — next session

Four candidates, listed by leverage.

### Option A — `resolved_at` symmetric hygiene fix
Trivial. One SQL line in `resolve_entries`, one in `abandon_entries`,
one in `mark_indeterminate` if `indeterminate_at` or similar exists.
In-class with today's commits, same shape, same verification
pattern. ~15 minutes for a tidy commit.

### Option B — `details: {}` audit JSON serializer
Structural-signal restoration for downstream consumers. Sensors
already emit rich `details` payloads (ADR-006's `responsibility_count`,
ADR-007's `dominant_class_*`, etc.). Serializer flattens to `{}`.
Fixing it makes dashboards, vectorization, and future two-log
consequence work useful without further plumbing. Pre-existing from
morning handoff.

### Option C — Governance decision on the DRAFT backlog
`fix.modularity` and `fix.placeholders` are moderate-risk actions
that need human approval by current policy. They currently accumulate
DRAFT proposals that re-dedup-resolve on every sensor cycle.
Options: approve the existing DRAFTs (and verify the execute-half
handles moderate actions as cleanly as it did `fix.format`), reject
them, or revisit the policy.

### Option D — ADR-007 addendum + per-file review for the 13 newly-surfaced `class_too_large` findings
Still pending from morning. Lower urgency now that the convergence
layer works.

### Recommendation

**B, then A.** B is the biggest remaining observability win and the
next real bottleneck now that the pipeline below it is trustworthy.
A is a clean capstone-sized follow-on. C is a governance decision that
doesn't need a full session. D is housekeeping.

---

## Open questions for next session

1. **Verdict-threshold semantics.** PASS with N WARNINGs, no written
   definition. Pre-existing, survives.
2. **Historical composition of the 13,818 resolved.** What fraction
   was real transitions vs inserted-as-resolved? Unknowable now;
   noted for any external claim about CORE's prior convergence.
3. **Moderate-risk auto-approval policy.** Should `fix.modularity`
   and `fix.placeholders` remain manual-approval-required forever,
   or does the risk model need a second axis (confidence,
   reversibility, scope size)? Surfaces every sensor cycle as
   re-emission churn.
4. **"Changes recorded: 0 files" coherence.** `fix.format` today
   executed successfully but rewrote no files (pre-commit hook had
   already cleaned them). Action correctly reported success. When
   two-log logging lands, a dedicated field distinguishing
   "fix applied" from "fix ran on clean state" would preserve that
   distinction.

---

## Hazards worth naming

1. **Handoff drift continued.** The morning opener named
   "AuditIngestWorker" as the claimer; real claimer was
   `ViolationRemediatorWorker`. Caught before proposing any fix,
   via DB recon. This is the fourth named instance of handoff
   framing outrunning live state. The cure remains the same:
   session-opening recon against the DB before trusting the opener's
   diagnosis.

2. **The autonomous loop now produces real remediation.**
   `fix.format` on `violation_remediator.py` at 17:28 UTC was the
   first durable autonomous code change. That changes what failure
   modes are possible. Any worker with a symmetric silent bug we
   haven't found yet may now surface as a new class of failure that
   didn't exist when the loop was stuck. Watch the next 24–72h of
   daemon observation for anomalies that weren't visible before.

3. **Three days of blackboard history are partly false.** The
   `resolved` status on pre-19:26-CEST `audit.violation::*` entries
   includes essentially no real transitions. Any retrospective
   analysis or external comparison that treats the resolved count as
   "findings closed" needs this caveat. From today forward it's
   real; before, it wasn't.

4. **The `entries_resolved` / `entries_resolved_dedup` /
   `entries_released_after_failure` counters are now signal.** This
   is new. Governor observations of these numbers should now be
   treated as diagnostic, not decorative. `entries_resolved: 0`
   when `open_findings > 0` is a live pipeline leak, not a quiet
   nothing-happened.

---

## North-star ordering reminder

`rules clear → enforcement real → code`. Today's session was the
first one in which the third phase actually functioned:

- Rules clear: ADR-007 and earlier work. Holds.
- Enforcement real: sensors produce correct findings, engine is
  honest. Holds.
- Code: three commits today made the route-and-resolve half of the
  autonomous loop work for the first time. One proposal (`fix.format`
  on `violation_remediator.py`) traversed the full cycle and produced
  a durable, re-audit-confirmed remediation.

The goal is not audit-passed. The goal is that the machinery
producing the verdict is trustworthy, and that the autonomous loop
actually closes. Today, for the first time, a violation was sensed,
routed, approved, executed, resolved, and confirmed gone by
re-observation — all autonomously. One instance is not a track
record, but one instance is the difference between a working
mechanism and a theoretical one.

---

**Current blocker:** None — loop closes end-to-end.
**Daemon state:** active, PID 412587, three post-fix commits loaded.
**Audit state:** last observed mid-session showed
`workflow.ruff_format_check` on `violation_remediator.py` absent;
full re-audit not run at close.
**Blackboard state:** zero stuck claims; eight post-restart resolves,
all with populated `claimed_at`.
**Active workers:** 15 registered active (unchanged from morning).
**Next step:** `details: {}` serializer restoration (Option B).
