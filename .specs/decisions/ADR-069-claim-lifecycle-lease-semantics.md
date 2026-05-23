# ADR-069 — Claim Lifecycle: Lease Semantics

**Date:** 2026-05-23
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Band:** E — Constitutional Completeness
**Closes:** #439
**Related:** ADR-015, ADR-045, ADR-053

---

## Context

CORE's blackboard records ownership of work-in-progress on each
`blackboard_entries` row through two columns: `claimed_by` (the worker
UUID) and `claimed_at` (the moment claim was taken). A row in
`status='claimed'` is understood by the system to be "owned by some
worker, who will resolve it." There is no third column encoding how
long that ownership assertion remains valid, and no mechanism by which
the row itself can express "this claim has expired."

This omission shows up wherever the claiming worker terminates
without first transitioning the row to a terminal status. Every
termination mode — daemon restart, worker hang, OOM kill, SIGKILL,
network partition, declaration-name change, decommission — leaves the
row indefinitely in `claimed`. The system has no general resolution
mechanism because the model does not have a general resolution concept.

Measured 2026-05-23:

- 154 `audit.violation` findings stuck claimed by `Violation Executor`
  across 2026-05-13 → 2026-05-19, attributable to daemon restarts.
  Released by raw SQL during the diagnostic session that produced
  this ADR.
- Two daemon restarts during the same session produced 26 fresh stuck
  claims each — 52 new orphans in ~25 minutes. Confirmed: the orphan
  rate is structural, not historical.
- `BlackboardShopManager` already detects this condition. It posts
  `blackboard.entry_stale` findings (SLA = 3600 s) for any claim past
  its declared lifetime. 239 such meta-findings were open at session
  start. **The sensor flags; nothing acts.** Detection without
  resolution is itself a symptom of the missing model — there is no
  formal `expiry` to act on, only an external observer's guess.

The shape of the gap is the same shape ADR-016 (confidence floor) was
filed to refuse: an authority claim without a constitutional bound on
how that authority terminates. There, the bound is a confidence
threshold; here, the bound is a time. The principle is identical —
**lifecycle states are first-class, encoded in the model, not asserted
by surveillance.**

Three alternative fixes were considered and rejected as workarounds
that would lock the model gap in as a permanent design choice:

1. **Per-worker startup self-release** — a `Worker._register()` hook
   that releases own-uuid claims at every cycle start. Handles
   daemon-restart-orphan only; every other termination mode (hang,
   OOM, partition, rename, decommission) needs a separate workaround.
   Each workaround is a special case the next reader of the schema
   has to learn.
2. **Janitor in `BlackboardShopManager`** — extend the existing
   stale-detection sweep to call `release_claimed_entries` on
   sufficiently-old claims. Requires the sensor to *infer* worker
   liveness from `worker_registry.last_heartbeat` correlation, which
   is an external observer reasoning about something the row itself
   should declare. Threshold tuning becomes load-bearing.
