---
kind: adr
id: ADR-104
title: ADR-104 — Orphaned-claim reaper (claim lifecycle is process-scoped, not loop-scoped)
status: accepted
---

<!-- path: .specs/decisions/ADR-104-orphaned-claim-reaper.md -->

# ADR-104 — Orphaned-claim reaper (claim lifecycle is process-scoped, not loop-scoped)

**Date:** 2026-06-13
**Status:** Accepted — **Revision B** (governor agreed the revised logic on 2026-06-13: the four ratifications stand, and the two altitude-review corrections — ADR-069 grounding + the D8 lease — are accepted. The three originals were resolved earlier the same day; a "are we doing it right" review then surfaced the two gaps recorded under "Revision B — altitude-review corrections," which this accepted revision incorporates. Implementation is the execution arm's responsibility per the CORE development contract; it lands as one change-set, governor-reviewed at the logic/ADR level.)
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-13 — drafted under explicit "yes, draft the ADR stub" authorization. The original recon claimed `release_claimed_entries` runs "only at normal loop completion"; Revision B corrects this — the recon did not read `Worker.start()`, whose ADR-069 D8 `finally` block already releases held claims on graceful shutdown and on exception. Governor pre-selected the continuous-sweep approach over a startup-only reaper, and elected to anchor the new autonomous rail in an ADR before implementation.)

**Grounding decisions:**
- ADR-082 — writer-as-sensor retention policy; established `BlackboardShopManager` as the blackboard janitor running bounded hygiene sweeps (telemetry TTL, DELEGATE-finding TTL, stale-alert auto-resolution). This ADR adds one more sweep of the same class.
- ADR-070 D8 — destructive/rate-limited autonomous operations must ship their rails (row caps) in the same change. The reclaim cap (D3) is that discipline applied to the reaper.
- ADR-071 D2.2 — atomic actions sandbox their production in `var/tmp/core-action-sandbox-<uuid>/`; the *mutation* is already restart-safe. This ADR closes the residual leak: the *claim* is not.
- ADR-041 — governed per-worker liveness thresholds; the "alive worker uuids" set that defines orphanhood is read through `WorkerRegistryService` at the ADR-041 threshold.
- **ADR-069 D8 / D2 / D6 — the closest prior art (added in Revision B).** D8 already releases a worker's held claims in the `Worker.start()` `finally` block on graceful shutdown (`CancelledError`), on uncaught exception, and on the success path. D8's own docstring names the remaining gap: *"the lease mechanism (ADR-069 D2/D6, future work) remains the recovery path for ungraceful exits where the finally block cannot run."* This ADR **is** that D2/D6 lease/recovery work realized — both the reaper (recovery) and the lease (D8 below, the renewal that makes "alive" honest).

**Related:**
- #563 / F-19 re-anchor (governor call 2026-06-13) — an orphaned claim is a finding stuck in `claimed` forever; it never resolves and never re-claims, so it sits as permanent `total_open` backlog and silently skews the very convergence metric the re-anchor just made honest. This ADR removes a silent corruption source feeding that gauge.
- `papers/CORE-Instrument-Attestation.md` — the "no silent instrument" principle. A reaper that releases claims silently would itself be a silent instrument; D4 forces it to emit what it reaped.
- `src/will/workers/blackboard_shop_manager.py` — the janitor the sweep attaches to.
- `src/body/services/blackboard_service/blackboard_service.py:156` — `release_claimed_entries` (resets `status='open'`, `claimed_by=NULL`, only for `status='claimed'`); the reset primitive the new sweep reuses.
- Memory `[[reference_blackboard_claim_semantics]]` — release nulls `claimed_by`; worker_uuid vs claimed_by.
- Memory `[[feedback_destructive_autonomous_needs_rails_first]]` — the reclaim cap and the fail-safe (D3, D5) ship in the same change as the reaper.
- Memory `[[reference_blackboard_abandoned_two_semantics]]` — orphan-abandon (after the reclaim cap) is Type-B "daemon cannot self-heal," distinct from Type-A audit-trail abandons.

