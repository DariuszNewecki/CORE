-- 20260503_retire_vector_sync_worker.sql
--
-- GH #187 — ADR-018 structural retirement of VectorSyncWorker.
--
-- ADR-018 (2026-05-01) designated VectorSyncWorker as superseded by the
-- decomposed RepoCrawler/RepoEmbedder pair on the autonomous code-vector sync
-- path. The YAML was flipped to status: deprecated at that time. ADR-018 §5
-- deferred class-file deletion as "future cleanup once `deprecated` has held
-- for a meaningful period and no regression has surfaced." That period has
-- held; this migration takes up the structural retirement.
--
-- Deletes the single core.worker_registry row whose worker_uuid matches the
-- identity declared in .intent/workers/vector_sync_worker.yaml. The match is
-- on worker_uuid (the stable identity from the YAML), not on the surrogate
-- primary key id.
--
-- Deletes 1020 historical blackboard entries (heartbeats +
-- sync.vectors.code.complete reports from 2026-04-26 to 2026-05-01) along
-- with the worker_registry row. ADR-018 §3's "remain on the blackboard"
-- statement applied to the deprecation phase; structural retirement (#187)
-- supersedes it. The blackboard rows are FK children of worker_registry via
-- blackboard_entries_worker_uuid_fkey (NO ACTION), so they must be removed
-- inside the same transaction before the parent row can be deleted.
--
-- INVARIANT: this migration is applied as part of the same commit that
-- deletes src/will/workers/vector_sync_worker.py and
-- .intent/workers/vector_sync_worker.yaml. DB state and tree state advance
-- together — the registry row, the FK-child blackboard entries, the class
-- file, and the declaration are retired atomically.
--
-- The atomic action sync.vectors.code is preserved unchanged for the manual
-- `core-admin dev sync --write` CLI path per ADR-018 D1. This migration does
-- not touch any other table.
--
-- Forward-only. No rollback.

BEGIN;

DELETE FROM core.blackboard_entries
WHERE worker_uuid = 'e5f6a7b8-c9d0-4e1f-9a2b-3c4d5e6f7a81';

DELETE FROM core.worker_registry
WHERE worker_uuid = 'e5f6a7b8-c9d0-4e1f-9a2b-3c4d5e6f7a81';

-- Verification: both row sets must be gone after the DELETEs within the same
-- transaction. count = 0 is the only acceptable post-state for each.
SELECT count(*) AS remaining_blackboard_entries
FROM core.blackboard_entries
WHERE worker_uuid = 'e5f6a7b8-c9d0-4e1f-9a2b-3c4d5e6f7a81';

SELECT count(*) AS remaining_worker_registry_rows
FROM core.worker_registry
WHERE worker_uuid = 'e5f6a7b8-c9d0-4e1f-9a2b-3c4d5e6f7a81';

COMMIT;