3. **(This ADR's direction) — claim becomes a time-bounded lease**
   with explicit expiry, written on the row at claim time and
   extendable by the claimant during long ceremonies. Every
   termination mode collapses to the same mechanism: lease expires,
   row becomes available again.

The third option is more work — schema migration, base-class API,
per-worker contract update. The first two would be faster to ship.
This ADR proposes the third because the model gap, once papered
over, becomes the gap future ADRs have to argue around. ADR-016
refused the equivalent shortcut at the confidence layer; this ADR
refuses it at the lifecycle layer.

The cost of this direction during the interim — continued orphan
production at the rate of ~26 per daemon restart, manually released
by governor SQL when noticed — is accepted as the price of doing the
fix correctly.

---

## Decisions

### D1 — Claim becomes a time-bounded lease

A `claimed` row carries a constitutional guarantee of ownership only
until a declared expiry time. After that time, the row is eligible
for re-claim by any worker permitted to claim entries of its kind,
regardless of whether the prior claimant has transitioned the row
itself.

This is the central inversion. Today, the claim is unconditional
and external observation is required to decide when it has gone
stale. After D1, the claim is conditional on a declared expiry, and
the row itself answers the question "is this claim still valid?"
without consulting any external state.

The `claimed_by` column retains its meaning (whose claim it is). The
new lease behaviour does not change *who* may claim — only how long a
claim, once taken, remains binding.

---

### D2 — Schema: `lease_expires_at` added; `claimed_at` retained for forensic

Adds one nullable column to `core.blackboard_entries`:

```
ALTER TABLE core.blackboard_entries
  ADD COLUMN lease_expires_at TIMESTAMPTZ NULL;
```

Semantics:

| `status` | `claimed_by` | `claimed_at` | `lease_expires_at` |
|---|---|---|---|
| `open` | NULL | NULL | NULL |
| `claimed` (live lease) | worker_uuid | claim moment | future TIMESTAMPTZ |
| `claimed` (expired lease) | worker_uuid | claim moment | past TIMESTAMPTZ |
| any terminal status † | worker_uuid | claim moment | NULL |

† All seven terminal statuses share identical lease semantics:
`resolved`, `abandoned`, `indeterminate`, `suppressed`,
`awaiting_reaudit`, `dry_run_complete`, `deferred_to_proposal`.

`claimed_at` is preserved as a forensic record of when the claim
was first taken. `lease_expires_at` is the operationally-relevant
field. On any terminal transition, `lease_expires_at` is set back to
NULL — the lease has been resolved by terminal action and no longer
applies. (`claimed_at` is unchanged so the audit trail of when ownership
began is preserved.)

The new column is nullable to support the migration path (D7); after
backfill, every `status='claimed'` row carries a non-null
`lease_expires_at`.

**Open question for governor review:** whether to add a CHECK
constraint that enforces "if status='claimed' then lease_expires_at
is not null." Recommended yes, deferred until backfill is complete
to avoid migration ordering hazard.

---

### D3 — Lease length is declared per worker, required

Every worker that holds claims — daemon-run or CLI-triggered — **must**
declare `lease_seconds` under `mandate.schedule` in its
`.intent/workers/<name>.yaml`. The value is the lease duration applied
at claim time to every row claimed by an instance of this worker:

```yaml
mandate:
  schedule:
    max_interval: 300
    batch_size: 50
    lease_seconds: 600    # REQUIRED
```

CLI-triggered workers (no daemon schedule) declare a `schedule` block
containing `lease_seconds` even when no other scheduling fields apply.
The `schedule` block is the canonical home for lease semantics across
both worker types; CLI-triggered workers do not get a separate
placement.

There is no runtime fallback. The runtime never computes a default
from `max_interval` or any other source. A worker declaration missing
`lease_seconds` fails `intent_validator.py` at daemon startup and the
worker does not register. This is intentional: the lease duration is a
governance decision belonging to the declaration, not a code-level
constant. Each worker explicitly considers its own lease as a
declared bound on its ownership window rather than inheriting an
unexamined global.

`META/worker.schema.json` is extended in the same migration that adds
`lease_seconds` to existing declarations. The schema marks the field
required; the validator's existing enforcement of required fields
then refuses any worker that omits it.

**Migration-time value selection.** Existing worker YAMLs receive
`lease_seconds` values computed at migration time as
`2 × max_interval`, with the following named overrides:

| Worker | Type | max_interval | Migration value | Rationale |
|---|---|---|---|---|
| `violation_executor` | daemon | 300 s | **3600 s** | Worst-case batch is 12 files × ~3 min ceremony = ~36 min. `2 × max_interval = 600 s` is known-inadequate. 3600 s covers the worst case with ~1.7× headroom and leaves room for slower-than-expected LLM calls without forcing every cycle to end with renewal calls. |
| `proposal_consumer_worker` | daemon | 60 s | **1800 s** | Permitted tools include `canary.validate` (runs pytest), `crate.apply`, `git.commit`. `2 × max_interval = 120 s` is known-inadequate for a pytest-bearing canary. 1800 s covers a slow test run with 3× headroom. |
| `violation_remediator_body` | CLI | n/a | **1800 s** | No `max_interval` (CLI-triggered, instantiated by `core-admin workers remediate`). Same ceremony class as `proposal_consumer_worker` (`llm.remote_coder` + `canary.validate` + `crate.apply` + `git.commit`). Governor `Ctrl-C` is the analogue of daemon restart; 1800 s gives the same headroom as the daemon-side worker. |
| all other daemons | daemon | varies | `2 × max_interval` | Conservative default for short-cadence workers; long enough that one skipped cycle does not cost claims, short enough that a dead worker's claims return within two cycles. |

The `2 × max_interval` formula is the *migration-time* heuristic for
picking a starting value, not a runtime fallback. Once written into
the declaration it is a governance artifact — subsequent tuning is
done by amending the declaration, not by changing the formula.

---

### D4 — Renewal API and abandonment contract

`BlackboardService` gains:

```python
async def renew_lease(
    self,
    entry_ids: list[str],
    claimed_by: uuid.UUID,
    additional_seconds: int,
) -> int:
    """
    Extend lease_expires_at by additional_seconds for each entry in
    entry_ids, only where the caller still holds the claim.

    Returns the number of rows updated. The caller compares this to
    len(entry_ids); any shortfall means one or more entries have been
    re-claimed since the caller acquired them.
    """
```

Renewal *extends* the existing `lease_expires_at` rather than
overwriting it — the worker is asking for more time, not declaring a
fresh lease. Race conditions between renewal and re-claim are
resolved by the `claimed_by = :caller` predicate in the UPDATE
clause; only matched rows are updated.

**Renewal is per-batch.** The signature accepts `entry_ids:
list[str]`, never a single `entry_id`. The single-entry case is
expressed as a one-element list. Rationale: the workers that
actually need mid-ceremony renewal are batch processors — VE holds
up to 12 files per claim, `proposal_consumer_worker` up to its
`batch_size`. Per-entry renewal on a 12-finding batch is 12 DB
round-trips per checkpoint; per-batch is one UPDATE with
`WHERE id = ANY(:entry_ids) AND claimed_by = :caller AND status =
'claimed'` — same race protection, single statement. The uniform
signature avoids special-casing single-entry workers.

**Any partial loss is treated as full batch loss.** If the UPDATE's
returned rowcount is less than `len(entry_ids)`, the worker raises
`LeaseExpiredError` carrying the full batch — not just the lost
entries. The worker cannot reason about *when* during the cycle any
individual entry was lost; a re-claim that happened minutes ago means
another claimant may already be mid-ceremony on that entry, and the
current worker's in-memory state for the *other* entries was built
under an assumption that no longer holds. Atomic batch ownership is
the only stance that does not require workers to reason about partial
timeline ordering. Throughput cost is real (one bad entry yields the
whole batch) but it is the trade that keeps the model coherent.
Smaller batches at risk is a feature, not a bug.

**`additional_seconds` is drawn from `self._lease_seconds`** (the
worker's own declaration loaded from `mandate.schedule.lease_seconds`),
never from a literal at the call site. Workers do not pick a renewal
amount — they extend by another full lease-length, whatever their
declaration says that is. The base class wraps the renewal call so
worker authors never see the value; `self.renew_current_lease(entry_ids)`
is the worker-facing API and reads `self._lease_seconds` internally.
This prevents the hardcoded-policy violation that an
`additional_seconds=600`-style literal at a call site would
reintroduce.

Long ceremonies (LLM call, canary run) are expected to call renewal
at known checkpoints. Short cycles do not need to renew — they finish
well within the initial lease. The base class provides a default
renewal pattern; workers with ceremony shapes that do not fit the
default override it.

**Abandonment contract.** A rowcount shortfall on renewal is one
signal of lease loss; another is a state-changing UPDATE whose
`claimed_by = self.worker_uuid` predicate fails to match. Without a
defined contract, every worker author independently decides what
"abandon" means — some will silently swallow, some will commit the
in-progress crate anyway, some will call
`_mark_findings("abandoned")` on findings that may now belong to
another worker (writer-conflict). The contract removes that
ambiguity.

A new exception `LeaseExpiredError` (in `shared.workers.errors`) is
raised by:

- `Worker.renew_current_lease(entry_ids)` when `BlackboardService.renew_lease`
  returns a rowcount less than `len(entry_ids)`. The exception
  carries the full submitted batch, not just the lost subset (per
  the per-batch decision above), and
- any state-changing helper whose UPDATE clause carries the
  `claimed_by = self.worker_uuid` predicate and fails to match.

The exception is caught by `Worker.start()` at the existing top-level
try/except (`src/shared/workers/base.py:172`), which:

1. Calls `self._on_lease_lost(entry_ids)` — a new hook with a no-op
   default implementation. Workers with rollback needs (partial
   crate, opened canary sandbox, half-written file) override this
   hook to clean local state.
2. Does NOT mark the affected findings as abandoned. The findings
   are now owned by whoever re-claimed them; their lifecycle is
   that worker's responsibility.
3. Does NOT commit any in-progress artifact (crate, proposal, file
   write, blackboard report) derived from the lost-lease work.
4. Re-raises the exception after the hook returns so the existing
   `worker.error` blackboard entry is posted by the surrounding
   exception handler.

Worker authors override `_on_lease_lost` only when local cleanup is
required. The contract is the named hook, not free-form exception
handling at each call site.


---

### D5 — Terminal transitions release the lease

Any transition to a terminal status (`resolved`, `abandoned`,
`indeterminate`, `suppressed`, `awaiting_reaudit`, `dry_run_complete`,
`deferred_to_proposal`) sets `lease_expires_at = NULL` as part of the
same UPDATE statement. The lease has been resolved by terminal
action and no longer applies. `claimed_at` and `claimed_by` are
preserved on the row (audit trail of who closed it and when ownership
began).

This rule extends the existing pattern at
`src/body/services/blackboard_service/blackboard_service.py:454`
(`update_entry_status`, which already sets `resolved_at` on terminal
transition).

---

### D6 — Re-claim on expiry is the same mechanism as initial claim

The claim query at
`src/body/services/blackboard_service/blackboard_claim_service.py:175`
changes its predicate:

```sql
-- before
WHERE status = 'open'

-- after
WHERE (
  status = 'open'
  OR (status = 'claimed' AND lease_expires_at < now())
)
```

The row's `status` does not change at the moment of expiry — it
remains `claimed`. The claim query's predicate now recognizes
expired-claimed as equivalent to open. When the row is re-claimed,
the UPDATE clause overwrites `claimed_by`, `claimed_at`, and
`lease_expires_at` to reflect the new claimant.

This preserves the existing `FOR UPDATE SKIP LOCKED` race-protection
shape — only one re-claimer can win per row.

The old claimant, if alive, will discover its claim loss at the next
renewal call (returns False / raises `LeaseExpiredError` per D4) or
at the first attempted terminal-status transition (UPDATE with
`claimed_by = old_uuid` predicate fails to match, raising
`LeaseExpiredError`).

**Index.** The new predicate adds a per-cycle scan of `claimed` rows
whose `lease_expires_at` is in the past. The existing index on
`status` covers the `status = 'open'` branch; the expired-claimed
branch needs `lease_expires_at` lookup scoped to `status = 'claimed'`.
The migration that adds the column also adds a partial index:

```sql
CREATE INDEX idx_blackboard_lease_expiry
  ON core.blackboard_entries (lease_expires_at)
  WHERE status = 'claimed';
```

Partial because `lease_expires_at` is NULL on every other status and
only the claimed subset is queried under this predicate. Storage
cost is negligible (claimed-set cardinality is small by design); the
index makes the access pattern explicit and prevents the expiry
predicate from degrading into a sequential scan as the blackboard
grows.

**Open question:** whether the row's `status` should also flip back
to `open` at the moment of expiry — by a sensor, a background task,
or lazily on the next claim. Recommended: no separate transition.
The predicate-based view of expired-claimed-as-open is sufficient
and avoids introducing a third actor in the lifecycle. Deferred to
implementation.

---

### D7 — Migration: schema, declarations, backfill

The migration is one unit, applied in this order:

1. `ALTER TABLE core.blackboard_entries ADD COLUMN lease_expires_at
   TIMESTAMPTZ NULL;`
2. `CREATE INDEX idx_blackboard_lease_expiry` per D6.
3. Every existing `.intent/workers/<name>.yaml` is updated to declare
   `mandate.schedule.lease_seconds` per the table in D3 (`3600` for
   `violation_executor`, `2 × max_interval` for the others).
   `META/worker.schema.json` is extended to mark the field required;
   `intent_validator.py` then enforces presence on next daemon startup.
4. Backfill: for every row currently in `status='claimed'`, set
   `lease_expires_at = claimed_at + INTERVAL '600 seconds'`.

   **Migration constant: 600 s.** This value is load-bearing for one
   re-claim cycle only — the next claim cycle's UPDATE writes a fresh
   `lease_expires_at` derived from the claiming worker's declared
   `lease_seconds`. The migration constant exists solely to give
   the existing stuck rows a deterministic expiry. 600 s matches the
   conservative `2 × max_interval` value that short-cadence workers
   receive in their declarations, and is short enough that any rows
   stuck at migration time become re-claimable within one cycle of
   the new code path activating. It is a one-shot bootstrap value,
   not a runtime constant.

5. No CHECK constraint in this migration. The constraint referenced
   in D2 is deferred to a follow-up migration after one release cycle
   of running without it, so any backfill mismatch surfaces as
   warnings rather than as a constraint violation that blocks the
   migration.

`release_claimed_entries` (today's manual-override helper) is
retained but reclassified as a governor-override utility, not a
lifecycle mechanism. Documentation and call sites updated to reflect
that callers should normally let leases expire.

`BlackboardShopManager`'s stale-detection role under the new model
becomes "report on workers consistently exceeding their declared
lease length" — diagnostic, not enforcement. Its existing
`blackboard.entry_stale` finding subject is retained for that
purpose; the SLA constant becomes worker-specific (drawn from each
worker's declared `lease_seconds`) rather than the current single
3600 s.

---

## State at ADR acceptance

At the time this ADR is accepted, the following is the live state:

- 0 stuck `claimed` rows in `core.blackboard_entries` for
  `architecture.cli.api_only` (released during the 2026-05-23
  session that produced this ADR).
- `lease_expires_at` column does not exist; backfill not yet run.
- No worker declaration carries `lease_seconds`.
- `BlackboardService.renew_lease` does not exist.
- `BlackboardShopManager` continues to flag stale claims as
  `blackboard.entry_stale` findings; no janitor exists.
- `release_claimed_entries` is the only mechanism for releasing
  stuck claims; it is operator-invoked, not automatic.
- Issue #439 records the gap and references this ADR as the
  proposed direction.

---

## Consequences

**Positive:**

- Every termination mode (restart, hang, OOM, kill, partition,
  rename, decommission) resolves through one mechanism. The
  patchwork of workarounds that would otherwise accumulate is
  prevented at the design stage.
- The blackboard schema becomes self-describing with respect to
  validity. No external observer needs to consult
  `worker_registry.last_heartbeat` or infer liveness from
  registration timestamps. The row answers "is this claim valid?"
  directly.
- GxP / EU AI Act audit-trail integrity is strengthened. A claimed
  row whose worker died now has a deterministic, model-declared
  point at which its claim ceases — not an after-the-fact janitor
  guess. The audit narrative becomes "claim expired at T per
  declared lease" instead of "system noticed claim was stale and
  released it on a sweep."
- ADR-016's posture (governance bounded in the model, not asserted
  by surveillance) is preserved consistently across the
  confidence and lifecycle dimensions of governance.

**Negative:**

- Schema migration touches every claiming worker. Migration ordering
  must complete before any worker is upgraded to the renewal API,
  to avoid a worker holding a claim under the old model while the
  new model is being applied. The window is short (one migration)
  but requires coordination.
- Workers with long ceremonies must learn renewal as a contract
  obligation. A worker that forgets to renew loses its claim
  mid-ceremony; this is a real regression for any worker not
  updated. The base-class default helps but does not eliminate the
  obligation.
- `BlackboardShopManager`'s role narrows. Its existing detection
  half remains useful (workers exceeding lease are slow workers,
  worth flagging) but the constituency that consumed
  `blackboard.entry_stale` findings as a primary signal must be
  re-pointed at lease-expiry observability.
- Interim cost: the orphan rate (~26 per restart) continues until
  the ADR ships. This cost is explicitly accepted as the price of
  the correct fix. The accumulation is observable via
  `BlackboardShopManager`'s existing `blackboard.entry_stale`
  findings — the governor's manual-release obligation during the
  interim is bounded to sessions where that signal fires above its
  current ambient rate. Sessions without the signal require no
  intervention; the interim is not open-ended.

---

## Verification

Deferred to implementation. At implementation, verification is:

1. Migration applied: `core.blackboard_entries.lease_expires_at`
   exists as nullable TIMESTAMPTZ; every row currently in
   `status='claimed'` carries a non-null value (backfilled per the
   600 s migration constant in D7).
2. Partial index `idx_blackboard_lease_expiry` exists on
   `(lease_expires_at) WHERE status = 'claimed'` (D6).
3. Every `.intent/workers/*.yaml` (daemon-run and CLI-triggered)
   declares `mandate.schedule.lease_seconds`;
   `META/worker.schema.json` marks the field required;
   `intent_validator.py` refuses any worker that omits it.
   `violation_executor.yaml` carries `3600`;
   `proposal_consumer_worker.yaml` and `violation_remediator_body.yaml`
   carry `1800`; all other workers carry their `2 × max_interval`
   migration-time value (D3).
4. No runtime fallback for `lease_seconds` exists in the worker
   base class or service layer. Searching the codebase for
   `2 * max_interval`, `lease_default`, or equivalent constants
   returns no matches outside the migration script and this ADR.
5. `BlackboardService.renew_lease(entry_ids, claimed_by,
   additional_seconds) -> int` exists, accepts a list of entry IDs,
   and passes a smoke test: rowcount equals the matched-and-still-held
   subset; a batch with any re-claimed entry returns a rowcount less
   than `len(entry_ids)`.
6. `Worker.renew_current_lease(entry_ids: list[str])` exists in the
   base class, reads `self._lease_seconds` from the worker's
   declaration, forwards to `BlackboardService.renew_lease`, and
   raises `LeaseExpiredError` carrying the full submitted batch when
   the returned rowcount is less than `len(entry_ids)`. No worker
   calls `BlackboardService.renew_lease` directly with a literal
   `additional_seconds` value.
7. `shared.workers.errors.LeaseExpiredError` exists; `Worker.start()`
   catches it, invokes `self._on_lease_lost(entry_ids)`, then
   re-raises. The hook has a no-op default; workers requiring
   rollback override it.
8. The claim query at
   `src/body/services/blackboard_service/blackboard_claim_service.py:175`
   recognizes `(status='claimed' AND lease_expires_at < now())` as
   re-claimable.
9. `Worker.start()` (`src/shared/workers/base.py:168`) does not
   contain a startup self-release hook for own-uuid claims.
   (Workaround option A was rejected; verify it did not slip in.)
10. Smoke test: claim a finding → `SIGKILL` the worker → confirm
    the row becomes re-claimable at lease expiry without external
    intervention. This is the canonical demonstration of the
    model's self-describing property.
11. `BlackboardShopManager`'s `blackboard.entry_stale` SLA is
    drawn per-worker from each worker's declared `lease_seconds`,
    not the previous hardcoded 3600 s.
12. `core.autonomous_proposals` and other tables that may need
    parallel lease semantics are reviewed (out of scope for this
    ADR; a follow-up ADR may be needed if they exhibit the same
    gap).
13. Issue #439 closed by the implementing commit, with the
    `project_restart_orphan_wedge_open` memory updated to reflect
    closure.

---

## References

- ADR-015 — Consequence chain attribution; established the pattern
  of governance state being self-describing on the row rather than
  asserted by an observer. This ADR extends that pattern to
  ownership lifecycle.
- ADR-016 — Confidence floor enforcement; the cognate pattern at
  the confidence dimension. Refuses unbounded authority claims;
  this ADR refuses unbounded ownership claims.
- ADR-045 — `awaiting_reaudit` quarantine state; adjacent
  lifecycle work covering a different gap (the reject-revive-reclaim
  loop). Does not overlap with this ADR's claim-expiry concern.
- ADR-053 D7 — Request-level attribution for GxP readiness; the
  API-layer analogue of this ADR's worker-layer concern.
- 21 CFR Part 11 §11.50 — electronic signature meaning. The lease
  expiry is part of what gives a claim its constitutional meaning;
  without it, "claimed" is an ambiguous assertion that fails the
  §11.50 interpretability test.
- EU AI Act Article 17(1)(m) — accountability framework. A claim
  that never expires has no declared accountability boundary;
  the lease model encodes that boundary as model state.
- Issue #439 — the live case; this ADR is the directional answer.
- `src/body/services/blackboard_service/blackboard_service.py:153`
  — `release_claimed_entries`, the today-manual helper, becomes
  a governor-override utility under this ADR.
- `src/body/services/blackboard_service/blackboard_claim_service.py:175`
  — claim query whose predicate D6 extends.
- `src/will/workers/blackboard_shop_manager.py` — stale-detection
  sensor whose role narrows under D7.
- `src/shared/workers/base.py:289` — `_register`; intentionally
  not modified (option A was rejected).
- `.intent/META/worker.schema.json` — schema extended in the D7
  migration to mark `mandate.schedule.lease_seconds` required, so
  `intent_validator.py` enforces presence without code changes.
- `.intent/workers/violation_executor.yaml` — primary worker
  declaration; receives `lease_seconds: 3600` override per D3.
- `.intent/workers/proposal_consumer_worker.yaml` — daemon worker
  with `canary.validate` ceremony; receives `lease_seconds: 1800`
  override per D3.
- `.intent/workers/violation_remediator_body.yaml` — CLI-triggered
  worker (no daemon schedule); receives `lease_seconds: 1800` per
  D3, declared inside a `schedule` block that exists solely to
  carry the lease field.
- `var/audits/repo_artifacts_orphans_2026-05-23.txt` — adjacent
  orphan-on-removal pile (#441), unrelated lifecycle gap surfaced
  during the same diagnostic session.
- Session 2026-05-23 diagnostic trail: commits `70294044`
  (KeyError fix in helpers used on rarer paths), `81df30a0`
  (`ConfigService.get_secret` pass-through; root cause that
  masked the leak for 10 days), `dcb4b74d` (`LLMResourceConfig`
  pass-through closure of #440).
