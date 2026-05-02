<!-- path: .specs/decisions/ADR-020-worker-liveness-derived-from-heartbeat.md -->

# ADR-020 — Worker liveness derived from heartbeat, not from registry status

**Status:** Accepted
**Date:** 2026-05-02
**Author:** Darek (Dariusz Newecki)
**Closes:** #184
**Supersedes:** nothing
**Related:** `papers/CORE-ShopManager.md`, `papers/CORE-Authority-Without-Registries.md`, ADR-015 (consequence chain attribution), #173 (dashboard fix that surfaced the underlying gap), #174 (autonomy idle since restart — sharper diagnosis after this ADR)

---

## Context

Three workers — Audit Ingest, Vector Sync, Repo Crawler — were observed registered with `status='active'` in `core.worker_registry` while no corresponding process was running. The dashboard fix landed in #173 now renders these as `stale` correctly by deriving liveness from `last_heartbeat`, but the registry row's `status` column still claims they are active. #184 was opened to decide what `status` should mean and who maintains it.

The investigation that motivated this ADR establishes the following.

### What the schema declares

The SQLAlchemy model at `shared/infrastructure/database/models/workers.py` defines:

```python
status: Mapped[str] = mapped_column(
    Text, nullable=False, server_default="active"
)  # active | stopped | abandoned
```

The schema declares a three-state machine: `active | stopped | abandoned`.

### What the code actually writes

Two write paths to `core.worker_registry` exist in the current tree, both in `shared/workers/base.py`:

1. `Worker._register()` — `INSERT … VALUES (…, 'active', now()) ON CONFLICT … DO UPDATE SET status='active', last_heartbeat=now()`.
2. `Worker._post_entry()` heartbeat branch — `UPDATE … SET last_heartbeat=now(), status='active' WHERE worker_uuid=…`.

No write path in the current tree ever sets `status='stopped'` or `status='abandoned'` on a `worker_registry` row. The declared state machine has no transition logic. It is dead-on-arrival.

### What `last_heartbeat` actually does

`last_heartbeat` is faithfully maintained: written on register, written on every heartbeat. It is the only column that reflects supervision reality.

### What the readers do

- **`WorkerShopManager`** (`will/workers/worker_shop_manager.py`) reads `seconds_silent = EXTRACT(EPOCH FROM (now() - last_heartbeat))` and posts `worker.silent::{worker_uuid}` blackboard findings when a worker exceeds its declared `max_interval + glide_off`. It does not read `status` for liveness; it only filters out `'abandoned'` rows.
- **The runtime-health dashboard** (`cli/resources/runtime/health.py`) filters `WHERE status='active'` to bound the scan, then derives stale/red/amber from `last_heartbeat` against 10-minute and 60-minute thresholds. The `status` filter does no liveness work; it is a holdover that happens to function only because nothing ever writes anything other than `'active'`.

### Historical residue

A diagnostic in `.specs/state/2026-04-20-daemon-reactivation-recon.md` records 20 rows with `status='abandoned'` in production, oldest 2026-03-13, newest 2026-04-07, no growth since. These are residue from a write path that no longer exists. There is no `core-admin` command to clean them; only raw SQL. They are operational debt.

### What the constitutional law says

`papers/CORE-ShopManager.md` §3 places liveness in heartbeats: *"Detects Workers that have not posted a heartbeat within SLA."* The supervisor's power is to *detect and post a finding*, not to transition registry state. The paper does not assign `worker_registry.status` mutation to any worker.

`papers/CORE-Authority-Without-Registries.md` §1 captures the failure mode this ADR addresses: *"Static registries often become de facto sources of truth, creating hidden coupling between law and machinery. This coupling leads to drift: the registry becomes authoritative, while the law decays."* The scope of that paper is constitutional rule authority, not runtime supervision, but the diagnosis transfers exactly: `worker_registry.status` is a registry value that has become a de-facto source of truth (the dashboard reads it) while drifting from the actual law (heartbeats).

### Summary of the gap

Two columns encode supervision: `status` (a shadow that nothing maintains) and `last_heartbeat` (the actual signal). When they disagree — as they currently do for the three workers in #184 and the 20 historical `abandoned` rows — `last_heartbeat` is right and `status` is wrong. The system has been running on `last_heartbeat` all along; `status` is a vestigial column.

