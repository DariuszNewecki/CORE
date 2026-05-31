<!-- target path (on acceptance): .specs/decisions/ADR-041-per-worker-liveness-thresholds-and-orphan-skip.md -->

# ADR-041 — Per-worker liveness thresholds and orphan-skip in the DAL

**Date:** 2026-05-12
**Status:** Accepted
**Author:** Draft for governor review
**Amends:** ADR-020 D3 (DAL signature). ADR-020 D1, D2, D4 preserved.
**Related:** ADR-020 (worker liveness derived from heartbeat); 2026-05-12 governance dashboard investigation

---

## Context

ADR-020 established `last_heartbeat` as the canonical liveness signal (D1), retired the dead `status` column (D2), centralised the reader pattern in `WorkerRegistryService` (D3), and noted that per-worker thresholds live in `.intent/workers/*.yaml` (D4). It explicitly accepted (D4) that the dashboard's "alive count" panel would use a single global threshold rather than per-worker semantics, on the grounds that dashboards are imprecise by nature and the supervisor (`WorkerShopManager`) handles the precise case.

Two failure modes surfaced during the 2026-05-12 governance dashboard session that ADR-020 did not anticipate:

### Failure mode 1 — long-cadence workers false-positive against the global threshold

`CommitReachabilityAuditor` declares `schedule.max_interval: 3600` (runs hourly). At 41 minutes since its last heartbeat — fully within its declared schedule — the dashboard flags it stale. ADR-020 D4 accepted this trade-off in principle. In practice, the 2026-05-12 session showed that the noise from this trade-off **mixes with real signals on the same panel**, and an operator cannot distinguish acknowledged-imprecision from a real worker stall by looking at the dashboard alone. The trade-off is more expensive than ADR-020 estimated.

### Failure mode 2 — orphan registry rows

Three rows in `core.worker_registry` are now orphans — their `worker_uuid` values are not declared by any active `.intent/workers/*.yaml`:

