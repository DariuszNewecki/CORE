<!-- path: .specs/decisions/ADR-104-orphaned-claim-reaper.md -->

# ADR-104 — Orphaned-claim reaper (claim lifecycle is process-scoped, not loop-scoped)

**Date:** 2026-06-13
**Status:** Proposed (draft for governor review)
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-13 — drafted under explicit "yes, draft the ADR stub" authorization, following a recon that confirmed `release_claimed_entries` is called only inside worker run-loops at normal completion, with no startup or janitor sweep releasing claims held by dead workers. Governor pre-selected the continuous-sweep approach over a startup-only reaper, and elected to anchor the new autonomous rail in an ADR before implementation.)

**Grounding decisions:**
- ADR-082 — writer-as-sensor retention policy; established `BlackboardShopManager` as the blackboard janitor running bounded hygiene sweeps (telemetry TTL, DELEGATE-finding TTL, stale-alert auto-resolution). This ADR adds one more sweep of the same class.
- ADR-070 D8 — destructive/rate-limited autonomous operations must ship their rails (row caps) in the same change. The reclaim cap (D3) is that discipline applied to the reaper.
- ADR-071 D2.2 — atomic actions sandbox their production in `var/tmp/core-action-sandbox-<uuid>/`; the *mutation* is already restart-safe. This ADR closes the residual leak: the *claim* is not.
- ADR-041 — governed per-worker liveness thresholds; the "alive worker uuids" set that defines orphanhood is read through `WorkerRegistryService` at the ADR-041 threshold.

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

### The gap

A worker claims a blackboard finding by setting `status='claimed'`, `claimed_by=<worker_uuid>`. It releases the claim — `release_claimed_entries`, resetting to `open` — **only at normal loop completion** (`violation_remediator`, `test_remediator`, `violation_executor`). There is no other release path:

- No startup hook releases claims left by a previous daemon generation.
- No janitor sweep releases claims whose owner has died mid-work.

`BlackboardShopManager` *detects* SLA-stale entries and posts `blackboard.entry_stale` findings about them, but it **never resets the claim** — detection without remediation.

### Why a restart guarantees orphans

Worker UUIDs differ across daemon generations (documented at `blackboard_shop_manager.py:257`, which deduplicates stale findings *by subject* precisely because poster UUIDs change across restarts). Therefore a claim held by a pre-restart worker is owned by a `worker_uuid` that **is never alive again**. It is permanently stuck in `claimed`, and because claims are taken `WHERE claimed_by IS NULL`, that finding is never re-processed by any future generation. A single-worker crash without a full restart produces the same orphan.

### Severity — latent, not on fire

At authoring time `SELECT COUNT(*) WHERE status='claimed'` returns **0** — nothing was mid-claim at the last restart. The gap bites only when a restart or crash lands while a mutation worker holds a claim. Real, probabilistic, and silent when it happens: the loss is a finding that never resolves, which inflates backlog and the F-19 convergence trajectory without any error surfacing.

### Why continuous, not startup-only

A startup-only reaper would close the restart case but miss claims orphaned by a single-worker crash between restarts. Because orphanhood is defined by *owner liveness* (not by a restart event), a continuous sweep in the existing janitor cycle catches both, composes with the ADR-082 hygiene sweeps already running there, and needs no new worker or registration. This is the runtime-gate-over-startup-hook posture: self-heal on a cadence, fail loud, don't depend on a clean shutdown.

---

## Decisions

### D1 — Orphaned claims are reaped continuously by `BlackboardShopManager` (constitutional)

Each `BlackboardShopManager` cycle releases orphaned claims via a new bounded sweep. A claim is **orphaned** iff all hold:

1. `status = 'claimed'`;
2. `claimed_at < now() - claim_grace_seconds` (a grace window so an entry just claimed by a worker that has not yet emitted its run-start heartbeat is not yanked); and
3. `claimed_by` is **not** in the set of currently-alive worker uuids from `WorkerRegistryService.fetch_alive_workers(threshold = ADR-041 alive_threshold)`.

Condition (3) is the safety invariant: a claim is only reaped when its owner is *provably gone*. A live, long-working worker keeps its claim because it keeps heartbeating.

### D2 — Release semantics reuse the existing reset

A reaped claim is reset to `status='open'`, `claimed_by=NULL` — the exact semantics of `release_claimed_entries`. The finding re-enters the work queue for a live worker to reclaim. A new bounded method `BlackboardService.release_orphaned_claims(live_uuids, grace_seconds, batch_max)` performs this as a single batched `UPDATE` and returns the released count.