---

## Decisions

### D1 — `last_heartbeat` is the canonical liveness signal

A worker is alive if and only if its `last_heartbeat` is within a declared threshold. The threshold is per-worker, computed from each worker's `.intent/workers/*.yaml` `mandate.schedule.max_interval + glide_off`, with `_FALLBACK_THRESHOLD = 600` seconds for workers without a schedule declaration. This is the same derivation `WorkerShopManager` already performs.

No other column in any table is authoritative for liveness. Anything that needs to know whether a worker is alive reads `last_heartbeat` and applies the threshold.

### D2 — Drop the `status` column from `core.worker_registry`

`core.worker_registry.status` is removed. The schema's declared `active | stopped | abandoned` state machine is retired in full. The migration:

1. Adds a SQL migration script `infra/scripts/migrations/20260502_drop_worker_registry_status.sql` that runs `ALTER TABLE core.worker_registry DROP COLUMN status;`.
2. Removes the `status` field from `shared/infrastructure/database/models/workers.py`.
3. Updates `Worker._register()` and `Worker._post_entry()` (in `shared/workers/base.py`) to drop `status` from their INSERT/UPDATE statements.
4. Updates every reader of `worker_registry.status` to either drop the filter or replace it with the `last_heartbeat`-derived check (see D3).

The 20 historical `abandoned` rows do not need separate cleanup — they are absorbed into the migration. After the column drop, every row in `worker_registry` represents a registered worker, and its liveness is determined by its heartbeat freshness alone.

### D3 — Centralize liveness derivation in `WorkerRegistryService`

`body/services/worker_registry_service.py` gains a single method whose query encodes the threshold-based liveness check. The existing `fetch_registered_workers()` already computes `seconds_silent`; D3 builds on that. Two new shapes are added, both pure DAL, no new responsibility:

- `fetch_alive_workers(threshold_sec: int) -> list[dict]` — returns rows where `last_heartbeat > now() - INTERVAL ':threshold seconds'`.
- `fetch_stale_workers(threshold_sec: int) -> list[dict]` — returns rows where `last_heartbeat <= now() - INTERVAL ':threshold seconds'`, along with `seconds_silent`.

Callers that previously filtered `WHERE status='active'` migrate to one of these. Callers that previously joined on `(worker_name, status='active')` (the runtime-health Violation Executor lookup at `cli/resources/runtime/health.py:45849` in the export) drop the status clause and rely on `worker_name` plus the alive predicate.

This centralization preserves the architectural invariant from `papers/CORE-ShopManager.md`: supervisors and dashboards read the same source of truth (heartbeat freshness) and derive liveness through the same predicate.

### D4 — Per-worker thresholds remain owned by `.intent/workers/*.yaml`