---

## Context

### The gap (corrected in Revision B)

A worker claims a blackboard finding by setting `status='claimed'`, `claimed_by=<worker_uuid>`, and releases it (`release_claimed_entries`, resetting to `open`) at normal loop completion. **It also releases on the broader exit paths**: `Worker.start()`'s ADR-069 D8 `finally` block calls `_release_held_claims()` on graceful shutdown (`CancelledError` from `core-admin daemon down`), on uncaught exception, **and** on the success path. So a clean restart and a crashing-but-not-killed worker both release their claims.

The residual gap is **ungraceful death only** — `SIGKILL`, OOM-kill, power loss, container teardown — where the `finally` block never runs. In that case:

- No startup hook releases claims left by the dead generation.
- No janitor sweep releases a claim whose owner died without unwinding its stack.

`BlackboardShopManager` *detects* SLA-stale entries and posts `blackboard.entry_stale` findings about them, but it **never resets the claim** — detection without remediation.

### Why ungraceful death orphans a claim

Worker UUIDs differ across daemon generations (documented at `blackboard_shop_manager.py:257`, which deduplicates stale findings *by subject* precisely because poster UUIDs change across restarts). A claim held by a worker that was `SIGKILL`ed is owned by a `worker_uuid` that **is never alive again**. It is permanently stuck in `claimed`, and because claims are taken `WHERE claimed_by IS NULL`, that finding is never re-processed by any future generation. (A *graceful* restart does not produce this — D8 released the claim on the way down. The orphan requires the `finally` block to have been skipped.)

### Severity — latent, not on fire

At authoring time `SELECT COUNT(*) WHERE status='claimed'` returns **0** — nothing was mid-claim at the last restart. The gap bites only when an *ungraceful* kill lands while a mutation worker holds a claim. Real, probabilistic, and silent when it happens: the loss is a finding that never resolves, which inflates backlog and the F-19 convergence trajectory without any error surfacing.

### Why continuous, not startup-only

A startup-only reaper would close the restart case but miss claims orphaned by a single-worker crash between restarts. Because orphanhood is defined by *owner liveness* (not by a restart event), a continuous sweep in the existing janitor cycle catches both, composes with the ADR-082 hygiene sweeps already running there, and needs no new worker or registration. This is the runtime-gate-over-startup-hook posture: self-heal on a cadence, fail loud, don't depend on a clean shutdown.

---

## Decisions

### D1 — Orphaned claims are reaped continuously by `BlackboardShopManager` (constitutional)

Each `BlackboardShopManager` cycle releases orphaned claims via a new bounded sweep. A claim is **orphaned** iff all hold:

1. `status = 'claimed'`;
2. `claimed_at < now() - claim_grace_seconds` (a grace window so an entry just claimed by a worker that has not yet emitted its run-start heartbeat is not yanked; **ratified = the ADR-041 alive-threshold, currently 600 s**, so "not alive" and "past grace" read off one clock); and
3. `claimed_by` is **not** in the set of currently-alive worker uuids from `WorkerRegistryService.fetch_alive_workers(threshold = ADR-041 alive_threshold)`.

Condition (3) is the safety invariant: a claim is only reaped when its owner is *provably gone*. **This invariant holds only because of the D8 lease.** Heartbeats fire at run-*start* and update `worker_registry.last_heartbeat` (`Worker.post_heartbeat`, `base.py:694`); a mutation worker that claims a batch and processes it for longer than the alive-threshold in a single `run()` (real for `violation_executor` / `test_remediator` LLM-backed batches) would, *without* the lease, fall out of the alive-set **while still working** and have its live claims reaped — duplicate work, and the D3 cap burned on healthy runs. A live slow worker and a dead worker are indistinguishable to condition (3) unless the live one keeps renewing. D8 makes "stale heartbeat" honestly mean "gone."

### D2 — Release semantics reuse the existing reset