- `a1b2c3d4-…ef1234567890` (was Audit Ingest Worker, rotated to a fresh UUID; the YAML is now `status: paused`)
- `a2b3c4d5-…f12345678902` (was Repo Embedder, rotated to a fresh UUID)
- (the third worker's old UUID was cleaned up by `Worker._register()` `ON CONFLICT` update — see ADR-020 D2 amendment, not in scope here)

These rows have a frozen `last_heartbeat` — no process is updating them and none ever will. They are also not flagged by any current SQL filter. ADR-020 has nothing to say about them because UUID rotation as a maintenance operation post-dates it: the orphan class did not exist in 2026-05-02.

`WorkerShopManager` (session 2026-05-12) gained an orphan-skip filter so it stops posting false `worker.silent` findings against these rows. The DAL methods named in ADR-020 D3 (`fetch_stale_workers`) have no equivalent filter — they return the orphan rows as stale.

### Why both readings of the situation are uncomfortable

- **Strict ADR-020 compliance.** Per D4 the dashboard's global-threshold imprecision is acknowledged and accepted. The orphan problem is new and uncovered by ADR-020 — clearly the DAL needs an orphan-skip. But CommitReachabilityAuditor stays a false-positive. Two of three is solved; one is "by design."
- **Bypass via blackboard.** A separate ADR proposed earlier in this session would have made `worker.silent` findings the canonical signal (replacing D1's heartbeat derivation). This was rejected here because it conflicts directly with ADR-020 D1, which is correct on its merits — the heartbeat is the cheapest, most direct fact, and ADR-020's analysis of why supervision should not own state mutation still holds.

The minimal change that fully resolves both failure modes without disturbing ADR-020's core (D1, D2) is to **strengthen D3 to apply per-worker thresholds** (a tighter DAL signature) and **add D5 to formalise orphan-skip** (a new policy uncovered by post-ADR-020 maintenance practice).

---

## Decisions

### D1 — ADR-020 D1, D2, D4 (in part) preserved

`last_heartbeat` remains the canonical liveness signal (ADR-020 D1). The `status` column stays retired (ADR-020 D2). Per-worker thresholds remain declared in `.intent/workers/*.yaml` (ADR-020 D4 partial).

The part of ADR-020 D4 that is no longer in force: the dashboard's "alive count" panel is no longer permitted to use a single global threshold across all workers. Long-cadence workers MUST be compared against their own declared `max_interval + glide_off`.

### D2 — Amendment to ADR-020 D3 — per-worker thresholds in the DAL

`WorkerRegistryService` gains a new method whose signature accepts per-worker threshold data:

```python
async def fetch_stale_workers_with_schedules(
    self,
    thresholds: dict[str, int],   # worker_uuid (str) → max_interval + glide_off
    active_uuids: set[str],       # UUIDs declared by active YAMLs (orphan-skip)
    fallback_sec: int,            # threshold for active workers w/o schedule
) -> list[dict[str, Any]]:
    """Return worker_registry rows considered stale under per-worker rules."""
```

The previous `fetch_stale_workers(threshold_sec)` is preserved for compatibility and marked deprecated. It is removed in a follow-up commit once all callers migrate.

### D3 — Orphan-skip is policy, not a local supervisor heuristic

Liveness reads across the system MUST exclude `worker_registry` rows whose `worker_uuid` is not declared by any `.intent/workers/*.yaml` with `status: active`. The orphan-skip rule moves out of `WorkerShopManager`'s local implementation and into a shared schedule-loader module (`shared/workers/schedule.py`) that all readers consume.

A registry row whose UUID matches no active YAML represents one of:

- a worker that was renamed/rotated (the new UUID is the live one);
- a worker that was deleted from declarations;
- a worker whose YAML was switched to `status: paused`.

In all three cases the row's `last_heartbeat` will never be refreshed by a live process, so any threshold-based liveness check will eventually classify it as stale forever. The orphan-skip is therefore not an optimisation — it is the correctness condition under which liveness reads remain meaningful in the presence of declaration drift.

### D4 — One YAML-reader for all readers

The YAML-scanning logic that produces `(thresholds, active_uuids, fallback_sec)` is centralised in a new module `src/shared/workers/schedule.py`. Both `WorkerShopManager` (the producer of `worker.silent` findings) and `WorkerRegistryService` callers (dashboard, health_log_service) consume this single loader. WorkerShopManager's existing local methods (`_load_worker_thresholds`, `_load_active_worker_uuids`, added session 2026-05-12) are removed and replaced with a single call to the shared loader.

The `WorkerScheduleState` returned by the loader also carries `fallback_sec` — the canonical liveness threshold for active workers that declare no `schedule` block, sourced from `operational_config.workers.worker_shop.fallback_threshold_sec`. All readers (and the producer) take their fallback from this single field rather than each loading the value from config independently; this closes the last drift surface (e.g. the dashboard's pre-ADR-041 path used `_CFG_H.worker_alive_threshold_sec`, a different config key).

This prevents the drift that motivated this ADR from recurring at the YAML-reading layer: there is one place where `.intent/workers/*.yaml` is scanned for schedule data, and one place where the no-schedule fallback is sourced.

### D5 — Dashboard binary stale/alive

The dashboard's "Loop Running" panel currently distinguishes amber (silent 10–60 min) from red (silent > 60 min) using two hardcoded cut-offs. Under D2 these cut-offs are no longer the rule — per-worker thresholds are. The amber/red distinction loses its semantic basis and becomes binary: a worker is either over its own declared threshold (stale, red) or it isn't (alive, green).

If a future ADR re-introduces a tiered display, it does so on top of per-worker thresholds (e.g., red at `2× max_interval`), not on a global cut-off.

---

## Consequences

**Positive**

- The three false positives observed 2026-05-12 (Audit Ingest, Repo Embedder, Commit Reachability Auditor) all clear without any change to ADR-020 D1's canonical premise. The system reads what it always read; it just applies the right thresholds and skips dead rows.
- WorkerShopManager and the dashboard inherit the same liveness rule by shared construction (D4), not by separate maintenance. Drift at the YAML-reading layer becomes structurally impossible.
- The DAL's signature becomes type-honest: liveness depends on per-worker data, and the type system now says so.

**Negative**

- The amber tier on the dashboard's Loop Running panel disappears (D5). Operators who relied on the amber-vs-red distinction lose it. Restoring tiers in a follow-up ADR is straightforward (e.g., "red at 2× threshold") but is not included here to keep this change minimal.
- `WorkerRegistryService.fetch_stale_workers(threshold_sec)` remains in place for one commit cycle before being removed. Brief temporary surface duplication.
- Dashboard reads now require a YAML scan per render. Cheap (~ten files), but no longer pure SQL. Mitigated by caching at the shared loader level if needed.

**What does *not* change**

- ADR-020 D1: `last_heartbeat` is the canonical signal. Unchanged.
- ADR-020 D2: `status` column stays retired. Unchanged.
- WorkerShopManager's role as producer of `worker.silent` findings is unchanged. Other readers do not consult those findings — they apply the same rule to the same source data (`last_heartbeat`).
- The constitutional contract for workers (declare in `.intent/workers/`, register, heartbeat, blackboard) is unchanged.

---

## Implementation

1. **New module** `src/shared/workers/schedule.py` exposes:

   ```python
   @dataclass(frozen=True)
   class WorkerScheduleState:
       thresholds: dict[str, int]      # worker_uuid (str) → max_interval + glide_off
       active_uuids: frozenset[str]    # status: active YAMLs
       fallback_sec: int               # threshold for active workers w/o schedule

   def load_worker_schedule_state() -> WorkerScheduleState: ...
   ```

   Pure function over `.intent/workers/*.yaml`. Keying changed from worker_name (in WorkerShopManager's pre-ADR-041 local methods) to worker_uuid — UUIDs are ASCII by definition and present at every lookup site, so the SQL_ASCII title-sanitisation step that the local methods needed is no longer required.

2. **WorkerShopManager migration.** `_load_worker_thresholds` and `_load_active_worker_uuids` are removed. The supervisor calls `load_worker_schedule_state()` once per cycle and reads `thresholds[worker_uuid]` directly, with `state.fallback_sec` as the fallback. The lookup key switches from sanitised worker_name to worker_uuid to match the new shared shape.

3. **DAL extension.** `body/services/worker_registry_service.py` gains `fetch_stale_workers_with_schedules` per D2. The query fetches registered rows + `seconds_silent` (it already does this), then applies per-row threshold + orphan-skip in Python — the data shape requirements (variable threshold per row) don't fit one SQL parameter cleanly, and the row count is small enough that post-query filtering is appropriate.

4. **Dashboard migration.** `cli/resources/runtime/health.py` "Loop Running" panel calls `load_worker_schedule_state()` and `fetch_stale_workers_with_schedules(...)`. The dual-cutoff branch is removed; result is binary stale/alive (D5).

5. **health_log_service migration.** `body/services/health_log_service.py` `silent_workers` count uses the same DAL method. Out-of-scope reader (`admin/health.py`) reads the persisted snapshot; no change needed there.

6. **Deprecation.** `fetch_stale_workers(threshold_sec)` is kept for one commit, then removed in a follow-up after migration is verified.

---

## Verification

After implementation:

- The three false-positive workers (Audit Ingest, Repo Embedder, Commit Reachability Auditor) are absent from the dashboard's Loop Running stale list.
- `core-admin runtime health` shows the same alive/stale set as a manual query of `WorkerRegistryService.fetch_stale_workers_with_schedules(...)`.
- The next `system_health_log` snapshot reports a `silent_workers` count consistent with WorkerShopManager's blackboard findings (the two are now derived from the same source data via the same rule).
- WorkerShopManager's behaviour observably unchanged (same findings posted, same auto-resolution cadence).

---

## Note — 2026-05-31 (post-implementation observation)

A 3-hour cycle measurement during the 2026-05-31 runtime-health investigation falsified one claim above and surfaced two adjacent gaps. This Note records the divergence; the original decisions (D1–D5) stand.

### One verification claim no longer holds

The Verification section (above) names Repo Embedder among workers absent from the dashboard's Loop Running stale list. Today's measurement: Repo Embedder declares `max_interval: 600` and has observed max cycle gap 1864s (avg 840s). It trips its threshold on every cycle spike. The other two named workers still fit (Audit Ingest at 1800, Commit Reachability Auditor at 3600). Repo Embedder's value was either insufficient at acceptance time and undetected, or its cycle grew post-acceptance; either way the verification claim against it is stale.

### Two readers were left on the pre-ADR-041 path

D5 migrated the dashboard's Loop Running panel to per-worker thresholds. Not migrated: `cli/resources/runtime/health.py::_worker_colour` and `_liveness_label` (the Workers table in `core-admin runtime health`) — both still read `_CFG_H.worker_alive_threshold_sec` (a global value). The runtime health Workers view therefore continues to false-positive against long-cadence workers exactly as ADR-020 D4 originally accepted, even though D1/D5 said the dashboard would not. `cli/resources/admin/health.py` is a candidate for the same check.

### Value-vs-reality drift is uncovered by this ADR — #516 owns it

D4 closed *reader-side* drift: all consumers of liveness thresholds now go through `load_worker_schedule_state`. It did not close *value-side* drift: that the configured `max_interval` matches the worker's actual cycle behavior. With no audit enforcing this invariant, values silently fall out of fit as workloads change. 2026-05-31 measurement: 10 of 11 long-cadence workers configured at `max_interval: 600` had observed max gaps exceeding 660s; 9,125 false-positive `worker.silent` findings accumulated over 7 days (62% of the abandoned pile).

Interim manual fix: commit `329919d4` bumped four worker YAMLs (`audit_sensor_architecture`, `audit_sensor_purity`, `audit_sensor_cli`, `repo_crawler`) to `max_interval: 1200`. The remaining unfit workers are intentionally not patched in advance of #516 — the right closure is a measurement-vs-config audit rule, not a sweep of hand-tuned values.

Tracking issue: **#516 — "Worker max_interval values are unmeasured — no audit ensures config matches observed cycle reality."**