The constitutional source of a worker's heartbeat SLA stays where it is: in the worker's own declaration. `WorkerShopManager` already loads these thresholds; D3 does not duplicate that responsibility. Service callers that need a generic threshold for table-wide queries (e.g., the dashboard's "alive count" panel) use a single declared default, sourced from `.intent/enforcement/config/governance_paths.yaml` (or the equivalent appropriate config path; the exact key is left to the implementation pass).

This ADR does not change the existing per-worker threshold logic in `WorkerShopManager`. It only declares that the same derivation pattern is the only sanctioned liveness signal anywhere in the system.

---

## Consequences

### Forward changes required to close #184

1. **Migration** — `infra/scripts/migrations/20260502_drop_worker_registry_status.sql` drops the column. Forward-only; no rollback path because the column carried no information not derivable from `last_heartbeat`.
2. **Model update** — `shared/infrastructure/database/models/workers.py` removes the `status` field from the `WorkerRegistry` mapped class.
3. **Worker base updates** — `shared/workers/base.py` removes `status` from the `INSERT` in `_register()` and from the heartbeat `UPDATE` in `_post_entry()`. The constitutional contract is unchanged: workers still register, still heartbeat, still post blackboard entries. Only the dead column reference is removed.
4. **DAL update** — `body/services/worker_registry_service.py`:
   - `fetch_registered_workers()` removes `status` from its `SELECT` projection and removes the `WHERE status != 'abandoned'` clause.
   - Adds `fetch_alive_workers(threshold_sec)` and `fetch_stale_workers(threshold_sec)` per D3.
5. **Reader migration** — `cli/resources/runtime/health.py`: the "Loop Running" panel and the "Autonomous Reach" panel both query `WHERE status='active'`. Both queries change to use the new DAL methods. The dashboard's behavior is unchanged from the user's perspective; only its source of truth tightens.
6. **WorkerShopManager** — no change required. The supervisor already reads `seconds_silent`; it never relied on `status` for liveness. It does not need to be updated.

### Side effect on #174

`#174` (autonomy idle since restart) is plausibly upstream-caused by registry/supervision drift. After this ADR lands, the dashboard's liveness display becomes the authoritative status check. The diagnosis for `#174` sharpens: whatever the daemon is or is not doing, the alive-vs-stale view of `worker_registry` will reflect it accurately. This ADR does not directly resolve `#174`; it makes the symptom legible.

### What does *not* change

- `core.blackboard_entries.status` is unrelated to `worker_registry.status` and is not in scope. The blackboard's status column has real, well-defined transitions (`open | claimed | resolved | abandoned`) that are actively maintained by multiple workers.
- The constitutional contract for workers (mandatory `.intent/workers/` declaration, mandatory blackboard write per cycle, mandatory heartbeat) is unchanged.
- Per-worker SLAs declared in `.intent/workers/*.yaml` are unchanged.

### Migration ordering

The migration is forward-only, applied in this order:
1. Apply the SQL migration (drops the column).
2. Land code changes in a single commit (model, base worker, DAL, dashboard readers).
3. Restart the daemon.

The dependency direction matters: dropping the column first breaks code that still references it, so the SQL and code changes are co-deployed. Standard procedure for additive-then-removal would not help here — the column was never information-bearing for the writers. There is nothing to migrate *from*; only references to remove.

---

## Alternatives considered

**Alternative A — Implement the declared state machine.** Keep `status` and add the missing transitions: `Worker.shutdown()` writes `'stopped'` on graceful exit; daemon-startup reconciliation writes `'stopped'` for any `'active'` row whose `last_heartbeat` is stale and whose process is not currently registered; some additional path writes `'abandoned'` for terminally lost rows. This was the path implied by `#184`'s exit criteria.

Rejected because the column would still be redundant with `last_heartbeat`. The transitions would have to be maintained in two places (graceful shutdown, daemon reconciliation) for a signal that is already cleanly derivable from one column. `papers/CORE-ShopManager.md` §3 also argues against assigning state mutation to the supervisor, and graceful-shutdown handling is fragile precisely in the failure modes (crashes, OOM kills, kill -9) where supervision matters most. Heartbeat freshness handles all failure modes uniformly; explicit state transitions handle only the cooperative ones.

**Alternative B — Add a `supervision_state` column.** Keep `status` as enrollment lifecycle (`enrolled | retired`), add `supervision_state` as liveness (`running | stopped | unknown`), have the dashboard read both.

Rejected because it doubles the surface area without resolving the underlying drift problem. Two new columns that can disagree with `last_heartbeat` create two new shadow signals to maintain. The number of supervision-meaningful columns goes from one (heartbeat) plus one shadow (status) to one plus two shadows. This is the failure mode `papers/CORE-Authority-Without-Registries.md` §1 names directly.

**Alternative C — Repurpose `status` for enrollment lifecycle without adding a second column.** Keep the column, redefine its values to `enrolled | retired`, drop the liveness semantics. The column would mean "this worker UUID is currently declared in `.intent/workers/`."

Considered but rejected as not in scope for this ADR. The need for an enrollment-lifecycle signal does not currently exist — `.intent/workers/*.yaml` is the source of truth for which workers are declared, and a registry row exists if and only if the worker has registered at least once. Adding a meaning to `status` to address a problem that has not been observed is speculative. If a future need emerges, a separate ADR adds the column with the appropriate name; this one removes the column whose declared semantics are inactive.

---