A reaped claim is reset to `status='open'`, `claimed_by=NULL` — the exact semantics of `release_claimed_entries`. The finding re-enters the work queue for a live worker to reclaim. A new bounded method `BlackboardService.release_orphaned_claims(live_uuids, grace_seconds, batch_max)` performs this as a single batched `UPDATE` and returns the released count.

### D3 — Reclaim rail: abandon after N orphan-releases

To prevent a crash→reclaim→crash→reap loop on a genuinely unprocessable finding, each entry tracks an `orphan_release_count`, incremented on each reap. When it reaches **N (ratified: 3)**, the entry is `abandon`ed (terminal) instead of re-opened, and a terminal finding `blackboard.claim_orphan_abandoned::<entry_id>` is posted. This is the F-19 Type-B "daemon cannot self-heal" signal — **ratified to fold into the F-19 `stuck` bucket**, not into silent backlog. Per ADR-070 D8, this rail ships in the same change as the reaper, not later.

### D4 — The reaper is not a silent instrument

Every cycle, the released count is included in the `blackboard_shop_manager.run.complete` report. When `> 0`, a `blackboard.claim_orphaned::<entry_id>` finding is posted per reaped entry (`resolution_mechanism='self_resolve'`, auto-resolving when the entry next reaches terminal). A reaper that silently restored claims would be exactly the failure `CORE-Instrument-Attestation` names; the count is its liveness tell.

### D5 — Fail-safe: never reap on an unavailable liveness source

If `fetch_alive_workers` fails or returns an empty set, the sweep is **skipped for that cycle** and logs a warning. Reaping against an empty alive-set would mass-release every claim on a transient registry glitch. The reaper biases toward inaction when it cannot establish who is alive.

### D6 — Governed configuration, no hardcoded thresholds

`claim_grace_seconds`, the reclaim cap N, and `batch_max` live in `operational_config` (the `blackboard` section, beside the existing ADR-082 sweep config). The alive-threshold is the ADR-041 governed value. No magic numbers in `src/`.

### D8 — Workers renew a liveness lease mid-run (the rail that makes the reaper safe) — *Revision B, ships with the reaper*

The reaper's liveness test (D1 condition 3) is only honest if a still-working worker keeps proving it is alive. Today `post_heartbeat` fires once at run-start, so a worker holding a claimed batch for longer than the alive-threshold becomes indistinguishable from a dead one and would be wrongly reaped (see D1). Therefore:

- A worker that holds one or more claims **renews its liveness** (re-`post_heartbeat`, updating `worker_registry.last_heartbeat`) on a cadence strictly shorter than the alive-threshold, for as long as it holds claims within a single `run()`. This is the **lease** ADR-069 D2/D6 forecast: a held claim is a lease the owner must renew; a lease that lapses past the alive-threshold is, by definition, abandoned, and *only then* is the holder provably gone.
- Per **ADR-070 D8** (rails ship with the destructive op), this lease renewal lands in the **same change-set** as the reaper. Shipping the reaper without it would be shipping an autonomous claim-releaser whose "is the owner dead?" test returns false positives against healthy long runs — a destructive op without its rail.
- Renewal cadence is governed in `operational_config` (`lease_renew_interval_sec`), bounded below the alive-threshold with margin. No magic numbers in `src/`.

The lease is folded into ADR-104 rather than given its own ADR because the reaper is *unsafe in isolation*: the two are one concern (safe recovery of ungraceful-death orphans) with a recovery half and a renewal half. Provenance is ADR-069 D2/D6; this ADR realizes it.

### D7 — What this ADR explicitly does NOT decide

- **Claim TTL independent of liveness.** This ADR defines orphanhood by owner-liveness, not by a fixed claim age. A separate "a claim older than T is suspicious even if its owner is alive" policy is out of scope.
- **Changing how claims are taken.** The `WHERE claimed_by IS NULL` claim predicate is unchanged.
- **Mutation-sandbox lifecycle.** ADR-071 D2.2 governs orphaned `var/tmp/core-action-sandbox-*` directories; their cleanup is a separate concern from claim release.

---

