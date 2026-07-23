# Rollout runbook — active-finding dedup (blackboard ledger defect)

**Live execution requires fresh governor approval after CI + the rehearsal are green.**
This runbook exists so the live steps are quiesced, ordered, and reversible.

## Why ordering matters
The new posting code uses `INSERT … ON CONFLICT`, which **requires** the
`uq_active_finding_identity` index. The **old** posting code plain-inserts, which
would **violate** that index on a duplicate post. Therefore the index and the code
must move together, and the daemon must never be running the wrong pairing.

## Pre-flight
1. Re-run the read-only dry-run; confirm counts are stable (≈796 dups / 18 kept).
2. Snapshot: `pg_dump` of `core.blackboard_entries` (rollback of last resort).
3. Confirm CI green on the pushed commit (posting code + tests + schema.sql).

## Execution (writers quiesced throughout)
1. **Quiesce all blackboard writers:** `core-admin daemon down` (stops
   core-daemon + core-api). Verify: `systemctl --user is-active core-daemon core-api`
   → inactive. No process may write to `core.blackboard_entries` from here.
2. **Stage 1 migration** (columns + `last_seen_at` backfill):
   `psql "$CORE_DB" -f 20260722_active_finding_dedup.sql`
3. **Reconcile + index** (one transaction, `SHARE ROW EXCLUSIVE` lock — aggregate
   history, resolve dups with retained reason, create the index):
   `psql "$CORE_DB" -f 20260722_active_finding_reconcile.sql`
   Verify: 0 remaining duplicate active identities; `uq_active_finding_identity` exists.
4. **Deploy the compatible code** on the server (checkout the pushed commit). Do
   **not** start the daemon yet.
5. **Smoke-test the upsert** (still quiesced) — post the same finding twice via a
   one-off script; assert one row, `occurrence_count = 2`, `first_payload` retained.
6. **Restart:** `core-admin daemon up`. The daemon now runs the upsert path.
7. **Resolver:** the first `BlackboardShopManager` cycle runs
   `resolve_stale_alerts_for_terminal_targets` and closes the ~793 stale alerts
   whose targets are now resolved/recovered; or invoke it once explicitly.
8. **Verify convergence:** open-finding subjects drop to ~two dozen; `core-admin
   runtime dashboard` no longer diverging on meta-alerts.

## Rollback gates
- **Reconcile fails / dups remain / index creation errors:** the whole reconcile
  is one transaction — it rolls back atomically, leaving no partial state. Fix and
  re-run (idempotent).
- **Smoke-test or post-restart failure on the new code:** `core-admin daemon down`
  → **`DROP INDEX core.uq_active_finding_identity`** (mandatory — old code cannot
  coexist with it) → revert the code checkout → `core-admin daemon up`. The
  reconciled/aggregated rows are backward-compatible with old code; only the index
  is incompatible.
- **Catastrophic:** restore `core.blackboard_entries` from the pre-flight snapshot.

## Rehearsal record (core_test, 2026-07-22)
Seeded representative duplicates (stale family, recovered family, singleton,
claimed row, 4 alert cases) → ran the actual migration + reconcile files →
verified: deterministic aggregation (first/latest/sum/max-observation), retained
reason (no deletes), resolver outcomes (stale stays; recovered/terminal/missing
close), idempotent re-run (0 changes), and index rejection of a fresh duplicate.
8/8 integration tests pass against a real Postgres carrying the index.

## Rollout closure — live, 2026-07-23 (commit 3d7dd28e)

Executed against the live `core` database under the full quiesce/migrate/
reconcile/smoke-test/restart sequence above. Actual results:

- 798 duplicate source rows reconciled (resolved, retained reason
  `duplicate_open_row_reconciliation`, no deletes).
- 796 stale alerts resolved by the post-restart resolver cycle (all
  target-terminal closures — their target was one of the 798 reconciled rows).
- 17 legitimate stale alerts remaining; each independently verified to
  reference an existing, non-terminal, still-stale target.
- 26 non-stale open findings.
- 43 total open subjects.
- 0 duplicate active identities; `uq_active_finding_identity` valid and ready.
- All 17 services (core-daemon, core-api, 15 core-daemon-worker@* instances)
  healthy throughout, 0 restarts.

Smoke test (production posting path, quiesced): one active row, `occurrence_count
= 2`, `first_payload`/`payload` correctly split across post 1/post 2, `created_at`
unchanged, `last_seen_at` advanced, index remained valid; row resolved afterward
with reason `rollout_smoke_test_cleanup_3d7dd28e`.

**Process deviation:** the pre-flight `pg_dump` snapshot
(`core_blackboard_entries_pre_rollout_3d7dd28e.dump`) was deleted prematurely
during post-gate cleanup, before the rollback window was formally closed. Not a
rollout failure — the reconcile step's correctness had already been
independently verified (0 duplicate active identities, index valid) before
deletion — but it means no pre-rollout restore point exists. A fresh
post-convergence baseline was captured instead:
`var/tmp/core_blackboard_entries_POST_ROLLOUT_BASELINE_3d7dd28e_20260723T080324Z.dump`
(SHA-256 `2ebce446f938590b9cd4cde9b6b0143d15cf44454000dcfa29f672ee83a39206`,
manifest alongside it), verified via `pg_restore --list`. Retained outside
routine temp cleanup going forward.

No `.intent/` changes, no migration/reconcile re-run, and the unrelated
Prompt Drift Sensor error was left untouched, all per scope.