### D3 — Reclaim rail: abandon after N orphan-releases

To prevent a crash→reclaim→crash→reap loop on a genuinely unprocessable finding, each entry tracks an `orphan_release_count`, incremented on each reap. When it reaches **N (proposed: 3 — governor to ratify)**, the entry is `abandon`ed (terminal) instead of re-opened, and a terminal finding `blackboard.claim_orphan_abandoned::<entry_id>` is posted. This is the F-19 Type-B "daemon cannot self-heal" signal — it counts toward `stuck`, not toward silent backlog. Per ADR-070 D8, this rail ships in the same change as the reaper, not later.

### D4 — The reaper is not a silent instrument

Every cycle, the released count is included in the `blackboard_shop_manager.run.complete` report. When `> 0`, a `blackboard.claim_orphaned::<entry_id>` finding is posted per reaped entry (`resolution_mechanism='self_resolve'`, auto-resolving when the entry next reaches terminal). A reaper that silently restored claims would be exactly the failure `CORE-Instrument-Attestation` names; the count is its liveness tell.

### D5 — Fail-safe: never reap on an unavailable liveness source

If `fetch_alive_workers` fails or returns an empty set, the sweep is **skipped for that cycle** and logs a warning. Reaping against an empty alive-set would mass-release every claim on a transient registry glitch. The reaper biases toward inaction when it cannot establish who is alive.

### D6 — Governed configuration, no hardcoded thresholds

`claim_grace_seconds`, the reclaim cap N, and `batch_max` live in `operational_config` (the `blackboard` section, beside the existing ADR-082 sweep config). The alive-threshold is the ADR-041 governed value. No magic numbers in `src/`.

### D7 — What this ADR explicitly does NOT decide

- **Claim TTL independent of liveness.** This ADR defines orphanhood by owner-liveness, not by a fixed claim age. A separate "a claim older than T is suspicious even if its owner is alive" policy is out of scope.
- **Changing how claims are taken.** The `WHERE claimed_by IS NULL` claim predicate is unchanged.
- **Mutation-sandbox lifecycle.** ADR-071 D2.2 governs orphaned `var/tmp/core-action-sandbox-*` directories; their cleanup is a separate concern from claim release.

---

## Open ratifications (governor)

These are drafter proposals, not yet decided — the reason this is a stub:

1. **Reclaim cap N** (D3) — proposed 3. Lower is safer against loops, higher tolerates flaky-but-recoverable work.
2. **`claim_grace_seconds`** (D1) — proposed = the ADR-041 alive-threshold (so "not alive" and "past grace" use one clock). Alternative: a dedicated shorter grace.
3. **Does orphan-abandon fold into the F-19 `stuck` bucket** (D3) — proposed yes (it is genuinely "daemon cannot self-heal"), via a subject the `F19_CONVERGENCE_SQL` Type-B classifier already captures, or an explicit add to that classifier.

---

## Consequences

### Forward visibility

- The daemon becomes closer to kill-at-any-instant safe: a restart or crash mid-claim self-heals within one `BlackboardShopManager` cycle instead of leaving a permanent stuck finding.
- The operator no longer has to query `status='claimed'` to judge whether a restart is safe — the invariant the reaper enforces is the answer.
- F-19 backlog stops being silently inflated by orphaned-but-unresolvable claims; genuine non-self-healing work surfaces as `stuck` (D3) rather than as invisible permanent `total_open`.

### Non-changes

- The claim-taking path, the mutation sandbox, and the existing ADR-082 sweeps are unchanged.
- No new worker, no new registration — one sweep added to an existing janitor cycle.

### Acceptance criteria

1. `BlackboardService.release_orphaned_claims` exists, batched and bounded, with a basic test covering: an orphaned claim (dead owner, past grace) is released; a claim held by a live uuid is **not** released; the fail-safe skips on an empty alive-set.
2. `BlackboardShopManager.run()` calls it each cycle and reports the count (D4).
3. The reclaim cap (D3) abandons after N and posts the terminal finding, with a test.
4. `claim_grace_seconds`, N, and `batch_max` resolve from `operational_config` (D6).
5. The three open ratifications are resolved and reflected before `Status: Accepted`.

Implementation lands as one change-set after acceptance, with tests in the same change (signature/behaviour changes carry their tests).