## Ratifications (governor — 2026-06-13)

The three original open questions are resolved at the drafter-proposed values; Revision B adds a fourth, decided the same day:

1. **Reclaim cap N** (D3) — **3.** Tolerates two transient crashes before declaring a finding non-self-healing; balanced against reclaim-loop risk.
2. **`claim_grace_seconds`** (D1) — **= the ADR-041 alive-threshold (currently 600 s).** "Not alive" and "past grace" read off one clock; no second governed number to drift. *Revision B note:* this value is only **safe** because D8's lease makes the alive-set honest; the same-clock simplification would have produced live-worker reaps without the lease.
3. **Orphan-abandon folds into the F-19 `stuck` bucket** (D3) — **yes.** It is genuinely "daemon cannot self-heal" (Type-B); it must surface as `stuck`, not as invisible permanent `total_open` backlog. Implementation routes it through a subject the `F19_CONVERGENCE_SQL` Type-B classifier captures, or adds it explicitly to that classifier (the implementation change-set verifies which).
4. **Slow-worker safety mechanism** (D8, Revision B) — **the lease (workers renew liveness mid-run while holding claims).** Chosen over a conservative reaper ceiling or generation-scoped reaping because it makes the liveness signal *true* rather than guessing a margin, and it realizes the ADR-069 D2/D6 lease that was already named as the recovery path.

## Revision B — altitude-review corrections (2026-06-13)

After the original three ratifications, a "step back — are we doing it right" review found two issues the drafting recon missed:

- **Grounding correction.** The original "released only at normal loop completion" was wrong: ADR-069 D8's `Worker.start()` `finally` block already releases on graceful shutdown and on exception. The real gap is **ungraceful death only**. Gap statement, "Why … orphans," and severity corrected; ADR-069 added to Grounding.
- **Correctness gap → D8.** The ratified liveness test (D1 condition 3) would have reaped *live* slow workers, because heartbeats fire only at run-start. Resolved by the D8 lease, which ships with the reaper per ADR-070 D8.

Both materially grow scope (D8 + lease config + a slow-worker-not-reaped test), so Status returned to **Proposed** for a clean acceptance of the revised decision set.

---

## Consequences

### Forward visibility

- The daemon becomes closer to kill-at-any-instant safe: a restart or crash mid-claim self-heals within one `BlackboardShopManager` cycle instead of leaving a permanent stuck finding.
- The operator no longer has to query `status='claimed'` to judge whether a restart is safe — the invariant the reaper enforces is the answer.
- F-19 backlog stops being silently inflated by orphaned-but-unresolvable claims; genuine non-self-healing work surfaces as `stuck` (D3) rather than as invisible permanent `total_open`.

### Non-changes

- The claim-taking path, the mutation sandbox, and the existing ADR-082 sweeps are unchanged.
- No new worker, no new registration — one sweep added to an existing janitor cycle. (Revision B does touch the `Worker` base contract for the D8 lease — see below; this is not a *new* worker, but it is a base-class change beyond the original "one sweep" framing.)

### Acceptance criteria

1. `BlackboardService.release_orphaned_claims` exists, batched and bounded, with a basic test covering: an orphaned claim (dead owner, past grace) is released; a claim held by a live uuid is **not** released; the fail-safe skips on an empty alive-set.
2. `BlackboardShopManager.run()` calls it each cycle and reports the count (D4).
3. The reclaim cap (D3) abandons after N and posts the terminal finding, with a test.
4. `claim_grace_seconds`, N, `batch_max`, and `lease_renew_interval_sec` resolve from `operational_config` (D6/D8).
5. **(Revision B / D8)** A worker holding a claim renews its liveness on the governed cadence, with a test proving a worker whose run exceeds the alive-threshold but keeps renewing is **not** reaped (the live-slow-worker case D1 calls out).
6. The four ratifications (incl. the D8 lease) are resolved and reflected before `Status: Accepted`.

Implementation lands as one change-set after acceptance, with tests in the same change (signature/behaviour changes carry their tests).
