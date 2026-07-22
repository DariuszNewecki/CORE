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
